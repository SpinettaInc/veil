# HTTP API

`veil serve` exposes one pipeline to many sessions over JSON. It is standard
library only, so it works with the base install. Use it from other languages,
or when several tools or agents must share the same tokens.

```bash
veil serve --host 127.0.0.1 --port 8787 --profile balanced \
    --detection-mode standard --session-ttl 3600 --audit veil-audit.jsonl
```

| Option | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8787` | TCP port |
| `--profile` | `balanced` | Profile name or YAML path |
| `--detection-mode` | `standard` | `standard` or `hybrid` |
| `--session-ttl` | `3600` | Seconds of inactivity before a session's mappings are dropped |
| `--audit` | none | Append a counts-only JSONL audit log |

There is no authentication and no TLS. Anyone who can reach the port can
reconstruct any session whose id they know. Keep it on `127.0.0.1`, or put it
behind a gateway; do not bind `0.0.0.0` without the user asking.

## Endpoints

### `POST /anonymize`

```bash
curl -s localhost:8787/anonymize -H 'Content-Type: application/json' \
     -d '{"text": "I am Jane Example, jane@example.com"}'
```

```json
{
  "session_id": "3f9c...",
  "anonymized_text": "I am [PERSON_1], [EMAIL_1]",
  "degraded": false,
  "entities": [
    {"type": "PERSON", "start": 5, "end": 17, "token": "[PERSON_1]"},
    {"type": "EMAIL", "start": 19, "end": 35, "token": "[EMAIL_1]"}
  ]
}
```

Omit `session_id` to start a session. Send it again on later calls so the
same value keeps the same token. The response never echoes the original text.
If `degraded` is true, a detector was unavailable: do not forward the text.

To keep a file's contents out of your own context, build the request from the
file instead of pasting it:

```bash
jq -Rs '{text: ., session_id: "case-42"}' input.txt \
  | curl -s localhost:8787/anonymize -H 'Content-Type: application/json' -d @- \
  | jq -r .anonymized_text > input.anon.txt
```

### `POST /reconstruct`

```bash
curl -s localhost:8787/reconstruct -H 'Content-Type: application/json' \
     -d '{"text": "Reply to EMAIL_1 and cc [PERSON_1]", "session_id": "3f9c..."}'
```

```json
{"session_id": "3f9c...", "reconstructed_text": "Reply to jane@example.com and cc Jane Example", "replacements_made": 2}
```

`session_id` is required. An unknown or expired session is a `404`, never an
empty reconstruction.

### Sessions and health

| Request | Result |
|---|---|
| `GET /sessions/<id>` | Mapping counts by type, no values; `404` if unknown |
| `POST /sessions/<id>/clear` | `{"cleared": true}` and the mappings are dropped |
| `GET /health` | `status`, `version`, `degraded`, `detection_mode`, `spacy_model`, session count |

### Errors

| Status | Cause |
|---|---|
| `400` | Malformed JSON, missing `text`, non-string `session_id`, text over 200,000 characters |
| `404` | Unknown path or session |
| `500` | `{"error": "internal error (<Type>)"}`; the message never quotes the request |

Request bodies are never logged.

## Embedding in Python

```python
from veil.audit import AuditLogger
from veil.server import VeilService, create_server

service = VeilService(profile=..., session_ttl=1800, audit=AuditLogger("audit.jsonl"))
httpd = create_server("127.0.0.1", 0, service=service)   # port 0 picks a free port
print(httpd.server_address)
httpd.serve_forever()
```

`VeilService(**pipeline_kwargs)` accepts the `VeilPipeline` constructor
arguments. `service.anonymize(text, session_id)` and
`service.reconstruct(text, session_id)` can also be called directly, without
HTTP. `examples/09_api_server.py` drives the server in-process.
