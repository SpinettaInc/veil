# API server

`veil serve` exposes the pipeline over HTTP so a team can share one
deployment. It uses only the standard library.

```bash
veil serve --host 127.0.0.1 --port 8787 --profile balanced --audit veil-audit.jsonl
```

| Option | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address; `0.0.0.0` to expose |
| `--port` | `8787` | TCP port |
| `--profile` | `balanced` | Profile name or a YAML path |
| `--detection-mode` | `standard` | `standard` or `hybrid` (Presidio) |
| `--session-ttl` | `3600` | Seconds of inactivity before a session's mappings are dropped |
| `--audit` | – | Append a JSONL [audit log](audit.md) |

There is no authentication or TLS built in. Run it on a trusted network or
behind your API gateway.

## Endpoints

All requests and responses are JSON.

### `POST /anonymize`

```json
{"text": "I am Ana Kowalski, ana@k.io", "session_id": "optional"}
```

```json
{
  "session_id": "3f9c…",
  "anonymized_text": "I am [PERSON_1], [EMAIL_1]",
  "degraded": false,
  "entities": [
    {"type": "PERSON", "start": 5, "end": 17, "token": "[PERSON_1]"},
    {"type": "EMAIL", "start": 19, "end": 27, "token": "[EMAIL_1]"}
  ]
}
```

Omit `session_id` to start a session; reuse it so the same person keeps the
same token across calls.

### `POST /reconstruct`

```json
{"text": "Reply to EMAIL_1 and cc [PERSON_1]", "session_id": "3f9c…"}
```

```json
{"session_id": "3f9c…", "reconstructed_text": "Reply to ana@k.io and cc Ana Kowalski", "replacements_made": 2}
```

Unknown session → `404`.

### `GET /sessions/<id>` · `POST /sessions/<id>/clear` · `GET /health`

Mapping counts by type (no values), drop a session, and liveness/degraded
status respectively.

## Embedding

```python
from veil.server import VeilService, create_server

httpd = create_server("127.0.0.1", 0, service=VeilService(profile="paranoid"))
httpd.serve_forever()
```

`examples/09_api_server.py` drives the server in-process.
