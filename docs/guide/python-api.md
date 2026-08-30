# Python API

Complete guide to using Veil in your Python projects.

## Core Pipeline

The `VeilPipeline` class is the main entry point for anonymization.

### Basic Usage

```python
from veil import VeilPipeline

# Create pipeline with defaults
pipeline = VeilPipeline()

# Anonymize text
result = pipeline.anonymize("John Smith, email: john@example.com")

print(result.anonymized_text)  # "[PERSON_1], email: [EMAIL_1]"
print(result.entity_count)      # 2
print(result.replacements)      # {"John Smith": "[PERSON_1]", ...}
```

### Configuration Options

```python
from veil import VeilPipeline
from veil.weighting.config import DetectionProfile

pipeline = VeilPipeline(
    # Detection
    use_ner=True,                         # spaCy NER
    use_patterns=True,                    # Regex patterns
    use_presidio=True,                    # Microsoft Presidio

    # Profile
    profile=DetectionProfile.BALANCED,    # paranoid, balanced, minimal

    # Mode
    detection_mode="hybrid",              # standard, hybrid
    replacement_mode="token",             # token, faker, semantic

    # Weighting
    use_weighting=True,

    # Faker options
    faker_locale="en_US",
    faker_seed=42,
)
```

### Anonymization Result

```python
result = pipeline.anonymize("John Smith works at Acme Corp")

# Access result attributes
result.original_text      # "John Smith works at Acme Corp"
result.anonymized_text    # "[PERSON_1] works at [ORG_1]"
result.entities           # List of Entity objects
result.entity_count       # Number of entities found
result.replacements       # Dict mapping original -> replacement
```

### Reconstruction

```python
# After anonymization, reconstruct responses
llm_response = "I've noted [PERSON_1]'s information at [ORG_1]."

recon_result = pipeline.reconstruct(llm_response)

print(recon_result.reconstructed_text)
# "I've noted John Smith's information at Acme Corp."
```

### Session Management

```python
# Clear mappings between sessions
pipeline.clear_mappings()

# Get pipeline statistics
stats = pipeline.get_stats()
print(stats)
```

## Entity Detection

### Working with Entities

```python
from veil.detection.entity import Entity, EntityType

result = pipeline.anonymize("John Smith, SSN 123-45-6789")

for entity in result.entities:
    print(f"Text: {entity.text}")
    print(f"Type: {entity.entity_type}")  # EntityType enum
    print(f"Position: {entity.start}-{entity.end}")
    print(f"Confidence: {entity.confidence}")
    print(f"Source: {entity.source}")
    print()
```

### Entity Types

```python
from veil.detection.entity import EntityType

# Available entity types
EntityType.PERSON          # Names
EntityType.EMAIL           # Email addresses
EntityType.PHONE           # Phone numbers
EntityType.SSN             # Social Security Numbers
EntityType.CREDIT_CARD     # Credit card numbers
EntityType.IBAN            # International Bank Account Numbers
EntityType.IP_ADDRESS      # IP addresses (v4 and v6)
EntityType.ADDRESS         # Physical addresses
EntityType.DATE_OF_BIRTH   # Birth dates
EntityType.PASSPORT        # Passport numbers
EntityType.DRIVER_LICENSE  # Driver's license numbers
EntityType.ORG             # Organizations
EntityType.LOCATION        # Geographic locations
EntityType.URL             # Web URLs
# ... and more
```

### Direct Detection

```python
# Detect without anonymizing
entities = pipeline.detector.detect("John Smith, 555-123-4567")

for entity in entities:
    print(f"{entity.text}: {entity.entity_type.value}")
```

## Scoring

Get detailed privacy scores for entities:

```python
scores = pipeline.score_entities("Patient John Smith, SSN 123-45-6789")

for score in scores:
    print(f"Entity: {score.entity.text}")
    print(f"Base score: {score.base_score}")
    print(f"Context boost: {score.context_boost}")
    print(f"Rarity boost: {score.rarity_boost}")
    print(f"Total: {score.total_score}")
    print(f"Above threshold: {score.above_threshold}")
    print()
```

## LLM Proxy

### Basic Proxy Usage

```python
from veil.llm.proxy import VeilProxy
from veil.llm.providers import OpenAIProvider, LLMConfig

# Configure provider
config = LLMConfig(
    api_key="sk-...",
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=2048,
)

# Create provider
provider = OpenAIProvider(config)

# Create privacy proxy
proxy = VeilProxy(
    provider=provider,
    profile="balanced",
    detection_mode="hybrid",
    replacement_mode="token",
)

# Chat with automatic privacy
response = proxy.chat("My SSN is 123-45-6789, help with taxes")

print(response.original_input)         # Your original message
print(response.anonymized_input)       # What was sent to LLM
print(response.raw_response)           # LLM's response (with tokens)
print(response.reconstructed_response) # Final response (with real values)
print(response.entities_found)         # Number of entities protected
print(response.was_anonymized)         # True if entities were found
```

### Conversation History

The proxy keeps the conversation itself, in the form the provider saw it
(anonymized user turns, raw model turns), so follow-ups just work:

```python
proxy.chat("My email is john@example.com")
proxy.chat("Send the report there")          # provider sees "[EMAIL_1]" again
print(proxy.history)                          # list[Message], anonymized
proxy.clear_session()                         # new conversation: mappings + history
```

You can still pass `conversation_history=[...]` explicitly (for example when
restoring a conversation from storage). Those messages are anonymized before
they are sent, so passing the original turns is safe.

### Streaming

Chunks are yielded already reconstructed; a token split across two provider
chunks is held back until it completes.

```python
for chunk in proxy.chat_stream("My SSN is 123-45-6789"):
    print(chunk, end="", flush=True)
```

### Fail closed

```python
from veil.core.detector import DetectionUnavailableError

try:
    proxy = VeilProxy(provider)               # strict=True by default
except DetectionUnavailableError as e:
    ...                                       # spaCy model / Presidio missing

proxy = VeilProxy(provider, strict=False)     # run degraded ...
proxy.chat("...")                             # ... but this still raises unless
proxy = VeilProxy(provider, strict=False, allow_degraded=True)
```

### Different Providers

```python
from veil.llm.providers import (
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    LLMConfig,
)

# OpenAI
openai_config = LLMConfig(api_key="sk-...", model="gpt-4o-mini")
openai_provider = OpenAIProvider(openai_config)

# Anthropic
anthropic_config = LLMConfig(api_key="sk-ant-...", model="claude-sonnet-4-20250514")
anthropic_provider = AnthropicProvider(anthropic_config)

# Ollama (local)
ollama_config = LLMConfig(model="llama3.2", base_url="http://localhost:11434")
ollama_provider = OllamaProvider(ollama_config)
```

## Settings Management

```python
from veil.config import (
    get_settings,
    save_settings,
    reset_settings,
    AppSettings,
)

# Get current settings
settings = get_settings()

# Modify LLM settings
settings.llm.provider = "anthropic"
settings.llm.api_key = "sk-ant-..."
settings.llm.model = "claude-sonnet-4-20250514"

# Modify privacy settings
settings.privacy.profile = "paranoid"
settings.privacy.detection_mode = "hybrid"
settings.privacy.use_presidio = True

# Save to disk
save_settings()

# Reset to defaults
reset_settings()
```

## Error Handling

```python
from veil import VeilPipeline

try:
    pipeline = VeilPipeline(use_presidio=True)
except ImportError as e:
    print("Presidio not installed")
    pipeline = VeilPipeline(use_presidio=False)

try:
    result = pipeline.anonymize(text)
except Exception as e:
    print(f"Anonymization failed: {e}")
```

## Advanced: Custom Detection

```python
from veil.core.detector import EntityDetector
from veil.detection.patterns import PatternDetector
from veil.detection.ner import NERDetector

# Create custom detector
detector = EntityDetector(
    use_ner=True,
    use_patterns=True,
    use_presidio=False,
    mode="standard",
)

# Detect entities
entities = detector.detect("John Smith, 555-123-4567")
```

## Advanced: Custom Replacement

```python
from veil.replacement.engine import ReplacementEngine

# Create replacement engine
engine = ReplacementEngine(
    mode="faker",
    locale="en_US",
    seed=42,
)

# Generate replacement
replacement = engine.generate_replacement(entity)
```
