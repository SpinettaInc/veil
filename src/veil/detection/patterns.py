"""Regex-based pattern detection for PII and sensitive data.

Patterns inspired by Microsoft Presidio and common PII detection rules.
"""

import re
from dataclasses import dataclass
from typing import Callable, Optional

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
    """

    name: str
    entity_type: EntityType
    regex: re.Pattern[str]
    confidence: float = 0.9
    validator: Optional[Callable[[str], bool]] = None
    context_patterns: list[re.Pattern[str]] | None = None


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


def validate_phone(phone: str) -> bool:
    """Validate phone number has reasonable digit count."""
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15


# Pre-compiled regex patterns

PATTERNS: list[Pattern] = [
    # Email addresses
    Pattern(
        name="email",
        entity_type=EntityType.EMAIL,
        regex=re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
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
            r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b"
        ),
        confidence=0.85,
        validator=validate_ssn,
        context_patterns=[
            re.compile(r"social\s*security", re.IGNORECASE),
            re.compile(r"\bSSN\b", re.IGNORECASE),
            re.compile(r"social\s*sec", re.IGNORECASE),
        ],
    ),
    # Credit Card Numbers (major providers)
    Pattern(
        name="credit_card",
        entity_type=EntityType.CREDIT_CARD,
        regex=re.compile(
            r"\b(?:"
            r"4[0-9]{12}(?:[0-9]{3})?|"  # Visa
            r"5[1-5][0-9]{14}|"  # Mastercard
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
            r"\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b"
        ),
        confidence=0.75,
        validator=lambda x: validate_luhn(re.sub(r"[-\s]", "", x)),
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
            r"\b(?:\+?1[-.\s]?)?"
            r"(?:\([0-9]{3}\)|[0-9]{3})[-.\s]?"
            r"[0-9]{3}[-.\s]?"
            r"[0-9]{4}\b"
        ),
        confidence=0.8,
        validator=validate_phone,
        context_patterns=[
            re.compile(r"phone|tel|call|mobile|cell", re.IGNORECASE),
            re.compile(r"contact", re.IGNORECASE),
        ],
    ),
    # International Phone Numbers (no separators)
    Pattern(
        name="phone_international",
        entity_type=EntityType.PHONE,
        regex=re.compile(
            r"\b\+[1-9]\d{6,14}\b"
        ),
        confidence=0.85,
        validator=validate_phone,
    ),
    # International Phone with separators (+XX-XX-XXXX-XXXX format)
    Pattern(
        name="phone_international_formatted",
        entity_type=EntityType.PHONE,
        regex=re.compile(
            r"\+[1-9][0-9]{0,2}[-.\s][0-9]{1,4}[-.\s][0-9]{2,4}[-.\s][0-9]{2,6}"
        ),
        confidence=0.9,
        validator=validate_phone,
        context_patterns=[
            re.compile(r"phone|tel|call|mobile|cell|contact|fax", re.IGNORECASE),
        ],
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
            r"\b\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{0,4}\b"
        ),
        confidence=0.7,
        validator=validate_phone,
        context_patterns=[
            re.compile(r"phone|tel|call|mobile|cell|contact|fax|連絡|電話", re.IGNORECASE),
        ],
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
    # IPv6 Addresses (simplified)
    Pattern(
        name="ip_address_v6",
        entity_type=EntityType.IP_ADDRESS,
        regex=re.compile(
            r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}\b",
            re.IGNORECASE,
        ),
        confidence=0.9,
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
            r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}(?:[A-Z0-9]?){0,16}\b",
            re.IGNORECASE,
        ),
        confidence=0.85,
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
    ),
    # Medical Record Number (generic pattern)
    Pattern(
        name="medical_record",
        entity_type=EntityType.MEDICAL_RECORD,
        regex=re.compile(r"\b(?:MRN|MR)[-:\s]?[0-9]{6,10}\b", re.IGNORECASE),
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
    ),
    # US ZIP codes
    Pattern(
        name="postal_code_us",
        entity_type=EntityType.LOC,
        regex=re.compile(r"\b[0-9]{5}(?:-[0-9]{4})?\b"),
        confidence=0.6,
        context_patterns=[
            re.compile(r"address|zip|postal|city|state", re.IGNORECASE),
        ],
    ),
    # Date patterns (YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY)
    Pattern(
        name="date_iso",
        entity_type=EntityType.DATE,
        regex=re.compile(
            r"\b(?:19|20)[0-9]{2}[-/][0-1]?[0-9][-/][0-3]?[0-9]\b"
        ),
        confidence=0.85,
        context_patterns=[
            re.compile(r"date|born|dob|birthday|expire|issued", re.IGNORECASE),
        ],
    ),
    # Bank account numbers (generic)
    Pattern(
        name="bank_account",
        entity_type=EntityType.BANK_ACCOUNT,
        regex=re.compile(r"\b[0-9]{8,17}\b"),
        confidence=0.4,  # Low confidence without context
        context_patterns=[
            re.compile(r"account|bank|acct|routing|swift", re.IGNORECASE),
        ],
    ),
    # Street addresses (generic patterns)
    Pattern(
        name="address_street",
        entity_type=EntityType.LOC,
        regex=re.compile(
            r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:St(?:reet)?|Ave(?:nue)?|Rd|Road|Blvd|Boulevard|Dr(?:ive)?|Ln|Lane|Way|Pl(?:ace)?|Ct|Court)\b",
            re.IGNORECASE,
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
    ),
]


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
        self.patterns = patterns if patterns is not None else PATTERNS
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

        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                matched_text = match.group()

                # Skip if validator fails
                if pattern.validator and not pattern.validator(matched_text):
                    continue

                # Calculate confidence with context boost
                confidence = pattern.confidence
                if pattern.context_patterns:
                    context_start = max(0, match.start() - self.context_window)
                    context_end = min(len(text), match.end() + self.context_window)
                    context = text[context_start:context_end]

                    for ctx_pattern in pattern.context_patterns:
                        if ctx_pattern.search(context):
                            confidence = min(1.0, confidence + 0.1)
                            break

                entity = Entity(
                    text=matched_text,
                    entity_type=pattern.entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    source="pattern",
                    context=self._get_context(text, match.start(), match.end()),
                    metadata={"pattern_name": pattern.name},
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
