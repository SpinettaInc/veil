"""Hybrid/ensemble detection combining multiple detection sources.

This module provides a unified detector that combines:
- spaCy NER
- Microsoft Presidio
- Regex patterns

It uses voting and confidence boosting when multiple detectors agree.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from veil.detection.entity import Entity, EntityType, merge_overlapping_entities
from veil.detection.ner import SpacyNER, SPACY_AVAILABLE
from veil.detection.patterns import PatternDetector
from veil.detection.presidio import PresidioDetector, PRESIDIO_AVAILABLE


class DetectorType(str, Enum):
    """Available detector types."""

    SPACY = "spacy"
    PRESIDIO = "presidio"
    PATTERN = "pattern"


@dataclass
class DetectorConfig:
    """Configuration for a single detector in the ensemble.

    Attributes:
        enabled: Whether this detector is active
        weight: Weight for this detector's confidence (0.0-1.0)
        min_confidence: Minimum confidence threshold
    """

    enabled: bool = True
    weight: float = 1.0
    min_confidence: float = 0.0


class HybridDetector:
    """Ensemble detector combining multiple detection sources.

    Combines spaCy NER, Presidio, and regex patterns for robust entity
    detection. Uses configurable weights and voting for better accuracy.

    Key features:
    - Multiple detection sources for better coverage
    - Confidence boosting when detectors agree
    - Smart overlap handling
    - Configurable per-detector weights

    Example:
        >>> detector = HybridDetector()
        >>> entities = detector.detect("John Smith's email is john@example.com")
        >>> for e in entities:
        ...     print(f"{e.text}: {e.entity_type} ({e.confidence:.2f})")
        John Smith: PERSON (0.95)
        john@example.com: EMAIL (0.98)

    Attributes:
        spacy_detector: spaCy NER detector
        presidio_detector: Presidio detector
        pattern_detector: Regex pattern detector
        config: Per-detector configuration
    """

    # Confidence boost when multiple detectors agree
    AGREEMENT_BOOST = 0.15

    # Minimum overlap ratio to consider entities as matching
    OVERLAP_THRESHOLD = 0.8

    def __init__(
        self,
        use_spacy: bool = True,
        use_presidio: bool = True,
        use_patterns: bool = True,
        spacy_model: Optional[str] = None,
        presidio_language: str = "en",
        min_confidence: float = 0.0,
        agreement_boost: float = 0.15,
        spacy_config: Optional[DetectorConfig] = None,
        presidio_config: Optional[DetectorConfig] = None,
        pattern_config: Optional[DetectorConfig] = None,
    ) -> None:
        """Initialize the hybrid detector.

        Args:
            use_spacy: Whether to use spaCy NER
            use_presidio: Whether to use Presidio
            use_patterns: Whether to use regex patterns
            spacy_model: Specific spaCy model to use
            presidio_language: Language for Presidio
            min_confidence: Global minimum confidence threshold
            agreement_boost: Confidence boost when detectors agree
            spacy_config: Config for spaCy detector
            presidio_config: Config for Presidio detector
            pattern_config: Config for pattern detector
        """
        self.min_confidence = min_confidence
        self.agreement_boost = agreement_boost

        # Initialize detector configurations
        self.spacy_config = spacy_config or DetectorConfig(enabled=use_spacy)
        self.presidio_config = presidio_config or DetectorConfig(enabled=use_presidio)
        self.pattern_config = pattern_config or DetectorConfig(enabled=use_patterns)

        # Initialize detectors
        self.spacy_detector: Optional[SpacyNER] = None
        self.presidio_detector: Optional[PresidioDetector] = None
        self.pattern_detector: Optional[PatternDetector] = None

        # spaCy
        if self.spacy_config.enabled and SPACY_AVAILABLE:
            try:
                self.spacy_detector = SpacyNER(
                    model_name=spacy_model,
                    filter_false_positives=True,
                )
            except OSError as e:
                print(f"Warning: Could not load spaCy: {e}")
                self.spacy_config.enabled = False

        # Presidio
        if self.presidio_config.enabled and PRESIDIO_AVAILABLE:
            try:
                self.presidio_detector = PresidioDetector(
                    language=presidio_language,
                )
            except Exception as e:
                print(f"Warning: Could not load Presidio: {e}")
                self.presidio_config.enabled = False

        # Patterns
        if self.pattern_config.enabled:
            self.pattern_detector = PatternDetector()

        # Validate at least one detector is available
        if not any([
            self.spacy_detector,
            self.presidio_detector,
            self.pattern_detector,
        ]):
            raise ValueError("No detection methods available")

    def detect(self, text: str) -> list[Entity]:
        """Detect entities using all enabled detectors.

        Combines results from multiple detectors, boosts confidence when
        they agree, and handles overlapping entities.

        Args:
            text: Text to analyze

        Returns:
            List of detected entities, sorted by position
        """
        if not text or not text.strip():
            return []

        all_entities: list[Entity] = []

        # Collect from all detectors
        if self.spacy_detector and self.spacy_config.enabled:
            spacy_entities = self._detect_with_weight(
                self.spacy_detector.detect(text),
                self.spacy_config,
                "spacy",
            )
            all_entities.extend(spacy_entities)

        if self.presidio_detector and self.presidio_config.enabled:
            presidio_entities = self._detect_with_weight(
                self.presidio_detector.detect(text),
                self.presidio_config,
                "presidio",
            )
            all_entities.extend(presidio_entities)

        if self.pattern_detector and self.pattern_config.enabled:
            pattern_entities = self._detect_with_weight(
                self.pattern_detector.detect(text),
                self.pattern_config,
                "pattern",
            )
            all_entities.extend(pattern_entities)

        # Apply agreement boosting
        boosted_entities = self._apply_agreement_boost(all_entities)

        # Filter by minimum confidence
        if self.min_confidence > 0:
            boosted_entities = [
                e for e in boosted_entities if e.confidence >= self.min_confidence
            ]

        # Merge overlapping entities
        merged = merge_overlapping_entities(boosted_entities)

        return merged

    def _detect_with_weight(
        self,
        entities: list[Entity],
        config: DetectorConfig,
        source: str,
    ) -> list[Entity]:
        """Apply detector-specific weight and filtering.

        Args:
            entities: Entities from this detector
            config: Detector configuration
            source: Source name for metadata

        Returns:
            Weighted and filtered entities
        """
        result: list[Entity] = []
        for entity in entities:
            # Apply minimum confidence filter
            if entity.confidence < config.min_confidence:
                continue

            # Apply weight to confidence
            weighted_confidence = min(1.0, entity.confidence * config.weight)

            # Create new entity with weighted confidence
            weighted_entity = Entity(
                text=entity.text,
                entity_type=entity.entity_type,
                start=entity.start,
                end=entity.end,
                confidence=weighted_confidence,
                source=source,
                context=entity.context,
                metadata={**entity.metadata, "original_confidence": entity.confidence},
            )
            result.append(weighted_entity)

        return result

    def _apply_agreement_boost(self, entities: list[Entity]) -> list[Entity]:
        """Boost confidence when multiple detectors agree on an entity.

        Entities that are detected by multiple sources get a confidence boost.

        Args:
            entities: All entities from all detectors

        Returns:
            Entities with agreement-boosted confidence
        """
        if not entities:
            return []

        # Group entities by approximate position
        position_groups: dict[tuple[int, int], list[Entity]] = {}
        for entity in entities:
            # Find or create a group for this position
            group_key = None
            for key in position_groups:
                if self._positions_match(entity.start, entity.end, key[0], key[1]):
                    group_key = key
                    break

            if group_key is None:
                group_key = (entity.start, entity.end)
                position_groups[group_key] = []

            position_groups[group_key].append(entity)

        # Process groups and apply boosts
        result: list[Entity] = []
        for _pos, group in position_groups.items():
            if len(group) == 1:
                # Only one detector found this - keep as is
                result.append(group[0])
            else:
                # Multiple detectors agree - boost the best one
                best_entity = max(group, key=lambda e: e.confidence)
                unique_sources = len(set(e.source for e in group))

                # Calculate boost based on number of agreeing sources
                boost = self.agreement_boost * (unique_sources - 1)
                boosted_confidence = min(1.0, best_entity.confidence + boost)

                # Create boosted entity
                boosted_entity = Entity(
                    text=best_entity.text,
                    entity_type=best_entity.entity_type,
                    start=best_entity.start,
                    end=best_entity.end,
                    confidence=boosted_confidence,
                    source="hybrid",
                    context=best_entity.context,
                    metadata={
                        **best_entity.metadata,
                        "sources": [e.source for e in group],
                        "agreement_count": unique_sources,
                    },
                )
                result.append(boosted_entity)

        return result

    def _positions_match(
        self,
        start1: int,
        end1: int,
        start2: int,
        end2: int,
    ) -> bool:
        """Check if two position ranges overlap significantly.

        Args:
            start1, end1: First range
            start2, end2: Second range

        Returns:
            True if ranges overlap by at least OVERLAP_THRESHOLD
        """
        # Calculate overlap
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)

        if overlap_start >= overlap_end:
            return False

        overlap_length = overlap_end - overlap_start
        min_length = min(end1 - start1, end2 - start2)

        return overlap_length / min_length >= self.OVERLAP_THRESHOLD

    def detect_by_type(
        self,
        text: str,
        entity_types: list[EntityType],
    ) -> list[Entity]:
        """Detect entities of specific types only.

        Args:
            text: Text to analyze
            entity_types: List of entity types to detect

        Returns:
            List of entities matching the specified types
        """
        all_entities = self.detect(text)
        return [e for e in all_entities if e.entity_type in entity_types]

    def get_stats(self) -> dict:
        """Get statistics about the detector configuration.

        Returns:
            Dictionary with detector stats
        """
        return {
            "spacy_enabled": self.spacy_detector is not None,
            "spacy_model": (
                self.spacy_detector.model_name if self.spacy_detector else None
            ),
            "presidio_enabled": self.presidio_detector is not None,
            "patterns_enabled": self.pattern_detector is not None,
            "pattern_count": (
                len(self.pattern_detector.patterns) if self.pattern_detector else 0
            ),
            "min_confidence": self.min_confidence,
            "agreement_boost": self.agreement_boost,
        }

    @property
    def supported_entity_types(self) -> list[EntityType]:
        """List all entity types that can be detected."""
        types: set[EntityType] = set()

        if self.spacy_detector:
            types.update(self.spacy_detector.supported_entity_types)

        if self.presidio_detector:
            types.update(self.presidio_detector.supported_entity_types)

        if self.pattern_detector:
            types.update(self.pattern_detector.supported_entity_types)

        return list(types)

    def __repr__(self) -> str:
        detectors = []
        if self.spacy_detector:
            detectors.append("spacy")
        if self.presidio_detector:
            detectors.append("presidio")
        if self.pattern_detector:
            detectors.append("patterns")

        return f"HybridDetector(detectors=[{', '.join(detectors)}])"
