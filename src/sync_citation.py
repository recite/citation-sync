#!/usr/bin/env python3
"""
Citation File Format (CFF) synchronization with pyproject.toml metadata.

This script parses PEP 621 compliant pyproject.toml files and generates or updates
CITATION.cff files with synchronized metadata.
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import yaml
import jsonschema


class CitationSyncError(Exception):
    """Custom exception for citation sync errors."""
    pass


class CitationSyncer:
    """Main class for synchronizing CITATION.cff with pyproject.toml metadata."""
    
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
                                "affiliation": {"type": "string"}
                            }
                        },
                        {
                            "type": "object",
                            "required": ["name"],
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"}
                            }
                        }
                    ]
                }
            },
            "version": {"type": "string"},
            "date-released": {"type": "string"},
            "abstract": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "license": {"type": "string"},
            "repository-code": {"type": "string", "format": "uri"},
            "url": {"type": "string", "format": "uri"},
            "doi": {"type": "string"}
        }
    }

    def __init__(self, pyproject_path: str, citation_path: str):
        """Initialize the syncer with file paths."""
        self.pyproject_path = Path(pyproject_path)
        self.citation_path = Path(citation_path)
        self.pyproject_data = None
        self.citation_data = None

    def load_pyproject(self) -> Dict[str, Any]:
        """Load and parse pyproject.toml file."""
        if not self.pyproject_path.exists():
            raise CitationSyncError(f"pyproject.toml not found at {self.pyproject_path}")
        
        try:
            with open(self.pyproject_path, 'rb') as f:
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
            with open(self.citation_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            self.citation_data = data
            return data
        except Exception as e:
            raise CitationSyncError(f"Error parsing CITATION.cff: {e}")

    def extract_project_metadata(self) -> Dict[str, Any]:
        """Extract PEP 621 project metadata from pyproject.toml."""
        if not self.pyproject_data:
            raise CitationSyncError("pyproject.toml data not loaded")
        
        project_data = self.pyproject_data.get('project', {})
        
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
            if 'name' in author:
                name_parts = author['name'].strip().split()
                if len(name_parts) >= 2:
                    cff_author['given-names'] = ' '.join(name_parts[:-1])
                    cff_author['family-names'] = name_parts[-1]
                else:
                    cff_author['name'] = author['name']
            
            # Add email if present
            if 'email' in author:
                cff_author['email'] = author['email']
            
            # Add other fields if present
            for field in ['orcid', 'affiliation']:
                if field in author:
                    cff_author[field] = author[field]
            
            if cff_author:
                cff_authors.append(cff_author)
        
        return cff_authors

    def generate_citation_data(self, custom_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate CITATION.cff data from pyproject.toml metadata."""
        project_metadata = self.extract_project_metadata()
        custom_fields = custom_fields or {}
        
        # Required fields
        citation_data = {
            "cff-version": "1.2.0",
            "message": "If you use this software, please cite it as below.",
            "title": project_metadata.get('name', ''),
            "authors": []
        }
        
        # Parse authors
        if 'authors' in project_metadata:
            citation_data['authors'] = self.parse_authors(project_metadata['authors'])
        elif 'maintainers' in project_metadata:
            citation_data['authors'] = self.parse_authors(project_metadata['maintainers'])
        else:
            # Create a placeholder author
            citation_data['authors'] = [{"name": "Unknown"}]
        
        # Optional fields from pyproject.toml
        if 'version' in project_metadata:
            citation_data['version'] = project_metadata['version']
            citation_data['date-released'] = datetime.now().strftime('%Y-%m-%d')
        
        if 'description' in project_metadata:
            citation_data['abstract'] = project_metadata['description']
        
        if 'keywords' in project_metadata:
            citation_data['keywords'] = project_metadata['keywords']
        
        if 'license' in project_metadata:
            license_info = project_metadata['license']
            if isinstance(license_info, dict) and 'text' in license_info:
                citation_data['license'] = license_info['text']
            elif isinstance(license_info, str):
                citation_data['license'] = license_info
        
        # URLs from project metadata
        urls = project_metadata.get('urls', {})
        if 'Homepage' in urls:
            citation_data['url'] = urls['Homepage']
        elif 'Repository' in urls:
            citation_data['repository-code'] = urls['Repository']
        elif 'Source' in urls:
            citation_data['repository-code'] = urls['Source']
        
        # Override/add custom fields
        citation_data.update(custom_fields)
        
        return citation_data

    def validate_citation(self, citation_data: Dict[str, Any]) -> bool:
        """Validate CITATION.cff data against schema."""
        try:
            jsonschema.validate(citation_data, self.CFF_SCHEMA)
            return True
        except jsonschema.ValidationError as e:
            print(f"Validation error: {e.message}")
            return False

    def citations_equal(self, citation1: Dict[str, Any], citation2: Dict[str, Any]) -> bool:
        """Compare two citation dictionaries for equality."""
        def normalize_citation(citation: Dict[str, Any]) -> Dict[str, Any]:
            """Normalize citation data for comparison."""
            normalized = citation.copy()
            # Remove date-released for comparison as it auto-updates
            normalized.pop('date-released', None)
            return normalized
        
        norm1 = normalize_citation(citation1)
        norm2 = normalize_citation(citation2)
        
        return norm1 == norm2

    def write_citation(self, citation_data: Dict[str, Any]) -> None:
        """Write CITATION.cff file."""
        try:
            # Ensure directory exists
            self.citation_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.citation_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    citation_data, 
                    f, 
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                    width=80
                )
        except Exception as e:
            raise CitationSyncError(f"Error writing CITATION.cff: {e}")

    def sync(self, custom_fields: Optional[Dict[str, Any]] = None, 
             validate_only: bool = False, force_update: bool = False) -> Dict[str, Any]:
        """Main sync method."""
        results = {
            'updated': False,
            'changes_detected': False,
            'validation_status': 'unknown'
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
                results['validation_status'] = 'valid'
            else:
                results['validation_status'] = 'invalid'
                if validate_only:
                    return results
            
            # Check for changes
            if existing_citation:
                if not self.citations_equal(existing_citation, new_citation):
                    results['changes_detected'] = True
            else:
                results['changes_detected'] = True
            
            # Write file if needed
            if not validate_only and (results['changes_detected'] or force_update):
                self.write_citation(new_citation)
                results['updated'] = True
            
            return results
            
        except Exception as e:
            print(f"Error during sync: {e}")
            results['validation_status'] = 'error'
            return results


def main():
    """Main entry point for the script."""
    # Get environment variables
    pyproject_path = os.environ.get('PYPROJECT_PATH', './pyproject.toml')
    citation_path = os.environ.get('CITATION_PATH', './CITATION.cff')
    custom_fields_json = os.environ.get('CUSTOM_FIELDS', '{}')
    validate_only = os.environ.get('VALIDATE_ONLY', 'false').lower() == 'true'
    force_update = os.environ.get('FORCE_UPDATE', 'false').lower() == 'true'
    
    try:
        # Parse custom fields
        custom_fields = json.loads(custom_fields_json)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in CUSTOM_FIELDS")
        sys.exit(1)
    
    # Create syncer and run
    syncer = CitationSyncer(pyproject_path, citation_path)
    results = syncer.sync(custom_fields, validate_only, force_update)
    
    # Set outputs for GitHub Actions
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"updated={str(results['updated']).lower()}\n")
            f.write(f"changes-detected={str(results['changes_detected']).lower()}\n")
            f.write(f"validation-status={results['validation_status']}\n")
    
    # Set environment variable for conditional commit step
    if results['updated']:
        with open(os.environ.get('GITHUB_ENV', '/dev/null'), 'a') as f:
            f.write("CITATION_UPDATED=true\n")
    
    # Print results
    print(f"Sync completed:")
    print(f"  Updated: {results['updated']}")
    print(f"  Changes detected: {results['changes_detected']}")
    print(f"  Validation status: {results['validation_status']}")
    
    # Exit with error code if validation failed
    if results['validation_status'] == 'invalid':
        sys.exit(1)


if __name__ == '__main__':
    main()