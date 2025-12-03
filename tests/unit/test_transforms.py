"""Unit tests for transform functions."""

import pytest
from src.sync_citation import CitationSyncer


class TestTransformFunctions:
    """Test field transformation functions."""

    @pytest.fixture
    def syncer(self):
        """Create a syncer instance for testing."""
        return CitationSyncer("pyproject.toml", "citation.cff")

    def test_parse_authors_full_names(self, syncer):
        """Test parsing authors with full names."""
        authors = [
            {"name": "Jane Smith", "email": "jane@example.com"},
            {"name": "John Doe", "email": "john@example.com", "orcid": "0000-0000-0000-0000"}
        ]
        
        result = syncer.parse_authors(authors)
        
        expected = [
            {
                "given-names": "Jane",
                "family-names": "Smith", 
                "email": "jane@example.com"
            },
            {
                "given-names": "John",
                "family-names": "Doe",
                "email": "john@example.com",
                "orcid": "0000-0000-0000-0000"
            }
        ]
        assert result == expected

    def test_parse_authors_single_name(self, syncer):
        """Test parsing authors with single names."""
        authors = [{"name": "SingleName"}]
        result = syncer.parse_authors(authors)
        expected = [{"name": "SingleName"}]
        assert result == expected

    def test_parse_authors_multiple_given_names(self, syncer):
        """Test parsing authors with multiple given names."""
        authors = [{"name": "Mary Jane Watson Smith"}]
        result = syncer.parse_authors(authors)
        expected = [{"given-names": "Mary Jane Watson", "family-names": "Smith"}]
        assert result == expected

    def test_parse_authors_with_affiliation(self, syncer):
        """Test parsing authors with affiliation."""
        authors = [{"name": "Jane Smith", "affiliation": "University of Example"}]
        result = syncer.parse_authors(authors)
        expected = [{
            "given-names": "Jane",
            "family-names": "Smith",
            "affiliation": "University of Example"
        }]
        assert result == expected

    def test_parse_authors_string_input(self, syncer):
        """Test parsing authors from string input."""
        authors = ["Jane Smith"]
        result = syncer.parse_authors(authors)
        expected = [{"name": "Jane Smith"}]
        assert result == expected

    def test_parse_authors_empty_list(self, syncer):
        """Test parsing empty authors list."""
        authors = []
        result = syncer.parse_authors(authors)
        assert result == []

    def test_apply_transform_parse_authors(self, syncer):
        """Test _apply_transform for parse_authors."""
        authors = [{"name": "Jane Smith"}]
        result = syncer._apply_transform("parse_authors", authors)
        expected = [{"given-names": "Jane", "family-names": "Smith"}]
        assert result == expected

    def test_apply_transform_file_url(self, syncer):
        """Test _apply_transform for file_url."""
        result = syncer._apply_transform("file_url", "LICENSE")
        assert result == "file://LICENSE"

    def test_apply_transform_parse_license_string(self, syncer):
        """Test _apply_transform for parse_license_string."""
        result = syncer._apply_transform("parse_license_string", "MIT")
        assert result == "MIT"
        
        # Test with non-string input
        result = syncer._apply_transform("parse_license_string", {"text": "MIT"})
        assert result == "{'text': 'MIT'}"

    def test_apply_transform_unknown(self, syncer):
        """Test _apply_transform with unknown transform."""
        with pytest.raises(ValueError, match="Unknown transform: unknown_transform"):
            syncer._apply_transform("unknown_transform", "value")

    def test_ensure_required_fields_empty_citation(self, syncer):
        """Test _ensure_required_fields with empty citation data."""
        citation_data = {}
        syncer._ensure_required_fields(citation_data)
        
        assert citation_data["cff-version"] == "1.2.0"
        assert citation_data["message"] == "If you use this software, please cite it as below."
        assert citation_data["title"] == "Unknown"
        assert citation_data["authors"] == [{"name": "Unknown"}]

    def test_ensure_required_fields_partial_citation(self, syncer):
        """Test _ensure_required_fields with partial citation data."""
        citation_data = {
            "title": "My Project",
            "authors": [{"name": "Jane Smith"}]
        }
        syncer._ensure_required_fields(citation_data)
        
        # Should add missing required fields
        assert citation_data["cff-version"] == "1.2.0"
        assert citation_data["message"] == "If you use this software, please cite it as below."
        # Should preserve existing fields
        assert citation_data["title"] == "My Project"
        assert citation_data["authors"] == [{"name": "Jane Smith"}]

    def test_ensure_required_fields_complete_citation(self, syncer):
        """Test _ensure_required_fields with complete citation data."""
        citation_data = {
            "cff-version": "1.2.0",
            "message": "Custom message",
            "title": "My Project",
            "authors": [{"name": "Jane Smith"}]
        }
        original = citation_data.copy()
        syncer._ensure_required_fields(citation_data)
        
        # Should not modify existing complete data
        assert citation_data == original