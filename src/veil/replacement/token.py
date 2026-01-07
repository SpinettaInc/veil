"""Token-based replacement strategy for anonymizing entities."""

from typing import Protocol

from veil.core.mapper import MappingStore
from veil.detection.entity import Entity, EntityType


class ReplacementStrategy(Protocol):
    """Protocol for replacement strategies."""

    def generate_replacement(
        self,
        entity: Entity,
        mapping_store: MappingStore,
    ) -> str:
        """Generate a replacement for an entity.

        Args:
            entity: The entity to replace
            mapping_store: Store for tracking mappings

        Returns:
            Replacement string
        """
        ...


class TokenReplacer:
    """Token-based replacement strategy.

    Generates replacements in the format [TYPE_N] where:
    - TYPE is the entity type (e.g., PERSON, ORG)
    - N is a sequential number for that type

    Examples:
        - "John Smith" -> "[PERSON_1]"
        - "Acme Corp" -> "[ORG_1]"
        - "Jane Doe" -> "[PERSON_2]"

    Attributes:
        bracket_style: Style of brackets to use
        include_type: Whether to include entity type in token
    """

    def __init__(
        self,
        bracket_style: str = "square",  # "square", "angle", "curly"
        include_type: bool = True,
        uppercase: bool = True,
    ) -> None:
        """Initialize the token replacer.

        Args:
            bracket_style: Style of brackets ("square", "angle", "curly")
            include_type: Whether to include entity type in replacement
            uppercase: Whether to uppercase the type name
        """
        self.include_type = include_type
        self.uppercase = uppercase

        # Set bracket characters
        if bracket_style == "square":
            self.open_bracket = "["
            self.close_bracket = "]"
        elif bracket_style == "angle":
            self.open_bracket = "<"
            self.close_bracket = ">"
        elif bracket_style == "curly":
            self.open_bracket = "{"
            self.close_bracket = "}"
        else:
            raise ValueError(f"Unknown bracket style: {bracket_style}")

    def generate_replacement(
        self,
        entity: Entity,
        mapping_store: MappingStore,
    ) -> str:
        """Generate a token replacement for an entity.

        If the entity's original text already has a mapping, returns
        the existing replacement. Otherwise, generates a new token.

        Args:
            entity: The entity to replace
            mapping_store: Store for tracking mappings

        Returns:
            Token replacement string (e.g., "[PERSON_1]")
        """
        # Check if we already have a mapping for this text
        existing = mapping_store.get_replacement(entity.text)
        if existing:
            return existing

        # Generate new token
        token = self._format_token(entity.entity_type, mapping_store)

        return token

    def _format_token(
        self,
        entity_type: EntityType,
        mapping_store: MappingStore,
    ) -> str:
        """Format a token for an entity type.

        Args:
            entity_type: Type of entity
            mapping_store: Store to get next number from

        Returns:
            Formatted token string
        """
        number = mapping_store.next_token_number(entity_type)

        if self.include_type:
            type_name = entity_type.value
            if self.uppercase:
                type_name = type_name.upper()
            token_content = f"{type_name}_{number}"
        else:
            token_content = str(number)

        return f"{self.open_bracket}{token_content}{self.close_bracket}"

    def is_token(self, text: str) -> bool:
        """Check if text looks like a generated token.

        Args:
            text: Text to check

        Returns:
            True if text matches token pattern
        """
        if not text:
            return False

        return (
            text.startswith(self.open_bracket)
            and text.endswith(self.close_bracket)
            and "_" in text
        )

    def parse_token(self, token: str) -> tuple[str, int] | None:
        """Parse a token to extract type and number.

        Args:
            token: Token string to parse

        Returns:
            Tuple of (type_name, number) or None if invalid
        """
        if not self.is_token(token):
            return None

        # Remove brackets
        content = token[len(self.open_bracket):-len(self.close_bracket)]

        # Split on underscore
        parts = content.rsplit("_", 1)
        if len(parts) != 2:
            return None

        type_name, number_str = parts

        try:
            number = int(number_str)
        except ValueError:
            return None

        return (type_name, number)


class AnonymizationResult:
    """Result of anonymizing text.

    Attributes:
        original_text: The original input text
        anonymized_text: The anonymized output text
        entities: List of detected entities
        mapping_store: Store with all mappings used
    """

    def __init__(
        self,
        original_text: str,
        anonymized_text: str,
        entities: list[Entity],
        mapping_store: MappingStore,
    ) -> None:
        """Initialize the result.

        Args:
            original_text: Original input text
            anonymized_text: Anonymized output text
            entities: Detected entities
            mapping_store: Mapping store used
        """
        self.original_text = original_text
        self.anonymized_text = anonymized_text
        self.entities = entities
        self.mapping_store = mapping_store

    @property
    def entity_count(self) -> int:
        """Number of entities detected."""
        return len(self.entities)

    @property
    def replacements(self) -> dict[str, str]:
        """Dictionary of original -> replacement mappings."""
        return {
            entry.original: entry.replacement
            for entry in self.mapping_store
        }

    def __repr__(self) -> str:
        return (
            f"AnonymizationResult(entities={self.entity_count}, "
            f"mappings={len(self.mapping_store)})"
        )


def apply_replacements(
    text: str,
    entities: list[Entity],
    replacer: TokenReplacer,
    mapping_store: MappingStore,
) -> str:
    """Apply replacements to text for detected entities.

    Replaces entities in reverse order (from end to start) to preserve
    character positions as we modify the text.

    Args:
        text: Original text
        entities: List of entities to replace (sorted by position)
        replacer: Replacement strategy to use
        mapping_store: Store for tracking mappings

    Returns:
        Text with entities replaced
    """
    if not entities:
        return text

    # Sort entities by start position (descending) to replace from end
    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)

    result = text
    for entity in sorted_entities:
        # Generate or get existing replacement
        replacement = replacer.generate_replacement(entity, mapping_store)

        # Add to mapping store if new
        if not mapping_store.has_original(entity.text):
            mapping_store.add(
                original=entity.text,
                replacement=replacement,
                entity_type=entity.entity_type,
                entity=entity,
            )

        # Replace in text
        result = result[:entity.start] + replacement + result[entity.end:]

    return result
