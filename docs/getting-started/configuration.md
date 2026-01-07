# Configuration

Veil can be configured through environment variables, configuration files, and programmatic settings.

## Configuration File

Settings are stored in a JSON file at platform-specific locations:

| Platform | Location |
|----------|----------|
| Linux | `~/.config/veil/settings.json` |
| macOS | `~/Library/Application Support/veil/settings.json` |
| Windows | `%APPDATA%/veil/settings.json` |

### Default Configuration

```json
{
  "llm": {
    "provider": "openai",
    "api_key": "",
    "model": "gpt-4o-mini",
    "base_url": "",
    "temperature": 0.7,
    "max_tokens": 2048
  },
  "privacy": {
    "profile": "balanced",
    "detection_mode": "hybrid",
    "replacement_mode": "token",
    "use_presidio": true
  },
  "ui": {
    "theme": "system",
    "show_anonymization": true,
    "auto_clear_session": false
  },
  "system_prompt": ""
}
```

## Programmatic Configuration

### Loading and Saving Settings

```python
from veil.config import get_settings, save_settings, reset_settings

# Get current settings (loads from file or creates defaults)
settings = get_settings()

# Modify settings
settings.llm.provider = "anthropic"
settings.llm.api_key = "sk-ant-..."
settings.privacy.profile = "paranoid"

# Save to file
save_settings()

# Reset to defaults
reset_settings()
```

### LLM Settings

```python
from veil.config import get_settings

settings = get_settings()

# Provider configuration
settings.llm.provider = "openai"      # openai, anthropic, ollama
settings.llm.api_key = "sk-..."       # API key
settings.llm.model = "gpt-4o-mini"    # Model name
settings.llm.base_url = ""            # Custom endpoint (for Ollama)
settings.llm.temperature = 0.7        # 0.0 - 2.0
settings.llm.max_tokens = 2048        # Max response length
```

### Privacy Settings

```python
settings = get_settings()

# Detection profile
settings.privacy.profile = "balanced"  # paranoid, balanced, minimal

# Detection mode
settings.privacy.detection_mode = "hybrid"  # standard, hybrid

# Replacement mode
settings.privacy.replacement_mode = "token"  # token, faker, semantic

# Use Microsoft Presidio
settings.privacy.use_presidio = True
```

### UI Settings

```python
settings = get_settings()

# Theme
settings.ui.theme = "system"  # light, dark, system

# Show anonymization details
settings.ui.show_anonymization = True

# Clear session on new chat
settings.ui.auto_clear_session = False
```

## Pipeline Configuration

Configure the VeilPipeline directly:

```python
from veil import VeilPipeline
from veil.weighting.config import DetectionProfile

pipeline = VeilPipeline(
    # Detection options
    use_ner=True,              # Enable spaCy NER
    use_patterns=True,         # Enable regex patterns
    use_presidio=True,         # Enable Presidio

    # Profile
    profile=DetectionProfile.BALANCED,

    # Detection mode
    detection_mode="hybrid",   # standard or hybrid

    # Replacement
    replacement_mode="token",  # token, faker, or semantic

    # Weighting
    use_weighting=True,        # Enable semantic weighting

    # Faker options (when using faker mode)
    faker_locale="en_US",
    faker_seed=42,             # For reproducibility
)
```

## Detection Profiles

| Profile | Threshold | Description |
|---------|-----------|-------------|
| `paranoid` | 0.3 | Maximum protection, may have false positives |
| `balanced` | 0.5 | Good tradeoff between privacy and usability |
| `minimal` | 0.7 | Only high-confidence PII, fewer false positives |

```python
from veil import VeilPipeline

# Paranoid - detect everything
pipeline = VeilPipeline(profile="paranoid")

# Balanced - default
pipeline = VeilPipeline(profile="balanced")

# Minimal - only obvious PII
pipeline = VeilPipeline(profile="minimal")
```

## Environment Variables

While Veil primarily uses the configuration file, you can also set API keys via environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

These will be picked up by the respective LLM providers if not set in the configuration.

## CLI Configuration

The CLI accepts configuration options as flags:

```bash
# Profile
veil anonymize "text" --profile paranoid

# Detection mode
veil anonymize "text" --hybrid
veil anonymize "text" --presidio

# Replacement mode
veil anonymize "text" --mode token
veil anonymize "text" --mode faker
veil anonymize "text" --mode semantic

# Disable specific detectors
veil anonymize "text" --no-ner
veil anonymize "text" --no-patterns
veil anonymize "text" --no-weighting
```
