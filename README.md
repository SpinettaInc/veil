# Veil 🥷💨

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

# Follow-ups reuse the same tokens; the proxy keeps the (anonymized)
# conversation history itself, so the provider never sees originals.
proxy.chat("What did I just tell you?")

# Streaming yields already-reconstructed text
for chunk in proxy.chat_stream("Summarise my details"):
    print(chunk, end="")
```

Reconstruction is tolerant of the model rewriting a token (`EMAIL_1`,
`[email 1]`, `<Email_1>` all restore), and one person keeps one token across
turns and spellings (`Dr. John Smith`, `john smith`, `Smith`).

### API server

```bash
veil serve --port 8787 --audit veil-audit.jsonl      # binds 127.0.0.1 by default
curl -s localhost:8787/anonymize -d '{"text": "I am Ana Kowalski, ana@k.io"}'
# {"session_id": "…", "anonymized_text": "I am [PERSON_1], [EMAIL_1]", "entities": [...]}
curl -s localhost:8787/reconstruct -d '{"text": "Mail EMAIL_1", "session_id": "…"}'
```

Sessions keep their own token mappings and expire after an hour of inactivity
(`--session-ttl`). Standard library only — no extra dependencies. There is no
authentication built in; put it behind your gateway for team use.

### Audit log

```python
from veil.audit import AuditLogger, summarize
pipeline = VeilPipeline(audit=AuditLogger("veil-audit.jsonl"))
```

One JSON line per call with counts by entity type, timing, profile, session
and a `degraded` flag — never the text, values or tokens. `summarize(path)`
aggregates a log for compliance reporting.

### Batch

```python
results = pipeline.anonymize_batch(docs, separate_sessions=True)  # spaCy runs batched
```

### Fail closed

If a requested detector cannot be loaded (spaCy model missing, Presidio not
installed) Veil raises `DetectionUnavailableError` instead of silently
anonymizing less. Pass `strict=False` to `VeilPipeline`/`VeilProxy` to run
degraded; results then carry `degraded=True`, and the proxy still refuses to
send unless `allow_degraded=True`.

## Detection profiles

- `paranoid` - Catches everything, might over-detect
- `balanced` - Good default
- `minimal` - Only obvious stuff

```bash
veil anonymize "text" --profile paranoid
veil anonymize "text" --profile ./my-profile.yaml   # custom profile
```

Profiles are YAML files (`src/veil/config/profiles/*.yaml`). A custom profile
only needs to list what it changes, and can add its own regex detectors:

```yaml
threshold: 0.5
entity_weights:
  EMPLOYEE_ID: 0.95
custom_patterns:
  - name: employee_id
    entity_type: EMPLOYEE_ID      # becomes [EMPLOYEE_ID_1]
    regex: "\\bEMP-\\d{5}\\b"
    confidence: 0.95
    context: ["badge", "employee"]  # optional; requires_context: true to gate on it
```

## What it detects

Names, emails, phones, SSNs, credit cards, addresses, IBANs, IPs, medical records, passport numbers, and more.

Well-known brands and vendors (Amex, Visa, Google, Microsoft, …) are *not*
anonymized in the `balanced` and `minimal` profiles — naming them identifies
nobody. `paranoid` still replaces them; profiles can extend the list with
`public_entities:`.

## Replacement modes

```bash
veil anonymize "John Smith" --mode token   # [PERSON_1]
veil anonymize "John Smith" --mode faker   # Michael Johnson
veil anonymize "John Smith" --mode semantic # James Wilson
```

Only `token` mode round-trips unambiguously: a fake name can also appear in the
model's reply on its own and would be "restored" to the real one. Veil never
picks a fake value that already occurs in your input, but for proxy use prefer
`token`.

## Optional dependencies

```bash
pip install -e ".[desktop]"  # Gradio app + OpenAI/Anthropic
pip install -e ".[faker]"    # Realistic fake data
pip install -e ".[rarity]"   # wordfreq: corpus-based rarity scoring
pip install -e ".[full]"     # Everything
```

## Development

```bash
pip install -e ".[dev]"
pytest -m "not desktop"                  # fast lane
pytest                                   # everything, incl. Gradio app tests
python benchmarks/run.py --corpus all    # precision / recall / latency
```

CI runs lint, tests, and the precision benchmark in both detection modes with
a minimum F1 gate (`.github/workflows/ci.yml`).

## Roadmap

### Near term
- [ ] Browser extension for web-based LLM chats
- [ ] Support for more languages (Spanish, German, French)
- [x] Custom entity types via config
- [x] Batch processing (`anonymize_batch`)

### Medium term
- [ ] Local embedding models for semantic replacement
- [ ] Plugin system for custom detectors
- [x] API server mode (`veil serve`)
- [x] Audit logging (`veil.audit`) and `summarize()` reports

### Long term
- [ ] On-device models for fully offline detection
- [ ] Enterprise features (SSO, team management)
- [ ] Integration with more frameworks (LangChain, LlamaIndex)

## License

MIT
