# Audit log

`veil.audit.AuditLogger` records **what Veil did, never what it saw**: one
JSON line per operation with counts by entity type, timing, profile, session
id and the `degraded` flag. Text, values and tokens are never written, so the
log can go to a SIEM or be retained for compliance.

```python
from veil import VeilPipeline
from veil.audit import AuditLogger, summarize

with AuditLogger("veil-audit.jsonl") as audit:
    pipeline = VeilPipeline(audit=audit)
    pipeline.anonymize("Ana Kowalski, ana@k.io")

print(summarize("veil-audit.jsonl"))
# {'anonymize_calls': 1, 'reconstruct_calls': 0, 'sessions': 1,
#  'degraded_calls': 0, 'entities_by_type': {'EMAIL': 1, 'PERSON': 1},
#  'avg_anonymize_ms': 3.1}
```

Record example:

```json
{"degraded": false, "detection_mode": "standard", "duration_ms": 3.1,
 "entity_count": 2, "entity_types": {"EMAIL": 1, "PERSON": 1},
 "event": "anonymize", "profile": "balanced", "replacement_mode": "token",
 "replacements_made": 0, "session_id": "…", "text_chars": 22, "timestamp": 1.7e9}
```

Events: `anonymize`, `reconstruct`, `llm_request` (provider, model, turn
count — from `VeilProxy(audit=...)`), `session_clear`.

`AuditLogger()` with no path keeps events in memory (`audit.events`) for tests
and dashboards. `veil serve --audit path` enables it for the API server, with
the HTTP session id as the audit session id.
