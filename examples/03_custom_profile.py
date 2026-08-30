"""Advanced: a YAML profile with custom entity types and context-gated patterns.

Run: PYTHONPATH=src python examples/03_custom_profile.py
"""

from pathlib import Path

from veil import VeilPipeline
from veil.weighting.config import WeightConfig

config = WeightConfig.from_yaml(Path(__file__).with_name("custom_profile.yaml"))
pipeline = VeilPipeline(weight_config=config)

text = (
    "Ref XYZ-999 is just a shelf label with no cue word nearby, so it is left alone. "
    "Meanwhile, badge EMP-48213 (Ana Kowalski) is assigned to project ABC-123."
)
result = pipeline.anonymize(text)
print(result.anonymized_text)

assert "[EMPLOYEE_ID_1]" in result.anonymized_text
assert "[PROJECT_CODE_1]" in result.anonymized_text
assert "[PROJECT_CODE_2]" not in result.anonymized_text  # XYZ-999: no cue word, not a code

# Custom tokens reconstruct like any other, even if the model reformats them.
print(
    pipeline.reconstruct("Please renew badge EMPLOYEE_ID_1 for project_code 1.").reconstructed_text
)
