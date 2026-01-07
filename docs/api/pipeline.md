# Pipeline API Reference

## VeilPipeline

The main class for text anonymization and reconstruction.

```python
from veil import VeilPipeline
```

### Constructor

```python
VeilPipeline(
    use_ner: bool = True,
    use_patterns: bool = True,
    use_presidio: bool = False,
    profile: DetectionProfile | str = "balanced",
    use_weighting: bool = True,
    replacement_mode: str = "token",
    faker_locale: str = "en_US",
    faker_seed: int | None = None,
    detection_mode: str = "standard",
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_ner` | bool | True | Enable spaCy NER detection |
| `use_patterns` | bool | True | Enable regex pattern detection |
| `use_presidio` | bool | False | Enable Microsoft Presidio |
| `profile` | str | "balanced" | Detection profile |
| `use_weighting` | bool | True | Enable semantic weighting |
| `replacement_mode` | str | "token" | Replacement strategy |
| `faker_locale` | str | "en_US" | Locale for faker mode |
| `faker_seed` | int | None | Seed for reproducibility |
| `detection_mode` | str | "standard" | Detection mode |

### Methods

#### anonymize

Anonymize sensitive entities in text.

```python
def anonymize(self, text: str) -> AnonymizationResult
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | str | Text to anonymize |

**Returns:** `AnonymizationResult`

**Example:**

```python
result = pipeline.anonymize("John Smith, john@example.com")
print(result.anonymized_text)
```

---

#### reconstruct

Reconstruct anonymized text with original values.

```python
def reconstruct(self, text: str) -> ReconstructionResult
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | str | Anonymized text to reconstruct |

**Returns:** `ReconstructionResult`

**Example:**

```python
result = pipeline.reconstruct("[PERSON_1] works at [ORG_1]")
print(result.reconstructed_text)
```

---

#### score_entities

Get detailed privacy scores for detected entities.

```python
def score_entities(self, text: str) -> list[EntityScore]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | str | Text to analyze |

**Returns:** List of `EntityScore` objects

**Example:**

```python
scores = pipeline.score_entities("John Smith, SSN 123-45-6789")
for score in scores:
    print(f"{score.entity.text}: {score.total_score}")
```

---

#### clear_mappings

Clear all entity mappings from the session.

```python
def clear_mappings(self) -> None
```

**Example:**

```python
pipeline.clear_mappings()
```

---

#### get_stats

Get pipeline statistics.

```python
def get_stats(self) -> dict
```

**Returns:** Dictionary with pipeline statistics

**Example:**

```python
stats = pipeline.get_stats()
print(stats["detector"])
print(stats["mappings"])
```

---

## AnonymizationResult

Result of an anonymization operation.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `original_text` | str | Original input text |
| `anonymized_text` | str | Text with entities replaced |
| `entities` | list[Entity] | Detected entities |
| `entity_count` | int | Number of entities found |
| `replacements` | dict | Mapping of original → replacement |

### Example

```python
result = pipeline.anonymize("John Smith")

print(result.original_text)    # "John Smith"
print(result.anonymized_text)  # "[PERSON_1]"
print(result.entity_count)      # 1
print(result.replacements)      # {"John Smith": "[PERSON_1]"}
```

---

## ReconstructionResult

Result of a reconstruction operation.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `original_text` | str | Input text (with tokens) |
| `reconstructed_text` | str | Text with original values |
| `replacements_made` | int | Number of replacements |

### Example

```python
result = pipeline.reconstruct("[PERSON_1] works here")

print(result.original_text)       # "[PERSON_1] works here"
print(result.reconstructed_text)  # "John Smith works here"
print(result.replacements_made)   # 1
```

---

## EntityScore

Privacy score for a detected entity.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `entity` | Entity | The detected entity |
| `base_score` | float | Base score from profile |
| `context_boost` | float | Boost from sensitive context |
| `rarity_boost` | float | Boost from rarity analysis |
| `total_score` | float | Combined score |
| `above_threshold` | bool | Whether entity exceeds threshold |

### Example

```python
scores = pipeline.score_entities("Patient John Smith")

for score in scores:
    print(f"Entity: {score.entity.text}")
    print(f"Base: {score.base_score}")
    print(f"Context: {score.context_boost}")
    print(f"Rarity: {score.rarity_boost}")
    print(f"Total: {score.total_score}")
    print(f"Anonymize: {score.above_threshold}")
```
