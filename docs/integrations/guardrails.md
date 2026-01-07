# Guardrails AI Integration

Veil integrates with [Guardrails AI](https://guardrailsai.com/) to provide PII validation in Guardrails pipelines.

## Installation

```bash
pip install guardrails-ai
```

## Validators

Veil provides two validators for Guardrails:

### VeilPIIValidator

Detects PII and optionally anonymizes it.

```python
from veil.integrations.guardrails import VeilPIIValidator
from guardrails import Guard

# Create validator
validator = VeilPIIValidator(
    profile="balanced",
    min_entities=1,
    on_fail="fix",  # Automatically anonymize
)

# Create guard
guard = Guard().use(validator)

# Validate text
result = guard.validate("My email is john@example.com")

if result.validation_passed:
    print("No PII detected")
else:
    print(f"PII detected and anonymized: {result.validated_output}")
```

#### Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `profile` | Detection profile: paranoid, balanced, minimal | balanced |
| `min_entities` | Minimum entities to trigger failure | 1 |
| `on_fail` | Action on failure: fix, exception, filter, etc. | exception |

#### On-Fail Actions

- `fix` - Automatically anonymize the text
- `exception` - Raise an exception
- `filter` - Filter out the entire output
- `refrain` - Return None
- `noop` - Do nothing (just report)

### VeilAnonymizer

Always anonymizes text (doesn't fail, just transforms).

```python
from veil.integrations.guardrails import VeilAnonymizer
from guardrails import Guard

# Create validator
anonymizer = VeilAnonymizer(
    profile="paranoid",
    replacement_mode="token",
)

# Create guard
guard = Guard().use(anonymizer)

# Always anonymizes
result = guard.validate("John Smith, SSN 123-45-6789")
print(result.validated_output)
# "[PERSON_1], SSN [SSN_1]"
```

#### Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `profile` | Detection profile | balanced |
| `detection_mode` | Detection mode: standard, hybrid | hybrid |
| `replacement_mode` | Replacement mode: token, faker, semantic | token |

## Convenience Function

Use `create_veil_guard` for quick setup:

```python
from veil.integrations.guardrails import create_veil_guard

# Create a guard with Veil PII detection
guard = create_veil_guard(
    profile="paranoid",
    on_fail="fix",
)

# Use the guard
result = guard.validate("My SSN is 123-45-6789")
```

## Use Cases

### Input Validation

Validate user input before sending to LLM:

```python
from veil.integrations.guardrails import create_veil_guard

guard = create_veil_guard(on_fail="fix")

def chat(user_input):
    # Validate and anonymize input
    result = guard.validate(user_input)
    safe_input = result.validated_output

    # Send to LLM
    response = llm.chat(safe_input)
    return response
```

### Output Validation

Ensure LLM outputs don't contain PII:

```python
guard = create_veil_guard(
    profile="paranoid",
    on_fail="exception",
)

def get_response(prompt):
    response = llm.chat(prompt)

    # Validate output
    try:
        result = guard.validate(response)
        return result.validated_output
    except Exception:
        return "Response contained PII and was blocked."
```

### Pipeline Integration

Use in Guardrails pipelines with other validators:

```python
from guardrails import Guard
from guardrails.hub import ToxicLanguage
from veil.integrations.guardrails import VeilPIIValidator

guard = Guard().use_many(
    VeilPIIValidator(on_fail="fix"),
    ToxicLanguage(on_fail="filter"),
)

result = guard.validate(text)
```

## Combining with LLM Calls

```python
from guardrails import Guard
from veil.integrations.guardrails import VeilPIIValidator, VeilAnonymizer

# Input guard (anonymize before LLM)
input_guard = Guard().use(VeilAnonymizer(profile="balanced"))

# Output guard (check for PII leaks)
output_guard = Guard().use(VeilPIIValidator(on_fail="fix"))

def safe_chat(user_input):
    # Anonymize input
    anon_input = input_guard.validate(user_input).validated_output

    # Call LLM with anonymized input
    response = llm.chat(anon_input)

    # Check output for any PII
    safe_output = output_guard.validate(response).validated_output

    return safe_output
```

## Advanced Configuration

### Custom Pipeline Options

```python
from veil.integrations.guardrails import VeilPIIValidator

validator = VeilPIIValidator(
    profile="paranoid",
    detection_mode="hybrid",  # Use all detectors
    use_presidio=True,         # Enable Presidio
    min_entities=2,            # Only fail if 2+ entities
    on_fail="fix",
)
```

### Accessing Detection Results

```python
from veil.integrations.guardrails import VeilPIIValidator
from guardrails import Guard

validator = VeilPIIValidator(on_fail="fix")
guard = Guard().use(validator)

result = guard.validate("John Smith, john@example.com")

# Access validation details
print(result.validation_passed)
print(result.validated_output)
print(result.error)  # If validation failed
```

## Best Practices

1. **Use `on_fail="fix"`** for seamless anonymization
2. **Use paranoid profile** for sensitive applications
3. **Combine with other validators** for comprehensive protection
4. **Validate both input and output** for complete coverage
5. **Log validation results** for audit trails
