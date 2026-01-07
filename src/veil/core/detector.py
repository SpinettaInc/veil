"""Core entity detection pipeline combining multiple detection methods."""

from enum import Enum
from typing import Optional

from veil.detection.entity import Entity, EntityType, merge_overlapping_entities
from veil.detection.ner import SpacyNER, SPACY_AVAILABLE
from veil.detection.patterns import PatternDetector
from veil.detection.hybrid import HybridDetector, DetectorConfig
from veil.detection.presidio import PRESIDIO_AVAILABLE


class DetectionMode(str, Enum):
    """Detection mode selection."""

    STANDARD = "standard"  # spaCy + patterns (original behavior)
    HYBRID = "hybrid"  # spaCy + Presidio + patterns with voting


class EntityDetector:
    """Combined entity detector using NER and pattern matching.

    This detector combines multiple detection methods:
    1. spaCy NER for named entities (persons, organizations, etc.)
    2. Regex patterns for structured PII (SSN, email, credit cards, etc.)
    3. (Hybrid mode) Microsoft Presidio for additional PII detection

    Results are merged to handle overlapping detections.

    Attributes:
        ner_detector: spaCy-based NER detector (optional)
        pattern_detector: Regex pattern detector
        hybrid_detector: Hybrid detector combining all sources (optional)
        use_ner: Whether NER is enabled and available
        mode: Detection mode (standard or hybrid)
    """

    def __init__(
        self,
        use_ner: bool = True,
        use_patterns: bool = True,
        use_presidio: bool = False,
        spacy_model: Optional[str] = None,
        min_confidence: float = 0.0,
        mode: str = "standard",
        agreement_boost: float = 0.15,
    ) -> None:
        """Initialize the entity detector.

        Args:
            use_ner: Whether to use spaCy NER detection
            use_patterns: Whether to use regex pattern detection
            use_presidio: Whether to use Presidio detection (enables hybrid mode)
            spacy_model: Specific spaCy model to use (or auto-detect)
            min_confidence: Minimum confidence threshold for entities
            mode: Detection mode ("standard" or "hybrid")
            agreement_boost: Confidence boost when detectors agree (hybrid mode)

        Raises:
            ValueError: If all detection methods are disabled
        """
        # Determine detection mode
        try:
            self.mode = DetectionMode(mode.lower())
        except ValueError:
            self.mode = DetectionMode.STANDARD

        # Enable hybrid mode if presidio is requested or mode is hybrid
        if use_presidio or self.mode == DetectionMode.HYBRID:
            self.mode = DetectionMode.HYBRID

        self.min_confidence = min_confidence
        self.use_ner = use_ner
        self.use_patterns = use_patterns
        self.use_presidio = use_presidio or self.mode == DetectionMode.HYBRID

        # Initialize detectors based on mode
        self.ner_detector: Optional[SpacyNER] = None
        self.pattern_detector: Optional[PatternDetector] = None
        self.hybrid_detector: Optional[HybridDetector] = None

        if self.mode == DetectionMode.HYBRID:
            # Use hybrid detector
            try:
                self.hybrid_detector = HybridDetector(
                    use_spacy=use_ner,
                    use_presidio=self.use_presidio and PRESIDIO_AVAILABLE,
                    use_patterns=use_patterns,
                    spacy_model=spacy_model,
                    min_confidence=min_confidence,
                    agreement_boost=agreement_boost,
                )
            except Exception as e:
                print(f"Warning: Could not initialize hybrid detector: {e}")
                print("Falling back to standard mode")
                self.mode = DetectionMode.STANDARD

        if self.mode == DetectionMode.STANDARD:
            # Standard mode: separate detectors
            if not use_ner and not use_patterns:
                raise ValueError("At least one detection method must be enabled")

            if use_ner:
                if SPACY_AVAILABLE:
                    try:
                        self.ner_detector = SpacyNER(
                            model_name=spacy_model,
                            filter_false_positives=True,
                        )
                    except OSError as e:
                        print(f"Warning: Could not load spaCy model: {e}")
                        self.use_ner = False
                else:
                    print("Warning: spaCy not available, NER disabled")
                    self.use_ner = False

            if use_patterns:
                self.pattern_detector = PatternDetector()

    def detect(self, text: str) -> list[Entity]:
        """Detect all entities in text.

        Combines results from all enabled detection methods and merges
        overlapping entities (keeping higher confidence ones).

        Args:
            text: Text to analyze

        Returns:
            List of detected entities, sorted by position
        """
        if not text or not text.strip():
            return []

        # Use hybrid detector if available
        if self.mode == DetectionMode.HYBRID and self.hybrid_detector:
            return self.hybrid_detector.detect(text)

        # Standard mode: combine spaCy and patterns
        all_entities: list[Entity] = []

        # Run NER detection
        if self.use_ner and self.ner_detector:
            ner_entities = self.ner_detector.detect(text)
            all_entities.extend(ner_entities)

        # Run pattern detection
        if self.use_patterns and self.pattern_detector:
            pattern_entities = self.pattern_detector.detect(text)
            all_entities.extend(pattern_entities)

        # Filter by minimum confidence
        if self.min_confidence > 0:
            all_entities = [
                e for e in all_entities if e.confidence >= self.min_confidence
            ]

        # Merge overlapping entities
        merged = merge_overlapping_entities(all_entities)

        return merged

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

    def detect_pii(self, text: str) -> list[Entity]:
        """Detect common PII entities.

        Focuses on high-risk PII types like SSN, credit cards, etc.

        Args:
            text: Text to analyze

        Returns:
            List of PII entities
        """
        pii_types = [
            EntityType.PERSON,
            EntityType.EMAIL,
            EntityType.PHONE,
            EntityType.SSN,
            EntityType.CREDIT_CARD,
            EntityType.IP_ADDRESS,
            EntityType.PASSPORT,
            EntityType.DRIVER_LICENSE,
            EntityType.BANK_ACCOUNT,
            EntityType.IBAN,
            EntityType.MEDICAL_RECORD,
        ]
        return self.detect_by_type(text, pii_types)

    @property
    def supported_entity_types(self) -> list[EntityType]:
        """List all entity types that can be detected."""
        if self.hybrid_detector:
            return self.hybrid_detector.supported_entity_types

        types: set[EntityType] = set()

        if self.ner_detector:
            types.update(self.ner_detector.supported_entity_types)

        if self.pattern_detector:
            types.update(self.pattern_detector.supported_entity_types)

        return list(types)

    def get_stats(self) -> dict:
        """Get statistics about the detector configuration.

        Returns:
            Dictionary with detector stats
        """
        if self.hybrid_detector:
            hybrid_stats = self.hybrid_detector.get_stats()
            return {
                "mode": self.mode.value,
                **hybrid_stats,
                "supported_types": [t.value for t in self.supported_entity_types],
            }

        return {
            "mode": self.mode.value,
            "ner_enabled": self.use_ner,
            "ner_model": (
                self.ner_detector.model_name if self.ner_detector else None
            ),
            "presidio_enabled": False,
            "patterns_enabled": self.use_patterns,
            "pattern_count": (
                len(self.pattern_detector.patterns) if self.pattern_detector else 0
            ),
            "min_confidence": self.min_confidence,
            "supported_types": [t.value for t in self.supported_entity_types],
        }

    def __repr__(self) -> str:
        if self.mode == DetectionMode.HYBRID:
            return f"EntityDetector(mode=hybrid, {self.hybrid_detector})"
        return (
            f"EntityDetector(mode=standard, ner={self.use_ner}, "
            f"patterns={self.use_patterns}, min_conf={self.min_confidence})"
        )
