"""Unit tests for schema mapping functionality."""

import pytest

from src.sync_citation import CitationSyncer, CitationSyncError


class TestSchemaMappingValidation:
    """Test schema mapping and field validation."""

    def test_valid_updatable_fields(self):
        """Test that valid updatable fields are accepted."""
        valid_fields = ["title", "version", "abstract", "authors", "keywords"]
        syncer = CitationSyncer(
            "pyproject.toml", "citation.cff", updatable_fields=valid_fields
        )
        assert syncer.updatable_fields == set(valid_fields)

    def test_invalid_updatable_fields(self):
        """Test that invalid updatable fields raise an error."""
        invalid_fields = ["invalid_field", "another_invalid"]
        with pytest.raises(CitationSyncError) as exc_info:
            CitationSyncer(
                "pyproject.toml", "citation.cff", updatable_fields=invalid_fields
            )
        error_msg = str(exc_info.value)
        assert "Invalid updatable fields:" in error_msg
        assert "invalid_field" in error_msg
        assert "another_invalid" in error_msg
        assert "Valid fields are:" in str(exc_info.value)

    def test_mixed_valid_invalid_updatable_fields(self):
        """Test mix of valid and invalid updatable fields."""
        mixed_fields = ["title", "invalid_field", "version"]
        with pytest.raises(CitationSyncError) as exc_info:
            CitationSyncer(
                "pyproject.toml", "citation.cff", updatable_fields=mixed_fields
            )
        assert "Invalid updatable fields: invalid_field" in str(exc_info.value)

    def test_valid_exclude_fields(self):
        """Test that valid exclude fields are accepted."""
        exclude_fields = ["date-released", "message"]
        syncer = CitationSyncer(
            "pyproject.toml", "citation.cff", exclude_fields=exclude_fields
        )
        assert syncer.exclude_fields == set(exclude_fields)

    def test_invalid_exclude_fields(self):
        """Test that invalid exclude fields raise an error."""
        invalid_fields = ["bad_field"]
        with pytest.raises(CitationSyncError) as exc_info:
            CitationSyncer(
                "pyproject.toml", "citation.cff", exclude_fields=invalid_fields
            )
        assert "Invalid exclude fields: bad_field" in str(exc_info.value)

    def test_fields_to_update_calculation(self):
        """Test that fields_to_update is calculated correctly."""
        updatable = ["title", "version", "abstract", "authors"]
        exclude = ["abstract"]
        syncer = CitationSyncer(
            "pyproject.toml",
            "citation.cff",
            updatable_fields=updatable,
            exclude_fields=exclude,
        )
        expected = set(updatable) - set(exclude)
        assert syncer.fields_to_update == expected

    def test_should_update_field(self):
        """Test the should_update_field method."""
        syncer = CitationSyncer(
            "pyproject.toml", "citation.cff", updatable_fields=["title", "version"]
        )
        assert syncer.should_update_field("title") is True
        assert syncer.should_update_field("version") is True
        assert syncer.should_update_field("abstract") is False
        assert syncer.should_update_field("doi") is False

    def test_default_updatable_fields(self):
        """Test that default updatable fields include all mapped fields."""
        syncer = CitationSyncer("pyproject.toml", "citation.cff")

        # Should include all CFF fields that can be mapped from pyproject.toml
        expected_fields = {
            "title",
            "version",
            "abstract",
            "authors",
            "keywords",
            "license",
            "license-url",
            "url",
            "repository-code",
            "repository-artifact",
            # Plus computed fields
            "cff-version",
            "message",
            "date-released",
        }
        assert syncer.updatable_fields == expected_fields
