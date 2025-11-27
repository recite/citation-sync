# Contributing to Citation Sync

Thank you for considering contributing to Citation Sync! We welcome contributions from the community.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/soodoku/citation-sync.git
cd citation-sync
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r src/requirements.txt
pip install -e ".[dev]"
```

## Testing

### Local Testing

Test the script directly:
```bash
python src/sync_citation.py
```

### Testing with Act

You can test GitHub Actions locally using [act](https://github.com/nektos/act):

```bash
# Install act following the instructions at https://github.com/nektos/act
act -j test-action
```

## Code Quality

We use several tools to maintain code quality:

```bash
# Format code
black src/
isort src/

# Lint code
flake8 src/
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Add tests if applicable
5. Ensure all tests pass and code quality checks pass
6. Commit your changes: `git commit -m "feat: add your feature"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Submit a pull request

## Pull Request Guidelines

- Provide a clear description of the problem and solution
- Include any relevant issue numbers
- Add tests for new functionality
- Update documentation as needed
- Ensure all CI checks pass

## Code of Conduct

Please be respectful and inclusive in all interactions. We aim to create a welcoming environment for all contributors.

## Questions?

Feel free to open an issue for questions or discussion about potential contributions.