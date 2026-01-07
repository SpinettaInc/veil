# Architecture

This document describes the internal architecture of Veil.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        VeilPipeline                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Detector   │  │   Scorer    │  │   ReplacementEngine     │ │
│  │             │  │             │  │                         │ │
│  │ ┌─────────┐ │  │  Weighting  │  │  ┌─────────────────┐   │ │
│  │ │  NER    │ │  │  + Context  │  │  │ TokenReplacer   │   │ │
│  │ ├─────────┤ │  │  + Rarity   │  │  ├─────────────────┤   │ │
│  │ │ Pattern │ │  │             │  │  │ FakerReplacer   │   │ │
│  │ ├─────────┤ │  │             │  │  ├─────────────────┤   │ │
│  │ │Presidio │ │  │             │  │  │SemanticReplacer │   │ │
│  │ └─────────┘ │  │             │  │  └─────────────────┘   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    MappingStore                          │   │
│  │           Original ←→ Replacement Mappings               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### VeilPipeline

The main orchestrator that coordinates all components.

**Responsibilities:**

- Initialize detection, scoring, and replacement components
- Orchestrate the anonymization flow
- Manage the mapping store
- Handle reconstruction

**Key Methods:**

- `anonymize(text)` - Main anonymization entry point
- `reconstruct(text)` - Restore original values
- `score_entities(text)` - Get detailed scoring
- `clear_mappings()` - Reset session

### Detection Layer

#### EntityDetector

Orchestrates multiple detection sources.

```python
class EntityDetector:
    def __init__(self, use_ner, use_patterns, use_presidio, mode):
        if mode == "hybrid":
            self.hybrid_detector = HybridDetector(...)
        else:
            self.ner_detector = NERDetector(...)
            self.pattern_detector = PatternDetector(...)
```

#### NERDetector

Uses spaCy for Named Entity Recognition.

- Loads spaCy model (`en_core_web_sm` by default)
- Maps spaCy labels to Veil EntityTypes
- Includes false positive filtering

#### PatternDetector

Uses compiled regex patterns for structured data.

- Pre-compiled patterns for performance
- Validation (e.g., Luhn check for credit cards)
- High precision for structured formats

#### PresidioDetector

Wraps Microsoft Presidio for additional PII detection.

- Uses Presidio's AnalyzerEngine
- Maps Presidio types to Veil EntityTypes
- Configurable recognizers

#### HybridDetector

Ensemble approach combining all detectors.

```python
class HybridDetector:
    AGREEMENT_BOOST = 0.15

    def detect(self, text):
        # Collect from all sources
        # Merge overlapping entities
        # Apply agreement boosting
        # Return deduplicated list
```

### Scoring Layer

#### PrivacyScorer

Calculates privacy scores for entities.

```
Score = BaseScore + ContextBoost + RarityBoost
```

Components:

1. **BaseScore**: From profile configuration per entity type
2. **ContextBoost**: Added when sensitive keywords detected
3. **RarityBoost**: Added for unique/rare values (TF-IDF)

#### ContextAnalyzer

Detects sensitive context patterns.

```python
CONTEXT_PATTERNS = {
    "medical": ["patient", "diagnosis", "prescription", ...],
    "financial": ["account", "balance", "transaction", ...],
    "legal": ["plaintiff", "defendant", "court", ...],
}
```

#### TFIDFAnalyzer

Calculates term rarity using TF-IDF.

- Rare names get higher scores
- Common words get lower scores

### Replacement Layer

#### ReplacementEngine

Factory for replacers based on mode.

```python
class ReplacementEngine:
    def __init__(self, mode):
        if mode == "token":
            self.replacer = TokenReplacer()
        elif mode == "faker":
            self.replacer = FakerReplacer()
        elif mode == "semantic":
            self.replacer = SemanticReplacer()
```

#### TokenReplacer

Generates typed, numbered tokens.

```
John Smith → [PERSON_1]
jane@email.com → [EMAIL_1]
Another Person → [PERSON_2]
```

#### FakerReplacer

Generates realistic fake values.

```
John Smith → Michael Johnson
jane@email.com → sarah.wilson@example.com
```

#### SemanticReplacer

Generates semantically similar values.

```
Google → Microsoft
John → James
New York → Los Angeles
```

### Storage Layer

#### MappingStore

Bidirectional mapping storage.

```python
class MappingEntry:
    original: str
    replacement: str
    entity_type: EntityType

class MappingStore:
    _forward: dict[str, MappingEntry]   # original → entry
    _reverse: dict[str, MappingEntry]   # replacement → entry
```

Features:

- O(1) lookup in both directions
- Serializable to JSON
- Session-scoped (no persistence by default)

## Data Flow

### Anonymization Flow

```
1. Input: "John Smith, john@example.com"
           │
           ▼
2. Detection: [Entity(John Smith, PERSON), Entity(john@example.com, EMAIL)]
           │
           ▼
3. Scoring: [Score(John Smith, 0.85), Score(john@example.com, 0.95)]
           │
           ▼
4. Filtering: Entities above threshold
           │
           ▼
5. Replacement: Generate tokens/fakes
           │
           ▼
6. Mapping: Store original ←→ replacement
           │
           ▼
7. Output: "[PERSON_1], [EMAIL_1]"
```

### Reconstruction Flow

```
1. Input: "Hello [PERSON_1], sent to [EMAIL_1]"
           │
           ▼
2. Token Detection: Find all [TYPE_N] patterns
           │
           ▼
3. Mapping Lookup: [PERSON_1] → "John Smith"
           │
           ▼
4. String Replacement: Replace tokens with originals
           │
           ▼
5. Output: "Hello John Smith, sent to john@example.com"
```

## Configuration

### Detection Profiles

```python
PROFILES = {
    "paranoid": {
        "threshold": 0.3,
        "base_scores": {...},
        "context_patterns": [...],
    },
    "balanced": {
        "threshold": 0.5,
        ...
    },
    "minimal": {
        "threshold": 0.7,
        ...
    },
}
```

## Extension Points

### Adding Entity Types

1. Add to `EntityType` enum
2. Add patterns to `PatternDetector`
3. Add mapping to `FakerReplacer`
4. Add base scores to profiles

### Adding Detectors

1. Implement detector with `detect(text) -> list[Entity]`
2. Add to `HybridDetector` sources
3. Update `EntityDetector` initialization

### Adding Replacement Modes

1. Create replacer class with `replace(entity) -> str`
2. Add to `ReplacementEngine` factory
3. Add to CLI and config options
