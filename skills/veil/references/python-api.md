# Python API

```python
from veil import VeilPipeline, MappingStore, Entity, EntityType
```

## Pipeline

```python
pipeline = VeilPipeline()
result = pipeline.anonymize("Jane Example works at Acme, jane@example.com")

result.anonymized_text     # "[PERSON_1] works at [ORG_1], [EMAIL_1]"
result.entities            # list[Entity]: text, entity_type, start, end, confidence, source
result.entity_count
result.replacements        # {original: replacement}
result.scores              # list[PrivacyScore] when weighting is on
result.degraded            # True only with strict=False and a missing detector
result.mapping_store       # the session this result belongs to

reply = "I will write to EMAIL_1 and copy [PERSON_1]."
pipeline.reconstruct(reply).reconstructed_text
```

Constructor options, with defaults:

```python
VeilPipeline(
    use_ner=True,                 # spaCy named entities
    use_patterns=True,            # regex detectors with validators
    use_presidio=False,           # True forces hybrid mode
    spacy_model=None,             # default: best installed (trf > lg > md > sm)
    min_confidence=0.0,           # drop detections below this confidence
    bracket_style="square",       # "square" | "angle" | "curly"
    profile=DetectionProfile.BALANCED,
    weight_config=None,           # WeightConfig.from_yaml(...) overrides profile
    use_weighting=True,           # False: replace every detection
    replacement_mode="token",     # "token" | "faker" | "semantic"
    faker_locale="en_US",
    faker_seed=None,
    semantic_threshold=0.6,
    detection_mode="standard",    # "standard" | "hybrid"
    agreement_boost=0.15,         # hybrid: confidence added when detectors agree
    strict=True,                  # raise if a requested detector cannot load
    audit=None,                   # AuditLogger
)
```

`DetectionProfile` and `parse_profile("paranoid")` are in
`veil.weighting.config`. Unknown mode or profile names raise `ValueError`.

Other methods:

```python
pipeline.anonymize(text, entity_types=[EntityType.PERSON, EntityType.EMAIL])
pipeline.process(text)                 # -> (anonymized_text, replacements)
pipeline.score_entities(text)          # list[PrivacyScore], nothing replaced
pipeline.detector.detect(text)         # raw detections, before scoring
pipeline.get_mapping("Jane Example")   # -> "[PERSON_1]" or None
pipeline.get_original("[PERSON_1]")    # -> "Jane Example" or None
pipeline.set_profile(DetectionProfile.PARANOID)
pipeline.set_replacement_mode("faker")
pipeline.add_pattern(pattern)          # see profiles.md
pipeline.clear_mappings()              # start a new session
pipeline.get_stats()                   # detectors, model, threshold, mapping counts
```

One-off helper: `from veil.core.pipeline import anonymize` returns
`(anonymized_text, replacements)` from a temporary pipeline.

## Sessions

The mapping store is session state on the pipeline. It persists across
`anonymize()` calls, so "Jane Example", "Ms. Example" and "Example" resolve to
one token, and a later text reuses earlier tokens.

```python
import json

# Save
state = pipeline.mapping_store.to_dict()
json.dump(state, open("session.json", "w"))    # contains originals: protect it

# Restore, in another process
pipeline = VeilPipeline()
pipeline.mapping_store = MappingStore.from_dict(json.load(open("session.json")))
pipeline.anonymize("Jane Example called again")   # still [PERSON_1]

# Restore without touching the pipeline's current session
store = MappingStore.from_dict(state)
pipeline.reconstruct(reply, mapping_store=store)
text, count = store.restore(reply)                # no pipeline needed
```

`store.get_stats()` gives counts by type without values.

## Batches

```python
results = pipeline.anonymize_batch(texts)                            # one shared session
results = pipeline.anonymize_batch(texts, separate_sessions=True)    # unlinkable documents

for result in results:
    pipeline.reconstruct(model_output, mapping_store=result.mapping_store)
```

`anonymize_batch` runs spaCy in batch mode and is the fast path for many
documents. With `separate_sessions=True` token numbering restarts per
document and each result keeps its own store.

## Fail-closed detection

```python
from veil.core.detector import DetectionUnavailableError

try:
    pipeline = VeilPipeline(detection_mode="hybrid", use_presidio=True)
except DetectionUnavailableError:
    ...   # spaCy model or Presidio missing: install it, or stop

pipeline = VeilPipeline(strict=False)       # runs with what is available
result = pipeline.anonymize(text)
if result.degraded:
    ...   # the text may still contain sensitive data: do not send it on
```

## Audit log

Counts, timing, profile, session id and the degraded flag. Never text, values
or tokens.

```python
from veil.audit import AuditLogger, summarize

with AuditLogger("veil-audit.jsonl") as audit:
    pipeline = VeilPipeline(audit=audit)
    pipeline.anonymize("Jane Example, jane@example.com")
    audit.new_session()                # call when the conversation resets

summarize("veil-audit.jsonl")
# {'anonymize_calls': 1, 'reconstruct_calls': 0, 'sessions': 1, 'degraded_calls': 0,
#  'entities_by_type': {'EMAIL': 1, 'PERSON': 1}, 'avg_anonymize_ms': ...}
```

`AuditLogger()` with no path keeps events in memory (`audit.events`). Events:
`anonymize`, `reconstruct`, `llm_request`, `session_clear`.

## Guardrails AI

Requires `pip install guardrails-ai`.

```python
from guardrails import Guard
from veil.integrations.guardrails import VeilAnonymizer, VeilPIIValidator, create_veil_guard

# Always anonymize
guard = Guard().use(VeilAnonymizer(profile="paranoid", replacement_mode="token"))
guard.validate("Jane Example, SSN 123-45-6789").validated_output

# Fail (or fix) when PII is present
validator = VeilPIIValidator(
    profile="balanced",
    detection_mode="hybrid",     # default; pass "standard" and use_presidio=False without Presidio
    use_presidio=True,
    min_entities=1,
    entity_types=["PERSON", "EMAIL"],   # optional; unknown names raise ValueError
    on_fail="fix",               # fix | exception | filter | refrain | noop
)
guard = Guard().use(validator)

guard = create_veil_guard(profile="paranoid", on_fail="fix")
```

Guardrails AI collects usage telemetry of its own by default and sends it
to its vendor. Turn it off before using it with sensitive data (`guardrails
configure --disable-metrics`, or `enable_metrics=false` in `~/.guardrailsrc`)
and check its documentation for the current setting.

Each validation starts from an empty mapping, so tokens do not link one
validated text to the next. These validators are one-way: use `VeilPipeline`
or `VeilProxy` when replies must be reconstructed.

## Desktop app settings

Only the desktop app reads these; pipelines are configured by constructor
arguments.

```python
from veil.config import get_settings, save_settings, reset_settings

settings = get_settings()                 # ~/.config/veil/settings.json, mode 0600
settings.llm.provider = "ollama"
settings.llm.model = "llama3.2"
settings.privacy.profile = "paranoid"
settings.privacy.detection_mode = "hybrid"
save_settings()
```
