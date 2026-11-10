"""Unified replacement engine with strategy selection."""

from enum import Enum
from typing import Any

from veil.core.mapper import MappingStore
from veil.detection.entity import Entity
from veil.replacement.faker_gen import FAKER_AVAILABLE, FakerReplacer
from veil.replacement.semantic import SemanticReplacer
from veil.replacement.token import TokenReplacer


class ReplacementMode(Enum):
    """Available replacement modes.

    Attributes:
        TOKEN: Simple token replacement like [PERSON_1]
        FAKER: Realistic fake data using Faker library
        SEMANTIC: Embedding-based semantically similar replacements
    """
    TOKEN = "token"
    FAKER = "faker"
    SEMANTIC = "semantic"


class ReplacementEngine:
    """Unified replacement engine supporting multiple strategies.

    This engine provides a single interface for all replacement strategies
    and handles strategy selection, initialization, and fallbacks.

    Example:
        >>> engine = ReplacementEngine(mode=ReplacementMode.FAKER)
        >>> result = engine.replace(entity, mapping_store)
        >>> print(result)  # "Michael Johnson" (for PERSON entity)

    Attributes:
        mode: Current replacement mode
        replacer: Active replacer instance
    """

    def __init__(
        self,
        mode: ReplacementMode = ReplacementMode.TOKEN,
        # Token options
        bracket_style: str = "square",
        # Faker options
        faker_locale: str = "en_US",
        faker_seed: int | None = None,
        # Semantic options
        similarity_threshold: float = 0.6,
        use_semantic_fallback: bool = True,
    ) -> None:
        """Initialize the replacement engine.

        Args:
            mode: Replacement mode to use
            bracket_style: Bracket style for token mode
            faker_locale: Locale for faker mode
            faker_seed: Random seed for faker reproducibility
            similarity_threshold: Similarity threshold for semantic mode
            use_semantic_fallback: Use fallback pools in semantic mode

        Raises:
            ImportError: If faker mode selected but faker not installed
        """
        self.mode = mode
        self._bracket_style = bracket_style
        self._faker_locale = faker_locale
        self._faker_seed = faker_seed
        self._similarity_threshold = similarity_threshold
        self._use_semantic_fallback = use_semantic_fallback

        # Initialize appropriate replacer
        self.replacer = self._create_replacer(mode)
        self._fallback = TokenReplacer(bracket_style=bracket_style)

    def _create_replacer(
        self,
        mode: ReplacementMode,
    ) -> TokenReplacer | FakerReplacer | SemanticReplacer:
        """Create replacer for specified mode.

        Args:
            mode: Replacement mode

        Returns:
            Appropriate replacer instance
        """
        if mode == ReplacementMode.TOKEN:
            return TokenReplacer(bracket_style=self._bracket_style)

        elif mode == ReplacementMode.FAKER:
            if not FAKER_AVAILABLE:
                raise ImportError(
                    "Faker library required for faker mode. "
                    "Install with: pip install faker"
                )
            return FakerReplacer(
                locale=self._faker_locale,
                seed=self._faker_seed,
            )

        elif mode == ReplacementMode.SEMANTIC:
            return SemanticReplacer(
                similarity_threshold=self._similarity_threshold,
                use_fallback=self._use_semantic_fallback,
            )

        else:
            raise ValueError(f"Unknown replacement mode: {mode}")

    # Attempts at a non-colliding fake value before falling back to a token
    MAX_ATTEMPTS = 6

    def replace(
        self,
        entity: Entity,
        mapping_store: MappingStore,
        context: str | None = None,
    ) -> str:
        """Replacement for an entity: its existing one, or a newly generated one.

        Args:
            entity: Entity to replace
            mapping_store: Mapping store for tracking
            context: Optional surrounding context (for semantic mode)

        Returns:
            Replacement string
        """
        # Partial names resolve to the same replacement as the full name
        existing = mapping_store.get_replacement_for(entity.text, entity.entity_type)
        return existing or self._generate(entity, mapping_store, context)

    def _generate(
        self, entity: Entity, mapping_store: MappingStore, context: str | None
    ) -> str:
        if context and isinstance(self.replacer, SemanticReplacer):
            return self.replacer.get_context_aware_replacement(entity, context, mapping_store)
        return self.replacer.generate_replacement(entity, mapping_store)

    def _new_replacement(
        self, entity: Entity, text: str, mapping_store: MappingStore, context: str | None
    ) -> str:
        """Generate a replacement that reconstruction can map back unambiguously.

        A fake value is unusable if it is already the replacement of another
        original (both would be restored as that one), occurs in the input,
        or is itself a mapped original. After a few attempts a token is used
        instead: it is ugly in faker/semantic output but always unique.
        """
        for _ in range(self.MAX_ATTEMPTS):
            replacement = self._generate(entity, mapping_store, context)
            if not (
                mapping_store.is_blocked(replacement)
                or replacement in text
                or mapping_store.has_original(replacement)
            ):
                return replacement
            mapping_store.block({replacement})
        return self._fallback.generate_replacement(entity, mapping_store)

    def replace_all(
        self,
        text: str,
        entities: list[Entity],
        mapping_store: MappingStore,
    ) -> str:
        """Apply replacements to text for all entities.

        Args:
            text: Original text
            entities: Entities to replace
            mapping_store: Mapping store for tracking

        Returns:
            Text with all entities replaced
        """
        if not entities:
            return text

        # Decide replacements in reading order so the first (usually fullest)
        # mention of a name defines its token.
        pieces: list[str] = []
        cursor = 0
        for entity in sorted(entities, key=lambda e: e.start):
            replacement = mapping_store.get_replacement_for(entity.text, entity.entity_type)
            if replacement is None:
                context = None
                if self.mode == ReplacementMode.SEMANTIC:
                    context = text[max(0, entity.start - 50) : entity.end + 50]
                replacement = self._new_replacement(entity, text, mapping_store, context)

            # Registers a new entry, or this surface form as an alias
            mapping_store.add(
                original=entity.text,
                replacement=replacement,
                entity_type=entity.entity_type,
                entity=entity,
            )
            pieces.append(text[cursor : entity.start])
            pieces.append(replacement)
            cursor = entity.end
        pieces.append(text[cursor:])
        return "".join(pieces)

    def set_mode(self, mode: ReplacementMode) -> None:
        """Change the replacement mode.

        Args:
            mode: New replacement mode

        Raises:
            ImportError: If faker mode but faker not installed
        """
        if mode != self.mode:
            self.mode = mode
            self.replacer = self._create_replacer(mode)

    def clear_cache(self) -> None:
        """Clear any cached state in the replacer."""
        if isinstance(self.replacer, SemanticReplacer):
            self.replacer.clear_used()

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the replacement engine.

        Returns:
            Dictionary with engine statistics
        """
        stats: dict[str, Any] = {
            "mode": self.mode.value,
            "replacer_type": type(self.replacer).__name__,
        }

        if self.mode == ReplacementMode.TOKEN:
            stats["bracket_style"] = self._bracket_style

        elif self.mode == ReplacementMode.FAKER:
            stats["locale"] = self._faker_locale

        elif self.mode == ReplacementMode.SEMANTIC:
            stats["similarity_threshold"] = self._similarity_threshold
            stats["use_fallback"] = self._use_semantic_fallback
            if isinstance(self.replacer, SemanticReplacer):
                stats["used_replacements"] = len(self.replacer._used_replacements)

        return stats


def create_engine(
    mode: str = "token",
    **kwargs: Any,
) -> ReplacementEngine:
    """Factory function to create a replacement engine.

    Args:
        mode: Replacement mode ("token", "faker", or "semantic")
        **kwargs: Additional arguments passed to ReplacementEngine

    Returns:
        Configured ReplacementEngine instance
    """
    try:
        replacement_mode = ReplacementMode(mode.lower())
    except ValueError:
        valid = ", ".join([m.value for m in ReplacementMode])
        raise ValueError(f"Invalid mode '{mode}'. Choose from: {valid}")

    return ReplacementEngine(mode=replacement_mode, **kwargs)
