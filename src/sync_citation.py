#!/usr/bin/env python3
"""
Citation File Format (CFF) synchronization with pyproject.toml metadata.

This script parses PEP 621 compliant pyproject.toml files and generates or updates
CITATION.cff files with synchronized metadata.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import tomllib

import jsonschema
import yaml


class CitationSyncError(Exception):
    """Custom exception for citation sync errors."""

    pass


class CitationSyncer:
    """Main class for synchronizing CITATION.cff with pyproject.toml metadata."""

    # Complete PEP 621 → CFF Field Mapping Analysis
    # ============================================
    #
    # PEP 621 Fields with CFF Equivalents:
    # - name              → title
    # - version           → version
    # - description       → abstract
    # - authors[]         → authors[] (with transformation)
    # - maintainers[]     → authors[] (fallback, with transformation)
    # - keywords[]        → keywords[]
    # - license           → license (string) OR license-url (if file)
    # - urls{}            → url, repository-code, repository-artifact
    #
    # PEP 621 Fields WITHOUT CFF Equivalents:
    # - readme            (no CFF equivalent)
    # - requires-python   (no CFF equivalent)
    # - dependencies[]    (no CFF equivalent, could inspire references)
    # - optional-dependencies{}  (no CFF equivalent)
    # - scripts{}         (no CFF equivalent)
    # - gui-scripts{}     (no CFF equivalent)
    # - entry-points{}    (no CFF equivalent)
    # - dynamic[]         (no CFF equivalent)
    # - classifiers[]     (no CFF equivalent)
    #
    # This mapping defines the ONLY fields that can be updated from pyproject.toml
    PYPROJECT_TO_CFF_MAPPING = {
        # Core metadata (direct 1:1 mappings)
        "name": {"cff_field": "title", "priority": 1, "transform": None},
        "version": {"cff_field": "version", "priority": 1, "transform": None},
        "description": {"cff_field": "abstract", "priority": 1, "transform": None},
        "keywords": {"cff_field": "keywords", "priority": 1, "transform": None},
        # Authors (conflict resolution: authors > maintainers)
        "authors": {
            "cff_field": "authors",
            "priority": 1,
            "transform": "parse_authors",
        },
        "maintainers": {
            "cff_field": "authors",
            "priority": 2,  # Lower priority than authors
            "transform": "parse_authors",
        },
        # License (conflict resolution: text > file > string)
        "license": {
            "cff_field": "license",
            "priority": 3,  # Lowest priority
            "transform": "parse_license_string",
        },
        "license.text": {"cff_field": "license", "priority": 1, "transform": None},
        "license.file": {
            "cff_field": "license-url",
            "priority": 1,
            "transform": "file_url",
        },
        # URLs (conflict resolution by priority)
        "urls.Homepage": {"cff_field": "url", "priority": 1, "transform": None},
        "urls.Documentation": {"cff_field": "url", "priority": 2, "transform": None},
        "urls.Repository": {
            "cff_field": "repository-code",
            "priority": 1,
            "transform": None,
        },
        "urls.Source": {
            "cff_field": "repository-code",
            "priority": 2,
            "transform": None,
        },
        "urls.Download": {
            "cff_field": "repository-artifact",
            "priority": 1,
            "transform": None,
        },
    }

    # Special fields that get computed/derived
    COMPUTED_FIELDS = {
        "date-released": "computed_on_version_change",
        "cff-version": "constant_1.2.0",
        "message": "default_message",
    }

    # CFF 1.2.0 schema validation (basic required fields)
    CFF_SCHEMA = {
        "type": "object",
        "required": ["cff-version", "message", "title", "authors"],
        "properties": {
            "cff-version": {"type": "string", "pattern": r"^1\.2\.0$"},
            "message": {"type": "string"},
            "title": {"type": "string"},
            "authors": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "oneOf": [
                        {
                            "type": "object",
                            "required": ["given-names", "family-names"],
                            "properties": {
                                "given-names": {"type": "string"},
                                "family-names": {"type": "string"},
                                "email": {"type": "string"},
                                "orcid": {"type": "string"},
                                "affiliation": {"type": "string"},
                            },
                        },
                        {
                            "type": "object",
                            "required": ["name"],
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                            },
                        },
                    ]
                },
            },
            "version": {"type": "string"},
            "date-released": {"type": "string"},
            "abstract": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "license": {"type": "string"},
            "repository-code": {"type": "string", "format": "uri"},
            "url": {"type": "string", "format": "uri"},
            "doi": {"type": "string"},
        },
    }

    def __init__(
        self,
        pyproject_path: str,
        citation_path: str,
        updatable_fields: Optional[List[str]] = None,
        exclude_fields: Optional[List[str]] = None,
    ):
        """Initialize the syncer with file paths and update configuration."""
        self.pyproject_path = Path(pyproject_path)
        self.citation_path = Path(citation_path)
        self.pyproject_data = None
        self.citation_data = None

        # Default updatable fields are all mapped CFF fields + computed fields
        mapped_cff_fields = {
            mapping["cff_field"] for mapping in self.PYPROJECT_TO_CFF_MAPPING.values()
        }
        default_updatable = mapped_cff_fields | set(self.COMPUTED_FIELDS.keys())

        # User configuration
        self.updatable_fields = (
            set(updatable_fields) if updatable_fields else default_updatable
        )
        self.exclude_fields = set(exclude_fields) if exclude_fields else set()

        # Validate user-specified fields
        all_valid_cff_fields = mapped_cff_fields | set(self.COMPUTED_FIELDS.keys())

        if updatable_fields:
            invalid_updatable = set(updatable_fields) - all_valid_cff_fields
            if invalid_updatable:
                raise CitationSyncError(
                    f"Invalid updatable fields: {', '.join(invalid_updatable)}. "
                    f"Valid fields are: {', '.join(sorted(all_valid_cff_fields))}"
                )

        if exclude_fields:
            invalid_exclude = set(exclude_fields) - all_valid_cff_fields
            if invalid_exclude:
                raise CitationSyncError(
                    f"Invalid exclude fields: {', '.join(invalid_exclude)}. "
                    f"Valid fields are: {', '.join(sorted(all_valid_cff_fields))}"
                )

        # Final set of fields that will be updated
        self.fields_to_update = self.updatable_fields - self.exclude_fields

    def load_pyproject(self) -> Dict[str, Any]:
        """Load and parse pyproject.toml file."""
        if not self.pyproject_path.exists():
            raise CitationSyncError(
                f"pyproject.toml not found at {self.pyproject_path}"
            )

        try:
            with open(self.pyproject_path, "rb") as f:
                data = tomllib.load(f)
            self.pyproject_data = data
            return data
        except Exception as e:
            raise CitationSyncError(f"Error parsing pyproject.toml: {e}")

    def load_citation(self) -> Optional[Dict[str, Any]]:
        """Load existing CITATION.cff file if it exists."""
        if not self.citation_path.exists():
            return None

        try:
            with open(self.citation_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.citation_data = data
            return data
        except Exception as e:
            raise CitationSyncError(f"Error parsing CITATION.cff: {e}")

    def extract_project_metadata(self) -> Dict[str, Any]:
        """Extract PEP 621 project metadata from pyproject.toml."""
        if not self.pyproject_data:
            raise CitationSyncError("pyproject.toml data not loaded")

        project_data = self.pyproject_data.get("project", {})

        if not project_data:
            raise CitationSyncError("No [project] section found in pyproject.toml")

        return project_data

    def parse_authors(self, authors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse authors from PEP 621 format to CFF format."""
        cff_authors = []

        for author in authors:
            if isinstance(author, str):
                cff_authors.append({"name": author})
                continue

            cff_author = {}

            # Handle name field (could be full name)
            if "name" in author:
                name_parts = author["name"].strip().split()
                if len(name_parts) >= 2:
                    cff_author["given-names"] = " ".join(name_parts[:-1])
                    cff_author["family-names"] = name_parts[-1]
                else:
                    cff_author["name"] = author["name"]

            # Add email if present
            if "email" in author:
                cff_author["email"] = author["email"]

            # Add other fields if present
            for field in ["orcid", "affiliation"]:
                if field in author:
                    cff_author[field] = author[field]

            if cff_author:
                cff_authors.append(cff_author)

        return cff_authors

    def get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = key_path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    def should_update_field(self, cff_field: str) -> bool:
        """Check if a CFF field should be updated based on user configuration."""
        return cff_field in self.fields_to_update

    def generate_citation_data(
        self, custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate CITATION.cff data from pyproject.toml using schema mapping."""
        project_metadata = self.extract_project_metadata()
        custom_fields = custom_fields or {}

        # Start with existing citation data to preserve non-updatable fields
        if self.citation_data:
            citation_data = self.citation_data.copy()
        else:
            citation_data = {}

        # Apply schema-based mappings with conflict resolution
        field_candidates = {}  # cff_field -> [(priority, value, transform)]

        for pyproject_field, mapping_info in self.PYPROJECT_TO_CFF_MAPPING.items():
            cff_field = mapping_info["cff_field"]
            priority = mapping_info["priority"]
            transform = mapping_info["transform"]

            if not self.should_update_field(cff_field):
                continue

            # Get value from pyproject.toml (supports nested keys)
            value = self.get_nested_value(project_metadata, pyproject_field)
            if value is None:
                continue

            # Collect candidates for each CFF field
            if cff_field not in field_candidates:
                field_candidates[cff_field] = []
            field_candidates[cff_field].append((priority, value, transform))

        # Apply the highest priority value for each CFF field
        for cff_field, candidates in field_candidates.items():
            # Sort by priority (lower number = higher priority)
            candidates.sort(key=lambda x: x[0])
            priority, value, transform = candidates[0]  # Take highest priority

            # Apply transformation
            if transform:
                value = self._apply_transform(transform, value)

            citation_data[cff_field] = value

        # Handle computed fields
        self._update_computed_fields(citation_data, project_metadata)

        # Ensure minimum required fields exist
        self._ensure_required_fields(citation_data)

        # Override/add custom fields (these take highest priority)
        citation_data.update(custom_fields)

        return citation_data

    def _apply_transform(self, transform: str, value: Any) -> Any:
        """Apply transformation to a field value."""
        if transform == "parse_authors":
            return self.parse_authors(value)
        elif transform == "file_url":
            return f"file://{value}"
        elif transform == "parse_license_string":
            return str(value)  # Convert to string if needed
        else:
            raise ValueError(f"Unknown transform: {transform}")

    def _update_computed_fields(
        self, citation_data: Dict[str, Any], project_metadata: Dict[str, Any]
    ) -> None:
        """Update computed fields based on special logic."""
        # Always update core required fields if they're in updatable fields
        if self.should_update_field("cff-version"):
            citation_data["cff-version"] = "1.2.0"

        if self.should_update_field("message"):
            citation_data["message"] = (
                "If you use this software, please cite it as below."
            )

        # Handle version-dependent date update
        if self.should_update_field("date-released") and "version" in project_metadata:
            old_version = citation_data.get("version")
            new_version = project_metadata["version"]

            # Only update date if version actually changed
            if old_version != new_version:
                citation_data["date-released"] = datetime.now().strftime("%Y-%m-%d")

    def _ensure_required_fields(self, citation_data: Dict[str, Any]) -> None:
        """Ensure minimum required CFF fields exist."""
        # CFF requires: cff-version, message, title, authors
        if "cff-version" not in citation_data:
            citation_data["cff-version"] = "1.2.0"

        if "message" not in citation_data:
            citation_data["message"] = (
                "If you use this software, please cite it as below."
            )

        if "title" not in citation_data:
            citation_data["title"] = "Unknown"

        if "authors" not in citation_data:
            citation_data["authors"] = [{"name": "Unknown"}]

    def validate_citation(self, citation_data: Dict[str, Any]) -> bool:
        """Validate CITATION.cff data against schema."""
        try:
            jsonschema.validate(citation_data, self.CFF_SCHEMA)
            return True
        except jsonschema.ValidationError as e:
            print(f"Validation error: {e.message}")
            return False

    def citations_equal(
        self, citation1: Dict[str, Any], citation2: Dict[str, Any]
    ) -> bool:
        """Compare two citation dictionaries for equality."""

        def normalize_citation(citation: Dict[str, Any]) -> Dict[str, Any]:
            """Normalize citation data for comparison."""
            normalized = citation.copy()
            # Remove date-released for comparison as it auto-updates
            normalized.pop("date-released", None)
            return normalized

        norm1 = normalize_citation(citation1)
        norm2 = normalize_citation(citation2)

        return norm1 == norm2

    def write_citation(self, citation_data: Dict[str, Any]) -> None:
        """Write CITATION.cff file."""
        try:
            # Ensure directory exists
            self.citation_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.citation_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    citation_data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                    width=80,
                )
        except Exception as e:
            raise CitationSyncError(f"Error writing CITATION.cff: {e}")

    def sync(
        self,
        custom_fields: Optional[Dict[str, Any]] = None,
        validate_only: bool = False,
        force_update: bool = False,
    ) -> Dict[str, Any]:
        """Main sync method."""
        results = {
            "updated": False,
            "changes_detected": False,
            "validation_status": "unknown",
        }

        try:
            # Load pyproject.toml
            self.load_pyproject()

            # Load existing CITATION.cff if it exists
            existing_citation = self.load_citation()

            # Generate new citation data
            new_citation = self.generate_citation_data(custom_fields)

            # Validate the generated citation
            if self.validate_citation(new_citation):
                results["validation_status"] = "valid"
            else:
                results["validation_status"] = "invalid"
                if validate_only:
                    return results

            # Check for changes
            if existing_citation:
                if not self.citations_equal(existing_citation, new_citation):
                    results["changes_detected"] = True
            else:
                results["changes_detected"] = True

            # Write file if needed
            if not validate_only and (results["changes_detected"] or force_update):
                self.write_citation(new_citation)
                results["updated"] = True

            return results

        except Exception as e:
            print(f"Error during sync: {e}")
            results["validation_status"] = "error"
            return results


def main():
    """Main entry point for the script."""
    # Get environment variables
    pyproject_path = os.environ.get("PYPROJECT_PATH", "./pyproject.toml")
    citation_path = os.environ.get("CITATION_PATH", "./CITATION.cff")
    custom_fields_json = os.environ.get("CUSTOM_FIELDS", "{}")
    validate_only = os.environ.get("VALIDATE_ONLY", "false").lower() == "true"
    force_update = os.environ.get("FORCE_UPDATE", "false").lower() == "true"

    # Parse field configuration
    updatable_fields_str = os.environ.get("UPDATABLE_FIELDS", "")
    exclude_fields_str = os.environ.get("EXCLUDE_FIELDS", "")

    updatable_fields = (
        [f.strip() for f in updatable_fields_str.split(",") if f.strip()]
        if updatable_fields_str
        else None
    )
    exclude_fields = (
        [f.strip() for f in exclude_fields_str.split(",") if f.strip()]
        if exclude_fields_str
        else None
    )

    try:
        # Parse custom fields
        custom_fields = json.loads(custom_fields_json)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in CUSTOM_FIELDS")
        sys.exit(1)

    # Create syncer and run
    syncer = CitationSyncer(
        pyproject_path, citation_path, updatable_fields, exclude_fields
    )
    results = syncer.sync(custom_fields, validate_only, force_update)

    # Set outputs for GitHub Actions
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"updated={str(results['updated']).lower()}\n")
            f.write(f"changes-detected={str(results['changes_detected']).lower()}\n")
            f.write(f"validation-status={results['validation_status']}\n")

    # Set environment variable for conditional commit step
    if results["updated"]:
        with open(os.environ.get("GITHUB_ENV", "/dev/null"), "a") as f:
            f.write("CITATION_UPDATED=true\n")

    # Print results
    print("Sync completed:")
    print(f"  Updated: {results['updated']}")
    print(f"  Changes detected: {results['changes_detected']}")
    print(f"  Validation status: {results['validation_status']}")

    # Exit with error code if validation failed
    if results["validation_status"] == "invalid":
        sys.exit(1)


if __name__ == "__main__":
    main()
