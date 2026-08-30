"""Bidirectional mapping store for tracking original <-> replacement mappings."""

import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from veil.detection.entity import Entity, EntityType

_TITLE_RE = re.compile(
    r"^(?:mr|mrs|ms|miss|mx|dr|prof|professor|sir|dame|rev|fr|sr|jr|hon)\.?\s+",
    re.IGNORECASE,
)
_POSSESSIVE_RE = re.compile(r"(?:'s|’s|')$")
_WS_RE = re.compile(r"\s+")

# Matches anything that looks like one of our replacement tokens, in any
# bracket style, so text that already contains "[PERSON_1]" never collides
# with a token we generate.
TOKEN_LIKE_RE = re.compile(
    r"[\[<{]\s*(?P<btype>[A-Za-z][A-Za-z_ ]{1,30}?)[\s_-]*(?P<bnum>\d{1,6})\s*[\]>}]"
    r"|(?<![A-Za-z0-9_])(?P<type>[A-Z][A-Z_]{2,30}?)_(?P<num>\d{1,6})(?![A-Za-z0-9_])"
)


def token_identity(text: str) -> tuple[str, int] | None:
    """Normalise a token-shaped string to ``(TYPE, number)``.

    ``"[EMAIL 2]"``, ``"{email_2}"`` and ``"EMAIL_2"`` all give ``("EMAIL", 2)``,
    which is the identity tolerant reconstruction matches on.
    """
    m = TOKEN_LIKE_RE.fullmatch(text.strip())
    if not m:
        return None
    raw_type = m.group("btype") or m.group("type")
    number = m.group("bnum") or m.group("num")
    type_key = re.sub(r"[\s_]+", "_", raw_type.strip()).upper()
    return type_key, int(number)


def token_spans(text: str) -> list[tuple[int, int]]:
    """Character spans of everything in ``text`` that already looks like a token."""
    return [(m.start(), m.end()) for m in TOKEN_LIKE_RE.finditer(text)]


# NER labels a bare surname as any of these
_SURNAME_CONFUSABLE_TYPES = frozenset({EntityType.ORG, EntityType.GPE, EntityType.LOC})


def normalize_original(text: str, entity_type: EntityType | None = None) -> str:
    """Canonical lookup key for an original value.

    Casefolds, collapses whitespace, and for people strips honorifics and a
    trailing possessive, so "Dr. John Smith", "john smith" and "John Smith's"
    all resolve to the same mapping.
    """
    key = _WS_RE.sub(" ", text.strip())
    if entity_type in (EntityType.PERSON, None):
        key = _TITLE_RE.sub("", key)
        key = _POSSESSIVE_RE.sub("", key)
    return key.casefold()


@dataclass
class MappingEntry:
    """A single mapping entry between original and replacement text.

    Attributes:
        original: Original sensitive text
        replacement: Anonymized replacement text
        entity_type: Type of entity
        entity: The full Entity object (for metadata)
        count: Number of times this entity appeared in text
        aliases: Other surface forms that map to the same replacement
            (e.g. "Smith" and "john smith" for the entry "John Smith")
    """

    original: str
    replacement: str
    entity_type: EntityType
    entity: Entity | None = None
    count: int = 1
    aliases: list[str] = field(default_factory=list)


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
        # _forward is keyed by normalize_original(); see get_entry
        self._forward: dict[str, MappingEntry] = {}
        self._reverse: dict[str, MappingEntry] = {}
        self._by_type: dict[EntityType, list[MappingEntry]] = {}
        self._entries: list[MappingEntry] = []
        # Replacement strings that must never be generated because something
        # tolerant reconstruction would match already occurs in the input.
        # Stored as exact strings and as normalised token identities.
        self._blocked: set[str] = set()
        self._blocked_ids: set[tuple[str, int]] = set()
        self._lock = threading.RLock()

    def add(
        self,
        original: str,
        replacement: str,
        entity_type: EntityType,
        entity: Entity | None = None,
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
        key = normalize_original(original, entity_type)
        with self._lock:
            # Check if we already have this original (or a variant of it)
            existing = self._forward.get(key)
            if existing is not None:
                existing.count += 1
                return existing

            # Same replacement already issued (partial-name match): register
            # this surface form as an alias; the canonical original is kept
            # so reconstruction restores the fullest form.
            existing = self._reverse.get(replacement)
            if existing is not None:
                existing.count += 1
                existing.aliases.append(original)
                self._forward[key] = existing
                return existing

            entry = MappingEntry(
                original=original,
                replacement=replacement,
                entity_type=entity_type,
                entity=entity,
            )
            self._forward[key] = entry
            self._reverse[replacement] = entry
            self._by_type.setdefault(entity_type, []).append(entry)
            self._entries.append(entry)
            return entry

    def block(self, replacements: set[str]) -> None:
        """Forbid the given strings (and their token identities) as future replacements."""
        with self._lock:
            self._blocked |= replacements
            for r in replacements:
                ident = token_identity(r)
                if ident:
                    self._blocked_ids.add(ident)

    def block_tokens_in(self, text: str) -> None:
        """Forbid any token-like strings already present in ``text``."""
        found = {text[s:e] for s, e in token_spans(text)}
        if found:
            self.block(found)

    def is_blocked(self, replacement: str) -> bool:
        """Whether a replacement string is forbidden or already in use."""
        if replacement in self._blocked or replacement in self._reverse:
            return True
        ident = token_identity(replacement)
        return ident is not None and ident in self._blocked_ids

    def find_partial_match(
        self, original: str, entity_type: EntityType
    ) -> MappingEntry | None:
        """Find the entry a shorter surface form refers to.

        "Smith" after "John Smith" has been mapped resolves to that entry when
        exactly one PERSON entry contains the token; ambiguous forms return None.

        Args:
            original: Surface form to resolve
            entity_type: Its entity type (only PERSON is resolved)

        Returns:
            The matching entry, or None
        """
        if entity_type != EntityType.PERSON:
            return None
        words = set(normalize_original(original, entity_type).split())
        if not words:
            return None
        with self._lock:
            subset_of = [
                e for e in self._by_type.get(entity_type, [])
                if words < set(normalize_original(e.original, entity_type).split())
            ]
            if len(subset_of) == 1:
                return subset_of[0]
            if subset_of:
                return None
            # The new form is fuller than an existing one ("John Smith" after
            # "Smith"): adopt its token and promote the fuller form to canonical.
            superset_of = [
                e for e in self._by_type.get(entity_type, [])
                if set(normalize_original(e.original, entity_type).split()) < words
            ]
            if len(superset_of) == 1:
                entry = superset_of[0]
                entry.aliases.append(entry.original)
                entry.original = original
                self._forward[normalize_original(original, entity_type)] = entry
                return entry
        return None

    def get_replacement_for(self, original: str, entity_type: EntityType) -> str | None:
        """Replacement for an original, resolving partial names.

        A lone capitalised word that NER labelled ORG/GPE/LOC ("Smith called")
        is still checked against known people: NER labels for bare surnames
        are unreliable, and leaking a second token for the same person is
        worse than a wrong type.
        """
        entry = self._forward.get(normalize_original(original, entity_type))
        if entry is None:
            entry = self.find_partial_match(original, entity_type)
        if (
            entry is None
            and entity_type in _SURNAME_CONFUSABLE_TYPES
            and " " not in original.strip()
        ):
            entry = self.find_partial_match(original, EntityType.PERSON)
        return entry.replacement if entry else None

    def get_replacement(self, original: str) -> str | None:
        """Get the replacement for an original text.

        Args:
            original: Original sensitive text

        Returns:
            Replacement text, or None if not found
        """
        entry = self.get_entry(original)
        return entry.replacement if entry else None

    def get_original(self, replacement: str) -> str | None:
        """Get the original text for a replacement.

        Args:
            replacement: Anonymized replacement text

        Returns:
            Original text, or None if not found
        """
        entry = self._reverse.get(replacement)
        return entry.original if entry else None

    def get_entry(self, original: str) -> MappingEntry | None:
        """Get the full mapping entry for an original text.

        Args:
            original: Original sensitive text

        Returns:
            MappingEntry, or None if not found
        """
        return self._forward.get(normalize_original(original))

    def get_entry_by_replacement(self, replacement: str) -> MappingEntry | None:
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
        return normalize_original(original) in self._forward

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

    def next_token_number(self, entity_type: EntityType, label: str | None = None) -> int:
        """Get the next token number for a given entity type.

        Used for generating sequential tokens like [PERSON_1], [PERSON_2], etc.
        Custom patterns share ``EntityType.CUSTOM`` but each label
        (``[EMPLOYEE_ID_n]``, ``[PROJECT_CODE_n]``) numbers independently.

        Args:
            entity_type: Type of entity
            label: Custom pattern label, if any

        Returns:
            Next available number (1-indexed)
        """
        if label is None:
            return self.count_by_type(entity_type) + 1
        with self._lock:
            same_label = sum(
                1
                for e in self._by_type.get(entity_type, [])
                if e.entity is not None and e.entity.metadata.get("label") == label
            )
        return same_label + 1

    def clear(self) -> None:
        """Clear all mappings."""
        with self._lock:
            self._forward.clear()
            self._reverse.clear()
            self._by_type.clear()
            self._entries.clear()
            self._blocked.clear()
            self._blocked_ids.clear()

    def __len__(self) -> int:
        """Return the number of mappings."""
        return len(self._entries)

    def __iter__(self) -> Iterator[MappingEntry]:
        """Iterate over all mapping entries."""
        with self._lock:
            return iter(list(self._entries))

    def __contains__(self, original: str) -> bool:
        """Check if an original text has a mapping."""
        return normalize_original(original) in self._forward

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
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
    def from_dict(cls, data: dict[str, Any]) -> "MappingStore":
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

    def get_stats(self) -> dict[str, Any]:
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
