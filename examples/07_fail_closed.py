"""Safety: Veil refuses to run with a missing detector unless you opt in.

Run: PYTHONPATH=src python examples/07_fail_closed.py
"""

from veil import VeilPipeline
from veil.core.detector import DetectionUnavailableError

try:
    VeilPipeline(spacy_model="en_core_web_does_not_exist")
except DetectionUnavailableError as exc:
    print("strict (default) ->", type(exc).__name__, "-", str(exc)[:70], "...")

# Opting in to degraded mode: regex patterns still work, NER does not, and
# every result says so.
pipeline = VeilPipeline(spacy_model="en_core_web_does_not_exist", strict=False)
result = pipeline.anonymize("Priya Raghunathan, priya@example.com")
print("degraded        ->", result.anonymized_text, "| degraded =", result.degraded)
print("reasons         ->", pipeline.detector.degradation_reasons)

# VeilProxy additionally refuses to send a degraded result to a provider
# unless constructed with allow_degraded=True.
