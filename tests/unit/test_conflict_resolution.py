"""Unit tests for field conflict resolution."""

from unittest.mock import Mock

import pytest

from src.sync_citation import CitationSyncer


class TestConflictResolution:
    """Test priority-based conflict resolution for multiple→single field mappings."""

    @pytest.fixture
    def syncer(self):
        """Create a syncer instance for testing."""
        return CitationSyncer("pyproject.toml", "citation.cff")

    def test_get_nested_value(self, syncer):
        """Test nested value extraction."""
        data = {
            "urls": {
                "Homepage": "https://example.com",
                "Repository": "https://github.com/user/repo",
            },
            "license": {"text": "MIT"},
        }

        assert syncer.get_nested_value(data, "urls.Homepage") == "https://example.com"
        assert (
            syncer.get_nested_value(data, "urls.Repository")
            == "https://github.com/user/repo"
        )
        assert syncer.get_nested_value(data, "license.text") == "MIT"
        assert syncer.get_nested_value(data, "nonexistent.field") is None
        assert syncer.get_nested_value(data, "urls.Nonexistent") is None

    def test_authors_priority_resolution(self, syncer):
        """Test that 'authors' takes priority over 'maintainers'."""
        # Mock the methods we need
        syncer.pyproject_data = {
            "project": {
                "authors": [{"name": "Author One"}],
                "maintainers": [{"name": "Maintainer One"}],
            }
        }
        syncer.citation_data = {}
        syncer.should_update_field = Mock(return_value=True)
        syncer.parse_authors = Mock(side_effect=lambda x: [{"name": x[0]["name"]}])

        result = syncer.generate_citation_data()

        # Should use authors, not maintainers
        syncer.parse_authors.assert_called_with([{"name": "Author One"}])
        assert result["authors"] == [{"name": "Author One"}]

    def test_maintainers_fallback(self, syncer):
        """Test that 'maintainers' is used when 'authors' is not present."""
        syncer.pyproject_data = {
            "project": {"maintainers": [{"name": "Maintainer One"}]}
        }
        syncer.citation_data = {}
        syncer.should_update_field = Mock(return_value=True)
        syncer.parse_authors = Mock(side_effect=lambda x: [{"name": x[0]["name"]}])

        result = syncer.generate_citation_data()

        syncer.parse_authors.assert_called_with([{"name": "Maintainer One"}])
        assert result["authors"] == [{"name": "Maintainer One"}]

    def test_license_priority_resolution(self, syncer):
        """Test license priority: license.text > license.file > license."""
        syncer.pyproject_data = {
            "project": {
                "license": {
                    "text": "Apache 2.0",
                    "file": "LICENSE",
                },  # Both in license object
            }
        }
        syncer.citation_data = {}
        syncer.should_update_field = Mock(return_value=True)

        result = syncer.generate_citation_data()

        # license.text should win for the license field
        assert result.get("license") == "Apache 2.0"
        assert result.get("license-url") == "file://LICENSE"

    def test_url_priority_resolution(self, syncer):
        """Test URL priority: Homepage > Documentation for 'url' field."""
        syncer.pyproject_data = {
            "project": {
                "urls": {
                    "Homepage": "https://homepage.com",  # Priority 1
                    "Documentation": "https://docs.com",  # Priority 2
                }
            }
        }
        syncer.citation_data = {}
        syncer.should_update_field = Mock(return_value=True)

        result = syncer.generate_citation_data()

        # Homepage should win
        assert result.get("url") == "https://homepage.com"

    def test_repository_code_priority(self, syncer):
        """Test repository-code priority: Repository > Source."""
        syncer.pyproject_data = {
            "project": {
                "urls": {
                    "Repository": "https://github.com/repo",  # Priority 1
                    "Source": "https://gitlab.com/source",  # Priority 2
                }
            }
        }
        syncer.citation_data = {}
        syncer.should_update_field = Mock(return_value=True)

        result = syncer.generate_citation_data()

        # Repository should win
        assert result.get("repository-code") == "https://github.com/repo"

    def test_no_conflict_single_source(self, syncer):
        """Test that single sources work correctly without conflicts."""
        syncer.pyproject_data = {
            "project": {
                "name": "test-project",
                "version": "1.0.0",
                "description": "A test project",
                "keywords": ["test", "python"],
            }
        }
        syncer.citation_data = {}
        syncer.should_update_field = Mock(return_value=True)

        result = syncer.generate_citation_data()

        assert result.get("title") == "test-project"
        assert result.get("version") == "1.0.0"
        assert result.get("abstract") == "A test project"
        assert result.get("keywords") == ["test", "python"]

    def test_field_exclusion_prevents_conflicts(self, syncer):
        """Test that excluded fields don't participate in conflict resolution."""
        syncer.pyproject_data = {
            "project": {
                "authors": [{"name": "Author"}],
                "maintainers": [{"name": "Maintainer"}],
            }
        }
        syncer.citation_data = {}
        # Exclude authors field
        syncer.should_update_field = Mock(side_effect=lambda field: field != "authors")
        syncer.parse_authors = Mock(side_effect=lambda x: [{"name": x[0]["name"]}])

        result = syncer.generate_citation_data()

        # parse_authors should not be called since authors field is excluded
        syncer.parse_authors.assert_not_called()
        # Authors field will still be present with default value
        assert result["authors"] == [{"name": "Unknown"}]
