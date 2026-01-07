"""Bidirectional mapping store for tracking original <-> replacement mappings."""

from dataclasses import dataclass, field
from typing import Iterator, Optional

from veil.detection.entity import Entity, EntityType


@dataclass
class MappingEntry:
    """A single mapping entry between original and replacement text.

    Attributes:
        original: Original sensitive text
        replacement: Anonymized replacement text
        entity_type: Type of entity
        entity: The full Entity object (for metadata)
        count: Number of times this entity appeared in text
    """

    original: str
    replacement: str
    entity_type: EntityType
    entity: Optional[Entity] = None
    count: int = 1


class MappingStore:
    """Bidirectional mapping store for anonymization.

    Tracks mappings between original sensitive text and their replacements,
    allowing both forward (anonymize) and reverse (deanonymize) lookups.

    This store is session-scoped by default - mappings are kept in memory
    and discarded when the session ends.

    Attributes:
        _forward: Maps original text -> replacement
        _reverse: Maps replacement -> original
        _by_type: Maps entity type -> list of mapping entries
        _entries: All mapping entries
    """

    def __init__(self) -> None:
        """Initialize an empty mapping store."""
        self._forward: dict[str, MappingEntry] = {}
        self._reverse: dict[str, MappingEntry] = {}
        self._by_type: dict[EntityType, list[MappingEntry]] = {}
        self._entries: list[MappingEntry] = []

    def add(
        self,
        original: str,
        replacement: str,
        entity_type: EntityType,
        entity: Optional[Entity] = None,
    ) -> MappingEntry:
        """Add a new mapping.

        If the original text already exists, increments the count
        instead of creating a duplicate.

        Args:
            original: Original sensitive text
            replacement: Anonymized replacement
            entity_type: Type of entity
            entity: Full Entity object (optional)

        Returns:
            The created or existing MappingEntry
        """
        # Check if we already have this original
        if original in self._forward:
            existing = self._forward[original]
            existing.count += 1
            return existing

        # Create new entry
        entry = MappingEntry(
            original=original,
            replacement=replacement,
            entity_type=entity_type,
            entity=entity,
        )

        # Add to forward and reverse lookups
        self._forward[original] = entry
        self._reverse[replacement] = entry

        # Add to by-type index
        if entity_type not in self._by_type:
            self._by_type[entity_type] = []
        self._by_type[entity_type].append(entry)

        self._entries.append(entry)
        return entry

    def get_replacement(self, original: str) -> Optional[str]:
        """Get the replacement for an original text.

        Args:
            original: Original sensitive text

        Returns:
            Replacement text, or None if not found
        """
        entry = self._forward.get(original)
        return entry.replacement if entry else None

    def get_original(self, replacement: str) -> Optional[str]:
        """Get the original text for a replacement.

        Args:
            replacement: Anonymized replacement text

        Returns:
            Original text, or None if not found
        """
        entry = self._reverse.get(replacement)
        return entry.original if entry else None

    def get_entry(self, original: str) -> Optional[MappingEntry]:
        """Get the full mapping entry for an original text.

        Args:
            original: Original sensitive text

        Returns:
            MappingEntry, or None if not found
        """
        return self._forward.get(original)

    def get_entry_by_replacement(self, replacement: str) -> Optional[MappingEntry]:
        """Get the full mapping entry for a replacement.

        Args:
            replacement: Anonymized replacement text

        Returns:
            MappingEntry, or None if not found
        """
        return self._reverse.get(replacement)

    def get_by_type(self, entity_type: EntityType) -> list[MappingEntry]:
        """Get all mappings of a specific entity type.

        Args:
            entity_type: Type of entities to retrieve

        Returns:
            List of mapping entries
        """
        return self._by_type.get(entity_type, [])

    def has_original(self, original: str) -> bool:
        """Check if an original text has a mapping.

        Args:
            original: Original text to check

        Returns:
            True if mapping exists
        """
        return original in self._forward

    def has_replacement(self, replacement: str) -> bool:
        """Check if a replacement text exists.

        Args:
            replacement: Replacement text to check

        Returns:
            True if mapping exists
        """
        return replacement in self._reverse

    def count_by_type(self, entity_type: EntityType) -> int:
        """Count mappings of a specific entity type.

        Args:
            entity_type: Type of entities to count

        Returns:
            Number of mappings
        """
        return len(self._by_type.get(entity_type, []))

    def next_token_number(self, entity_type: EntityType) -> int:
        """Get the next token number for a given entity type.

        Used for generating sequential tokens like [PERSON_1], [PERSON_2], etc.

        Args:
            entity_type: Type of entity

        Returns:
            Next available number (1-indexed)
        """
        return self.count_by_type(entity_type) + 1

    def clear(self) -> None:
        """Clear all mappings."""
        self._forward.clear()
        self._reverse.clear()
        self._by_type.clear()
        self._entries.clear()

    def __len__(self) -> int:
        """Return the number of mappings."""
        return len(self._entries)

    def __iter__(self) -> Iterator[MappingEntry]:
        """Iterate over all mapping entries."""
        return iter(self._entries)

    def __contains__(self, original: str) -> bool:
        """Check if an original text has a mapping."""
        return original in self._forward

    def to_dict(self) -> dict[str, dict]:
        """Export mappings to a dictionary.

        Returns:
            Dictionary with mapping data
        """
        return {
            "mappings": [
                {
                    "original": entry.original,
                    "replacement": entry.replacement,
                    "entity_type": entry.entity_type.value,
                    "count": entry.count,
                }
                for entry in self._entries
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MappingStore":
        """Create a MappingStore from a dictionary.

        Args:
            data: Dictionary with mapping data

        Returns:
            New MappingStore instance
        """
        store = cls()
        for mapping in data.get("mappings", []):
            entry = store.add(
                original=mapping["original"],
                replacement=mapping["replacement"],
                entity_type=EntityType(mapping["entity_type"]),
            )
            entry.count = mapping.get("count", 1)
        return store

    def get_stats(self) -> dict:
        """Get statistics about the mapping store.

        Returns:
            Dictionary with statistics
        """
        type_counts = {
            entity_type.value: len(entries)
            for entity_type, entries in self._by_type.items()
        }

        return {
            "total_mappings": len(self),
            "by_type": type_counts,
            "unique_originals": len(self._forward),
            "unique_replacements": len(self._reverse),
        }

    def __repr__(self) -> str:
        return f"MappingStore(mappings={len(self)})"
