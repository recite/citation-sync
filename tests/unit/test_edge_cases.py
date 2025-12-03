"""Unit tests for edge cases and error handling."""

import pytest
import tempfile
from pathlib import Path
from src.sync_citation import CitationSyncer, CitationSyncError


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_missing_pyproject_file(self, temp_dir):
        """Test error when pyproject.toml doesn't exist."""
        syncer = CitationSyncer(
            str(temp_dir / "nonexistent.toml"), 
            str(temp_dir / "citation.cff")
        )
        
        with pytest.raises(CitationSyncError, match="pyproject.toml not found"):
            syncer.sync()

    def test_invalid_pyproject_syntax(self, temp_dir):
        """Test error with malformed pyproject.toml."""
        pyproject_path = temp_dir / "pyproject.toml"
        with open(pyproject_path, "w") as f:
            f.write("invalid toml syntax [[[")
        
        syncer = CitationSyncer(str(pyproject_path), str(temp_dir / "citation.cff"))
        
        with pytest.raises(CitationSyncError, match="Error parsing pyproject.toml"):
            syncer.sync()

    def test_missing_project_section(self, temp_dir):
        """Test error when [project] section is missing."""
        pyproject_path = temp_dir / "pyproject.toml" 
        with open(pyproject_path, "w") as f:
            f.write("[tool.ruff]\nline-length = 88\n")
        
        syncer = CitationSyncer(str(pyproject_path), str(temp_dir / "citation.cff"))
        
        with pytest.raises(CitationSyncError, match="No \\[project\\] section found"):
            syncer.sync()

    def test_empty_project_section(self, temp_dir):
        """Test with minimal project section."""
        pyproject_path = temp_dir / "pyproject.toml"
        with open(pyproject_path, "w") as f:
            f.write("[project]\n")  # Empty project section
        
        citation_path = temp_dir / "citation.cff"
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        
        result = syncer.sync()
        
        # Should create minimal valid citation
        assert result["updated"] is True
        assert result["validation_status"] == "valid"

    def test_malformed_citation_file(self, temp_dir):
        """Test error with malformed existing CITATION.cff."""
        pyproject_path = temp_dir / "pyproject.toml"
        with open(pyproject_path, "w") as f:
            f.write("[project]\nname = 'test'\n")
        
        citation_path = temp_dir / "citation.cff"
        with open(citation_path, "w") as f:
            f.write("invalid yaml: [[[")
        
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        
        with pytest.raises(CitationSyncError, match="Error parsing CITATION.cff"):
            syncer.sync()

    def test_validate_only_mode(self, temp_dir):
        """Test validate-only mode doesn't write files."""
        pyproject_path = temp_dir / "pyproject.toml"
        with open(pyproject_path, "w") as f:
            f.write("[project]\nname = 'test'\nversion = '1.0.0'\n")
        
        citation_path = temp_dir / "citation.cff"
        # File doesn't exist initially
        
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        result = syncer.sync(validate_only=True)
        
        # Should validate but not create file
        assert result["updated"] is False
        assert result["validation_status"] == "valid"
        assert not citation_path.exists()

    def test_force_update_mode(self, temp_dir):
        """Test force-update mode updates even without changes."""
        pyproject_path = temp_dir / "pyproject.toml"
        with open(pyproject_path, "w") as f:
            f.write("[project]\nname = 'test'\nversion = '1.0.0'\n")
        
        citation_path = temp_dir / "citation.cff"
        with open(citation_path, "w") as f:
            f.write("""cff-version: 1.2.0
message: If you use this software, please cite it as below.
title: test
authors:
- name: Unknown
version: 1.0.0
""")
        
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        
        # Normal sync - no changes
        result1 = syncer.sync()
        assert result1["updated"] is False
        assert result1["changes_detected"] is False
        
        # Force update - should update even without changes
        result2 = syncer.sync(force_update=True)
        assert result2["updated"] is True

    def test_special_characters_in_fields(self, temp_dir):
        """Test handling of special characters in metadata fields."""
        pyproject_path = temp_dir / "pyproject.toml"
        with open(pyproject_path, "wb") as f:
            import tomli_w
            tomli_w.dump({
                "project": {
                    "name": "test-with-émojis-and-ünïcödé",
                    "description": "Description with 'quotes' and \"smart quotes\" and symbols: ©®™",
                    "authors": [{"name": "Åuthor with Spëcial Chärs"}],
                    "keywords": ["tëst", "ünïcödé", "spëcial-chars"]
                }
            }, f)
        
        citation_path = temp_dir / "citation.cff"
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        
        result = syncer.sync()
        
        assert result["updated"] is True
        assert result["validation_status"] == "valid"
        
        # Check file was created and contains unicode
        assert citation_path.exists()
        content = citation_path.read_text(encoding='utf-8')
        assert "test-with-émojis-and-ünïcödé" in content
        assert "Åuthor with Spëcial" in content  # Name gets split

    def test_empty_lists_and_none_values(self, temp_dir):
        """Test handling of empty lists and None values."""
        pyproject_path = temp_dir / "pyproject.toml"
        with open(pyproject_path, "wb") as f:
            import tomli_w
            tomli_w.dump({
                "project": {
                    "name": "test",
                    "authors": [],  # Empty authors list
                    "keywords": [],  # Empty keywords list
                    "maintainers": []  # Empty maintainers list
                }
            }, f)
        
        citation_path = temp_dir / "citation.cff"
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        
        result = syncer.sync()
        
        assert result["updated"] is True
        # Empty authors will be replaced with Unknown, so validation should pass
        assert result["validation_status"] == "valid"

    def test_very_large_metadata(self, temp_dir):
        """Test handling of very large metadata."""
        pyproject_path = temp_dir / "pyproject.toml"
        
        # Create large metadata
        large_description = "A " + "very " * 1000 + "long description"
        many_authors = [{"name": f"Author {i}"} for i in range(100)]
        many_keywords = [f"keyword{i}" for i in range(50)]
        
        with open(pyproject_path, "wb") as f:
            import tomli_w
            tomli_w.dump({
                "project": {
                    "name": "large-project",
                    "description": large_description,
                    "authors": many_authors,
                    "keywords": many_keywords
                }
            }, f)
        
        citation_path = temp_dir / "citation.cff"
        syncer = CitationSyncer(str(pyproject_path), str(citation_path))
        
        result = syncer.sync()
        
        assert result["updated"] is True
        assert result["validation_status"] == "valid"
        
        # Verify content
        assert citation_path.exists()
        content = citation_path.read_text()
        assert "large-project" in content
        assert len([line for line in content.split('\n') if 'Author' in line]) == 100

    def test_mixed_author_formats(self):
        """Test parsing mixed author formats."""
        syncer = CitationSyncer("pyproject.toml", "citation.cff")
        mixed_authors = [
            "Jane Smith",  # String format
            {"name": "John Doe"},  # Dict with name only
            {"name": "Mary Jane Watson", "email": "mary@example.com"},  # Dict with email
            {"name": "Dr. Alex Johnson III", "orcid": "0000-0000-0000-0000", "affiliation": "University"}  # Full dict
        ]
        
        result = syncer.parse_authors(mixed_authors)
        
        assert len(result) == 4
        assert result[0] == {"name": "Jane Smith"}
        assert result[1] == {"given-names": "John", "family-names": "Doe"}
        assert result[2] == {"given-names": "Mary Jane", "family-names": "Watson", "email": "mary@example.com"}
        assert result[3]["given-names"] == "Dr. Alex Johnson"
        assert result[3]["family-names"] == "III"
        assert result[3]["orcid"] == "0000-0000-0000-0000"
        assert result[3]["affiliation"] == "University"