# Profiles and custom entity types

## How a detection becomes a replacement

Every detection gets a privacy score:

```
score = type_weight * confidence_factor + rarity + context_boost + relationship_boost
```

- `type_weight` comes from the profile (`entity_weights`).
- `confidence_factor` is `min(1, detector_confidence + 0.15)`.
- `rarity` rewards terms that are rare in the document (and in English, when
  the optional `wordfreq` package is installed).
- `context_boost` is added when cue vocabulary is nearby ("patient",
  "account", "salary").
- `relationship_boost` is added when entities appear in an identifying
  relation to one another.

The entity is replaced when the score reaches the profile `threshold`.

| Profile | Threshold | Character |
|---|---|---|
| `paranoid` | 0.3 | Replaces almost everything detected, including dates, places and organizations |
| `balanced` | 0.5 | Default. People and identifiers; well-known brands and generic numbers stay |
| `minimal` | 0.8 | Only unmistakable identifiers |

`--no-weighting` (`use_weighting=False`) skips scoring and replaces every
detection.

To see the numbers for a file without printing its contents:

```bash
python scripts/veil_tool.py scan input.txt --profile balanced
```

## Entity types

Named entities: `PERSON`, `ORG`, `GPE`, `LOC`, `FAC`, `PRODUCT`, `EVENT`,
`WORK_OF_ART`, `DATE`, `TIME`, `MONEY`, `QUANTITY`, `CARDINAL`, `ORDINAL`,
`PERCENT`, `NORP`, `LANGUAGE`, `LAW`.

Structured identifiers: `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `IP_ADDRESS`,
`URL`, `LICENSE_PLATE`, `PASSPORT`, `DRIVER_LICENSE`, `BANK_ACCOUNT`, `IBAN`,
`MEDICAL_RECORD`, `HEALTH_PLAN`, `DEVICE_ID`.

These are the values accepted by `--types` and by `entity_types=[...]`.
Cards are Luhn-checked and IBANs mod-97-checked. Loose shapes (bank account,
postal code, generic phone, driver licence, unformatted SSN) only count with
a cue word nearby.

## A custom profile

Any YAML file can be used wherever a profile name is accepted. List only what
changes; the rest falls back to the built-in defaults.

```yaml
# corp.yaml
threshold: 0.45
rarity_factor: 0.1
entity_weights:
  PERSON: 1.0
  EMPLOYEE_ID: 0.95        # weight for the custom type declared below
  PROJECT_CODE: 0.7
custom_patterns:
  - name: employee_id
    entity_type: EMPLOYEE_ID          # any name; the token becomes [EMPLOYEE_ID_1]
    regex: "\\bEMP-\\d{5}\\b"
    confidence: 0.95
  - name: project_code
    entity_type: PROJECT_CODE
    regex: "\\b[A-Z]{3}-\\d{3}\\b"
    confidence: 0.6
    context: ["project", "codename", "initiative"]   # cue regexes nearby
    context_boost: 0.1
    requires_context: true            # drop matches with no cue nearby
    ignore_case: false
```

```bash
python scripts/veil_tool.py anonymize in.txt --out out.txt --session s.json --profile corp.yaml
veil anonymize "Badge EMP-48213 is active" --profile ./corp.yaml
veil serve --profile ./corp.yaml
```

```python
from veil import VeilPipeline
from veil.weighting.config import WeightConfig

pipeline = VeilPipeline(weight_config=WeightConfig.from_yaml("corp.yaml"))
```

Rules:

- A name under `entity_weights` that is neither a built-in type nor declared
  by a `custom_patterns` entry is an error.
- Use `requires_context: true` for loose shapes that also match ordinary text.
- Check the result with `scan` on a sample that contains the identifiers.
- Writing a profile for a client? The regexes describe their identifier
  formats, so keep the file with the client's material.

## Adding a pattern in code

```python
import re
from veil import EntityType, VeilPipeline
from veil.detection.patterns import Pattern

pipeline = VeilPipeline(use_weighting=False)
pipeline.add_pattern(
    Pattern(
        name="ticket",
        entity_type=EntityType.CUSTOM,
        label="TICKET",                       # token: [TICKET_1]
        regex=re.compile(r"\bTCK-\d{6}\b"),
        confidence=0.95,
    )
)
```

With weighting on, give the label a weight in a profile (`entity_weights:
{TICKET: 0.9}`), otherwise it is scored with the generic custom weight.
