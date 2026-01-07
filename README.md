# Veil

Privacy-preserving proxy for LLMs. Anonymize sensitive data before sending to AI, get it back in responses.

## What it does

```
You:     "My SSN is 123-45-6789, help with taxes"
LLM sees: "My SSN is [SSN_1], help with taxes"
LLM says: "For your SSN [SSN_1], I recommend..."
You see:  "For your SSN 123-45-6789, I recommend..."
```

Your private data never leaves your machine.

## Install

```bash
pip install -e .
python -m spacy download en_core_web_sm
```

## Usage

### CLI

```bash
# Anonymize text
veil anonymize "John Smith, john@example.com"

# Detect without changing
veil detect "My phone is 555-123-4567"

# Launch desktop app
veil app
```

### Python

```python
from veil import VeilPipeline

pipeline = VeilPipeline()
result = pipeline.anonymize("Email me at john@example.com")
print(result.anonymized_text)  # "Email me at [EMAIL_1]"
```

### With LLMs

```python
from veil.llm.proxy import VeilProxy
from veil.llm.providers import OpenAIProvider, LLMConfig

provider = OpenAIProvider(LLMConfig(api_key="sk-...", model="gpt-4o-mini"))
proxy = VeilProxy(provider)

response = proxy.chat("My SSN is 123-45-6789")
print(response.reconstructed_response)  # Original values restored
```

## Detection profiles

- `paranoid` - Catches everything, might over-detect
- `balanced` - Good default
- `minimal` - Only obvious stuff

```bash
veil anonymize "text" --profile paranoid
```

## What it detects

Names, emails, phones, SSNs, credit cards, addresses, IBANs, IPs, medical records, passport numbers, and more.

## Replacement modes

```bash
veil anonymize "John Smith" --mode token   # [PERSON_1]
veil anonymize "John Smith" --mode faker   # Michael Johnson
veil anonymize "John Smith" --mode semantic # James Wilson
```

## Optional dependencies

```bash
pip install -e ".[desktop]"  # Gradio app + OpenAI/Anthropic
pip install -e ".[faker]"    # Realistic fake data
pip install -e ".[full]"     # Everything
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Roadmap

### Near term
- [ ] Browser extension for web-based LLM chats
- [ ] Support for more languages (Spanish, German, French)
- [ ] Custom entity types via config
- [ ] Batch processing for large documents

### Medium term
- [ ] Local embedding models for semantic replacement
- [ ] Plugin system for custom detectors
- [ ] API server mode for team deployments
- [ ] Audit logging and compliance reports

### Long term
- [ ] On-device models for fully offline detection
- [ ] Enterprise features (SSO, team management)
- [ ] Integration with more frameworks (LangChain, LlamaIndex)

## License

MIT
