"""Weight configuration for semantic privacy scoring."""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from veil.detection.entity import EntityType

# Card networks, big tech, common SaaS: mentioning them is not PII.
DEFAULT_PUBLIC_ENTITIES: frozenset[str] = frozenset(
    s.casefold()
    for s in (
        "Amex", "American Express", "Visa", "Mastercard", "Discover", "JCB", "PayPal", "Stripe",
        "Google", "Alphabet", "Microsoft", "Apple", "Amazon", "AWS", "Meta", "Facebook",
        "Instagram", "WhatsApp", "Twitter", "LinkedIn", "YouTube", "Netflix", "Spotify",
        "OpenAI", "Anthropic", "IBM", "Oracle", "SAP", "Salesforce", "Adobe", "Intel",
        "Nvidia", "AMD", "Samsung", "Sony", "Uber", "Airbnb", "Slack", "Zoom", "GitHub",
        "GitLab", "Atlassian", "Jira", "Dropbox", "Shopify", "Cloudflare", "Reddit",
        "Windows", "Linux", "Android", "iOS", "Chrome", "Firefox", "Excel", "Outlook",
        "Gmail", "Python", "Java", "JavaScript", "Docker", "Kubernetes",
    )
)


class DetectionProfile(str, Enum):
    """Pre-configured detection sensitivity profiles."""

    PARANOID = "paranoid"  # Maximum detection, may over-detect
    BALANCED = "balanced"  # Good tradeoff (default)
    MINIMAL = "minimal"  # Only high-confidence PII


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

    # Extra regex detectors from a profile file (see pattern_from_dict)
    custom_patterns: list[dict[str, Any]] = field(default_factory=list)

    # Weights for custom pattern labels (entities of type CUSTOM carry the
    # label in metadata["label"])
    custom_weights: dict[str, float] = field(default_factory=dict)

    # Well-known brands / vendors: naming them identifies nobody. ORG/PRODUCT
    # spans matching (casefolded) get ``public_entity_weight`` instead of the
    # type weight. Profiles may extend the list; paranoid still catches them.
    public_entities: set[str] = field(default_factory=lambda: set(DEFAULT_PUBLIC_ENTITIES))
    public_entity_weight: float = 0.3

    # Where the config came from (profile name or file path), for diagnostics
    source: str = "defaults"

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
            EntityType.TIME: 0.30,
            # Financial - moderate to high
            EntityType.MONEY: 0.30,
            EntityType.PERCENT: 0.15,
            EntityType.CARDINAL: 0.15,
            EntityType.ORDINAL: 0.10,
            EntityType.QUANTITY: 0.20,
            # Other named entities
            EntityType.PRODUCT: 0.35,
            EntityType.EVENT: 0.35,
            EntityType.WORK_OF_ART: 0.35,
            EntityType.NORP: 0.45,
            EntityType.LANGUAGE: 0.30,
            EntityType.LAW: 0.30,
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
            "ADP": 0.1,  # Prepositions
            "AUX": 0.1,  # Auxiliary verbs
            "CCONJ": 0.1,  # Coordinating conjunctions
            "DET": 0.1,  # Determiners
            "PART": 0.1,  # Particles
            "PRON": 0.2,  # Pronouns
            "SCONJ": 0.1,  # Subordinating conjunctions
            # Punctuation/symbols
            "PUNCT": 0.0,
            "SYM": 0.2,
            "X": 0.3,  # Other
        }

    @staticmethod
    def _default_context_patterns() -> list[ContextPattern]:
        """Default context patterns that boost sensitivity."""
        return [
            # Executive/leadership roles
            ContextPattern.from_string(
                r"\b(?:CEO|CTO|CFO|COO|President|Chairman)\s+(?:of\s+)?",
                0.15,
                "Executive role context",
            ),
            ContextPattern.from_string(
                r"\b(?:founder|director|manager|executive)\s+(?:of\s+)?",
                0.10,
                "Leadership role context",
            ),
            # Medical/Health context
            ContextPattern.from_string(
                r"\bpatient\s+(?:named?|called|is|was)?\s*", 0.20, "Patient reference"
            ),
            ContextPattern.from_string(
                r"\bdiagnos(?:ed|is)\s+(?:with\s+)?", 0.20, "Diagnosis context"
            ),
            ContextPattern.from_string(r"\bmedical\s+record", 0.15, "Medical record context"),
            ContextPattern.from_string(
                r"\bhealth\s+(?:insurance|plan|condition)", 0.15, "Health-related context"
            ),
            # Financial context
            ContextPattern.from_string(
                r"\baccount\s*(?:number|#|no\.?)?", 0.20, "Account number context"
            ),
            ContextPattern.from_string(r"\bsocial\s*security", 0.25, "Social security context"),
            ContextPattern.from_string(r"\b(?:credit|debit)\s*card", 0.15, "Credit card context"),
            ContextPattern.from_string(
                r"\bbank\s+(?:account|routing)", 0.20, "Bank account context"
            ),
            # Personal information context
            ContextPattern.from_string(r"\bborn\s+(?:on|in)\s*", 0.15, "Birth date context"),
            ContextPattern.from_string(r"\blives?\s+(?:at|in)\s*", 0.15, "Address context"),
            ContextPattern.from_string(r"\bworks?\s+(?:at|for)\s*", 0.10, "Employment context"),
            ContextPattern.from_string(
                r"\bcontact\s+(?:at|via|:)?\s*", 0.10, "Contact info context"
            ),
            # Identity document context
            ContextPattern.from_string(
                r"\bpassport\s*(?:number|#|no\.?)?", 0.20, "Passport context"
            ),
            ContextPattern.from_string(
                r"\b(?:driver'?s?\s*)?licen[cs]e\s*(?:number|#|no\.?)?", 0.20, "License context"
            ),
            # Possessive patterns (my, his, her + sensitive noun)
            ContextPattern.from_string(
                r"\b(?:my|his|her|their)\s+(?:name|email|phone|address|ssn)",
                0.15,
                "Possessive personal info",
            ),
        ]

    def get_entity_weight(
        self, entity_type: EntityType, label: "str | None" = None, text: "str | None" = None
    ) -> float:
        """Get the base weight for an entity type (or a custom pattern label / public brand)."""
        if entity_type == EntityType.CUSTOM and label and label in self.custom_weights:
            return self.custom_weights[label]
        if (
            text is not None
            and entity_type in (EntityType.ORG, EntityType.PRODUCT)
            and text.strip().casefold() in self.public_entities
        ):
            return self.public_entity_weight
        return self.entity_weights.get(entity_type, 0.3)

    def get_pos_multiplier(self, pos_tag: str) -> float:
        """Get the multiplier for a POS tag."""
        return self.pos_multipliers.get(pos_tag, 1.0)

    # Pre-configured profiles

    # ---- YAML profiles -------------------------------------------------

    @classmethod
    def from_yaml(cls, path: "str | Path") -> "WeightConfig":
        """Load a profile from a YAML file.

        Recognised keys: ``threshold``, ``rarity_factor``, ``context_window``,
        ``entity_weights`` (EntityType name -> weight), ``pos_multipliers``,
        ``context_patterns`` (list of ``{pattern, boost, description}``) and
        ``custom_patterns`` (see ``veil.detection.patterns.pattern_from_dict``).
        Missing sections fall back to the built-in defaults, so a custom
        profile only needs to list what it changes.
        """
        import yaml  # type: ignore[import-untyped]

        path = Path(path)
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data, source=str(path))

    @classmethod
    def from_dict(cls, data: dict[str, Any], source: str = "dict") -> "WeightConfig":
        """Build a config from a parsed profile mapping (see ``from_yaml``)."""
        custom_patterns = list(data.get("custom_patterns") or [])
        custom_labels = {str(p.get("entity_type", "CUSTOM")).upper() for p in custom_patterns}
        weights: dict[EntityType, float] = {}
        custom_weights: dict[str, float] = {}
        unknown: list[str] = []
        for name, value in (data.get("entity_weights") or {}).items():
            label = str(name).upper()
            try:
                weights[EntityType(label)] = float(value)
            except ValueError:
                if label in custom_labels:
                    custom_weights[label] = float(value)
                else:
                    unknown.append(str(name))
        if unknown:
            raise ValueError(
                f"{source}: unknown entity types in entity_weights: {unknown} "
                "(declare them under custom_patterns first)"
            )

        patterns = [
            ContextPattern.from_string(p["pattern"], float(p["boost"]), p.get("description", ""))
            for p in (data.get("context_patterns") or [])
        ]
        config = cls(
            entity_weights=weights,
            pos_multipliers={
                str(k): float(v) for k, v in (data.get("pos_multipliers") or {}).items()
            },
            context_patterns=patterns,
            threshold=float(data.get("threshold", 0.5)),
            rarity_factor=float(data.get("rarity_factor", 0.1)),
            context_window=int(data.get("context_window", 100)),
            custom_patterns=custom_patterns,
            custom_weights=custom_weights,
            source=source,
        )
        if "public_entities" in data:
            config.public_entities |= {str(s).casefold() for s in data["public_entities"] or []}
        if "public_entity_weight" in data:
            config.public_entity_weight = float(data["public_entity_weight"])
        # A profile may list only the weights it changes; fill the rest in
        if weights:
            for entity_type, default in cls._default_entity_weights().items():
                config.entity_weights.setdefault(entity_type, default)
        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the YAML profile schema (inverse of ``from_dict``)."""
        return {
            "threshold": self.threshold,
            "rarity_factor": self.rarity_factor,
            "context_window": self.context_window,
            "entity_weights": {
                **{t.value: round(w, 3) for t, w in self.entity_weights.items()},
                **self.custom_weights,
            },
            "pos_multipliers": dict(self.pos_multipliers),
            "context_patterns": [
                {"pattern": p.pattern.pattern, "boost": p.boost, "description": p.description}
                for p in self.context_patterns
            ],
            "custom_patterns": list(self.custom_patterns),
        }


PROFILES_DIR = Path(__file__).resolve().parent.parent / "config" / "profiles"


def profile_path(profile: DetectionProfile) -> Path:
    """Location of the YAML file that defines a built-in profile."""
    return PROFILES_DIR / f"{profile.value}.yaml"


def get_paranoid_config() -> WeightConfig:
    """Get paranoid profile - maximum detection sensitivity."""
    config = WeightConfig(threshold=0.3, rarity_factor=0.15)

    # Boost all entity weights
    for entity_type in config.entity_weights:
        config.entity_weights[entity_type] = min(1.0, config.entity_weights[entity_type] + 0.1)

    return config


def get_balanced_config() -> WeightConfig:
    """Get balanced profile - good tradeoff (default)."""
    return WeightConfig(threshold=0.5, rarity_factor=0.1)


def get_minimal_config() -> WeightConfig:
    """Get minimal profile - only high-confidence PII."""
    config = WeightConfig(threshold=0.8, rarity_factor=0.05)

    # Reduce weights for less sensitive types
    low_priority_types = [
        EntityType.DATE,
        EntityType.TIME,
        EntityType.MONEY,
        EntityType.PERCENT,
        EntityType.CARDINAL,
        EntityType.ORDINAL,
        EntityType.PRODUCT,
        EntityType.EVENT,
        EntityType.WORK_OF_ART,
        EntityType.GPE,
        EntityType.LOC,
        EntityType.FAC,
    ]

    for entity_type in low_priority_types:
        if entity_type in config.entity_weights:
            config.entity_weights[entity_type] *= 0.5

    return config


_BUILTIN_CONFIGS = {
    DetectionProfile.PARANOID: get_paranoid_config,
    DetectionProfile.BALANCED: get_balanced_config,
    DetectionProfile.MINIMAL: get_minimal_config,
}


def get_profile_config(profile: DetectionProfile) -> WeightConfig:
    """Get weight configuration for a detection profile.

    The YAML file under ``config/profiles/`` is the source of truth; the
    Python builders above are the fallback if the file is missing and the
    reference used to regenerate it (``python -m veil.weighting.config``).
    """
    path = profile_path(profile)
    if path.exists():
        config = WeightConfig.from_yaml(path)
        config.source = profile.value
        return config
    return _BUILTIN_CONFIGS[profile]()


def load_profile(name_or_path: "str | Path") -> WeightConfig:
    """Resolve a profile name (``balanced``) or a YAML path to a config."""
    text = str(name_or_path)
    try:
        return get_profile_config(DetectionProfile(text.lower()))
    except ValueError:
        pass
    path = Path(text)
    if not path.exists():
        valid = ", ".join(p.value for p in DetectionProfile)
        raise ValueError(f"Unknown profile {text!r}: use one of {valid} or a path to a .yaml file")
    return WeightConfig.from_yaml(path)


def regenerate_profile_files() -> list[Path]:
    """Write the built-in profiles to YAML from the Python definitions."""
    import yaml

    written = []
    for profile, builder in _BUILTIN_CONFIGS.items():
        config = builder()
        header = (
            f"# {profile.value.capitalize()} detection profile.\n"
            "# Source of truth for this profile; loaded by veil.weighting.config.\n"
            "# Regenerate from the Python defaults with: python -m veil.weighting.config\n"
            "# Entity types must be EntityType names; custom_patterns entries take\n"
            "# name, regex, entity_type, confidence, context (list), requires_context.\n"
        )
        body = yaml.safe_dump(
            {"name": profile.value, **config.to_dict()}, sort_keys=False, allow_unicode=True
        )
        path = profile_path(profile)
        path.write_text(header + body, encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in regenerate_profile_files():
        print(f"wrote {p}")
