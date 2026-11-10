"""Regex-based pattern detection for PII and sensitive data.

Patterns inspired by Microsoft Presidio and common PII detection rules.
"""

import ipaddress
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from veil.detection.entity import Entity, EntityType


@dataclass
class Pattern:
    """A regex pattern for detecting sensitive data.

    Attributes:
        name: Human-readable name for the pattern
        entity_type: Type of entity this pattern detects
        regex: Compiled regex pattern
        confidence: Base confidence score for matches
        validator: Optional function to validate matches
        context_patterns: Patterns that boost confidence when found nearby
        context_boost: Confidence added when a context pattern matches
        trim_to_valid: Retry a match the validator rejects with trailing
            groups removed (see the field comment)
        requires_context: Drop the match entirely unless a context pattern
            matches nearby. Use for loose patterns (any 8+ digit number, any
            5-digit number) that are only meaningful with a cue like
            "account" or "zip".
    """

    name: str
    entity_type: EntityType
    regex: re.Pattern[str]
    confidence: float = 0.9
    validator: Callable[[str], bool] | None = None
    context_patterns: list[re.Pattern[str]] | None = None
    context_boost: float = 0.1
    requires_context: bool = False
    label: str | None = None  # user-facing type name for CUSTOM patterns
    # When the validator rejects a match, retry with trailing
    # whitespace-separated groups removed. For greedy patterns that can
    # swallow the next word ("<IBAN> BIC", "<IBAN> EUR").
    trim_to_valid: bool = False


# Validation functions for specific patterns


def validate_luhn(number: str) -> bool:
    """Validate a number using the Luhn algorithm (credit cards, etc.)."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False

    # Luhn algorithm
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0


def validate_ssn(ssn: str) -> bool:
    """Validate US Social Security Number format."""
    # Remove separators
    digits = re.sub(r"[-\s]", "", ssn)
    if len(digits) != 9 or not digits.isdigit():
        return False

    # SSN cannot start with 000, 666, or 900-999
    area = int(digits[:3])
    if area == 0 or area == 666 or area >= 900:
        return False

    # Group number (middle 2 digits) cannot be 00
    if digits[3:5] == "00":
        return False

    # Serial number (last 4 digits) cannot be 0000
    if digits[5:] == "0000":
        return False

    return True


def validate_email(email: str) -> bool:
    """Basic email validation."""
    # Check for common invalid patterns
    if email.startswith(".") or email.endswith("."):
        return False
    if ".." in email:
        return False
    return "@" in email and "." in email.split("@")[-1]


def validate_iban(iban: str) -> bool:
    """Validate an IBAN with the ISO 7064 mod-97 check."""
    compact = re.sub(r"\s", "", iban).upper()
    if not 15 <= len(compact) <= 34 or not compact[:2].isalpha() or not compact[2:4].isdigit():
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(numeric) % 97 == 1


def validate_ipv6(candidate: str) -> bool:
    """Whether the candidate is a real IPv6 address.

    Needs a digit: "::" alone, or hex-looking identifiers around a scope
    operator ("cafe::bad"), are not addresses anyone wrote down.
    """
    if not any(ch.isdigit() for ch in candidate):
        return False
    try:
        ipaddress.IPv6Address(candidate)
    except ValueError:
        return False
    return True


def validate_phone(phone: str) -> bool:
    """Validate phone number has reasonable digit count."""
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15


# Pre-compiled regex patterns

_SSN_CUES = [
    re.compile(r"social\s*sec", re.IGNORECASE),
    re.compile(r"\bSSN\b", re.IGNORECASE),
]
_PHONE_CUES = [
    re.compile(
        r"\b(?:phones?|tel|telephone|call(?:s|ed|ing)?|mobile|cell(?:phone)?|contact|fax)\b"
        r"|連絡|電話",
        re.IGNORECASE,
    ),
]

PATTERNS: list[Pattern] = [
    # Email addresses
    Pattern(
        name="email",
        entity_type=EntityType.EMAIL,
        regex=re.compile(
            r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,}\b",
            re.IGNORECASE,
        ),
        confidence=0.95,
        validator=validate_email,
    ),
    # US Social Security Numbers
    Pattern(
        name="ssn",
        entity_type=EntityType.SSN,
        regex=re.compile(
            r"\b(?!000|666|9\d{2})\d{3}[-\s](?!00)\d{2}[-\s](?!0000)\d{4}\b"
        ),
        confidence=0.85,
        validator=validate_ssn,
        context_patterns=_SSN_CUES,
    ),
    # An unformatted nine-digit number is an order id far more often than an
    # SSN, so it needs a cue nearby
    Pattern(
        name="ssn_unformatted",
        entity_type=EntityType.SSN,
        regex=re.compile(r"\b(?!000|666|9\d{2})\d{3}(?!00)\d{2}(?!0000)\d{4}\b"),
        confidence=0.85,
        validator=validate_ssn,
        context_patterns=_SSN_CUES,
        requires_context=True,
    ),
    # Credit Card Numbers (major providers)
    Pattern(
        name="credit_card",
        entity_type=EntityType.CREDIT_CARD,
        regex=re.compile(
            r"\b(?:"
            r"4[0-9]{12}(?:[0-9]{3})?|"  # Visa
            r"5[1-5][0-9]{14}|"  # Mastercard
            r"2[2-7][0-9]{14}|"  # Mastercard 2-series
            r"3(?:0[0-5]|[68][0-9])[0-9]{11}|"  # Diners Club
            r"62[0-9]{14,17}|"  # UnionPay
            r"3[47][0-9]{13}|"  # Amex
            r"6(?:011|5[0-9]{2})[0-9]{12}|"  # Discover
            r"(?:2131|1800|35\d{3})\d{11}"  # JCB
            r")\b"
        ),
        confidence=0.8,
        validator=validate_luhn,
        context_patterns=[
            re.compile(r"credit\s*card", re.IGNORECASE),
            re.compile(r"card\s*number", re.IGNORECASE),
            re.compile(r"\bCC\b"),
            re.compile(r"visa|mastercard|amex|discover", re.IGNORECASE),
        ],
    ),
    # Credit card with separators
    Pattern(
        name="credit_card_formatted",
        entity_type=EntityType.CREDIT_CARD,
        regex=re.compile(
            r"\b\d{4}[-\s]\d{4,6}[-\s]\d{4,5}(?:[-\s]\d{3,4})?\b"
        ),
        confidence=0.8,
        validator=lambda x: 13 <= len(re.sub(r"[-\s]", "", x)) <= 19
        and validate_luhn(re.sub(r"[-\s]", "", x)),
        context_patterns=[
            re.compile(r"credit\s*card", re.IGNORECASE),
            re.compile(r"card\s*number", re.IGNORECASE),
        ],
    ),
    # US Phone Numbers
    Pattern(
        name="phone_us",
        entity_type=EntityType.PHONE,
        regex=re.compile(
            r"(?<![\w.+-])(?:\+?1[-.\s]?)?"
            r"(?:\([0-9]{3}\)\s?|[0-9]{3})[-.\s]?"
            r"[0-9]{3}[-.\s]?"
            r"[0-9]{4}\b"
        ),
        confidence=0.8,
        validator=validate_phone,
        context_patterns=_PHONE_CUES,
    ),
    # International Phone Numbers (no separators)
    Pattern(
        name="phone_international",
        entity_type=EntityType.PHONE,
        regex=re.compile(
            r"(?<![\w+])\+[1-9]\d{6,14}\b"
        ),
        confidence=0.85,
        validator=validate_phone,
    ),
    # International Phone with separators (+XX-XX-XXXX-XXXX format)
    Pattern(
        name="phone_international_formatted",
        entity_type=EntityType.PHONE,
        regex=re.compile(
            # two to five groups after the country code: "+44 7911 123456",
            # "+81-90-1234-5678", "+49 30 1234 5678"
            r"(?<![\w+])\+[1-9][0-9]{0,2}(?:[-.\s][0-9]{1,6}){2,5}\b"
        ),
        confidence=0.9,
        validator=validate_phone,
        context_patterns=_PHONE_CUES,
    ),
    # Japanese mobile phones (090/080/070-XXXX-XXXX)
    Pattern(
        name="phone_japan_mobile",
        entity_type=EntityType.PHONE,
        regex=re.compile(
            r"\b0[789]0[-.\s]?[0-9]{4}[-.\s]?[0-9]{4}\b"
        ),
        confidence=0.9,
        validator=validate_phone,
    ),
    # Japanese landlines (0X-XXXX-XXXX or 0XX-XXX-XXXX)
    Pattern(
        name="phone_japan_landline",
        entity_type=EntityType.PHONE,
        regex=re.compile(
            r"\b0[1-9][0-9]{0,2}[-.\s][0-9]{2,4}[-.\s][0-9]{4}\b"
        ),
        confidence=0.85,
        validator=validate_phone,
    ),
    # Generic phone with parentheses and various formats
    Pattern(
        name="phone_generic",
        entity_type=EntityType.PHONE,
        regex=re.compile(
            r"(?<![\w.+-])\(?\d{2,4}\)?[-.\s]\d{2,4}[-.\s]?\d{3,4}(?:[-.\s]?\d{1,4})?\b"
        ),
        confidence=0.7,
        validator=validate_phone,
        context_patterns=_PHONE_CUES,
        requires_context=True,
    ),
    # IPv4 Addresses
    Pattern(
        name="ip_address_v4",
        entity_type=EntityType.IP_ADDRESS,
        regex=re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        confidence=0.9,
    ),
    # IPv6 addresses: a permissive candidate ("::" compression anywhere, or
    # all eight groups), then the standard library decides
    Pattern(
        name="ip_address_v6",
        entity_type=EntityType.IP_ADDRESS,
        regex=re.compile(
            r"(?<![\w:.])(?:"
            r"(?:[0-9a-f]{1,4}(?::[0-9a-f]{1,4}){0,6})?::(?:[0-9a-f]{1,4}(?::[0-9a-f]{1,4}){0,6})?"
            r"|(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}"
            r")(?![\w:])",
            re.IGNORECASE,
        ),
        confidence=0.9,
        validator=validate_ipv6,
    ),
    # URLs
    Pattern(
        name="url",
        entity_type=EntityType.URL,
        regex=re.compile(
            r"\bhttps?://[^\s<>\"{}|\\^`\[\]]+",
            re.IGNORECASE,
        ),
        confidence=0.95,
    ),
    # IBAN (International Bank Account Number)
    Pattern(
        name="iban",
        entity_type=EntityType.IBAN,
        regex=re.compile(
            r"\b[A-Z]{2}[0-9]{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b",
            re.IGNORECASE,  # people type them in lower case; mod-97 keeps prose out
        ),
        confidence=0.9,
        validator=validate_iban,
        trim_to_valid=True,
        context_patterns=[
            re.compile(r"IBAN|bank\s*account|account\s*number", re.IGNORECASE),
        ],
    ),
    # US Passport Number
    Pattern(
        name="passport_us",
        entity_type=EntityType.PASSPORT,
        regex=re.compile(r"\b[A-Z][0-9]{8}\b"),
        confidence=0.6,  # Lower confidence - needs context
        context_patterns=[
            re.compile(r"passport", re.IGNORECASE),
        ],
        context_boost=0.3,
    ),
    # US Driver's License (generic pattern - varies by state)
    Pattern(
        name="drivers_license",
        entity_type=EntityType.DRIVER_LICENSE,
        regex=re.compile(r"\b[A-Z][0-9]{7,8}\b"),
        confidence=0.5,  # Low confidence without context
        context_patterns=[
            re.compile(r"driver'?s?\s*licen[cs]e|DL\s*#?|license\s*#", re.IGNORECASE),
        ],
        context_boost=0.4,
        requires_context=True,
    ),
    # Medical Record Number (generic pattern)
    Pattern(
        name="medical_record",
        entity_type=EntityType.MEDICAL_RECORD,
        regex=re.compile(r"\b(?:MRN|MR)[-:#\s]{0,3}[0-9]{6,10}\b", re.IGNORECASE),
        confidence=0.9,
        context_patterns=[
            re.compile(r"medical\s*record|patient\s*id|MRN", re.IGNORECASE),
        ],
    ),
    # Japanese postal codes (XXX-XXXX)
    Pattern(
        name="postal_code_japan",
        entity_type=EntityType.LOC,
        regex=re.compile(r"\b[0-9]{3}-[0-9]{4}\b"),
        confidence=0.8,
        context_patterns=[
            re.compile(r"address|postal|zip|〒|住所", re.IGNORECASE),
        ],
        requires_context=True,
    ),
    # US ZIP codes
    Pattern(
        name="postal_code_us",
        entity_type=EntityType.LOC,
        regex=re.compile(r"\b[0-9]{5}(?:-[0-9]{4})?\b"),
        confidence=0.6,
        context_patterns=[
            re.compile(r"\b(?:address|zip|postal|city|state)\b", re.IGNORECASE),
        ],
        context_boost=0.2,
        requires_context=True,
    ),
    # Date patterns (YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY)
    Pattern(
        name="date_iso",
        entity_type=EntityType.DATE,
        regex=re.compile(
            r"\b(?:19|20)[0-9]{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12][0-9]|3[01])(?!\d)"
        ),
        confidence=0.85,
        context_patterns=[
            re.compile(r"date|born|dob|birthday|expire|issued", re.IGNORECASE),
        ],
    ),
    # Date patterns with a four-digit year last (DD/MM/YYYY or MM/DD/YYYY)
    Pattern(
        name="date_dmy",
        entity_type=EntityType.DATE,
        regex=re.compile(
            r"\b(?:0?[1-9]|[12][0-9]|3[01])[-/.](?:0?[1-9]|[12][0-9]|3[01])[-/.](?:19|20)[0-9]{2}\b"
        ),
        confidence=0.85,
        context_patterns=[
            re.compile(r"date|born|dob|birthday|expire|issued|admitted", re.IGNORECASE),
        ],
    ),
    # Bank account numbers (generic)
    Pattern(
        name="bank_account",
        entity_type=EntityType.BANK_ACCOUNT,
        regex=re.compile(r"\b[0-9]{8,17}\b"),
        confidence=0.4,  # Low confidence without context
        context_patterns=[
            re.compile(r"\b(?:accounts?|bank(?:ing)?|acct|routing|swift)\b", re.IGNORECASE),
        ],
        context_boost=0.4,
        requires_context=True,
    ),
    # Street addresses (generic patterns)
    Pattern(
        name="address_street",
        entity_type=EntityType.LOC,
        regex=re.compile(
            # Street names are capitalised; only the suffix is case-insensitive.
            # With the whole pattern case-insensitive, "2 steps that way" is an address.
            r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}"
            r"(?i:St(?:reet)?|Ave(?:nue)?|Rd|Road|Blvd|Boulevard|Dr(?:ive)?|Ln|Lane|Way|Pl(?:ace)?|Ct|Court)\b",
        ),
        confidence=0.8,
        context_patterns=[
            re.compile(r"address|ship|mail|deliver|location|住所", re.IGNORECASE),
        ],
    ),
    # Japanese address format (X-X-X pattern)
    Pattern(
        name="address_japan_block",
        entity_type=EntityType.LOC,
        regex=re.compile(r"\b[0-9]{1,2}-[0-9]{1,2}-[0-9]{1,2}\b"),
        confidence=0.6,
        context_patterns=[
            re.compile(r"address|住所|cho|chome|丁目|番地", re.IGNORECASE),
        ],
        requires_context=True,
    ),
]


def pattern_from_dict(spec: dict[str, Any]) -> Pattern:
    """Build a Pattern from a profile-YAML ``custom_patterns`` entry.

    Keys: ``name`` (required), ``regex`` (required), ``entity_type`` (an
    EntityType name; unknown names become CUSTOM and the given label is kept
    in ``metadata``), ``confidence``, ``context`` (list of regexes),
    ``context_boost``, ``requires_context``.
    """
    name = spec["name"]
    label = str(spec.get("entity_type", "CUSTOM")).upper()
    try:
        entity_type = EntityType(label)
    except ValueError:
        entity_type = EntityType.CUSTOM
    context = spec.get("context") or []
    return Pattern(
        name=name,
        entity_type=entity_type,
        regex=re.compile(spec["regex"], re.IGNORECASE if spec.get("ignore_case", False) else 0),
        confidence=float(spec.get("confidence", 0.9)),
        context_patterns=[re.compile(c, re.IGNORECASE) for c in context] or None,
        context_boost=float(spec.get("context_boost", 0.1)),
        requires_context=bool(spec.get("requires_context", False)),
        label=label if entity_type == EntityType.CUSTOM else None,
    )


def _mask_tokens(text: str) -> str:
    """Blank out token-shaped strings, preserving offsets."""
    from veil.core.mapper import token_spans  # local import: mapper imports entity

    spans = token_spans(text)
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


class PatternDetector:
    """Detect sensitive data using regex patterns.

    This detector uses pre-defined regex patterns to find PII and other
    sensitive information like SSNs, credit cards, emails, phone numbers, etc.

    Attributes:
        patterns: List of patterns to use for detection
        context_window: Characters of context to check for context patterns
    """

    def __init__(
        self,
        patterns: list[Pattern] | None = None,
        context_window: int = 100,
    ) -> None:
        """Initialize the pattern detector.

        Args:
            patterns: Custom patterns to use. If None, uses default PATTERNS.
            context_window: Window size for checking context patterns.
        """
        self.patterns = list(patterns) if patterns is not None else list(PATTERNS)
        self.context_window = context_window

    def detect(self, text: str) -> list[Entity]:
        """Detect sensitive patterns in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected entities
        """
        if not text:
            return []

        entities: list[Entity] = []
        # Context cues must come from the user's words, not from tokens left by
        # an earlier pass ("[IP_ADDRESS_1]" must not make "30000" look like a ZIP)
        context_text = _mask_tokens(text)

        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                matched_text = match.group()
                end = match.end()

                # Skip if validator fails
                if pattern.validator and not pattern.validator(matched_text):
                    if not pattern.trim_to_valid:
                        continue
                    while re.search(r"\s", matched_text.strip()):
                        matched_text = matched_text.rsplit(None, 1)[0]
                        if pattern.validator(matched_text):
                            break
                    else:
                        continue
                    end = match.start() + len(matched_text)

                # Calculate confidence with context boost
                confidence = pattern.confidence
                if pattern.context_patterns:
                    context_start = max(0, match.start() - self.context_window)
                    context_end = min(len(text), end + self.context_window)
                    context = context_text[context_start:context_end]

                    has_context = any(
                        ctx_pattern.search(context) for ctx_pattern in pattern.context_patterns
                    )
                    if has_context:
                        confidence = min(1.0, confidence + pattern.context_boost)
                    elif pattern.requires_context:
                        continue

                entity = Entity(
                    text=matched_text,
                    entity_type=pattern.entity_type,
                    start=match.start(),
                    end=end,
                    confidence=confidence,
                    source="pattern",
                    context=self._get_context(text, match.start(), end),
                    metadata={"pattern_name": pattern.name, "label": pattern.label},
                )
                entities.append(entity)

        return entities

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Extract context around a match."""
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        return text[context_start:context_end]

    def add_pattern(self, pattern: Pattern) -> None:
        """Add a custom pattern to the detector.

        Args:
            pattern: Pattern to add
        """
        self.patterns.append(pattern)

    def remove_pattern(self, name: str) -> bool:
        """Remove a pattern by name.

        Args:
            name: Name of the pattern to remove

        Returns:
            True if pattern was found and removed
        """
        original_len = len(self.patterns)
        self.patterns = [p for p in self.patterns if p.name != name]
        return len(self.patterns) < original_len

    @property
    def supported_entity_types(self) -> list[EntityType]:
        """List of entity types this detector can find."""
        return list(set(p.entity_type for p in self.patterns))
