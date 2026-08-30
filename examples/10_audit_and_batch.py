"""Advanced: audit logging (counts only, never content) and batch processing.

Run: PYTHONPATH=src python examples/10_audit_and_batch.py
"""

import json
import tempfile
from pathlib import Path

from veil import VeilPipeline
from veil.audit import AuditLogger, summarize

log_path = Path(tempfile.mkdtemp()) / "veil-audit.jsonl"

docs = [
    "Invoice for Globex Corp, attn Hank Scorpio, due 2024-02-01. IBAN DE89 3704 0044 0532 0130 00.",
    "Patient Mary Johnson (MRN-12345678), follow-up with Dr. Robert Wilson.",
    "Support ticket from olivia@example.net: login fails from 10.0.0.5.",
] * 10

with AuditLogger(log_path) as audit:
    pipeline = VeilPipeline(audit=audit)
    # spaCy runs in batch mode; each document gets its own session/token numbering
    results = pipeline.anonymize_batch(docs, separate_sessions=True)

print(results[0].anonymized_text)
print(results[1].anonymized_text)
print()
print("first audit record:")
print("  ", log_path.read_text().splitlines()[0])
print()
print("summary:", json.dumps(summarize(log_path), indent=2))

raw = log_path.read_text()
assert "Scorpio" not in raw and "olivia@example.net" not in raw and "[PERSON_1]" not in raw
