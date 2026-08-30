"""Presidio-based detection for PII and sensitive data.

Wraps Microsoft Presidio for enhanced entity detection.
"""


try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_analyzer.nlp_engine import SpacyNlpEngine

    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False
    AnalyzerEngine = None  # type: ignore
    RecognizerResult = None  # type: ignore
    SpacyNlpEngine = None  # type: ignore

from veil.detection.entity import Entity, EntityType
from veil.detection.ner import _DURATION_RE, _is_specific_date, is_false_positive

# Presidio types whose spans come from its spaCy NER and need the same
# false-positive filtering as our own NER output
_PRESIDIO_NER_LABELS = {
    "PERSON": "PERSON",
    "LOCATION": "GPE",
    "NRP": "NORP",
    "ORGANIZATION": "ORG",
}

# Presidio entity types that tend to have high false positive rates. They are
# only accepted when Presidio itself is fairly confident.
PRESIDIO_HIGH_FP_TYPES = {
    "DATE_TIME",  # Often matches non-date text
    "US_DRIVER_LICENSE",  # Matches many alphanumeric codes
    "MEDICAL_LICENSE",  # Overly broad matching
    "LOCATION",  # Can match common words
    "US_BANK_NUMBER",  # Any long digit run
    "US_PASSPORT",
}
HIGH_FP_MIN_SCORE = 0.65


# Mapping from Presidio entity types to our EntityType
PRESIDIO_TO_ENTITY_TYPE: dict[str, EntityType] = {
    # Common PII
    "PERSON": EntityType.PERSON,
    "EMAIL_ADDRESS": EntityType.EMAIL,
    "PHONE_NUMBER": EntityType.PHONE,
    "LOCATION": EntityType.LOC,
    "DATE_TIME": EntityType.DATE,
    "NRP": EntityType.NORP,  # Nationality, Religion, Political group
    "ORGANIZATION": EntityType.ORG,
    # Financial
    "CREDIT_CARD": EntityType.CREDIT_CARD,
    "IBAN_CODE": EntityType.IBAN,
    "US_BANK_NUMBER": EntityType.BANK_ACCOUNT,
    "UK_NHS": EntityType.MEDICAL_RECORD,
    # Government IDs
    "US_SSN": EntityType.SSN,
    "US_PASSPORT": EntityType.PASSPORT,
    "US_DRIVER_LICENSE": EntityType.DRIVER_LICENSE,
    # Technical
    "IP_ADDRESS": EntityType.IP_ADDRESS,
    "URL": EntityType.URL,
    # Medical
    "MEDICAL_LICENSE": EntityType.MEDICAL_RECORD,
    # Other
    "CRYPTO": EntityType.BANK_ACCOUNT,  # Crypto wallet
}


class PresidioDetector:
    """Named Entity Recognition using Microsoft Presidio.

    Presidio provides robust PII detection with support for 50+ entity types.
    This class wraps Presidio to match Veil's Entity interface.

    Attributes:
        analyzer: Presidio AnalyzerEngine instance
        language: Language for detection
    """

    DEFAULT_ENTITIES = [
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "LOCATION",
        "DATE_TIME",
        "CREDIT_CARD",
        "IBAN_CODE",
        "US_SSN",
        "US_PASSPORT",
        "US_DRIVER_LICENSE",
        "IP_ADDRESS",
        "URL",
        "ORGANIZATION",
        "US_BANK_NUMBER",
        "MEDICAL_LICENSE",
        "NRP",
    ]

    def __init__(
        self,
        language: str = "en",
        entities: list[str] | None = None,
        context_window: int = 50,
        score_threshold: float = 0.3,
        nlp: object | None = None,
        model_name: str = "en_core_web_lg",
    ) -> None:
        """Initialize the Presidio detector.

        Args:
            language: Language code for detection (e.g., "en")
            entities: List of Presidio entity types to detect.
                     If None, uses DEFAULT_ENTITIES.
            context_window: Characters of context to capture around entities
            score_threshold: Minimum Presidio score to accept (0.0-1.0)
            nlp: An already-loaded spaCy ``Language`` to reuse instead of
                letting Presidio load its own copy (saves ~1s and ~500MB)
            model_name: Name reported to Presidio for ``nlp``

        Raises:
            ImportError: If presidio-analyzer is not installed
        """
        if not PRESIDIO_AVAILABLE:
            raise ImportError(
                "Presidio is not installed. Install it with:\n"
                "  pip install presidio-analyzer presidio-anonymizer\n"
                "Then download spaCy model:\n"
                "  python -m spacy download en_core_web_lg"
            )

        self.language = language
        self.entities = entities or self.DEFAULT_ENTITIES
        self.context_window = context_window
        self.score_threshold = score_threshold

        # Initialize Presidio analyzer, sharing the spaCy model when given
        if nlp is not None:
            engine = SpacyNlpEngine(models=[{"lang_code": language, "model_name": model_name}])
            engine.nlp = {language: nlp}  # type: ignore[assignment]
            self.analyzer = AnalyzerEngine(nlp_engine=engine, supported_languages=[language])
        else:
            self.analyzer = AnalyzerEngine()

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Extract context around an entity."""
        context_start = max(0, start - self.context_window)
        context_end = min(len(text), end + self.context_window)
        return text[context_start:context_end]

    def _map_entity_type(self, presidio_type: str) -> EntityType:
        """Map Presidio entity type to Veil EntityType."""
        return PRESIDIO_TO_ENTITY_TYPE.get(presidio_type, EntityType.UNKNOWN)

    def detect(self, text: str) -> list[Entity]:
        """Detect entities using Presidio.

        Args:
            text: Text to analyze

        Returns:
            List of detected entities
        """
        if not text or not text.strip():
            return []

        # Run Presidio analysis
        results = self.analyzer.analyze(
            text=text,
            language=self.language,
            entities=self.entities,
            score_threshold=self.score_threshold,
        )

        entities: list[Entity] = []
        for result in results:
            if (
                result.entity_type in PRESIDIO_HIGH_FP_TYPES
                and result.score < HIGH_FP_MIN_SCORE
            ):
                continue
            span_text = text[result.start:result.end]
            spacy_label = _PRESIDIO_NER_LABELS.get(result.entity_type)
            if spacy_label and is_false_positive(span_text, spacy_label):
                continue
            if result.entity_type == "DATE_TIME" and (
                _DURATION_RE.search(span_text) or not _is_specific_date(span_text)
            ):
                continue
            entity_type = self._map_entity_type(result.entity_type)

            entity = Entity(
                text=text[result.start:result.end],
                entity_type=entity_type,
                start=result.start,
                end=result.end,
                confidence=result.score,
                source="presidio",
                context=self._get_context(text, result.start, result.end),
                metadata={
                    "presidio_type": result.entity_type,
                    "recognizer": result.recognition_metadata.get(
                        "recognizer_name", "unknown"
                    ) if result.recognition_metadata else "unknown",
                },
            )
            entities.append(entity)

        return entities

    def detect_batch(self, texts: list[str]) -> list[list[Entity]]:
        """Detect entities in multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of entity lists, one per input text
        """
        return [self.detect(text) for text in texts]

    @property
    def supported_entity_types(self) -> list[EntityType]:
        """List of entity types this detector can find."""
        return list(set(PRESIDIO_TO_ENTITY_TYPE.values()))

    @classmethod
    def is_available(cls) -> bool:
        """Check if Presidio is available."""
        return PRESIDIO_AVAILABLE


