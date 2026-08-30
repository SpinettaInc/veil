# Installation

This guide covers the various ways to install Veil and its optional dependencies.

## Requirements

- Python 3.10 or higher
- pip (Python package manager)

## Basic Installation

Install the core Veil package:

```bash
pip install -e .
```

This includes:

- Core anonymization pipeline
- CLI interface
- spaCy NER detection
- Pattern-based detection
- Token replacement

## Optional Dependencies

Veil has several optional dependency groups for additional features:

### Desktop App

Install the Gradio-based desktop application:

```bash
pip install -e ".[desktop]"
```

Includes: `gradio`, `openai`, `anthropic`, `requests`

### Faker Replacement

For generating realistic fake values:

```bash
pip install -e ".[faker]"
```

Includes: `faker`

### Semantic Replacement

For semantic similarity-based replacements:

```bash
pip install -e ".[embeddings]"
```

Includes: `gensim`

### Corpus-based rarity (optional)

```bash
pip install -e ".[rarity]"
```

Installs `wordfreq`; rare names then score higher than common words even in
short texts. Without it, rarity is estimated from the document alone.

### Full Installation

Install all optional dependencies:

```bash
pip install -e ".[full]"
```

### Development

For contributing to Veil:

```bash
pip install -e ".[dev]"
```

Includes: `pytest`, `pytest-cov`, `ruff`, `mypy`

## spaCy Model

Veil uses spaCy for Named Entity Recognition. Download a model:

```bash
# Small model (recommended for most use cases)
python -m spacy download en_core_web_sm

# Large model (better accuracy, larger size)
python -m spacy download en_core_web_lg
```

## Presidio (Optional)

For enhanced PII detection with Microsoft Presidio:

```bash
pip install presidio-analyzer presidio-anonymizer
```

## Verifying Installation

Check that Veil is installed correctly:

```bash
# Check version
veil version

# Test anonymization
veil anonymize "Test email: test@example.com"
```

Expected output:

```
╭──────────────────────────────────────────────────────────────────────────────╮
│ Test email: [EMAIL_1]                                                        │
╰──────────────────────────────────────────────────────────────────────────────╯

Detected 1 entities (profile: balanced, mode: token)
```

## Troubleshooting

### Command not found

If `veil` command is not found, ensure your Python scripts directory is in PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
```

### spaCy model not found

If you get a spaCy model error:

```bash
python -m spacy download en_core_web_sm
```

### Import errors

If you get import errors for optional features:

```bash
# Install the specific optional dependency
pip install -e ".[desktop]"  # For desktop app
pip install -e ".[faker]"    # For faker replacement
```
