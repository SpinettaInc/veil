"""Guardrails AI integration for Veil.

This module provides Guardrails AI validators that use Veil's detection
and anonymization capabilities. These validators can be used in any
Guardrails AI pipeline to detect and optionally fix PII.

Example:
    >>> from guardrails import Guard, OnFailAction
    >>> from veil.integrations.guardrails import VeilPIIValidator
    >>>
    >>> guard = Guard().use(VeilPIIValidator(on_fail=OnFailAction.FIX))
    >>> result = guard.validate("Contact John Smith at john@example.com")
    >>> print(result.validated_output)
    Contact [PERSON_1] at [EMAIL_1]
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

try:
    from guardrails import Guard, OnFailAction
    from guardrails.validators import (
        FailResult,
        PassResult,
        ValidationResult,
        Validator,
        register_validator,
    )

    GUARDRAILS_AVAILABLE = True
except ImportError:
    GUARDRAILS_AVAILABLE = False
    # Create stub classes for type hints
    Guard = None  # type: ignore
    OnFailAction = None  # type: ignore
    Validator = object  # type: ignore
    ValidationResult = None  # type: ignore

    def register_validator(*args, **kwargs):  # type: ignore
        def decorator(cls):
            return cls
        return decorator

    class PassResult:  # type: ignore
        pass

    class FailResult:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass


from veil.core.pipeline import VeilPipeline
from veil.core.mapper import MappingStore
from veil.detection.entity import Entity, EntityType
from veil.weighting.config import DetectionProfile


@dataclass
class PIIValidationResult:
    """Result from PII validation.

    Attributes:
        has_pii: Whether PII was detected
        entity_count: Number of entities found
        entities: List of detected entities
        anonymized_text: Text with PII replaced (if applicable)
        original_text: Original input text
    """

    has_pii: bool
    entity_count: int
    entities: List[Entity]
    anonymized_text: str
    original_text: str


if GUARDRAILS_AVAILABLE:

    @register_validator(name="veil/pii-detector", data_type="string")
    class VeilPIIValidator(Validator):
        """Guardrails validator that detects PII using Veil.

        This validator uses Veil's hybrid detection engine (spaCy + Presidio +
        patterns) to detect personally identifiable information in text.

        When used with OnFailAction.FIX, it automatically anonymizes the detected
        PII using Veil's replacement strategies.

        Args:
            profile: Detection profile ("paranoid", "balanced", "minimal")
            detection_mode: Detection mode ("standard" or "hybrid")
            replacement_mode: How to replace PII ("token", "faker", "semantic")
            use_presidio: Whether to use Presidio detection
            min_entities: Minimum entities to trigger failure (default: 1)
            entity_types: Specific entity types to detect (None = all)
            on_fail: What to do when PII is detected

        Example:
            >>> guard = Guard().use(
            ...     VeilPIIValidator(
            ...         profile="paranoid",
            ...         replacement_mode="faker",
            ...         on_fail=OnFailAction.FIX
            ...     )
            ... )
            >>> result = guard.validate("Email: john@example.com")
            >>> print(result.validated_output)
            Email: sarah.johnson@gmail.com
        """

        def __init__(
            self,
            profile: str = "balanced",
            detection_mode: str = "hybrid",
            replacement_mode: str = "token",
            use_presidio: bool = True,
            min_entities: int = 1,
            entity_types: Optional[List[str]] = None,
            on_fail: Optional[OnFailAction] = None,
            **kwargs,
        ):
            super().__init__(on_fail=on_fail or OnFailAction.NOOP, **kwargs)

            self.profile = profile
            self.detection_mode = detection_mode
            self.replacement_mode = replacement_mode
            self.use_presidio = use_presidio
            self.min_entities = min_entities
            self.entity_types = entity_types

            # Parse profile
            try:
                self._profile = DetectionProfile(profile.lower())
            except ValueError:
                self._profile = DetectionProfile.BALANCED

            # Parse entity types if provided
            self._entity_types: Optional[List[EntityType]] = None
            if entity_types:
                self._entity_types = []
                for et in entity_types:
                    try:
                        self._entity_types.append(EntityType(et.upper()))
                    except ValueError:
                        pass  # Skip invalid types

            # Create pipeline (lazy initialization)
            self._pipeline: Optional[VeilPipeline] = None

        def _get_pipeline(self) -> VeilPipeline:
            """Get or create the Veil pipeline."""
            if self._pipeline is None:
                self._pipeline = VeilPipeline(
                    use_ner=True,
                    use_patterns=True,
                    use_presidio=self.use_presidio,
                    profile=self._profile,
                    detection_mode=self.detection_mode,
                    replacement_mode=self.replacement_mode,
                )
            return self._pipeline

        def _validate(
            self,
            value: str,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> ValidationResult:
            """Validate text for PII.

            Args:
                value: Text to validate
                metadata: Optional metadata (unused)

            Returns:
                PassResult if no PII, FailResult with anonymized text if PII found
            """
            if not value or not value.strip():
                return PassResult()

            pipeline = self._get_pipeline()

            # Detect and anonymize
            if self._entity_types:
                result = pipeline.anonymize(value, entity_types=self._entity_types)
            else:
                result = pipeline.anonymize(value)

            # Check if enough entities were found
            if result.entity_count >= self.min_entities:
                # Build detailed error message
                entity_summary = self._build_entity_summary(result.entities)

                return FailResult(
                    error_message=(
                        f"PII detected: {result.entity_count} entities found. "
                        f"{entity_summary}"
                    ),
                    fix_value=result.anonymized_text,
                )

            return PassResult()

        def _build_entity_summary(self, entities: List[Entity]) -> str:
            """Build a summary of detected entities by type."""
            type_counts: Dict[str, int] = {}
            for entity in entities:
                type_name = entity.entity_type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1

            parts = [f"{count} {etype}" for etype, count in type_counts.items()]
            return f"Types: {', '.join(parts)}"

        def get_args(self) -> Dict[str, Any]:
            """Get validator arguments for serialization."""
            return {
                "profile": self.profile,
                "detection_mode": self.detection_mode,
                "replacement_mode": self.replacement_mode,
                "use_presidio": self.use_presidio,
                "min_entities": self.min_entities,
                "entity_types": self.entity_types,
            }

    @register_validator(name="veil/anonymizer", data_type="string")
    class VeilAnonymizer(Validator):
        """Guardrails validator that always anonymizes text.

        Unlike VeilPIIValidator which can pass or fail, this validator
        always processes the text through Veil's anonymization pipeline,
        even if no PII is detected.

        This is useful for scenarios where you want to ensure all text
        goes through the anonymization process regardless of content.

        Args:
            profile: Detection profile ("paranoid", "balanced", "minimal")
            replacement_mode: How to replace PII ("token", "faker", "semantic")
            detection_mode: Detection mode ("standard" or "hybrid")
            on_fail: Always uses FIX internally

        Example:
            >>> guard = Guard().use(VeilAnonymizer(profile="paranoid"))
            >>> result = guard.validate("John works at Acme")
            >>> print(result.validated_output)
            [PERSON_1] works at [ORG_1]
        """

        def __init__(
            self,
            profile: str = "balanced",
            replacement_mode: str = "token",
            detection_mode: str = "hybrid",
            use_presidio: bool = True,
            **kwargs,
        ):
            # Always use FIX since we always want to anonymize
            super().__init__(on_fail=OnFailAction.FIX, **kwargs)

            self.profile = profile
            self.replacement_mode = replacement_mode
            self.detection_mode = detection_mode
            self.use_presidio = use_presidio

            try:
                self._profile = DetectionProfile(profile.lower())
            except ValueError:
                self._profile = DetectionProfile.BALANCED

            self._pipeline: Optional[VeilPipeline] = None

        def _get_pipeline(self) -> VeilPipeline:
            """Get or create the Veil pipeline."""
            if self._pipeline is None:
                self._pipeline = VeilPipeline(
                    use_ner=True,
                    use_patterns=True,
                    use_presidio=self.use_presidio,
                    profile=self._profile,
                    detection_mode=self.detection_mode,
                    replacement_mode=self.replacement_mode,
                )
            return self._pipeline

        def _validate(
            self,
            value: str,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> ValidationResult:
            """Always anonymize text.

            Args:
                value: Text to anonymize
                metadata: Optional metadata (unused)

            Returns:
                FailResult with anonymized text (triggers FIX action)
            """
            if not value or not value.strip():
                return PassResult()

            pipeline = self._get_pipeline()
            result = pipeline.anonymize(value)

            if result.entity_count > 0:
                return FailResult(
                    error_message=f"Anonymized {result.entity_count} entities",
                    fix_value=result.anonymized_text,
                )

            # No entities found, but still return the (unchanged) text
            return PassResult()

        def get_args(self) -> Dict[str, Any]:
            """Get validator arguments for serialization."""
            return {
                "profile": self.profile,
                "replacement_mode": self.replacement_mode,
                "detection_mode": self.detection_mode,
                "use_presidio": self.use_presidio,
            }

    def create_veil_guard(
        profile: str = "balanced",
        detection_mode: str = "hybrid",
        replacement_mode: str = "token",
        use_presidio: bool = True,
        on_fail: OnFailAction = OnFailAction.FIX,
        entity_types: Optional[List[str]] = None,
    ) -> Guard:
        """Create a Guardrails Guard configured with Veil PII detection.

        This is a convenience function to quickly create a Guard with
        Veil's PII detection and anonymization capabilities.

        Args:
            profile: Detection profile ("paranoid", "balanced", "minimal")
            detection_mode: Detection mode ("standard" or "hybrid")
            replacement_mode: How to replace PII ("token", "faker", "semantic")
            use_presidio: Whether to use Presidio detection
            on_fail: Action when PII is detected
            entity_types: Specific entity types to detect (None = all)

        Returns:
            Configured Guard instance

        Example:
            >>> guard = create_veil_guard(profile="paranoid", on_fail=OnFailAction.FIX)
            >>> result = guard.validate("Email me at john@test.com")
            >>> print(result.validated_output)
            Email me at [EMAIL_1]
        """
        validator = VeilPIIValidator(
            profile=profile,
            detection_mode=detection_mode,
            replacement_mode=replacement_mode,
            use_presidio=use_presidio,
            entity_types=entity_types,
            on_fail=on_fail,
        )

        return Guard().use(validator)


else:
    # Stubs when Guardrails is not available

    class VeilPIIValidator:  # type: ignore
        """Stub class when Guardrails AI is not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Guardrails AI is not installed. Install it with:\n"
                "  pip install guardrails-ai"
            )

    class VeilAnonymizer:  # type: ignore
        """Stub class when Guardrails AI is not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Guardrails AI is not installed. Install it with:\n"
                "  pip install guardrails-ai"
            )

    def create_veil_guard(*args, **kwargs):  # type: ignore
        """Stub function when Guardrails AI is not installed."""
        raise ImportError(
            "Guardrails AI is not installed. Install it with:\n"
            "  pip install guardrails-ai"
        )
