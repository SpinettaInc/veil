"""Entity data model for detected sensitive information."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    """Types of sensitive entities that can be detected."""

    # Named entities (from NER)
    PERSON = "PERSON"
    ORG = "ORG"
    GPE = "GPE"  # Geopolitical entity (countries, cities, states)
    LOC = "LOC"  # Non-GPE locations
    FAC = "FAC"  # Facilities (buildings, airports)
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"
    WORK_OF_ART = "WORK_OF_ART"
    DATE = "DATE"
    TIME = "TIME"
    MONEY = "MONEY"
    QUANTITY = "QUANTITY"
    CARDINAL = "CARDINAL"
    ORDINAL = "ORDINAL"
    PERCENT = "PERCENT"
    NORP = "NORP"  # Nationalities, religious, political groups
    LANGUAGE = "LANGUAGE"
    LAW = "LAW"

    # Pattern-based entities (from regex)
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    SSN = "SSN"
    CREDIT_CARD = "CREDIT_CARD"
    IP_ADDRESS = "IP_ADDRESS"
    URL = "URL"
    LICENSE_PLATE = "LICENSE_PLATE"
    PASSPORT = "PASSPORT"
    DRIVER_LICENSE = "DRIVER_LICENSE"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    IBAN = "IBAN"

    # Medical (HIPAA)
    MEDICAL_RECORD = "MEDICAL_RECORD"
    HEALTH_PLAN = "HEALTH_PLAN"
    DEVICE_ID = "DEVICE_ID"

    # Custom/Other
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


@dataclass
class Entity:
    """Represents a detected sensitive entity in text.

    Attributes:
        text: The original text of the entity
        entity_type: The type/category of the entity
        start: Start character position in original text
        end: End character position in original text
        confidence: Detection confidence score (0.0 to 1.0)
        source: Which detector found this entity (e.g., "spacy", "regex")
        context: Surrounding text for context-aware processing
        metadata: Additional information about the entity
    """

    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float = 1.0
    source: str = "unknown"
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate entity after initialization."""
        if self.start < 0:
            raise ValueError("start position cannot be negative")
        if self.end < self.start:
            raise ValueError("end position must be >= start position")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    @property
    def length(self) -> int:
        """Length of the entity text."""
        return self.end - self.start

    def overlaps(self, other: "Entity") -> bool:
        """Check if this entity overlaps with another entity."""
        return not (self.end <= other.start or other.end <= self.start)

    def contains(self, other: "Entity") -> bool:
        """Check if this entity fully contains another entity."""
        return self.start <= other.start and self.end >= other.end

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary representation."""
        return {
            "text": self.text,
            "entity_type": self.entity_type.value,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "source": self.source,
            "context": self.context,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entity":
        """Create entity from dictionary representation."""
        return cls(
            text=data["text"],
            entity_type=EntityType(data["entity_type"]),
            start=data["start"],
            end=data["end"],
            confidence=data.get("confidence", 1.0),
            source=data.get("source", "unknown"),
            context=data.get("context", ""),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"Entity(text={self.text!r}, type={self.entity_type.value}, "
            f"pos=[{self.start}:{self.end}], conf={self.confidence:.2f})"
        )


# Structured, validated PII (regex + checksum) should win over a generic NER
# span covering the same characters; NER numeric/temporal labels are the
# least specific and lose to anything else.
_GENERIC_TYPES: frozenset[EntityType] = frozenset({
    EntityType.CARDINAL, EntityType.ORDINAL, EntityType.QUANTITY,
    EntityType.PERCENT, EntityType.DATE, EntityType.TIME, EntityType.MONEY,
    EntityType.UNKNOWN,
})
_STRUCTURED_TYPES: frozenset[EntityType] = frozenset({
    EntityType.EMAIL, EntityType.PHONE, EntityType.SSN, EntityType.CREDIT_CARD,
    EntityType.IP_ADDRESS, EntityType.URL, EntityType.IBAN, EntityType.PASSPORT,
    EntityType.DRIVER_LICENSE, EntityType.BANK_ACCOUNT, EntityType.MEDICAL_RECORD,
    EntityType.HEALTH_PLAN, EntityType.DEVICE_ID, EntityType.LICENSE_PLATE,
})


def _specificity(entity: Entity) -> int:
    if entity.entity_type in _STRUCTURED_TYPES:
        return 2
    if entity.entity_type in _GENERIC_TYPES:
        return 0
    return 1


def _rank(entity: Entity) -> tuple[int, float, int]:
    return (_specificity(entity), entity.confidence, entity.length)


def merge_overlapping_entities(entities: list[Entity]) -> list[Entity]:
    """Merge overlapping entities into a non-overlapping list.

    When two entities overlap the winner is chosen by, in order:
    type specificity (structured PII > named entity > generic NER label),
    confidence, then span length. Runs in O(n log n): after sorting by
    start position a new entity can only overlap the last kept one.

    Args:
        entities: List of entities to merge

    Returns:
        List of non-overlapping entities sorted by position
    """
    if not entities:
        return []

    sorted_entities = sorted(entities, key=lambda e: (e.start, -(e.end - e.start)))

    merged: list[Entity] = []
    for entity in sorted_entities:
        if merged and entity.overlaps(merged[-1]):
            if _rank(entity) > _rank(merged[-1]):
                merged[-1] = entity
            continue
        merged.append(entity)

    return merged
