# Contributing

Thank you for your interest in contributing to Veil!

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- pip or uv

### Setup Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd veil

# Install in development mode with all dependencies
pip install -e ".[dev,full]"

# Download spaCy model
python -m spacy download en_core_web_sm

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=veil --cov-report=term-missing

# Run specific test file
pytest tests/test_pipeline.py -v

# Run specific test
pytest tests/test_pipeline.py::TestPipeline::test_anonymize -v
```

## Code Style

We use the following tools for code quality:

### Ruff (Linting & Formatting)

```bash
# Check linting
ruff check src/

# Auto-fix issues
ruff check --fix src/

# Format code
ruff format src/
```

### MyPy (Type Checking)

```bash
mypy src/veil/
```

## Project Structure

```
veil/
├── src/veil/
│   ├── __init__.py         # Package exports
│   ├── cli.py              # CLI interface
│   ├── core/               # Core functionality
│   │   ├── pipeline.py     # Main VeilPipeline
│   │   ├── detector.py     # Detection orchestration
│   │   └── mapper.py       # Mapping storage
│   ├── detection/          # Detection engines
│   │   ├── entity.py       # Entity data model
│   │   ├── ner.py          # spaCy NER
│   │   ├── patterns.py     # Regex patterns
│   │   ├── presidio.py     # Presidio wrapper
│   │   └── hybrid.py       # Ensemble detector
│   ├── replacement/        # Replacement strategies
│   │   ├── engine.py       # Replacement engine
│   │   ├── token.py        # Token replacer
│   │   ├── faker_gen.py    # Faker replacer
│   │   └── semantic.py     # Semantic replacer
│   ├── weighting/          # Scoring system
│   │   ├── config.py       # Profile configs
│   │   ├── scorer.py       # Privacy scorer
│   │   ├── context.py      # Context analyzer
│   │   └── tfidf.py        # TF-IDF analysis
│   ├── llm/                # LLM integration
│   │   ├── proxy.py        # Privacy proxy
│   │   └── providers/      # LLM providers
│   ├── app/                # Desktop app
│   │   └── desktop.py      # Gradio UI
│   ├── integrations/       # Framework integrations
│   │   └── guardrails.py   # Guardrails AI
│   └── config/             # Configuration
│       └── settings.py     # Settings management
├── tests/                  # Test files
├── docs/                   # Documentation
├── pyproject.toml          # Project configuration
└── mkdocs.yml              # Docs configuration
```

## Writing Tests

### Test Structure

```python
# tests/test_example.py
import pytest
from veil import VeilPipeline

class TestExample:
    """Test class description."""

    def test_feature(self):
        """Test specific feature."""
        pipeline = VeilPipeline()
        result = pipeline.anonymize("test@example.com")
        assert "[EMAIL_1]" in result.anonymized_text

    def test_edge_case(self):
        """Test edge case."""
        pipeline = VeilPipeline()
        result = pipeline.anonymize("")
        assert result.entity_count == 0

    @pytest.mark.parametrize("input,expected", [
        ("test@example.com", 1),
        ("no entities here", 0),
    ])
    def test_parametrized(self, input, expected):
        """Test with multiple inputs."""
        pipeline = VeilPipeline()
        result = pipeline.anonymize(input)
        assert result.entity_count == expected
```

### Test Fixtures

```python
@pytest.fixture
def pipeline():
    """Create a pipeline for testing."""
    return VeilPipeline(profile="balanced")

def test_with_fixture(pipeline):
    result = pipeline.anonymize("John Smith")
    assert result.entity_count > 0
```

## Documentation

### Building Docs

```bash
# Serve locally
mkdocs serve

# Build static HTML
mkdocs build
```

### Documentation Style

- Use clear, concise language
- Include code examples
- Document all public APIs
- Add docstrings to all public functions

## Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/my-feature`
3. **Make** your changes
4. **Test** your changes: `pytest tests/ -v`
5. **Lint** your code: `ruff check src/`
6. **Commit** with a descriptive message
7. **Push** to your fork
8. **Open** a Pull Request

### PR Checklist

- [ ] Tests pass locally
- [ ] New code has tests
- [ ] Code follows style guidelines
- [ ] Documentation updated if needed
- [ ] Commit messages are clear

## Reporting Issues

When reporting issues, please include:

1. **Description** of the problem
2. **Steps to reproduce**
3. **Expected behavior**
4. **Actual behavior**
5. **Environment** (Python version, OS, package versions)
6. **Code sample** if applicable

## Feature Requests

We welcome feature requests! Please:

1. Check existing issues first
2. Describe the use case
3. Explain the expected behavior
4. Consider implementation implications

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
