"""Weight configuration for semantic privacy scoring."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import re

from veil.detection.entity import EntityType


class DetectionProfile(str, Enum):
    """Pre-configured detection sensitivity profiles."""

    PARANOID = "paranoid"    # Maximum detection, may over-detect
    BALANCED = "balanced"    # Good tradeoff (default)
    MINIMAL = "minimal"      # Only high-confidence PII


@dataclass
class ContextPattern:
    """A context pattern that boosts privacy sensitivity.

    When this pattern is found near an entity, the entity's
    privacy score is boosted by the specified amount.

    Attributes:
        pattern: Compiled regex pattern
        boost: Amount to add to privacy score (0.0 to 0.5 typically)
        description: Human-readable description
    """

    pattern: re.Pattern[str]
    boost: float
    description: str = ""

    @classmethod
    def from_string(cls, pattern_str: str, boost: float, description: str = "") -> "ContextPattern":
        """Create a ContextPattern from a string pattern."""
        return cls(
            pattern=re.compile(pattern_str, re.IGNORECASE),
            boost=boost,
            description=description,
        )


@dataclass
class WeightConfig:
    """Configuration for privacy score weighting.

    This configuration determines how entities are scored for
    privacy sensitivity. Higher scores = more likely to be anonymized.

    Attributes:
        entity_weights: Base weights by entity type (0.0 to 1.0)
        pos_multipliers: Multipliers by part-of-speech tag
        context_patterns: Patterns that boost sensitivity when nearby
        threshold: Minimum score to trigger anonymization
        rarity_factor: How much rarity affects the score (0.0 to 1.0)
    """

    # Base weights by entity type
    entity_weights: dict[EntityType, float] = field(default_factory=dict)

    # POS tag multipliers
    pos_multipliers: dict[str, float] = field(default_factory=dict)

    # Context patterns that boost sensitivity
    context_patterns: list[ContextPattern] = field(default_factory=list)

    # Score threshold for anonymization
    threshold: float = 0.5

    # How much rarity (TF-IDF) affects the score
    rarity_factor: float = 0.1

    # Context window size for pattern matching (characters)
    context_window: int = 100

    def __post_init__(self) -> None:
        """Initialize defaults if empty."""
        if not self.entity_weights:
            self.entity_weights = self._default_entity_weights()
        if not self.pos_multipliers:
            self.pos_multipliers = self._default_pos_multipliers()
        if not self.context_patterns:
            self.context_patterns = self._default_context_patterns()

    @staticmethod
    def _default_entity_weights() -> dict[EntityType, float]:
        """Default weights by entity type."""
        return {
            # Named entities - high sensitivity
            EntityType.PERSON: 0.95,
            EntityType.ORG: 0.85,
            EntityType.GPE: 0.75,
            EntityType.LOC: 0.70,
            EntityType.FAC: 0.70,

            # Pattern-based PII - very high sensitivity
            EntityType.SSN: 1.0,
            EntityType.CREDIT_CARD: 1.0,
            EntityType.EMAIL: 0.90,
            EntityType.PHONE: 0.85,
            EntityType.IP_ADDRESS: 0.80,
            EntityType.PASSPORT: 0.95,
            EntityType.DRIVER_LICENSE: 0.95,
            EntityType.BANK_ACCOUNT: 0.95,
            EntityType.IBAN: 0.95,

            # Medical - high sensitivity (HIPAA)
            EntityType.MEDICAL_RECORD: 1.0,
            EntityType.HEALTH_PLAN: 0.95,
            EntityType.DEVICE_ID: 0.90,

            # Temporal - moderate sensitivity
            EntityType.DATE: 0.60,
            EntityType.TIME: 0.40,

            # Financial - moderate to high
            EntityType.MONEY: 0.65,
            EntityType.PERCENT: 0.30,
            EntityType.CARDINAL: 0.25,
            EntityType.ORDINAL: 0.20,
            EntityType.QUANTITY: 0.30,

            # Other named entities
            EntityType.PRODUCT: 0.50,
            EntityType.EVENT: 0.45,
            EntityType.WORK_OF_ART: 0.35,
            EntityType.NORP: 0.55,
            EntityType.LANGUAGE: 0.30,
            EntityType.LAW: 0.40,
            EntityType.URL: 0.70,
            EntityType.LICENSE_PLATE: 0.85,

            # Fallback
            EntityType.CUSTOM: 0.50,
            EntityType.UNKNOWN: 0.30,
        }

    @staticmethod
    def _default_pos_multipliers() -> dict[str, float]:
        """Default multipliers by part-of-speech tag."""
        return {
            # Proper nouns are most likely to be identifying
            "PROPN": 1.2,

            # Common nouns - baseline
            "NOUN": 1.0,

            # Numbers can be identifying
            "NUM": 0.8,

            # Adjectives sometimes identifying
            "ADJ": 0.6,

            # Verbs rarely identifying
            "VERB": 0.3,

            # Adverbs rarely identifying
            "ADV": 0.3,

            # Function words - very low
            "ADP": 0.1,   # Prepositions
            "AUX": 0.1,   # Auxiliary verbs
            "CCONJ": 0.1, # Coordinating conjunctions
            "DET": 0.1,   # Determiners
            "PART": 0.1,  # Particles
            "PRON": 0.2,  # Pronouns
            "SCONJ": 0.1, # Subordinating conjunctions

            # Punctuation/symbols
            "PUNCT": 0.0,
            "SYM": 0.2,
            "X": 0.3,     # Other
        }

    @staticmethod
    def _default_context_patterns() -> list[ContextPattern]:
        """Default context patterns that boost sensitivity."""
        return [
            # Executive/leadership roles
            ContextPattern.from_string(
                r"\b(?:CEO|CTO|CFO|COO|President|Chairman)\s+(?:of\s+)?",
                0.15,
                "Executive role context"
            ),
            ContextPattern.from_string(
                r"\b(?:founder|director|manager|executive)\s+(?:of\s+)?",
                0.10,
                "Leadership role context"
            ),

            # Medical/Health context
            ContextPattern.from_string(
                r"\bpatient\s+(?:named?|called|is|was)?\s*",
                0.20,
                "Patient reference"
            ),
            ContextPattern.from_string(
                r"\bdiagnos(?:ed|is)\s+(?:with\s+)?",
                0.20,
                "Diagnosis context"
            ),
            ContextPattern.from_string(
                r"\bmedical\s+record",
                0.15,
                "Medical record context"
            ),
            ContextPattern.from_string(
                r"\bhealth\s+(?:insurance|plan|condition)",
                0.15,
                "Health-related context"
            ),

            # Financial context
            ContextPattern.from_string(
                r"\baccount\s*(?:number|#|no\.?)?",
                0.20,
                "Account number context"
            ),
            ContextPattern.from_string(
                r"\bsocial\s*security",
                0.25,
                "Social security context"
            ),
            ContextPattern.from_string(
                r"\b(?:credit|debit)\s*card",
                0.15,
                "Credit card context"
            ),
            ContextPattern.from_string(
                r"\bbank\s+(?:account|routing)",
                0.20,
                "Bank account context"
            ),

            # Personal information context
            ContextPattern.from_string(
                r"\bborn\s+(?:on|in)\s*",
                0.15,
                "Birth date context"
            ),
            ContextPattern.from_string(
                r"\blives?\s+(?:at|in)\s*",
                0.15,
                "Address context"
            ),
            ContextPattern.from_string(
                r"\bworks?\s+(?:at|for)\s*",
                0.10,
                "Employment context"
            ),
            ContextPattern.from_string(
                r"\bcontact\s+(?:at|via|:)?\s*",
                0.10,
                "Contact info context"
            ),

            # Identity document context
            ContextPattern.from_string(
                r"\bpassport\s*(?:number|#|no\.?)?",
                0.20,
                "Passport context"
            ),
            ContextPattern.from_string(
                r"\b(?:driver'?s?\s*)?licen[cs]e\s*(?:number|#|no\.?)?",
                0.20,
                "License context"
            ),

            # Possessive patterns (my, his, her + sensitive noun)
            ContextPattern.from_string(
                r"\b(?:my|his|her|their)\s+(?:name|email|phone|address|ssn)",
                0.15,
                "Possessive personal info"
            ),
        ]

    def get_entity_weight(self, entity_type: EntityType) -> float:
        """Get the base weight for an entity type."""
        return self.entity_weights.get(entity_type, 0.3)

    def get_pos_multiplier(self, pos_tag: str) -> float:
        """Get the multiplier for a POS tag."""
        return self.pos_multipliers.get(pos_tag, 1.0)


# Pre-configured profiles

def get_paranoid_config() -> WeightConfig:
    """Get paranoid profile - maximum detection sensitivity."""
    config = WeightConfig(threshold=0.3, rarity_factor=0.15)

    # Boost all entity weights
    for entity_type in config.entity_weights:
        config.entity_weights[entity_type] = min(
            1.0,
            config.entity_weights[entity_type] + 0.1
        )

    return config


def get_balanced_config() -> WeightConfig:
    """Get balanced profile - good tradeoff (default)."""
    return WeightConfig(threshold=0.5, rarity_factor=0.1)


def get_minimal_config() -> WeightConfig:
    """Get minimal profile - only high-confidence PII."""
    config = WeightConfig(threshold=0.8, rarity_factor=0.05)

    # Reduce weights for less sensitive types
    low_priority_types = [
        EntityType.DATE, EntityType.TIME, EntityType.MONEY,
        EntityType.PERCENT, EntityType.CARDINAL, EntityType.ORDINAL,
        EntityType.PRODUCT, EntityType.EVENT, EntityType.WORK_OF_ART,
        EntityType.GPE, EntityType.LOC, EntityType.FAC,
    ]

    for entity_type in low_priority_types:
        if entity_type in config.entity_weights:
            config.entity_weights[entity_type] *= 0.5

    return config


def get_profile_config(profile: DetectionProfile) -> WeightConfig:
    """Get weight configuration for a detection profile."""
    configs = {
        DetectionProfile.PARANOID: get_paranoid_config,
        DetectionProfile.BALANCED: get_balanced_config,
        DetectionProfile.MINIMAL: get_minimal_config,
    }
    return configs[profile]()
