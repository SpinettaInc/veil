"""Profiles, replacement modes and the score breakdown behind each decision.

Run: PYTHONPATH=src python examples/02_profiles_and_scoring.py
"""

from veil import VeilPipeline
from veil.weighting.config import DetectionProfile

text = (
    "CEO Jane Okafor of Globex Corp met Dr. Wei Zhang in Berlin on March 3, 2024 about a $2M deal."
)

print("== Same text, three profiles ==")
for profile in DetectionProfile:
    pipeline = VeilPipeline(profile=profile)
    result = pipeline.anonymize(text)
    print(f"{profile.value:<9} {result.anonymized_text}")

print("\n== Why each entity was (or wasn't) anonymized (balanced) ==")
pipeline = VeilPipeline(profile=DetectionProfile.BALANCED)
for score in pipeline.score_entities(text):
    flag = "ANON" if score.above_threshold else "keep"
    print(
        f"{flag}  {score.entity.text!r:<20} {score.total_score:.2f}  {'; '.join(score.contributing_factors)}"  # noqa: E501
    )

print("\n== Replacement modes ==")
print("token   :", VeilPipeline(replacement_mode="token").anonymize(text).anonymized_text)
try:
    import faker  # noqa: F401

    print(
        "faker   :",
        VeilPipeline(replacement_mode="faker", faker_seed=7).anonymize(text).anonymized_text,
    )
except ImportError:
    print("faker   : (pip install -e '.[faker]' to try realistic fake values)")

# Only token mode round-trips unambiguously; see README "Replacement modes".
