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

    def replace(
        self,
        entity: Entity,
        mapping_store: MappingStore,
        context: str | None = None,
    ) -> str:
        """Generate replacement for an entity.

        Args:
            entity: Entity to replace
            mapping_store: Mapping store for tracking
            context: Optional surrounding context (for semantic mode)

        Returns:
            Replacement string
        """
        # Check existing mapping first (partial names resolve to the same token)
        existing = mapping_store.get_replacement_for(entity.text, entity.entity_type)
        if existing:
            return existing

        # Use context-aware replacement for semantic mode
        if (
            self.mode == ReplacementMode.SEMANTIC
            and context
            and isinstance(self.replacer, SemanticReplacer)
        ):
            return self.replacer.get_context_aware_replacement(
                entity, context, mapping_store
            )

        return self.replacer.generate_replacement(entity, mapping_store)

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
        # mention of a name defines its token, then splice from the end so
        # earlier offsets stay valid.
        planned: list[tuple[Entity, str]] = []
        for entity in sorted(entities, key=lambda e: e.start):
            # Get context around entity for semantic mode
            context = None
            if self.mode == ReplacementMode.SEMANTIC:
                context_start = max(0, entity.start - 50)
                context_end = min(len(text), entity.end + 50)
                context = text[context_start:context_end]

            # Generate replacement; a fake value that already occurs in the
            # input (or is itself a mapped original) would corrupt
            # reconstruction, so retry a few times before accepting it.
            replacement = self.replace(entity, mapping_store, context)
            if not mapping_store.has_replacement(replacement):
                for _ in range(5):
                    if replacement not in text and not mapping_store.has_original(replacement):
                        break
                    mapping_store.block({replacement})
                    replacement = self.replace(entity, mapping_store, context)

            # Add to mapping store if new
            if not mapping_store.has_original(entity.text):
                mapping_store.add(
                    original=entity.text,
                    replacement=replacement,
                    entity_type=entity.entity_type,
                    entity=entity,
                )
            planned.append((entity, replacement))

        pieces: list[str] = []
        cursor = 0
        for entity, replacement in planned:
            pieces.append(text[cursor:entity.start])
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
