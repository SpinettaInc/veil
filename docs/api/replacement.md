# Replacement API Reference

## ReplacementEngine

Main replacement engine that delegates to specific replacers.

```python
from veil.replacement.engine import ReplacementEngine
```

### Constructor

```python
ReplacementEngine(
    mode: str = "token",
    locale: str = "en_US",
    seed: int | None = None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | str | "token" | Replacement mode |
| `locale` | str | "en_US" | Faker locale |
| `seed` | int | None | Random seed |

### Methods

#### generate_replacement

Generate a replacement for an entity.

```python
def generate_replacement(self, entity: Entity) -> str
```

**Example:**

```python
from veil.replacement.engine import ReplacementEngine
from veil.detection.entity import Entity, EntityType

engine = ReplacementEngine(mode="token")

entity = Entity(
    text="John Smith",
    entity_type=EntityType.PERSON,
    start=0,
    end=10,
    confidence=0.9,
    source="ner",
)

replacement = engine.generate_replacement(entity)
print(replacement)  # "[PERSON_1]"
```

---

## TokenReplacer

Replaces entities with typed, numbered tokens.

```python
from veil.replacement.token import TokenReplacer
```

### Constructor

```python
TokenReplacer(bracket_style: str = "square")
```

**Bracket Styles:**

| Style | Example |
|-------|---------|
| `square` | `[PERSON_1]` |
| `angle` | `<PERSON_1>` |
| `curly` | `{PERSON_1}` |

### Methods

#### replace

```python
def replace(self, entity: Entity) -> str
```

**Example:**

```python
from veil.replacement.token import TokenReplacer

replacer = TokenReplacer(bracket_style="square")
replacement = replacer.replace(entity)
print(replacement)  # "[PERSON_1]"
```

#### reset

Reset token counters.

```python
def reset(self) -> None
```

---

## FakerReplacer

Replaces entities with realistic fake values using Faker.

```python
from veil.replacement.faker_gen import FakerReplacer
```

### Constructor

```python
FakerReplacer(
    locale: str = "en_US",
    seed: int | None = None,
)
```

### Methods

#### replace

```python
def replace(self, entity: Entity) -> str
```

**Example:**

```python
from veil.replacement.faker_gen import FakerReplacer

replacer = FakerReplacer(locale="en_US", seed=42)
replacement = replacer.replace(person_entity)
print(replacement)  # "Michael Johnson"
```

### Entity Type Mappings

| EntityType | Faker Method |
|------------|--------------|
| PERSON | `fake.name()` |
| EMAIL | `fake.email()` |
| PHONE | `fake.phone_number()` |
| ADDRESS | `fake.address()` |
| COMPANY | `fake.company()` |
| SSN | `fake.ssn()` |
| CREDIT_CARD | `fake.credit_card_number()` |
| DATE | `fake.date()` |
| URL | `fake.url()` |
| IP_ADDRESS | `fake.ipv4()` |

---

## SemanticReplacer

Replaces entities with semantically similar values.

```python
from veil.replacement.semantic import SemanticReplacer
```

### Constructor

```python
SemanticReplacer()
```

### Methods

#### replace

```python
def replace(self, entity: Entity) -> str
```

**Example:**

```python
from veil.replacement.semantic import SemanticReplacer

replacer = SemanticReplacer()
replacement = replacer.replace(org_entity)
# "Google" → "Microsoft"
```

### How It Works

1. Uses word embeddings (Word2Vec/GloVe)
2. Finds most similar words by cosine similarity
3. Returns semantically related replacement

---

## MappingStore

Stores bidirectional mappings between original values and replacements.

```python
from veil.core.mapper import MappingStore
```

### Constructor

```python
MappingStore()
```

### Methods

#### add

Add a mapping.

```python
def add(self, original: str, replacement: str, entity_type: EntityType) -> None
```

#### get_replacement

Get replacement for original value.

```python
def get_replacement(self, original: str) -> str | None
```

#### get_original

Get original value for replacement.

```python
def get_original(self, replacement: str) -> str | None
```

#### clear

Clear all mappings.

```python
def clear(self) -> None
```

#### to_dict

Export mappings to dictionary.

```python
def to_dict(self) -> dict
```

#### from_dict

Import mappings from dictionary.

```python
@classmethod
def from_dict(cls, data: dict) -> MappingStore
```

### Example

```python
from veil.core.mapper import MappingStore
from veil.detection.entity import EntityType

store = MappingStore()

# Add mapping
store.add("John Smith", "[PERSON_1]", EntityType.PERSON)

# Lookup
print(store.get_replacement("John Smith"))  # "[PERSON_1]"
print(store.get_original("[PERSON_1]"))      # "John Smith"

# Export/Import
data = store.to_dict()
new_store = MappingStore.from_dict(data)
```

### Iteration

```python
for entry in store:
    print(f"{entry.original} → {entry.replacement}")
```
