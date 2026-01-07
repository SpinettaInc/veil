"""spaCy-based Named Entity Recognition for detecting sensitive entities."""

import re
from typing import Optional

try:
    import spacy
    from spacy.language import Language
    from spacy.tokens import Doc

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    Language = None  # type: ignore
    Doc = None  # type: ignore

from veil.detection.entity import Entity, EntityType


# Mapping from spaCy entity labels to our EntityType
SPACY_TO_ENTITY_TYPE: dict[str, EntityType] = {
    "PERSON": EntityType.PERSON,
    "ORG": EntityType.ORG,
    "GPE": EntityType.GPE,
    "LOC": EntityType.LOC,
    "FAC": EntityType.FAC,
    "PRODUCT": EntityType.PRODUCT,
    "EVENT": EntityType.EVENT,
    "WORK_OF_ART": EntityType.WORK_OF_ART,
    "DATE": EntityType.DATE,
    "TIME": EntityType.TIME,
    "MONEY": EntityType.MONEY,
    "QUANTITY": EntityType.QUANTITY,
    "CARDINAL": EntityType.CARDINAL,
    "ORDINAL": EntityType.ORDINAL,
    "PERCENT": EntityType.PERCENT,
    "NORP": EntityType.NORP,
    "LANGUAGE": EntityType.LANGUAGE,
    "LAW": EntityType.LAW,
}

# Common false positives to filter out
# These are common abbreviations/words that spaCy often misclassifies
FALSE_POSITIVE_PATTERNS: dict[str, set[str]] = {
    # Medical/clinical abbreviations misdetected as ORG
    "ORG": {
        "DOB", "HR", "BP", "SpO2", "T", "ORS", "CMP", "CBC", "ER", "PRN",
        "MRN", "PID", "ID", "Ref", "PO", "Apt", "St", "Ave", "Rd", "Blvd",
        "Suite", "Dept", "Lab", "Org", "LLC", "Inc", "Ltd", "Corp",
    },
    # Currency codes misdetected as PERSON/ORG
    "PERSON": {
        "JPY", "USD", "EUR", "GBP", "CNY", "KRW", "AUD", "CAD", "CHF",
        "NZ", "HK", "TX", "NY", "CA", "WA", "FL", "IL",  # State abbreviations
    },
    # Common words misdetected as GPE/LOC
    "GPE": {
        "Test", "Example", "Sample", "Fake", "Demo", "Dummy", "Mock",
    },
    "LOC": {
        "Test", "Example", "Sample", "Fake", "Demo", "Dummy", "Mock",
    },
    # Single letters often misdetected
    "CARDINAL": set(),  # Will be handled by length check
    "DATE": set(),  # Will be handled by pattern check
}

# Regex patterns for entities that look like false positives
FALSE_POSITIVE_REGEXES: dict[str, list[re.Pattern]] = {
    # Measurements often detected as ORG
    "ORG": [
        re.compile(r"^\d+/\d+$"),  # Blood pressure like "128/82"
        re.compile(r"^\d+°[CF]$"),  # Temperature like "37°C"
        re.compile(r"^\d+mg$", re.IGNORECASE),  # Dosage
        re.compile(r"^\d+%$"),  # Percentage
    ],
    # Alphanumeric codes detected as PERSON
    "PERSON": [
        re.compile(r"^[A-Z]{2,4}$"),  # Pure uppercase abbreviations
        re.compile(r"^\d"),  # Starts with digit
        re.compile(r"^\$|^€|^£|^¥"),  # Currency symbols
    ],
}


class SpacyNER:
    """Named Entity Recognition using spaCy.

    This class wraps spaCy's NER capabilities to detect named entities
    like persons, organizations, locations, dates, etc.

    Attributes:
        model_name: Name of the spaCy model to use
        nlp: The loaded spaCy language model
    """

    # Default models in order of preference (larger = more accurate)
    DEFAULT_MODELS = [
        "en_core_web_trf",  # Transformer-based (most accurate)
        "en_core_web_lg",   # Large model
        "en_core_web_md",   # Medium model
        "en_core_web_sm",   # Small model (fastest)
    ]

    def __init__(
        self,
        model_name: Optional[str] = None,
        context_window: int = 50,
        filter_false_positives: bool = True,
        min_entity_length: int = 2,
    ) -> None:
        """Initialize the spaCy NER detector.

        Args:
            model_name: Name of spaCy model to use. If None, tries to load
                       the best available model.
            context_window: Number of characters of context to capture
                           around each entity.
            filter_false_positives: Whether to filter common false positives
            min_entity_length: Minimum length for an entity to be valid

        Raises:
            ImportError: If spaCy is not installed
            OSError: If no suitable spaCy model is found
        """
        if not SPACY_AVAILABLE:
            raise ImportError(
                "spaCy is not installed. Install it with: pip install spacy\n"
                "Then download a model: python -m spacy download en_core_web_sm"
            )

        self.context_window = context_window
        self.filter_false_positives = filter_false_positives
        self.min_entity_length = min_entity_length
        self.model_name = model_name or self._find_best_model()
        self.nlp = self._load_model(self.model_name)

    def _find_best_model(self) -> str:
        """Find the best available spaCy model.

        Returns:
            Name of the best available model

        Raises:
            OSError: If no model is found
        """
        for model_name in self.DEFAULT_MODELS:
            if spacy.util.is_package(model_name):
                return model_name

        raise OSError(
            "No spaCy model found. Install one with:\n"
            "  python -m spacy download en_core_web_sm\n"
            "For better accuracy, use:\n"
            "  python -m spacy download en_core_web_lg"
        )

    def _load_model(self, model_name: str) -> "Language":
        """Load a spaCy model.

        Args:
            model_name: Name of the model to load

        Returns:
            Loaded spaCy language model
        """
        # Disable components we don't need for NER to improve speed
        nlp = spacy.load(
            model_name,
            disable=["parser", "lemmatizer", "textcat"],
        )
        return nlp

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Extract context around an entity.

        Args:
            text: Full text
            start: Entity start position
            end: Entity end position

        Returns:
            Context string around the entity
        """
        context_start = max(0, start - self.context_window)
        context_end = min(len(text), end + self.context_window)
        return text[context_start:context_end]

    def _is_false_positive(self, ent_text: str, label: str) -> bool:
        """Check if an entity is likely a false positive.

        Args:
            ent_text: The entity text
            label: The spaCy label for the entity

        Returns:
            True if the entity should be filtered out
        """
        if not self.filter_false_positives:
            return False

        # Filter by minimum length
        if len(ent_text.strip()) < self.min_entity_length:
            return True

        # Check against known false positive patterns
        fp_set = FALSE_POSITIVE_PATTERNS.get(label, set())
        if ent_text.strip() in fp_set:
            return True

        # Check regex patterns
        fp_regexes = FALSE_POSITIVE_REGEXES.get(label, [])
        for pattern in fp_regexes:
            if pattern.match(ent_text.strip()):
                return True

        # Additional heuristics
        text = ent_text.strip()

        # Single uppercase words (2-4 chars) are often abbreviations, not entities
        if label in ("ORG", "PERSON") and text.isupper() and 2 <= len(text) <= 4:
            # Unless it matches known organization patterns
            if not any(text.endswith(suffix) for suffix in ("LLC", "Inc", "Ltd", "Corp")):
                return True

        # Pure numbers should not be PERSON or ORG
        if label in ("PERSON", "ORG") and text.replace(",", "").replace(".", "").isdigit():
            return True

        # Common field labels misdetected
        if label == "ORG" and text in ("Account", "Issue", "User", "Name", "Email", "Phone"):
            return True

        return False

    def detect(self, text: str) -> list[Entity]:
        """Detect named entities in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected entities
        """
        if not text or not text.strip():
            return []

        doc = self.nlp(text)
        entities: list[Entity] = []

        for ent in doc.ents:
            # Filter false positives
            if self._is_false_positive(ent.text, ent.label_):
                continue

            entity_type = SPACY_TO_ENTITY_TYPE.get(ent.label_, EntityType.UNKNOWN)

            entity = Entity(
                text=ent.text,
                entity_type=entity_type,
                start=ent.start_char,
                end=ent.end_char,
                confidence=self._estimate_confidence(ent),
                source="spacy",
                context=self._get_context(text, ent.start_char, ent.end_char),
                metadata={
                    "spacy_label": ent.label_,
                    "spacy_kb_id": ent.kb_id_ if ent.kb_id_ else None,
                    "filtered": False,
                },
            )
            entities.append(entity)

        return entities

    def _estimate_confidence(self, ent) -> float:  # type: ignore
        """Estimate confidence score for an entity.

        spaCy doesn't provide confidence scores directly for NER,
        so we use heuristics based on entity characteristics.

        Args:
            ent: spaCy entity span

        Returns:
            Estimated confidence score (0.0 to 1.0)
        """
        # Base confidence
        confidence = 0.85

        # Longer entities are often more reliable
        if len(ent.text) > 10:
            confidence += 0.05

        # Title case for PERSON/ORG typically indicates proper detection
        if ent.label_ in ("PERSON", "ORG") and ent.text.istitle():
            confidence += 0.05

        # All caps might be an acronym - slightly less confident
        if ent.text.isupper() and len(ent.text) <= 5:
            confidence -= 0.05

        return min(1.0, max(0.0, confidence))

    def detect_batch(self, texts: list[str]) -> list[list[Entity]]:
        """Detect entities in multiple texts efficiently.

        Uses spaCy's pipe() for batch processing.

        Args:
            texts: List of texts to analyze

        Returns:
            List of entity lists, one per input text
        """
        if not texts:
            return []

        results: list[list[Entity]] = []

        for doc, text in zip(self.nlp.pipe(texts), texts):
            entities: list[Entity] = []
            for ent in doc.ents:
                # Filter false positives
                if self._is_false_positive(ent.text, ent.label_):
                    continue

                entity_type = SPACY_TO_ENTITY_TYPE.get(ent.label_, EntityType.UNKNOWN)
                entity = Entity(
                    text=ent.text,
                    entity_type=entity_type,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=self._estimate_confidence(ent),
                    source="spacy",
                    context=self._get_context(text, ent.start_char, ent.end_char),
                    metadata={"spacy_label": ent.label_},
                )
                entities.append(entity)
            results.append(entities)

        return results

    @property
    def supported_entity_types(self) -> list[EntityType]:
        """List of entity types this detector can find."""
        return list(SPACY_TO_ENTITY_TYPE.values())
