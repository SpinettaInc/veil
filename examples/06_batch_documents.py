"""Advanced: many documents, isolated sessions, throughput.

Run: PYTHONPATH=src python examples/06_batch_documents.py
"""

import time

from veil import VeilPipeline

documents = [
    "Invoice 2024-0093 for Globex Corp, attn Hank Scorpio, due 2024-02-01. Pay to IBAN DE89 3704 0044 0532 0130 00.",  # noqa: E501
    "Patient Mary Johnson (MRN-12345678), DOB March 15, 1985, follow-up with Dr. Robert Wilson.",
    "Support ticket from olivia@example.net: login fails from 10.0.0.5 since yesterday.",
] * 20  # 60 documents

# One pipeline (the spaCy model is loaded once and shared), one MappingStore per document.
pipeline = VeilPipeline()

t0 = time.perf_counter()
outputs = []
for doc in documents:
    pipeline.clear_mappings()  # new session: token numbering restarts, no cross-document linkage
    result = pipeline.anonymize(doc)
    outputs.append((result.anonymized_text, result.mapping_store.to_dict()))
elapsed = time.perf_counter() - t0

print(outputs[0][0])
print(outputs[1][0])
print(outputs[2][0])
print(
    f"\n{len(documents)} documents in {elapsed * 1000:.0f} ms ({elapsed * 1000 / len(documents):.1f} ms/doc)"  # noqa: E501
)
