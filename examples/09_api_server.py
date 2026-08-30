"""Advanced: run the HTTP API in-process and talk to it like a client would.

In production: `veil serve --port 8787 --audit veil-audit.jsonl`
(binds 127.0.0.1; put it behind your gateway to share it with a team).

Run: PYTHONPATH=src python examples/09_api_server.py
"""

import json
import threading
import urllib.request

from veil.server import VeilService, create_server

httpd = create_server("127.0.0.1", 0, service=VeilService())  # port 0 = pick a free one
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_address[1]}"


def call(path: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


print("health     :", call("/health"))
a = call(
    "/anonymize", {"text": "Ticket from Ana Kowalski <ana@k.io>: card 4111111111111111 declined"}
)
print("anonymize  :", a["anonymized_text"])
print("entities   :", [(e["type"], e["token"]) for e in a["entities"]])

# Same session -> same tokens; then map an LLM answer back.
sid = a["session_id"]
b = call("/anonymize", {"text": "Kowalski called again", "session_id": sid})
print("2nd call   :", b["anonymized_text"])
r = call(
    "/reconstruct", {"text": "Refunded CREDIT_CARD_1 and emailed [EMAIL_1].", "session_id": sid}
)
print("reconstruct:", r["reconstructed_text"])
call(f"/sessions/{sid}/clear", {})
httpd.shutdown()
