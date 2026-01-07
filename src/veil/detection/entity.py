"""Entity data model for detected sensitive information."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
    metadata: dict = field(default_factory=dict)

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

    def to_dict(self) -> dict:
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
    def from_dict(cls, data: dict) -> "Entity":
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


def merge_overlapping_entities(entities: list[Entity]) -> list[Entity]:
    """Merge overlapping entities, keeping the one with higher confidence.

    When entities overlap, the one with higher confidence wins.
    If confidences are equal, the longer entity wins.

    Args:
        entities: List of entities to merge

    Returns:
        List of non-overlapping entities
    """
    if not entities:
        return []

    # Sort by start position, then by length (descending)
    sorted_entities = sorted(entities, key=lambda e: (e.start, -(e.end - e.start)))

    merged: list[Entity] = []
    for entity in sorted_entities:
        # Check if this entity overlaps with any already merged entity
        overlap_found = False
        for i, existing in enumerate(merged):
            if entity.overlaps(existing):
                overlap_found = True
                # Keep the one with higher confidence, or longer if tied
                if entity.confidence > existing.confidence or (
                    entity.confidence == existing.confidence
                    and entity.length > existing.length
                ):
                    merged[i] = entity
                break

        if not overlap_found:
            merged.append(entity)

    # Re-sort by position
    return sorted(merged, key=lambda e: e.start)
