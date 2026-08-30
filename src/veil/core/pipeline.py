"""Main Veil pipeline for text anonymization and reconstruction."""

import re
import time
from dataclasses import dataclass, field
from typing import Any

from veil.audit import AuditLogger
from veil.core.detector import EntityDetector
from veil.core.mapper import MappingStore, token_spans
from veil.detection.entity import Entity, EntityType
from veil.detection.patterns import Pattern, pattern_from_dict
from veil.replacement.engine import ReplacementEngine, ReplacementMode
from veil.weighting.config import DetectionProfile, WeightConfig
from veil.weighting.scorer import PrivacyScore, PrivacyScorer


@dataclass
class AnonymizationResult:
    """Result of anonymizing text.

    Attributes:
        original_text: The original input text
        anonymized_text: The anonymized output text
        entities: List of detected entities
        mapping_store: Reference to the mapping store used
        scores: Privacy scores for each entity (if weighting enabled)
        degraded: True if a detection backend was unavailable, so the text
            may still contain sensitive data (only possible with strict=False)
    """

    original_text: str
    anonymized_text: str
    entities: list[Entity]
    mapping_store: MappingStore
    scores: list[PrivacyScore] = field(default_factory=list)
    degraded: bool = False

    @property
    def entity_count(self) -> int:
        """Number of entities detected and replaced."""
        return len(self.entities)

    @property
    def replacements(self) -> dict[str, str]:
        """Dictionary of original -> replacement mappings."""
        return {entry.original: entry.replacement for entry in self.mapping_store}

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


def _drop_inside_tokens(entities: list[Entity], text: str) -> list[Entity]:
    """Remove detections that overlap something that is already a token.

    Text that has been anonymized before (conversation history, a second
    pass) contains "[PERSON_1]"-style strings that NER happily labels as
    organisations. Re-tokenising them would break reconstruction.
    """
    spans = token_spans(text)
    if not spans:
        return entities
    return [
        e
        for e in entities
        if not any(e.start < t_end and t_start < e.end for t_start, t_end in spans)
    ]


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
        spacy_model: str | None = None,
        min_confidence: float = 0.0,  # Detection confidence (separate from privacy threshold)
        bracket_style: str = "square",
        profile: DetectionProfile = DetectionProfile.BALANCED,
        weight_config: WeightConfig | None = None,
        use_weighting: bool = True,
        replacement_mode: str = "token",
        faker_locale: str = "en_US",
        faker_seed: int | None = None,
        semantic_threshold: float = 0.6,
        detection_mode: str = "standard",
        agreement_boost: float = 0.15,
        strict: bool = True,
        audit: AuditLogger | None = None,
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
            strict: Fail with DetectionUnavailableError if a requested detector
                (spaCy model, Presidio) cannot be loaded, instead of silently
                anonymizing less. Results carry ``degraded=True`` when not strict.
            audit: Optional audit logger; receives counts and timings only,
                never text or tokens.
        """
        self.audit = audit
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
            strict=strict,
        )

        self.scorer: PrivacyScorer | None = None
        if use_weighting:
            if weight_config:
                self.scorer = PrivacyScorer(config=weight_config)
            else:
                self.scorer = PrivacyScorer(profile=profile)

        # Custom regex detectors declared in the profile file
        config_for_patterns = weight_config or (self.scorer.config if self.scorer else None)
        if config_for_patterns is not None:
            for spec in config_for_patterns.custom_patterns:
                self.add_pattern(pattern_from_dict(spec))

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
        entity_types: list[EntityType] | None = None,
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
                degraded=self.detector.degraded,
            )

        started = time.perf_counter()
        # Never generate a token that the input already contains verbatim
        self.mapping_store.block_tokens_in(text)

        # Detect entities
        if entity_types:
            all_entities = self.detector.detect_by_type(text, entity_types)
        else:
            all_entities = self.detector.detect(text)
        all_entities = _drop_inside_tokens(all_entities, text)
        return self._finish(text, all_entities, started)

    def _finish(self, text: str, entities: list[Entity], started: float) -> AnonymizationResult:
        """Score, replace, build the result and audit — shared by single and batch paths."""
        scores: list[PrivacyScore] = []
        if self.use_weighting and self.scorer and entities:
            scores = self.scorer.score_entities(entities, text)
            entities = [s.entity for s in scores if s.above_threshold]

        anonymized_text = self.replacement_engine.replace_all(
            text=text,
            entities=entities,
            mapping_store=self.mapping_store,
        )

        result = AnonymizationResult(
            original_text=text,
            anonymized_text=anonymized_text,
            entities=entities,
            mapping_store=self.mapping_store,
            scores=scores,
            degraded=self.detector.degraded,
        )
        if self.audit is not None:
            self.audit.log_anonymize(
                text_chars=len(text),
                entities=entities,
                duration_ms=(time.perf_counter() - started) * 1000,
                degraded=result.degraded,
                profile=self.profile.value,
                replacement_mode=self._replacement_mode,
                detection_mode=self._detection_mode,
            )
        return result

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

        started = time.perf_counter()
        entries = list(self.mapping_store)
        if not entries:
            return ReconstructionResult(
                anonymized_text=text, reconstructed_text=text, replacements_made=0
            )

        # One alternation, longest replacement first so "[PERSON_1]" can never
        # be matched inside "[PERSON_12]". Token-style replacements are matched
        # tolerantly (see _token_pattern): LLMs routinely drop brackets or
        # change case ("EMAIL_1", "[email 1]", "<Person_2>").
        lookup: dict[str, str] = {}
        alternatives: list[str] = []
        for entry in sorted(entries, key=lambda e: -len(e.replacement)):
            lookup[entry.replacement] = entry.original
            alternatives.append(
                f"(?P<g{len(alternatives)}>{self._token_pattern(entry.replacement)})"
            )
        group_to_original = {
            f"g{i}": lookup[e.replacement]
            for i, e in enumerate(sorted(entries, key=lambda e: -len(e.replacement)))
        }
        pattern = re.compile("|".join(alternatives), re.IGNORECASE)

        replacements_made = 0

        def _restore(match: "re.Match[str]") -> str:
            nonlocal replacements_made
            replacements_made += 1
            return group_to_original[match.lastgroup or ""]

        result = pattern.sub(_restore, text)
        if self.audit is not None:
            self.audit.log_reconstruct(
                text_chars=len(text),
                replacements_made=replacements_made,
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        return ReconstructionResult(
            anonymized_text=text,
            reconstructed_text=result,
            replacements_made=replacements_made,
        )

    def anonymize_batch(
        self,
        texts: list[str],
        entity_types: list[EntityType] | None = None,
        separate_sessions: bool = False,
    ) -> list[AnonymizationResult]:
        """Anonymize many texts, running spaCy in batch mode.

        Args:
            texts: Documents to anonymize
            entity_types: Optional restriction, as for ``anonymize``
            separate_sessions: Clear the mapping store before each document so
                token numbering restarts and nothing links documents together

        Returns:
            One AnonymizationResult per input, in order
        """
        if not texts:
            return []
        ner = self.detector.ner_detector
        ner_batches: list[list[Entity]] | None = None
        if ner is not None and self.detector.mode.value == "standard" and self.detector.use_ner:
            ner_batches = ner.detect_batch(texts)

        results = []
        for i, text in enumerate(texts):
            if separate_sessions:
                self.clear_mappings()
            if ner_batches is None:
                results.append(self.anonymize(text, entity_types))
                continue
            # Same steps as anonymize(), with the NER pass already done
            if not text:
                results.append(self.anonymize(text, entity_types))
                continue
            started = time.perf_counter()
            self.mapping_store.block_tokens_in(text)
            entities = list(ner_batches[i])
            if self.detector.use_patterns and self.detector.pattern_detector:
                entities.extend(self.detector.pattern_detector.detect(text))
            entities = _drop_inside_tokens(self.detector.finalize(entities, text), text)
            if entity_types:
                entities = [e for e in entities if e.entity_type in entity_types]
            results.append(self._finish(text, entities, started))
        return results

    _TOKEN_SHAPE_RE = re.compile(r"^([\[<{])\s*([A-Za-z][A-Za-z_ ]*?)[\s_-]*(\d+)\s*([\]>}])$")

    @classmethod
    def _token_pattern(cls, replacement: str) -> str:
        """Regex for one replacement string.

        Token-shaped replacements ("[CREDIT_CARD_2]") accept any bracket style
        or none, any case, and "_", "-" or spaces between the parts, but the
        number must be exact and not followed by more digits. Anything else
        (faker/semantic values) is matched literally and case-sensitively.
        """
        m = cls._TOKEN_SHAPE_RE.match(replacement)
        if not m:
            return f"(?-i:{re.escape(replacement)})"
        _, type_name, number, _ = m.groups()
        type_pat = r"[\s_-]*".join(
            re.escape(part) for part in re.split(r"[\s_]+", type_name.strip())
        )
        return rf"(?<![A-Za-z0-9_])(?:[\[<{{]\s*)?{type_pat}[\s_-]*{number}(?!\d)(?:\s*[\]>}}])?"

    def process(
        self,
        text: str,
        entity_types: list[EntityType] | None = None,
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

    def add_pattern(self, pattern: Pattern) -> None:
        """Register an extra regex detector on whichever pattern detector is active."""
        detector = self.detector.pattern_detector
        if detector is None and self.detector.hybrid_detector is not None:
            detector = self.detector.hybrid_detector.pattern_detector
        if detector is None:
            raise ValueError("Pattern detection is disabled; cannot add custom patterns")
        detector.add_pattern(pattern)

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

    def get_mapping(self, original: str) -> str | None:
        """Get the replacement for an original text.

        Args:
            original: Original text to look up

        Returns:
            Replacement token, or None if not found
        """
        return self.mapping_store.get_replacement(original)

    def get_original(self, replacement: str) -> str | None:
        """Get the original text for a replacement token.

        Args:
            replacement: Replacement token to look up

        Returns:
            Original text, or None if not found
        """
        return self.mapping_store.get_original(replacement)

    def get_stats(self) -> dict[str, Any]:
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
