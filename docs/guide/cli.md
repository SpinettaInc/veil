# CLI Reference

Complete reference for the Veil command-line interface.

## Global Options

```bash
veil [OPTIONS] COMMAND [ARGS]
```

| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Enable verbose output |
| `--help` | Show help message |

## Commands

### anonymize

Anonymize sensitive entities in text.

```bash
veil anonymize [OPTIONS] [TEXT]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TEXT` | Text to anonymize (optional if using --input) |

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--input`, `-i` | Input file to anonymize | - |
| `--output`, `-o` | Output file for anonymized text | - |
| `--mapping`, `-m` | Show the mapping table | False |
| `--profile`, `-p` | Detection profile: paranoid, balanced, minimal | balanced |
| `--mode`, `-r` | Replacement mode: token, faker, semantic | token |
| `--seed` | Random seed for faker mode | - |
| `--hybrid`, `-H` | Use hybrid detection | False |
| `--presidio` | Enable Presidio detection | False |
| `--no-ner` | Disable NER detection | False |
| `--no-patterns` | Disable pattern detection | False |
| `--no-weighting` | Disable semantic weighting | False |
| `--json`, `-j` | Output as JSON | False |

**Examples:**

```bash
# Basic anonymization
veil anonymize "John Smith works at Acme Corp"

# With mapping table
veil anonymize "John Smith, SSN 123-45-6789" --mapping

# File input/output
veil anonymize --input document.txt --output anonymized.txt

# Paranoid profile
veil anonymize "text" --profile paranoid

# Faker replacement
veil anonymize "John Smith" --mode faker

# Hybrid detection
veil anonymize "text" --hybrid

# JSON output
veil anonymize "John Smith" --json

# From stdin
echo "John Smith" | veil anonymize
```

---

### detect

Detect and display sensitive entities without anonymizing.

```bash
veil detect [OPTIONS] TEXT
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TEXT` | Text to analyze |

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--profile`, `-p` | Detection profile | balanced |
| `--hybrid`, `-H` | Use hybrid detection | False |
| `--presidio` | Enable Presidio detection | False |
| `--no-ner` | Disable NER detection | False |
| `--no-patterns` | Disable pattern detection | False |

**Example:**

```bash
veil detect "John Smith, email john@acme.com, SSN 123-45-6789"
```

Output:
```
┏━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Text           ┃ Type   ┃ Position   ┃ Confidence  ┃ Source   ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ John Smith     │ PERSON │ 0:10       │ 0.85        │ ner      │
│ john@acme.com  │ EMAIL  │ 18:31      │ 0.95        │ pattern  │
│ 123-45-6789    │ SSN    │ 37:48      │ 0.95        │ pattern  │
└────────────────┴────────┴────────────┴─────────────┴──────────┘
```

---

### score

Show privacy scores for detected entities.

```bash
veil score [OPTIONS] TEXT
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TEXT` | Text to analyze |

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--profile`, `-p` | Detection profile | balanced |
| `--no-ner` | Disable NER detection | False |
| `--no-patterns` | Disable pattern detection | False |

**Example:**

```bash
veil score "Patient John Smith, SSN 123-45-6789"
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

---

### reconstruct

Reconstruct anonymized text back to original.

```bash
veil reconstruct [OPTIONS] TEXT
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TEXT` | Anonymized text to reconstruct |

**Options:**

| Option | Description |
|--------|-------------|
| `--mapping`, `-m` | JSON file with mappings |

**Example:**

```bash
# Use mapping file
veil reconstruct "[PERSON_1] works at [ORG_1]" --mapping mappings.json

# Use session mappings (after anonymize command)
veil reconstruct "[PERSON_1] works at [ORG_1]"
```

---

### stats

Show statistics about the current pipeline.

```bash
veil stats
```

**Example:**

```bash
veil stats
```

Output:
```
╭────────────────────────────────╮
│ Veil Pipeline Statistics       │
╰────────────────────────────────╯

Detector:
  Mode: standard
  NER enabled: True
  NER model: en_core_web_sm
  Presidio enabled: False
  Patterns enabled: True
  Pattern count: 15

Profile: balanced
  Weighting enabled: True
  Threshold: 0.5
  Rarity factor: 0.1

Replacement:
  Mode: token
  Bracket style: square

Mappings:
  Total mappings: 0
```

---

### app

Launch the Veil desktop app.

```bash
veil app [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--share` | Create a public link | False |
| `--port`, `-p` | Port to run on | 7860 |
| `--host`, `-h` | Host to bind to | 127.0.0.1 |

**Examples:**

```bash
# Default launch
veil app

# Custom port
veil app --port 8080

# Create public link (for sharing)
veil app --share

# Bind to all interfaces
veil app --host 0.0.0.0
```

---

### version

Show Veil version information.

```bash
veil version
```
