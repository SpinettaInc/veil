"""Advanced: hybrid detection (spaCy + regex + Microsoft Presidio) with agreement boosting.

Run: PYTHONPATH=src python examples/08_hybrid_presidio.py
"""

from veil import VeilPipeline
from veil.detection.presidio import PRESIDIO_AVAILABLE

if not PRESIDIO_AVAILABLE:
    print("presidio-analyzer is not installed: pip install presidio-analyzer")
    raise SystemExit(0)

text = "Call John Smith at 212-555-0147; his SSN is 078-05-1120 and he lives in Boston."

# The full spaCy pipeline is loaded once and shared with Presidio.
pipeline = VeilPipeline(detection_mode="hybrid", use_presidio=True)
result = pipeline.anonymize(text)
print(result.anonymized_text)
print()
for entity in result.entities:
    sources = entity.metadata.get("sources", [entity.source])
    print(
        f"{entity.text!r:<16} {entity.entity_type.value:<8} conf={entity.confidence:.2f} sources={sources}"  # noqa: E501
    )
