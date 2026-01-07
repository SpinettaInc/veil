# Detection Profiles

Veil offers three detection profiles to balance privacy protection with usability.

## Overview

| Profile | Threshold | False Positives | Privacy Level |
|---------|-----------|-----------------|---------------|
| **Paranoid** | 0.3 | Higher | Maximum |
| **Balanced** | 0.5 | Moderate | Good |
| **Minimal** | 0.7 | Lower | Basic |

## Paranoid Profile

**Use when**: Maximum privacy is critical, and you can tolerate some over-detection.

```bash
veil anonymize "text" --profile paranoid
```

```python
pipeline = VeilPipeline(profile="paranoid")
```

**Characteristics:**

- Lowest threshold (0.3) - detects more entities
- Higher base scores for all entity types
- More aggressive context boosting
- May flag common words as entities

**Best for:**

- Medical records
- Legal documents
- Financial statements
- Any text with highly sensitive data

**Example:**

```
Input:  "Dr. Smith prescribed medication on Monday"
Output: "[PERSON_1] prescribed medication on [DATE_1]"
```

## Balanced Profile (Default)

**Use when**: You want good privacy protection without excessive false positives.

```bash
veil anonymize "text" --profile balanced
```

```python
pipeline = VeilPipeline(profile="balanced")
```

**Characteristics:**

- Moderate threshold (0.5)
- Balanced scoring for entity types
- Reasonable context sensitivity
- Good tradeoff between privacy and usability

**Best for:**

- General business communication
- Customer support
- Most everyday use cases

**Example:**

```
Input:  "John Smith called about order #12345"
Output: "[PERSON_1] called about order #12345"
```

## Minimal Profile

**Use when**: You only want to catch obvious, high-confidence PII.

```bash
veil anonymize "text" --profile minimal
```

```python
pipeline = VeilPipeline(profile="minimal")
```

**Characteristics:**

- Highest threshold (0.7)
- Only high-confidence detections
- Lower base scores
- Fewer false positives

**Best for:**

- Casual communication
- When precision matters more than recall
- Testing and development

**Example:**

```
Input:  "Email john@example.com or call 555-123-4567"
Output: "Email [EMAIL_1] or call [PHONE_1]"
```

## Profile Configuration Details

### Paranoid

```python
{
    "threshold": 0.3,
    "rarity_factor": 0.15,
    "base_scores": {
        "PERSON": 0.7,
        "ORG": 0.6,
        "EMAIL": 0.95,
        "PHONE": 0.9,
        "SSN": 0.98,
        "CREDIT_CARD": 0.98,
        # ...
    },
    "context_patterns": {
        "medical": [...],
        "financial": [...],
        "legal": [...],
    }
}
```

### Balanced

```python
{
    "threshold": 0.5,
    "rarity_factor": 0.1,
    "base_scores": {
        "PERSON": 0.5,
        "ORG": 0.4,
        "EMAIL": 0.95,
        "PHONE": 0.85,
        "SSN": 0.95,
        "CREDIT_CARD": 0.95,
        # ...
    }
}
```

### Minimal

```python
{
    "threshold": 0.7,
    "rarity_factor": 0.05,
    "base_scores": {
        "PERSON": 0.3,
        "ORG": 0.2,
        "EMAIL": 0.9,
        "PHONE": 0.8,
        "SSN": 0.95,
        "CREDIT_CARD": 0.95,
        # ...
    }
}
```

## Scoring System

Each detected entity receives a score based on:

1. **Base Score**: Depends on entity type and profile
2. **Context Boost**: Added when sensitive context is detected
3. **Rarity Boost**: Added for unique/rare values

```
Total Score = Base Score + Context Boost + Rarity Boost
```

Entity is anonymized if `Total Score >= Profile Threshold`

### View Scores

```bash
veil score "Patient John Smith, SSN 123-45-6789" --profile balanced
```

Output:
```
┏━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Entity      ┃ Type   ┃ Base  ┃ Context ┃ Rarity  ┃ Total  ┃ Anonymize?  ┃
┡━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━┩
│ John Smith  │ PERSON │ 0.50  │ +0.30   │ +0.050  │ 0.850  │ Yes         │
│ 123-45-6789 │ SSN    │ 0.95  │ +0.00   │ +0.000  │ 0.950  │ Yes         │
└─────────────┴────────┴───────┴─────────┴─────────┴────────┴─────────────┘
```

## Choosing a Profile

| Scenario | Recommended Profile |
|----------|---------------------|
| Healthcare data | Paranoid |
| Financial services | Paranoid |
| Legal documents | Paranoid |
| Business emails | Balanced |
| Customer support | Balanced |
| Internal notes | Balanced |
| Casual chat | Minimal |
| Development/testing | Minimal |

## Disabling Weighting

To detect all entities regardless of score:

```bash
veil anonymize "text" --no-weighting
```

```python
pipeline = VeilPipeline(use_weighting=False)
```
