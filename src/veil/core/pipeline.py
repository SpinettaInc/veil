"""Main Veil pipeline for text anonymization and reconstruction."""

from dataclasses import dataclass, field
from typing import Optional

from veil.core.detector import EntityDetector
from veil.core.mapper import MappingStore
from veil.detection.entity import Entity, EntityType
from veil.replacement.engine import ReplacementEngine, ReplacementMode
from veil.weighting.config import DetectionProfile, WeightConfig
from veil.weighting.scorer import PrivacyScorer, PrivacyScore


@dataclass
class AnonymizationResult:
    """Result of anonymizing text.

    Attributes:
        original_text: The original input text
        anonymized_text: The anonymized output text
        entities: List of detected entities
        mapping_store: Reference to the mapping store used
        scores: Privacy scores for each entity (if weighting enabled)
    """

    original_text: str
    anonymized_text: str
    entities: list[Entity]
    mapping_store: MappingStore
    scores: list[PrivacyScore] = field(default_factory=list)

    @property
    def entity_count(self) -> int:
        """Number of entities detected and replaced."""
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
            f"chars_orig={len(self.original_text)}, "
            f"chars_anon={len(self.anonymized_text)})"
        )


@dataclass
class ReconstructionResult:
    """Result of reconstructing anonymized text.

    Attributes:
        anonymized_text: The anonymized input text
        reconstructed_text: The reconstructed output text
        replacements_made: Number of replacements made
    """

    anonymized_text: str
    reconstructed_text: str
    replacements_made: int

    def __repr__(self) -> str:
        return f"ReconstructionResult(replacements={self.replacements_made})"


class VeilPipeline:
    """Main pipeline for text anonymization and reconstruction.

    This is the primary interface for using Veil. It coordinates:
    1. Entity detection (NER + patterns)
    2. Privacy scoring (semantic weighting)
    3. Replacement generation (tokens, faker, semantic)
    4. Mapping management
    5. Response reconstruction

    Example:
        >>> pipeline = VeilPipeline()
        >>> result = pipeline.anonymize("John Smith works at Acme Corp")
        >>> print(result.anonymized_text)
        [PERSON_1] works at [ORG_1]
        >>> print(result.replacements)
        {"John Smith": "[PERSON_1]", "Acme Corp": "[ORG_1]"}

    Attributes:
        detector: Entity detection pipeline
        scorer: Privacy score calculator
        replacer: Replacement strategy
        mapping_store: Bidirectional mapping store
        profile: Current detection profile
    """

    def __init__(
        self,
        use_ner: bool = True,
        use_patterns: bool = True,
        use_presidio: bool = False,
        spacy_model: Optional[str] = None,
        min_confidence: float = 0.0,  # Detection confidence (separate from privacy threshold)
        bracket_style: str = "square",
        profile: DetectionProfile = DetectionProfile.BALANCED,
        weight_config: Optional[WeightConfig] = None,
        use_weighting: bool = True,
        replacement_mode: str = "token",
        faker_locale: str = "en_US",
        faker_seed: Optional[int] = None,
        semantic_threshold: float = 0.6,
        detection_mode: str = "standard",
        agreement_boost: float = 0.15,
    ) -> None:
        """Initialize the Veil pipeline.

        Args:
            use_ner: Whether to use spaCy NER detection
            use_patterns: Whether to use regex pattern detection
            use_presidio: Whether to use Presidio detection (enables hybrid mode)
            spacy_model: Specific spaCy model to use
            min_confidence: Minimum detection confidence (0.0 to keep all)
            bracket_style: Bracket style for token replacement
            profile: Detection profile (paranoid, balanced, minimal)
            weight_config: Custom weight configuration (overrides profile)
            use_weighting: Whether to use semantic weighting to filter entities
            replacement_mode: Replacement strategy ("token", "faker", "semantic")
            faker_locale: Locale for faker mode
            faker_seed: Random seed for faker reproducibility
            semantic_threshold: Similarity threshold for semantic mode
            detection_mode: Detection mode ("standard" or "hybrid")
            agreement_boost: Confidence boost when detectors agree (hybrid mode)
        """
        self.profile = profile
        self.use_weighting = use_weighting
        self._replacement_mode = replacement_mode
        self._detection_mode = detection_mode

        self.detector = EntityDetector(
            use_ner=use_ner,
            use_patterns=use_patterns,
            use_presidio=use_presidio,
            spacy_model=spacy_model,
            min_confidence=min_confidence,
            mode=detection_mode,
            agreement_boost=agreement_boost,
        )

        self.scorer: Optional[PrivacyScorer] = None
        if use_weighting:
            if weight_config:
                self.scorer = PrivacyScorer(config=weight_config)
            else:
                self.scorer = PrivacyScorer(profile=profile)

        # Initialize replacement engine
        try:
            mode = ReplacementMode(replacement_mode.lower())
        except ValueError:
            mode = ReplacementMode.TOKEN

        self.replacement_engine = ReplacementEngine(
            mode=mode,
            bracket_style=bracket_style,
            faker_locale=faker_locale,
            faker_seed=faker_seed,
            similarity_threshold=semantic_threshold,
        )
        self.mapping_store = MappingStore()

    def anonymize(
        self,
        text: str,
        entity_types: Optional[list[EntityType]] = None,
    ) -> AnonymizationResult:
        """Anonymize sensitive entities in text.

        Detects sensitive entities, scores them for privacy sensitivity,
        and replaces those above the threshold with tokens.

        Args:
            text: Text to anonymize
            entity_types: Optional list of entity types to detect.
                         If None, detects all types.

        Returns:
            AnonymizationResult with anonymized text and metadata
        """
        if not text:
            return AnonymizationResult(
                original_text=text,
                anonymized_text=text,
                entities=[],
                mapping_store=self.mapping_store,
            )

        # Detect entities
        if entity_types:
            all_entities = self.detector.detect_by_type(text, entity_types)
        else:
            all_entities = self.detector.detect(text)

        # Apply semantic weighting to filter entities
        scores: list[PrivacyScore] = []
        if self.use_weighting and self.scorer and all_entities:
            scores = self.scorer.score_entities(all_entities, text)
            entities = [s.entity for s in scores if s.above_threshold]
        else:
            entities = all_entities

        # Apply replacements using replacement engine
        anonymized_text = self.replacement_engine.replace_all(
            text=text,
            entities=entities,
            mapping_store=self.mapping_store,
        )

        return AnonymizationResult(
            original_text=text,
            anonymized_text=anonymized_text,
            entities=entities,
            mapping_store=self.mapping_store,
            scores=scores,
        )

    def score_entities(self, text: str) -> list[PrivacyScore]:
        """Score entities without anonymizing.

        Useful for analyzing what would be detected and why.

        Args:
            text: Text to analyze

        Returns:
            List of privacy scores for all detected entities
        """
        entities = self.detector.detect(text)

        if not self.scorer or not entities:
            return []

        return self.scorer.score_entities(entities, text)

    def reconstruct(self, text: str) -> ReconstructionResult:
        """Reconstruct anonymized text by replacing tokens with originals.

        This is the reverse of anonymize() - it replaces tokens like
        [PERSON_1] back to their original values.

        Args:
            text: Anonymized text to reconstruct

        Returns:
            ReconstructionResult with reconstructed text
        """
        if not text:
            return ReconstructionResult(
                anonymized_text=text,
                reconstructed_text=text,
                replacements_made=0,
            )

        result = text
        replacements_made = 0

        # Replace all tokens with their originals
        for entry in self.mapping_store:
            if entry.replacement in result:
                result = result.replace(entry.replacement, entry.original)
                replacements_made += 1

        return ReconstructionResult(
            anonymized_text=text,
            reconstructed_text=result,
            replacements_made=replacements_made,
        )

    def process(
        self,
        text: str,
        entity_types: Optional[list[EntityType]] = None,
    ) -> tuple[str, dict[str, str]]:
        """Convenience method to anonymize and return simple results.

        Args:
            text: Text to anonymize
            entity_types: Optional entity types to detect

        Returns:
            Tuple of (anonymized_text, replacements_dict)
        """
        result = self.anonymize(text, entity_types)
        return result.anonymized_text, result.replacements

    def set_profile(self, profile: DetectionProfile) -> None:
        """Change the detection profile.

        Args:
            profile: New profile to use
        """
        self.profile = profile
        if self.use_weighting:
            self.scorer = PrivacyScorer(profile=profile)

    def clear_mappings(self) -> None:
        """Clear all stored mappings.

        Call this to start a fresh session.
        """
        self.mapping_store.clear()
        if self.scorer:
            self.scorer.clear_cache()
        self.replacement_engine.clear_cache()

    def set_replacement_mode(self, mode: str) -> None:
        """Change the replacement mode.

        Args:
            mode: New mode ("token", "faker", "semantic")
        """
        try:
            new_mode = ReplacementMode(mode.lower())
            self.replacement_engine.set_mode(new_mode)
            self._replacement_mode = mode
        except ValueError:
            valid = ", ".join([m.value for m in ReplacementMode])
            raise ValueError(f"Invalid mode '{mode}'. Choose from: {valid}")

    def get_mapping(self, original: str) -> Optional[str]:
        """Get the replacement for an original text.

        Args:
            original: Original text to look up

        Returns:
            Replacement token, or None if not found
        """
        return self.mapping_store.get_replacement(original)

    def get_original(self, replacement: str) -> Optional[str]:
        """Get the original text for a replacement token.

        Args:
            replacement: Replacement token to look up

        Returns:
            Original text, or None if not found
        """
        return self.mapping_store.get_original(replacement)

    def get_stats(self) -> dict:
        """Get statistics about the pipeline state.

        Returns:
            Dictionary with pipeline statistics
        """
        stats = {
            "detector": self.detector.get_stats(),
            "mappings": self.mapping_store.get_stats(),
            "profile": self.profile.value,
            "weighting_enabled": self.use_weighting,
            "replacement": self.replacement_engine.get_stats(),
        }

        if self.scorer:
            stats["scorer"] = self.scorer.get_stats()

        return stats

    def __repr__(self) -> str:
        return (
            f"VeilPipeline(mappings={len(self.mapping_store)}, "
            f"profile={self.profile.value}, "
            f"mode={self._replacement_mode}, "
            f"detector={self.detector})"
        )


# Convenience function for simple usage
def anonymize(
    text: str,
    use_ner: bool = True,
    use_patterns: bool = True,
    profile: DetectionProfile = DetectionProfile.BALANCED,
) -> tuple[str, dict[str, str]]:
    """Quick anonymization without creating a pipeline.

    Creates a temporary pipeline, anonymizes the text, and returns results.
    For repeated use, create a VeilPipeline instance instead.

    Args:
        text: Text to anonymize
        use_ner: Whether to use NER detection
        use_patterns: Whether to use pattern detection
        profile: Detection profile to use

    Returns:
        Tuple of (anonymized_text, replacements_dict)
    """
    pipeline = VeilPipeline(
        use_ner=use_ner,
        use_patterns=use_patterns,
        profile=profile,
    )
    return pipeline.process(text)
