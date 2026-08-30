"""spaCy-based Named Entity Recognition for detecting sensitive entities."""

import re

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
        # Form/field labels
        "Name", "Email", "Phone", "Fax", "Tel", "Address", "Subject", "Re",
        "Sincerely", "Regards", "Thanks", "Dear", "Attn", "Patient", "Customer",
        # Sentence-initial verbs/greetings spaCy mistakes for first names
        "Reach", "Call", "Contact", "Send", "Meet", "Please", "Best", "Hi", "Hello",
        "Note", "See", "Use", "Set", "Take", "Ask", "Tell", "Ping", "Text", "Ship",
        "Thank", "Cheers", "Kind", "Warm", "Yours",
    },
    # Common words misdetected as GPE/LOC
    "GPE": {
        "Test", "Example", "Sample", "Fake", "Demo", "Dummy", "Mock",
        "N", "S", "E", "W", "NW", "NE", "SW", "SE",  # Compass points in addresses
        "Q1", "Q2", "Q3", "Q4",  # Fiscal quarters
    },
    "LOC": {
        "Test", "Example", "Sample", "Fake", "Demo", "Dummy", "Mock",
        "N", "S", "E", "W", "NW", "NE", "SW", "SE",
    },
    # Single letters often misdetected
    "CARDINAL": set(),  # Will be handled by length check
    "DATE": set(),  # Will be handled by pattern check
}

# Regex patterns for entities that look like false positives
FALSE_POSITIVE_REGEXES: dict[str, list[re.Pattern[str]]] = {
    # Measurements often detected as ORG
    "ORG": [
        re.compile(r"^v?\d+(?:\.\d+)+$", re.IGNORECASE),  # Version strings like v1.2.3
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
    # Bare numbers that spaCy labels MONEY without any currency marker
    "MONEY": [
        re.compile(r"^[\d.,\s-]+$"),
    ],
}

# Numbered infrastructure ("Highway 101", "Gate 12") is not an identifying place
_NUMBERED_PLACE_RE = re.compile(
    r"^(?:highway|hwy|route|rte|interstate|i-|exit|gate|room|floor|terminal|platform|pier)"
    r"\s*-?\s*\d+\w*$",
    re.IGNORECASE,
)
for _label in ("FAC", "LOC", "GPE"):
    FALSE_POSITIVE_REGEXES.setdefault(_label, []).append(_NUMBERED_PLACE_RE)

# A DATE is only worth anonymizing when it pins down a specific day: it needs
# a month name plus a number, or a numeric day/month/year triple. Relative or
# coarse expressions ("yesterday", "Friday", "2019", "3-5 days") are dropped.
_MONTH_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b", re.IGNORECASE
)
_NUMERIC_DATE_RE = re.compile(r"\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b")
_DURATION_RE = re.compile(
    r"\b(?:second|minute|hour|day|week|month|year|decade|century)s?\b|\bago\b",
    re.IGNORECASE,
)


def _is_specific_date(text: str) -> bool:
    if _NUMERIC_DATE_RE.search(text):
        return True
    return bool(_MONTH_RE.search(text) and re.search(r"\d", text))


def _is_clock_time(text: str) -> bool:
    return bool(re.search(r"\d{1,2}:\d{2}|\d\s*(?:am|pm)\b", text, re.IGNORECASE))


_MODEL_CACHE: dict[tuple[str, bool], "Language"] = {}

# Everything the pipeline does not need for doc.ents
NON_NER_PIPES = ["parser", "tagger", "attribute_ruler", "lemmatizer", "textcat"]


def load_spacy_model(model_name: str, lean: bool = True) -> "Language":
    """Load a spaCy model once per process and share it.

    Args:
        model_name: spaCy package name
        lean: Disable every component except tok2vec + ner. Use ``False`` when
            the same object must also serve Presidio, whose context scoring
            needs lemmas.

    Returns:
        The shared ``Language`` instance
    """
    key = (model_name, lean)
    nlp = _MODEL_CACHE.get(key)
    if nlp is None:
        nlp = spacy.load(model_name, disable=NON_NER_PIPES if lean else [])
        _MODEL_CACHE[key] = nlp
    return nlp


_ORG_LABEL_WORDS = frozenset({
    "Account", "Issue", "User", "Name", "Email", "Phone", "Customer", "Service",
    "Manager", "Support", "Sales", "Team", "Department", "Subject", "Invoice",
    "Senior", "Junior", "Lead", "Head", "Director", "Engineer", "Analyst", "Officer",
    "Assistant", "Representative", "Specialist", "Coordinator", "Consultant", "Staff",
})
_NEVER_ENTITY_WORDS = frozenset(
    {"N", "S", "E", "W", "NW", "NE", "SW", "SE", "Q1", "Q2", "Q3", "Q4"}
)
_BARE_TOKEN_RE = re.compile(r"^[\[<{]?\s*[A-Z][A-Z_]{1,30}[\s_-]*\d{1,6}\s*[\]>}]?$")


def _strip_possessive(text: str, end_char: int) -> tuple[str, int]:
    """spaCy often includes a trailing "'s" in a PERSON/ORG span; leave it in the text."""
    for suffix in ("'s", "’s"):
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)], end_char - len(suffix)
    return text, end_char


def is_false_positive(ent_text: str, label: str, min_entity_length: int = 2) -> bool:
    """Check whether an NER span with a spaCy-style label is a likely false positive.

    Shared by the spaCy and Presidio detectors (Presidio's NER is spaCy too).

    Args:
        ent_text: The entity text
        label: spaCy label (PERSON, ORG, GPE, LOC, NORP, DATE, TIME, MONEY, FAC, ...)
        min_entity_length: Spans shorter than this are dropped

    Returns:
        True if the entity should be filtered out
    """
    # Filter by minimum length
    if len(ent_text.strip()) < min_entity_length:
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

    # Common field labels / job-title phrases misdetected ("Customer Service Manager")
    if label == "ORG" and all(w in _ORG_LABEL_WORDS for w in text.split()):
        return True

    # Compass points and quarters are never products/orgs/places
    if text in _NEVER_ENTITY_WORDS:
        return True

    # Anything shaped like one of our own tokens ("PERSON_1", "[EMAIL_2]")
    if _BARE_TOKEN_RE.match(text):
        return True

    # Temporal expressions: keep only ones that identify a specific moment
    if label == "DATE" and (_DURATION_RE.search(text) or not _is_specific_date(text)):
        return True
    if label == "TIME" and (_DURATION_RE.search(text) or not _is_clock_time(text)):
        return True

    # NORP/LAW: a single capitalised token that spaCy only saw because it
    # started a sentence (e.g. "Connect", "Chapter 12") is not a group
    if label == "NORP" and " " not in text and text[1:].islower():
        return True

    return False


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
        model_name: str | None = None,
        context_window: int = 50,
        filter_false_positives: bool = True,
        min_entity_length: int = 2,
        full_pipeline: bool = False,
    ) -> None:
        """Initialize the spaCy NER detector.

        Args:
            model_name: Name of spaCy model to use. If None, tries to load
                       the best available model.
            context_window: Number of characters of context to capture
                           around each entity.
            filter_false_positives: Whether to filter common false positives
            min_entity_length: Minimum length for an entity to be valid
            full_pipeline: Load the complete pipeline (so ``nlp`` can be shared
                with Presidio) instead of the lean NER-only one; detection
                still only runs tok2vec + ner.

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
        self.full_pipeline = full_pipeline
        self.nlp = load_spacy_model(self.model_name, lean=not full_pipeline)
        self._disabled_pipes = [p for p in NON_NER_PIPES if p in self.nlp.pipe_names]

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
        """Load a spaCy model, reusing an already-loaded instance.

        Loading a model costs ~1s (and ~500MB for ``en_core_web_lg``), so
        instances are shared process-wide. The pipeline only reads ``doc.ents``,
        so everything except tok2vec + ner is disabled.

        Args:
            model_name: Name of the model to load

        Returns:
            Loaded spaCy language model
        """
        return load_spacy_model(model_name)

    def _pipe(self, texts: list[str]) -> list["Doc"]:
        """Batch variant of ``_run`` using ``nlp.pipe``."""
        if not self._disabled_pipes:
            return list(self.nlp.pipe(texts))
        with self.nlp.select_pipes(disable=self._disabled_pipes):
            return list(self.nlp.pipe(texts))

    def _run(self, text: str) -> "Doc":
        """Run only tok2vec + ner, whichever pipeline variant is loaded."""
        if not self._disabled_pipes:
            return self.nlp(text)
        with self.nlp.select_pipes(disable=self._disabled_pipes):
            return self.nlp(text)

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
        """Check if an entity is likely a false positive (see is_false_positive)."""
        if not self.filter_false_positives:
            return False
        return is_false_positive(ent_text, label, self.min_entity_length)


    def detect(self, text: str) -> list[Entity]:
        """Detect named entities in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected entities
        """
        if not text or not text.strip():
            return []

        doc = self._run(text)
        entities: list[Entity] = []

        for ent in doc.ents:
            ent_text, end_char = (
                _strip_possessive(ent.text, ent.end_char)
                if ent.label_ == "PERSON"
                else (ent.text, ent.end_char)
            )
            # Filter false positives
            if self._is_false_positive(ent_text, ent.label_):
                continue

            entity_type = SPACY_TO_ENTITY_TYPE.get(ent.label_, EntityType.UNKNOWN)

            entity = Entity(
                text=ent_text,
                entity_type=entity_type,
                start=ent.start_char,
                end=end_char,
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

        for doc, text in zip(self._pipe(texts), texts):
            entities: list[Entity] = []
            for ent in doc.ents:
                ent_text, end_char = (
                    _strip_possessive(ent.text, ent.end_char)
                    if ent.label_ == "PERSON"
                    else (ent.text, ent.end_char)
                )
                # Filter false positives
                if self._is_false_positive(ent_text, ent.label_):
                    continue

                entity_type = SPACY_TO_ENTITY_TYPE.get(ent.label_, EntityType.UNKNOWN)
                entity = Entity(
                    text=ent_text,
                    entity_type=entity_type,
                    start=ent.start_char,
                    end=end_char,
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
