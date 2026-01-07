# Detection API Reference

## Entity

Represents a detected entity in text.

```python
from veil.detection.entity import Entity, EntityType
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | str | The detected text |
| `entity_type` | EntityType | Type of entity |
| `start` | int | Start position in text |
| `end` | int | End position in text |
| `confidence` | float | Detection confidence (0-1) |
| `source` | str | Detection source (ner, pattern, presidio) |

### Methods

#### to_dict

Convert entity to dictionary.

```python
def to_dict(self) -> dict
```

### Example

```python
from veil.detection.entity import Entity, EntityType

entity = Entity(
    text="john@example.com",
    entity_type=EntityType.EMAIL,
    start=10,
    end=26,
    confidence=0.95,
    source="pattern",
)

print(entity.text)         # "john@example.com"
print(entity.entity_type)  # EntityType.EMAIL
print(entity.confidence)   # 0.95
```

---

## EntityType

Enumeration of supported entity types.

```python
from veil.detection.entity import EntityType
```

### Values

| Value | Description |
|-------|-------------|
| `PERSON` | Person names |
| `ORG` | Organizations |
| `LOCATION` | Geographic locations |
| `EMAIL` | Email addresses |
| `PHONE` | Phone numbers |
| `SSN` | Social Security Numbers |
| `CREDIT_CARD` | Credit card numbers |
| `BANK_ACCOUNT` | Bank account numbers |
| `IBAN` | International Bank Account Numbers |
| `IP_ADDRESS` | IP addresses (v4/v6) |
| `ADDRESS` | Physical addresses |
| `DATE` | Dates |
| `DATE_OF_BIRTH` | Birth dates |
| `PASSPORT` | Passport numbers |
| `DRIVER_LICENSE` | Driver's license numbers |
| `NATIONAL_ID` | National ID numbers |
| `MEDICAL_RECORD` | Medical record numbers |
| `HEALTH_ID` | Health insurance IDs |
| `URL` | Web URLs |
| `USERNAME` | Usernames |
| `PASSWORD` | Passwords |
| `API_KEY` | API keys |
| `COMPANY` | Company names |
| `MONEY` | Monetary amounts |
| `CUSTOM` | Custom entity types |

---

## EntityDetector

Main detection orchestrator combining multiple detection sources.

```python
from veil.core.detector import EntityDetector
```

### Constructor

```python
EntityDetector(
    use_ner: bool = True,
    use_patterns: bool = True,
    use_presidio: bool = False,
    mode: str = "standard",
)
```

### Methods

#### detect

Detect entities in text.

```python
def detect(self, text: str) -> list[Entity]
```

**Example:**

```python
detector = EntityDetector(use_ner=True, use_patterns=True)
entities = detector.detect("John Smith, john@example.com")

for entity in entities:
    print(f"{entity.text}: {entity.entity_type.value}")
```

---

## NERDetector

spaCy-based Named Entity Recognition detector.

```python
from veil.detection.ner import NERDetector
```

### Constructor

```python
NERDetector(model: str = "en_core_web_sm")
```

### Methods

#### detect

```python
def detect(self, text: str) -> list[Entity]
```

**Example:**

```python
from veil.detection.ner import NERDetector

detector = NERDetector("en_core_web_sm")
entities = detector.detect("John Smith works at Acme Corp")
```

---

## PatternDetector

Regex pattern-based detector.

```python
from veil.detection.patterns import PatternDetector
```

### Constructor

```python
PatternDetector()
```

### Methods

#### detect

```python
def detect(self, text: str) -> list[Entity]
```

**Example:**

```python
from veil.detection.patterns import PatternDetector

detector = PatternDetector()
entities = detector.detect("Email: john@example.com, SSN: 123-45-6789")
```

### Detected Patterns

- Email addresses
- Phone numbers (US and international)
- Social Security Numbers
- Credit card numbers (with Luhn validation)
- IP addresses (IPv4 and IPv6)
- URLs
- IBAN numbers
- Passport numbers
- Driver's license numbers
- Medical record numbers

---

## PresidioDetector

Microsoft Presidio-based detector.

```python
from veil.detection.presidio import PresidioDetector
```

### Constructor

```python
PresidioDetector(language: str = "en")
```

### Methods

#### detect

```python
def detect(self, text: str) -> list[Entity]
```

**Example:**

```python
from veil.detection.presidio import PresidioDetector

detector = PresidioDetector("en")
entities = detector.detect("My SSN is 123-45-6789")
```

---

## HybridDetector

Ensemble detector combining multiple sources with agreement boosting.

```python
from veil.detection.hybrid import HybridDetector
```

### Constructor

```python
HybridDetector(
    use_ner: bool = True,
    use_patterns: bool = True,
    use_presidio: bool = True,
)
```

### Methods

#### detect

```python
def detect(self, text: str) -> list[Entity]
```

**Features:**

- Combines results from all enabled detectors
- Boosts confidence when multiple detectors agree
- Merges overlapping detections
- Returns deduplicated entity list

**Example:**

```python
from veil.detection.hybrid import HybridDetector

detector = HybridDetector(
    use_ner=True,
    use_patterns=True,
    use_presidio=True,
)

entities = detector.detect("John Smith, SSN 123-45-6789")
```

### Agreement Boost

When multiple detectors identify the same entity, confidence is boosted:

```python
AGREEMENT_BOOST = 0.15  # 15% boost per agreeing detector
```
