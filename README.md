# Citation Sync GitHub Action

A GitHub Action that automatically synchronizes [Citation File Format (CFF)](https://citation-file-format.github.io/) files with [PEP 621](https://peps.python.org/pep-0621/) metadata from `pyproject.toml`.

## Features

- 📊 **Automated Synchronization**: Keep `CITATION.cff` in sync with `pyproject.toml` metadata
- 🔍 **PEP 621 Compliant**: Supports standard Python project metadata
- ✅ **Schema Validation**: Ensures generated CFF files meet v1.2.0 specification
- 🔄 **Idempotent**: Only commits changes when actual differences are detected  
- ⚙️ **Configurable**: Support for custom fields and mappings
- 🚀 **Zero Dependencies**: No additional setup required in your repository

## Quick Start

Add this step to your GitHub workflow:

```yaml
- name: Sync CITATION.cff
  uses: your-username/citation-sync@v1
  with:
    commit: true
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `pyproject-path` | Path to pyproject.toml file | No | `./pyproject.toml` |
| `citation-path` | Path to CITATION.cff file | No | `./CITATION.cff` |
| `commit` | Auto-commit changes if CITATION.cff is updated | No | `false` |
| `commit-message` | Commit message when auto-committing | No | `chore: update CITATION.cff from pyproject.toml` |
| `custom-fields` | JSON object for additional CFF fields | No | `{}` |
| `validate-only` | Only validate existing CITATION.cff without updating | No | `false` |
| `force-update` | Force update even if no changes detected | No | `false` |

## Outputs

| Output | Description |
|--------|-------------|
| `updated` | Whether CITATION.cff was updated (`true`/`false`) |
| `changes-detected` | Whether changes were detected |
| `validation-status` | Status of CFF validation (`valid`/`invalid`/`error`) |

## Field Mapping

The action maps PEP 621 metadata to CFF fields as follows:

| pyproject.toml | CITATION.cff | Notes |
|----------------|--------------|-------|
| `project.name` | `title` | Required |
| `project.authors` | `authors` | Parsed into CFF person/entity format |
| `project.maintainers` | `authors` | Used if no authors specified |
| `project.version` | `version` | Auto-generates `date-released` |
| `project.description` | `abstract` | Project summary |
| `project.keywords` | `keywords` | List of keywords |
| `project.license.text` | `license` | License identifier |
| `project.urls.Homepage` | `url` | Project homepage |
| `project.urls.Repository` | `repository-code` | Source repository |

## Usage Examples

### Basic Usage

```yaml
name: Update Citation
on:
  release:
    types: [published]

jobs:
  update-citation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Sync CITATION.cff
        uses: your-username/citation-sync@v1
        with:
          commit: true
```

### With Custom Fields

```yaml
- name: Sync CITATION.cff with DOI
  uses: your-username/citation-sync@v1
  with:
    commit: true
    custom-fields: |
      {
        "doi": "10.5281/zenodo.123456",
        "repository-code": "https://github.com/user/repo",
        "type": "software"
      }
```

### Validation Only

```yaml
- name: Validate CITATION.cff
  uses: your-username/citation-sync@v1
  with:
    validate-only: true
```

### Integration with Python Package Publishing

```yaml
name: Publish Python Package
on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'
      
      - name: Update CITATION.cff
        uses: your-username/citation-sync@v1
        with:
          commit: true
          commit-message: "docs: update CITATION.cff for release ${{ github.ref_name }}"
      
      - name: Build package
        run: |
          python -m pip install --upgrade pip build
          python -m build
      
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

### Pre-commit Integration

You can also run this action on every push to ensure consistency:

```yaml
name: Check Citation Consistency
on: [push, pull_request]

jobs:
  check-citation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Check CITATION.cff consistency
        uses: your-username/citation-sync@v1
        with:
          validate-only: true
      
      - name: Comment PR if changes needed
        if: steps.citation-check.outputs.changes-detected == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '⚠️ CITATION.cff appears to be out of sync with pyproject.toml. Consider running the citation-sync action.'
            })
```

## Example pyproject.toml

Here's an example `pyproject.toml` that works well with this action:

```toml
[project]
name = "my-awesome-package"
version = "1.0.0"
description = "An awesome Python package for doing amazing things"
authors = [
    {name = "Jane Smith", email = "jane@example.com"},
    {name = "John Doe", email = "john@example.com", orcid = "https://orcid.org/0000-0000-0000-0000"}
]
keywords = ["python", "science", "data"]
license = {text = "MIT"}
readme = "README.md"

[project.urls]
Homepage = "https://my-awesome-package.readthedocs.io"
Repository = "https://github.com/user/my-awesome-package"
Issues = "https://github.com/user/my-awesome-package/issues"
```

This will generate a `CITATION.cff` like:

```yaml
cff-version: 1.2.0
message: If you use this software, please cite it as below.
title: my-awesome-package
authors:
  - given-names: Jane
    family-names: Smith
    email: jane@example.com
  - given-names: John
    family-names: Doe
    email: john@example.com
    orcid: https://orcid.org/0000-0000-0000-0000
version: 1.0.0
date-released: '2025-01-01'
abstract: An awesome Python package for doing amazing things
keywords:
  - python
  - science
  - data
license: MIT
repository-code: https://github.com/user/my-awesome-package
```

## Requirements

### Your Repository

- A `pyproject.toml` file with PEP 621 compliant `[project]` section
- At minimum: `name`, `authors` (or `maintainers`), and `version` fields

### GitHub Actions Permissions

If using `commit: true`, ensure your workflow has write permissions:

```yaml
permissions:
  contents: write
```

## Troubleshooting

### Common Issues

**Error: "No [project] section found"**
- Ensure your `pyproject.toml` has a `[project]` section with PEP 621 metadata

**Validation failed**
- Check that required fields (`name`, `authors`) are present in `pyproject.toml`
- Verify custom fields match CFF 1.2.0 schema requirements

**Changes not committed**
- Set `commit: true` in the action inputs
- Ensure workflow has `contents: write` permissions
- Check that there were actual changes to commit

### Debug Mode

Enable debug logging by setting the `ACTIONS_STEP_DEBUG` secret to `true` in your repository.

## Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Related Projects

- [Citation File Format](https://citation-file-format.github.io/) - Official CFF specification
- [cffconvert](https://github.com/citation-file-format/cffconvert-github-action) - Validate and convert CFF files
- [somesy](https://helmholtz.software/software/somesy) - Comprehensive metadata synchronization tool