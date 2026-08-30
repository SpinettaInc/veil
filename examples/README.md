# Examples

Every script runs offline and is executed by `tests/test_examples.py`, so they
stay working. Run one with:

```bash
PYTHONPATH=src python examples/01_basic_anonymize.py
```

(`PYTHONPATH=src` is only needed if you haven't `pip install -e .`'d this checkout.)

| Script | Level | Shows |
|---|---|---|
| `01_basic_anonymize.py` | basic | anonymize → inspect entities → reconstruct an LLM reply |
| `02_profiles_and_scoring.py` | basic | paranoid/balanced/minimal, score breakdown, replacement modes |
| `03_custom_profile.py` + `custom_profile.yaml` | advanced | YAML profile, custom entity types, context-gated patterns |
| `04_llm_proxy.py` | advanced | `VeilProxy`: provider only sees tokens, owned history, reconstructed streaming |
| `05_sessions_and_identity.py` | advanced | one token per person across spellings, save/restore a session, tolerant reconstruction |
| `06_batch_documents.py` | advanced | many documents, per-document sessions, throughput |
| `07_fail_closed.py` | safety | strict vs. degraded detection |
| `08_hybrid_presidio.py` | advanced | hybrid mode with Presidio and agreement boosting (skips if not installed) |
| `09_api_server.py` | advanced | the HTTP API (`veil serve`) driven in-process: sessions, reconstruct, clear |
| `10_audit_and_batch.py` | advanced | audit log with counts only, `anonymize_batch` with per-document sessions |

To use a real model in `04_llm_proxy.py`, replace `EchoAssistant` with
`OpenAIProvider`, `AnthropicProvider` or `OllamaProvider` from
`veil.llm.providers` (see the docstring at the top of the file).
