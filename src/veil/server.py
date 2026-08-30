"""HTTP API server: anonymize/reconstruct over JSON with per-session mappings.

Standard library only, so ``veil serve`` works with the base install. Intended
for a trusted network segment (it binds to 127.0.0.1 by default and has no
authentication of its own); put it behind your gateway for team use.

Endpoints (all JSON):

    GET  /health                          -> {"status": "ok", ...}
    POST /anonymize   {"text", "session_id"?}
                                          -> {"anonymized_text", "entities",
                                              "session_id", "degraded"}
    POST /reconstruct {"text", "session_id"}
                                          -> {"reconstructed_text", "replacements_made"}
    POST /sessions/<id>/clear             -> {"cleared": true}
    GET  /sessions/<id>                   -> mapping stats (counts only)

Sessions expire after ``session_ttl`` seconds of inactivity. One pipeline
configuration serves every session; the mapping store is per session.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from veil import __version__
from veil.audit import AuditLogger
from veil.core.mapper import MappingStore
from veil.core.pipeline import VeilPipeline


@dataclass
class _Session:
    store: MappingStore = field(default_factory=MappingStore)
    last_used: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)


class VeilService:
    """Thread-safe façade over one pipeline and many sessions."""

    def __init__(
        self,
        pipeline: VeilPipeline | None = None,
        session_ttl: float = 3600.0,
        max_text_chars: int = 200_000,
        audit: AuditLogger | None = None,
        **pipeline_kwargs: Any,
    ) -> None:
        self.pipeline = pipeline or VeilPipeline(**pipeline_kwargs)
        self.session_ttl = session_ttl
        self.max_text_chars = max_text_chars
        self.audit = audit
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.RLock()
        # The pipeline holds one MappingStore; requests swap it per session
        # under this lock so concurrent sessions never see each other's tokens.
        self._pipeline_lock = threading.Lock()

    # -- sessions ---------------------------------------------------------

    def _session(self, session_id: str | None) -> tuple[str, _Session]:
        with self._lock:
            self._expire()
            if session_id and session_id in self._sessions:
                sess = self._sessions[session_id]
            else:
                session_id = session_id or uuid4().hex
                sess = self._sessions.setdefault(session_id, _Session())
            sess.last_used = time.time()
            return session_id, sess

    def _expire(self) -> None:
        cutoff = time.time() - self.session_ttl
        for sid in [s for s, v in self._sessions.items() if v.last_used < cutoff]:
            del self._sessions[sid]

    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def session_stats(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            sess = self._sessions.get(session_id)
            return sess.store.get_stats() if sess else None

    # -- operations -------------------------------------------------------

    def anonymize(self, text: str, session_id: str | None = None) -> dict[str, Any]:
        if len(text) > self.max_text_chars:
            raise ValueError(f"text exceeds {self.max_text_chars} characters")
        sid, sess = self._session(session_id)
        with sess.lock, self._pipeline_lock:
            self.pipeline.mapping_store = sess.store
            if self.audit:
                self.audit.session_id = sid
            result = self.pipeline.anonymize(text)
        return {
            "session_id": sid,
            "anonymized_text": result.anonymized_text,
            "degraded": result.degraded,
            "entities": [
                {
                    "type": e.entity_type.value,
                    "start": e.start,
                    "end": e.end,
                    "token": sess.store.get_replacement(e.text),
                }
                for e in result.entities
            ],
        }

    def reconstruct(self, text: str, session_id: str) -> dict[str, Any]:
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(session_id)
        sid, sess = self._session(session_id)
        with sess.lock, self._pipeline_lock:
            self.pipeline.mapping_store = sess.store
            if self.audit:
                self.audit.session_id = sid
            result = self.pipeline.reconstruct(text)
        return {
            "session_id": sid,
            "reconstructed_text": result.reconstructed_text,
            "replacements_made": result.replacements_made,
        }

    def health(self) -> dict[str, Any]:
        det = self.pipeline.detector
        with self._lock:
            n = len(self._sessions)
        return {
            "status": "ok",
            "version": __version__,
            "degraded": det.degraded,
            "detection_mode": det.mode.value,
            "spacy_model": det.ner_detector.model_name if det.ner_detector else None,
            "sessions": n,
        }


def make_handler(service: VeilService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"veil/{__version__}"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib name
            # Never log request bodies; the default only logs the request line.
            pass

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > service.max_text_chars * 4 + 4096:
                raise ValueError("request body too large")
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("JSON object expected")
            return data

        def do_GET(self) -> None:  # noqa: N802 - stdlib name
            path = urlsplit(self.path).path
            if path == "/health":
                self._json(HTTPStatus.OK, service.health())
                return
            if path.startswith("/sessions/"):
                stats = service.session_stats(path.split("/")[2])
                if stats is None:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "unknown session"})
                else:
                    self._json(HTTPStatus.OK, stats)
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib name
            path = urlsplit(self.path).path
            try:
                if path == "/anonymize":
                    data = self._read_json()
                    text = data.get("text")
                    if not isinstance(text, str):
                        raise ValueError("'text' (string) is required")
                    self._json(HTTPStatus.OK, service.anonymize(text, data.get("session_id")))
                elif path == "/reconstruct":
                    data = self._read_json()
                    text = data.get("text")
                    sid = data.get("session_id")
                    if not isinstance(text, str) or not isinstance(sid, str):
                        raise ValueError("'text' and 'session_id' (strings) are required")
                    self._json(HTTPStatus.OK, service.reconstruct(text, sid))
                elif path.startswith("/sessions/") and path.endswith("/clear"):
                    cleared = service.clear_session(path.split("/")[2])
                    self._json(HTTPStatus.OK, {"cleared": cleared})
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except KeyError:
                self._json(HTTPStatus.NOT_FOUND, {"error": "unknown session"})
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    return Handler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    service: VeilService | None = None,
    **pipeline_kwargs: Any,
) -> ThreadingHTTPServer:
    """Build (but don't start) the HTTP server. ``port=0`` picks a free port."""
    svc = service or VeilService(**pipeline_kwargs)
    return ThreadingHTTPServer((host, port), make_handler(svc))


def serve(host: str = "127.0.0.1", port: int = 8787, **pipeline_kwargs: Any) -> None:
    """Run the server until interrupted."""
    httpd = create_server(host, port, **pipeline_kwargs)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
