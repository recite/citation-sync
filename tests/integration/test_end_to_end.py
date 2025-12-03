"""Integration tests for end-to-end workflows."""

import os
import tempfile
import yaml
import tomllib
from pathlib import Path
import pytest

from src.sync_citation import CitationSyncer


class TestEndToEndWorkflow:
    """Test complete pyproject.toml → CITATION.cff workflows."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def create_pyproject_toml(self, temp_dir: Path, config: dict):
        """Helper to create pyproject.toml file."""
        pyproject_path = temp_dir / "pyproject.toml"
        content = {
            "project": config
        }
        with open(pyproject_path, "wb") as f:
            import tomli_w
            tomli_w.dump(content, f)
        return pyproject_path

    def create_citation_cff(self, temp_dir: Path, config: dict):
        """Helper to create CITATION.cff file."""
        citation_path = temp_dir / "CITATION.cff"
        with open(citation_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        return citation_path

    def read_citation_cff(self, citation_path: Path) -> dict:
        """Helper to read CITATION.cff file."""
        with open(citation_path, "r") as f:
            return yaml.safe_load(f)

    def test_basic_sync_new_file(self, temp_dir):
        """Test syncing to a new CITATION.cff file."""
        # Create pyproject.toml
        pyproject_config = {
            "name": "test-project",
            "version": "1.0.0",
            "description": "A test project for citation sync",
            "authors": [
                {"name": "Jane Smith", "email": "jane@example.com"}
            ],
            "keywords": ["test", "citation", "python"],
            "license": {"text": "MIT"},
            "urls": {
                "Homepage": "https://example.com",
                "Repository": "https://github.com/user/test-project"
            }
        }
        pyproject_path = self.create_pyproject_toml(temp_dir, pyproject_config)
        citation_path = temp_dir / "CITATION.cff"

        # Run sync
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        result = syncer.sync()

        # Check results
        assert result["updated"] is True
        assert result["changes_detected"] is True
        assert result["validation_status"] == "valid"

        # Check generated file
        citation_data = self.read_citation_cff(citation_path)
        assert citation_data["cff-version"] == "1.2.0"
        assert citation_data["title"] == "test-project"
        assert citation_data["version"] == "1.0.0"
        assert citation_data["abstract"] == "A test project for citation sync"
        assert citation_data["authors"] == [{"given-names": "Jane", "family-names": "Smith", "email": "jane@example.com"}]
        assert citation_data["keywords"] == ["test", "citation", "python"]
        assert citation_data["license"] == "MIT"
        assert citation_data["url"] == "https://example.com"
        assert citation_data["repository-code"] == "https://github.com/user/test-project"

    def test_sync_with_existing_protected_fields(self, temp_dir):
        """Test syncing preserves protected fields in existing CITATION.cff."""
        # Create pyproject.toml
        pyproject_config = {
            "name": "test-project",
            "version": "2.0.0",
            "description": "Updated description"
        }
        pyproject_path = self.create_pyproject_toml(temp_dir, pyproject_config)

        # Create existing CITATION.cff with protected fields
        existing_citation = {
            "cff-version": "1.2.0",
            "message": "If you use this software, please cite it as below.",
            "title": "old-project",
            "authors": [{"name": "Unknown"}],
            "version": "1.0.0",
            "doi": "10.1234/example.doi",
            "preferred-citation": {
                "type": "article",
                "title": "My Research Paper",
                "authors": [{"name": "Jane Smith"}]
            }
        }
        citation_path = self.create_citation_cff(temp_dir, existing_citation)

        # Run sync
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        result = syncer.sync()

        # Check results
        assert result["updated"] is True
        assert result["changes_detected"] is True

        # Check updated file
        citation_data = self.read_citation_cff(citation_path)
        # Updated fields
        assert citation_data["title"] == "test-project"
        assert citation_data["version"] == "2.0.0"
        assert citation_data["abstract"] == "Updated description"
        # Protected fields preserved
        assert citation_data["doi"] == "10.1234/example.doi"
        assert citation_data["preferred-citation"]["title"] == "My Research Paper"

    def test_selective_field_updates(self, temp_dir):
        """Test updating only specific fields."""
        # Create pyproject.toml
        pyproject_config = {
            "name": "test-project",
            "version": "2.0.0",
            "description": "Updated description",
            "keywords": ["new", "keywords"]
        }
        pyproject_path = self.create_pyproject_toml(temp_dir, pyproject_config)

        # Create existing CITATION.cff
        existing_citation = {
            "cff-version": "1.2.0",
            "message": "If you use this software, please cite it as below.",
            "title": "old-project",
            "version": "1.0.0",
            "abstract": "Old description",
            "keywords": ["old", "keywords"],
            "authors": [{"name": "Unknown"}]
        }
        citation_path = self.create_citation_cff(temp_dir, existing_citation)

        # Run sync with only title and version updatable
        syncer = CitationSyncer(
            str(pyproject_path), 
            str(citation_path),
            updatable_fields=["title", "version"]
        )
        result = syncer.sync()

        # Check results
        assert result["updated"] is True

        # Check updated file
        citation_data = self.read_citation_cff(citation_path)
        # Updated fields
        assert citation_data["title"] == "test-project"
        assert citation_data["version"] == "2.0.0"
        # Non-updatable fields preserved
        assert citation_data["abstract"] == "Old description"
        assert citation_data["keywords"] == ["old", "keywords"]

    def test_field_exclusion(self, temp_dir):
        """Test excluding specific fields from updates."""
        # Create pyproject.toml
        pyproject_config = {
            "name": "test-project",
            "version": "2.0.0",
            "description": "New description"
        }
        pyproject_path = self.create_pyproject_toml(temp_dir, pyproject_config)

        # Create existing CITATION.cff
        existing_citation = {
            "cff-version": "1.2.0",
            "message": "Custom message - do not update",
            "title": "old-project",
            "version": "1.0.0",
            "authors": [{"name": "Unknown"}]
        }
        citation_path = self.create_citation_cff(temp_dir, existing_citation)

        # Run sync excluding message field
        syncer = CitationSyncer(
            str(pyproject_path), 
            str(citation_path),
            exclude_fields=["message"]
        )
        result = syncer.sync()

        # Check results
        assert result["updated"] is True

        # Check updated file
        citation_data = self.read_citation_cff(citation_path)
        # Updated fields
        assert citation_data["title"] == "test-project"
        assert citation_data["version"] == "2.0.0"
        assert citation_data["abstract"] == "New description"
        # Excluded field preserved
        assert citation_data["message"] == "Custom message - do not update"

    def test_custom_fields_override(self, temp_dir):
        """Test that custom fields take highest priority."""
        # Create pyproject.toml
        pyproject_config = {
            "name": "test-project",
            "version": "1.0.0"
        }
        pyproject_path = self.create_pyproject_toml(temp_dir, pyproject_config)
        citation_path = temp_dir / "CITATION.cff"

        # Run sync with custom fields
        custom_fields = {
            "title": "Custom Title Override",  # Should override pyproject name
            "doi": "10.1234/custom.doi",      # Should add new field
            "type": "dataset"                 # Should add new field
        }
        
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        result = syncer.sync(custom_fields=custom_fields)

        # Check results
        assert result["updated"] is True

        # Check generated file
        citation_data = self.read_citation_cff(citation_path)
        # Custom fields should override
        assert citation_data["title"] == "Custom Title Override"
        assert citation_data["doi"] == "10.1234/custom.doi"
        assert citation_data["type"] == "dataset"
        # Other pyproject fields still applied
        assert citation_data["version"] == "1.0.0"

    def test_no_changes_detected(self, temp_dir):
        """Test when no changes are detected."""
        # Create pyproject.toml
        pyproject_config = {
            "name": "test-project",
            "version": "1.0.0"
        }
        pyproject_path = self.create_pyproject_toml(temp_dir, pyproject_config)

        # Create matching CITATION.cff
        existing_citation = {
            "cff-version": "1.2.0",
            "message": "If you use this software, please cite it as below.",
            "title": "test-project",
            "version": "1.0.0",
            "authors": [{"name": "Unknown"}]
        }
        citation_path = self.create_citation_cff(temp_dir, existing_citation)

        # Run sync
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        result = syncer.sync()

        # Check results
        assert result["updated"] is False
        assert result["changes_detected"] is False
        assert result["validation_status"] == "valid"

    def test_conflict_resolution_integration(self, temp_dir):
        """Test priority-based conflict resolution in end-to-end workflow."""
        # Create pyproject.toml with conflicting sources
        pyproject_config = {
            "name": "test-project",
            "version": "1.0.0",
            "authors": [{"name": "Primary Author"}],
            "maintainers": [{"name": "Maintainer"}],
            "license": "GPL-3.0",  # Lower priority
            "urls": {
                "Homepage": "https://homepage.com",     # Should win for url
                "Documentation": "https://docs.com",    # Lower priority for url
                "Repository": "https://repo.com",       # Should win for repository-code
                "Source": "https://source.com"          # Lower priority for repository-code
            }
        }
        
        # Add license.text to project config (higher priority)
        pyproject_config["license"] = {"text": "MIT"}  # Should override string license
        
        pyproject_path = self.create_pyproject_toml(temp_dir, pyproject_config)
        citation_path = temp_dir / "CITATION.cff"

        # Run sync
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        result = syncer.sync()

        # Check results
        assert result["updated"] is True

        # Check conflict resolution
        citation_data = self.read_citation_cff(citation_path)
        # Authors should use authors, not maintainers
        assert citation_data["authors"] == [{"given-names": "Primary", "family-names": "Author"}]
        # License should use license.text, not license string
        assert citation_data["license"] == "MIT"
        # URLs should use higher priority options
        assert citation_data["url"] == "https://homepage.com"
        assert citation_data["repository-code"] == "https://repo.com"