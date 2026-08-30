"""Audit logging: what Veil did, never what it saw.

Each anonymize/reconstruct call appends one JSON line with counts, types,
timings and session/profile metadata. Original values, tokens and text are
never written, so the log itself is safe to ship to a SIEM or keep for
compliance reporting.

    from veil import VeilPipeline
    from veil.audit import AuditLogger

    pipeline = VeilPipeline(audit=AuditLogger("veil-audit.jsonl"))
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from veil.detection.entity import Entity


@dataclass
class AuditEvent:
    """One logged operation."""

    event: str  # "anonymize" | "reconstruct" | "session_clear" | "llm_request"
    session_id: str
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    text_chars: int = 0
    entity_count: int = 0
    entity_types: dict[str, int] = field(default_factory=dict)
    replacements_made: int = 0
    degraded: bool = False
    profile: str = ""
    replacement_mode: str = ""
    detection_mode: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        payload = {k: v for k, v in self.__dict__.items() if k != "extra"}
        payload.update(self.extra)
        return json.dumps(payload, sort_keys=True)


class AuditLogger:
    """Append-only JSONL audit log (thread-safe).

    Args:
        path: File to append to, or an open text stream. Parent directories
            are created. ``None`` keeps events in memory only (``events``),
            which is handy for tests and dashboards.
        session_id: Identifier for this pipeline/proxy session; a fresh UUID
            if omitted. Change it with ``new_session()``.
        keep_in_memory: Also retain events in ``self.events``.
    """

    def __init__(
        self,
        path: str | os.PathLike[str] | IO[str] | None = None,
        session_id: str | None = None,
        keep_in_memory: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._stream: IO[str] | None = None
        self._owns_stream = False
        if path is None:
            keep_in_memory = True
        elif hasattr(path, "write"):
            self._stream = path  # type: ignore[assignment]
        else:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._stream = open(p, "a", encoding="utf-8")  # noqa: SIM115 - long-lived
            self._owns_stream = True
        self.keep_in_memory = keep_in_memory
        self.events: list[AuditEvent] = []
        self.session_id = session_id or uuid.uuid4().hex

    def new_session(self, session_id: str | None = None) -> str:
        """Start a new session id (call when the conversation resets)."""
        self.session_id = session_id or uuid.uuid4().hex
        return self.session_id

    def log(self, event: AuditEvent) -> None:
        """Write one event."""
        line = event.to_json()
        with self._lock:
            if self.keep_in_memory:
                self.events.append(event)
            if self._stream is not None:
                self._stream.write(line + "\n")
                self._stream.flush()

    def log_anonymize(
        self,
        *,
        text_chars: int,
        entities: Iterable[Entity],
        duration_ms: float,
        degraded: bool,
        profile: str,
        replacement_mode: str,
        detection_mode: str,
    ) -> None:
        counts = Counter(e.entity_type.value for e in entities)
        self.log(
            AuditEvent(
                event="anonymize",
                session_id=self.session_id,
                duration_ms=round(duration_ms, 3),
                text_chars=text_chars,
                entity_count=sum(counts.values()),
                entity_types=dict(sorted(counts.items())),
                degraded=degraded,
                profile=profile,
                replacement_mode=replacement_mode,
                detection_mode=detection_mode,
            )
        )

    def log_reconstruct(
        self, *, text_chars: int, replacements_made: int, duration_ms: float
    ) -> None:
        self.log(
            AuditEvent(
                event="reconstruct",
                session_id=self.session_id,
                duration_ms=round(duration_ms, 3),
                text_chars=text_chars,
                replacements_made=replacements_made,
            )
        )

    def log_event(self, event: str, **extra: Any) -> None:
        """Log a custom event (e.g. ``llm_request`` with provider/model)."""
        self.log(AuditEvent(event=event, session_id=self.session_id, extra=extra))

    def close(self) -> None:
        if self._owns_stream and self._stream is not None:
            self._stream.close()
            self._stream = None

    def __enter__(self) -> AuditLogger:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def summarize(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Aggregate a JSONL audit log: calls, entities by type, degraded calls, timing."""
    calls = 0
    reconstructs = 0
    degraded = 0
    types: Counter[str] = Counter()
    total_ms = 0.0
    sessions: set[str] = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            sessions.add(rec.get("session_id", ""))
            if rec.get("event") == "anonymize":
                calls += 1
                degraded += int(bool(rec.get("degraded")))
                total_ms += float(rec.get("duration_ms", 0.0))
                types.update(rec.get("entity_types", {}))
            elif rec.get("event") == "reconstruct":
                reconstructs += 1
    return {
        "anonymize_calls": calls,
        "reconstruct_calls": reconstructs,
        "sessions": len(sessions),
        "degraded_calls": degraded,
        "entities_by_type": dict(sorted(types.items())),
        "avg_anonymize_ms": round(total_ms / calls, 3) if calls else 0.0,
    }
