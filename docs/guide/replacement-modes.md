# Replacement Modes

Veil offers three ways to replace detected entities.

## Token Mode (Default)

Replaces entities with typed, numbered placeholders.

```bash
veil anonymize "John Smith, email john@example.com" --mode token
```

**Output:**
```
[PERSON_1], email [EMAIL_1]
```

### Characteristics

- Simple, predictable tokens
- Easy to identify entity types
- Tokens increment per type: `[PERSON_1]`, `[PERSON_2]`, etc.
- Perfect reconstruction guaranteed

### Use Cases

- When you need exact reconstruction
- Debugging and testing
- When the LLM doesn't need realistic data

### Bracket Styles

```python
from veil import VeilPipeline

# Square brackets (default): [PERSON_1]
pipeline = VeilPipeline(replacement_mode="token")

# The bracket style is configured in the token replacer
# Options: square, angle, curly
```

---

## Faker Mode

Replaces entities with realistic fake values.

```bash
veil anonymize "John Smith, email john@example.com" --mode faker
```

**Output:**
```
Michael Johnson, email michael.johnson@gmail.com
```

### Characteristics

- Realistic fake data
- Maintains data type (email stays email-like)
- Uses the Faker library
- Consistent within session (same entity → same fake)

### Installation

```bash
pip install veil[faker]
# or
pip install faker
```

### Use Cases

- Testing with production-like data
- When LLM needs realistic values
- Demo environments

### Locale Support

```python
pipeline = VeilPipeline(
    replacement_mode="faker",
    faker_locale="de_DE",  # German
)
```

Available locales: `en_US`, `en_GB`, `de_DE`, `fr_FR`, `es_ES`, `it_IT`, `ja_JP`, `zh_CN`, and many more.

### Reproducibility

```python
pipeline = VeilPipeline(
    replacement_mode="faker",
    faker_seed=42,  # Same seed = same fake values
)
```

### Faker Mappings

| Entity Type | Faker Generator |
|-------------|-----------------|
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

## Semantic Mode

Replaces entities with semantically similar values.

```bash
veil anonymize "John Smith works at Google" --mode semantic
```

**Output:**
```
James Wilson works at Microsoft
```

### Characteristics

- Preserves semantic meaning
- Uses word embeddings for similarity
- Organizations replace with similar organizations
- Names replace with culturally similar names

### Installation

```bash
pip install veil[embeddings]
# or
pip install gensim
```

### Use Cases

- When context matters
- Training data anonymization
- Research and analysis

### How It Works

1. Loads word embeddings (Word2Vec/GloVe)
2. Finds similar words based on cosine similarity
3. Replaces with semantically related alternatives

### Examples

| Original | Semantic Replacement |
|----------|----------------------|
| Google | Microsoft, Amazon, Apple |
| John | James, Michael, David |
| New York | Los Angeles, Chicago |
| Doctor | Physician, Specialist |

---

## Comparison

| Feature | Token | Faker | Semantic |
|---------|-------|-------|----------|
| Reconstruction | Perfect | Perfect | Perfect |
| Realistic | No | Yes | Partial |
| Semantic meaning | No | Partial | Yes |
| Performance | Fast | Medium | Slower |
| Dependencies | None | Faker | Gensim |

## Choosing a Mode

| Scenario | Recommended Mode |
|----------|------------------|
| Development/Testing | Token |
| LLM conversations | Token |
| Demo with realistic data | Faker |
| Data analysis | Semantic |
| Training data | Semantic |
| Privacy audit | Token |

## Mixed Mode

You can use different modes for different entity types by customizing the replacement engine:

```python
from veil.replacement.engine import ReplacementEngine

# Create custom engine
engine = ReplacementEngine(mode="token")

# Override specific types
# (Advanced usage - see API reference)
```

## Reconstruction

All modes support perfect reconstruction:

```python
pipeline = VeilPipeline(replacement_mode="faker")

# Anonymize
result = pipeline.anonymize("John Smith, john@example.com")
# "Michael Johnson, michael.j@fake.com"

# The mapping is stored
# Original: John Smith → Replacement: Michael Johnson

# Reconstruct any text containing the replacements
llm_response = "Hello Michael Johnson!"
reconstructed = pipeline.reconstruct(llm_response)
# "Hello John Smith!"
```
