"""API server, audit log, public brands, batch anonymization."""

import json
import threading
import urllib.request
from collections.abc import Iterator
from urllib.error import HTTPError

import pytest

from veil import VeilPipeline
from veil.audit import AuditLogger, summarize
from veil.detection.ner import SPACY_AVAILABLE
from veil.server import VeilService, create_server
from veil.weighting.config import DetectionProfile

pytestmark = pytest.mark.skipif(not SPACY_AVAILABLE, reason="needs spaCy")


@pytest.fixture(scope="module")
def pipeline() -> VeilPipeline:
    try:
        return VeilPipeline()
    except OSError:
        pytest.skip("no spaCy model")


class TestPublicBrands:
    def test_card_network_is_not_anonymized_in_balanced(self, pipeline):
        pipeline.clear_mappings()
        out = pipeline.anonymize("Amex 3782 822463 10005 was declined by Visa.").anonymized_text
        assert out == "Amex [CREDIT_CARD_1] was declined by Visa."

    def test_paranoid_still_catches_brands(self):
        pipe = VeilPipeline(profile=DetectionProfile.PARANOID)
        assert "Amex" not in pipe.anonymize("Amex declined the card.").anonymized_text

    def test_unknown_org_is_still_anonymized(self, pipeline):
        pipeline.clear_mappings()
        assert "[ORG_1]" in pipeline.anonymize("Globex Corporation declined.").anonymized_text


class TestBatch:
    def test_batch_matches_single(self, pipeline):
        docs = ["Mail ana@k.io about Priya Raghunathan.", "Nothing here.", "", "Call 212-555-0147."]
        pipeline.clear_mappings()
        single = [pipeline.anonymize(d).anonymized_text for d in docs]
        pipeline.clear_mappings()
        batch = [r.anonymized_text for r in pipeline.anonymize_batch(docs)]
        assert batch == single

    def test_separate_sessions_restart_numbering(self, pipeline):
        docs = ["ana@k.io", "bob@k.io"]
        outs = [r.anonymized_text for r in pipeline.anonymize_batch(docs, separate_sessions=True)]
        assert outs == ["[EMAIL_1]", "[EMAIL_1]"]


class TestAudit:
    def test_events_have_counts_but_no_content(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        with AuditLogger(log, session_id="s1") as audit:
            pipe = VeilPipeline(audit=audit)
            r = pipe.anonymize("Ana Kowalski, ana@k.io")
            pipe.reconstruct(r.anonymized_text)
        lines = [json.loads(line) for line in log.read_text().splitlines()]
        assert [e["event"] for e in lines] == ["anonymize", "reconstruct"]
        assert lines[0]["entity_types"] == {"EMAIL": 1, "PERSON": 1}
        assert lines[0]["session_id"] == "s1" and lines[0]["profile"] == "balanced"
        assert lines[1]["replacements_made"] == 2
        raw = log.read_text()
        for secret in ("Ana", "Kowalski", "ana@k.io", "[PERSON_1]", "[EMAIL_1]"):
            assert secret not in raw
        assert summarize(log)["entities_by_type"] == {"EMAIL": 1, "PERSON": 1}

    def test_in_memory_logger(self):
        audit = AuditLogger()
        VeilPipeline(audit=audit).anonymize("Priya Raghunathan")
        assert audit.events[0].entity_count == 1


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    audit = AuditLogger()
    service = VeilService(session_ttl=60, audit=audit)
    httpd = create_server("127.0.0.1", 0, service=service)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=30) as resp:
        return json.loads(resp.read())


class TestServer:
    def test_health(self, server):
        h = _get(server, "/health")
        assert h["status"] == "ok" and h["degraded"] is False

    def test_anonymize_then_reconstruct_in_session(self, server):
        a = _post(server, "/anonymize", {"text": "I am Ana Kowalski, ana@k.io"})
        assert a["anonymized_text"] == "I am [PERSON_1], [EMAIL_1]"
        assert {e["type"] for e in a["entities"]} == {"PERSON", "EMAIL"}
        sid = a["session_id"]
        b = _post(server, "/anonymize", {"text": "Kowalski called again", "session_id": sid})
        assert b["anonymized_text"] == "[PERSON_1] called again"
        r = _post(
            server, "/reconstruct", {"text": "Sent to EMAIL_1 for [PERSON_1]", "session_id": sid}
        )
        assert r["reconstructed_text"] == "Sent to ana@k.io for Ana Kowalski"
        assert _get(server, f"/sessions/{sid}")["total_mappings"] == 2
        assert _post(server, f"/sessions/{sid}/clear", {})["cleared"] is True

    def test_sessions_are_isolated(self, server):
        a = _post(server, "/anonymize", {"text": "ana@k.io"})
        b = _post(server, "/anonymize", {"text": "bob@k.io"})
        assert a["session_id"] != b["session_id"]
        assert a["anonymized_text"] == b["anonymized_text"] == "[EMAIL_1]"
        r = _post(server, "/reconstruct", {"text": "[EMAIL_1]", "session_id": b["session_id"]})
        assert r["reconstructed_text"] == "bob@k.io"

    def test_errors(self, server):
        with pytest.raises(HTTPError) as exc:
            _post(server, "/reconstruct", {"text": "x", "session_id": "nope"})
        assert exc.value.code == 404
        with pytest.raises(HTTPError) as exc:
            _post(server, "/anonymize", {"text": 5})
        assert exc.value.code == 400

    def test_concurrent_sessions_do_not_cross(self, server):
        results: dict[int, str] = {}

        def worker(i: int) -> None:
            a = _post(server, "/anonymize", {"text": f"user{i}@k.io"})
            r = _post(server, "/reconstruct", {"text": "[EMAIL_1]", "session_id": a["session_id"]})
            results[i] = r["reconstructed_text"]

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results == {i: f"user{i}@k.io" for i in range(12)}
