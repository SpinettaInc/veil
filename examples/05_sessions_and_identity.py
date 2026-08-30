"""Advanced: one person = one token across turns and spellings; save/restore a session.

Run: PYTHONPATH=src python examples/05_sessions_and_identity.py
"""

import json

from veil import MappingStore, VeilPipeline

pipeline = VeilPipeline()

turns = [
    "Dr. John Smith reviewed the file.",
    "Later, john smith's assistant called.",
    "Smith confirmed by email: j.smith@clinic.example",
]
for turn in turns:
    print(pipeline.anonymize(turn).anonymized_text)

# Every spelling resolved to the same token; the canonical form is the fullest one.
entry = pipeline.mapping_store.get_entry_by_replacement("[PERSON_1]")
assert entry is not None
print(f"\n[PERSON_1] -> {entry.original!r}, also seen as {entry.aliases}")

# Persist the session (e.g. between requests of a web app) and continue later.
snapshot = json.dumps(pipeline.mapping_store.to_dict())
restored = VeilPipeline()
restored.mapping_store = MappingStore.from_dict(json.loads(snapshot))
print("\nrestored:", restored.anonymize("Send the summary to Smith.").anonymized_text)

# Tolerant reconstruction: models rewrite tokens all the time.
for reply in ["Tell PERSON_1 the results", "I emailed [email 1]", "cc: <Person_1>"]:
    print(f"{reply!r:<32} -> {restored.reconstruct(reply).reconstructed_text!r}")
