# Quick Start

Get up and running with Veil in 5 minutes.

## 1. Install Veil

```bash
pip install -e ".[desktop]"
python -m spacy download en_core_web_sm
```

## 2. Try the CLI

### Anonymize Text

```bash
veil anonymize "My name is John Smith, email john@example.com"
```

Output:
```
╭──────────────────────────────────────────────────────────────────────────────╮
│ My name is [PERSON_1], email [EMAIL_1]                                       │
╰──────────────────────────────────────────────────────────────────────────────╯

Detected 2 entities (profile: balanced, mode: token)
```

### See the Mapping

```bash
veil anonymize "John Smith, SSN 123-45-6789" --mapping
```

Output:
```
╭──────────────────────────────────────────────────────────────────────────────╮
│ [PERSON_1], SSN [SSN_1]                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯

┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Original       ┃ Replacement  ┃ Type   ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━┩
│ John Smith     │ [PERSON_1]   │ PERSON │
│ 123-45-6789    │ [SSN_1]      │ SSN    │
└────────────────┴──────────────┴────────┘
```

### Detect Without Anonymizing

```bash
veil detect "Contact: john@acme.com, 555-123-4567"
```

Output:
```
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Text            ┃ Type   ┃ Position   ┃ Confidence  ┃ Source   ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ john@acme.com   │ EMAIL  │ 9:22       │ 0.95        │ pattern  │
│ 555-123-4567    │ PHONE  │ 24:36      │ 0.90        │ pattern  │
└─────────────────┴────────┴────────────┴─────────────┴──────────┘
```

## 3. Use the Python API

```python
from veil import VeilPipeline

# Create a pipeline
pipeline = VeilPipeline(profile="balanced")

# Anonymize text
result = pipeline.anonymize(
    "Patient John Smith, DOB 01/15/1990, SSN 123-45-6789"
)

print("Anonymized:", result.anonymized_text)
print("Entities found:", result.entity_count)
print("Mappings:", result.replacements)

# Simulate LLM response with tokens
llm_response = "I've recorded [PERSON_1]'s information. Their SSN [SSN_1] is secured."

# Reconstruct with original values
reconstructed = pipeline.reconstruct(llm_response)
print("Reconstructed:", reconstructed.reconstructed_text)
```

Output:
```
Anonymized: Patient [PERSON_1], DOB [DATE_1], SSN [SSN_1]
Entities found: 3
Mappings: {'John Smith': '[PERSON_1]', '01/15/1990': '[DATE_1]', '123-45-6789': '[SSN_1]'}
Reconstructed: I've recorded John Smith's information. Their SSN 123-45-6789 is secured.
```

## 4. Launch the Desktop App

```bash
veil app
```

Open http://127.0.0.1:7860 in your browser.

The desktop app provides:

- **Chat Tab**: Send messages with automatic PII protection
- **Settings Tab**: Configure LLM provider and privacy settings
- **About Tab**: Information about Veil

## 5. Use with an LLM

```python
from veil.llm.proxy import VeilProxy
from veil.llm.providers import OpenAIProvider, LLMConfig

# Configure your LLM
config = LLMConfig(
    api_key="sk-your-api-key",
    model="gpt-4o-mini"
)
provider = OpenAIProvider(config)

# Create privacy-preserving proxy
proxy = VeilProxy(provider, profile="balanced")

# Chat with automatic anonymization
response = proxy.chat(
    "My name is Sarah Connor, email sarah@skynet.com. "
    "Help me write a professional bio."
)

print("What was sent to LLM:")
print(response.anonymized_input)
print()
print("Final response (with your real info):")
print(response.reconstructed_response)
```

## Next Steps

- [CLI Reference](../guide/cli.md) - Complete CLI documentation
- [Python API](../guide/python-api.md) - Detailed API guide
- [Detection Profiles](../guide/profiles.md) - Configure detection sensitivity
- [LLM Providers](../integrations/llm-providers.md) - Use different LLM services
