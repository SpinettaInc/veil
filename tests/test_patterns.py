"""Tests for regex pattern detection."""

import pytest

from veil.detection.entity import EntityType
from veil.detection.patterns import (
    PatternDetector,
    validate_email,
    validate_luhn,
    validate_phone,
    validate_ssn,
)


class TestValidators:
    """Tests for validation functions."""

    def test_validate_luhn_valid_cards(self):
        """Test Luhn validation with valid card numbers."""
        valid_cards = [
            "4111111111111111",  # Visa test card
            "5500000000000004",  # Mastercard test card
            "340000000000009",   # Amex test card
            "6011000000000004",  # Discover test card
        ]

        for card in valid_cards:
            assert validate_luhn(card), f"Card {card} should be valid"

    def test_validate_luhn_invalid_cards(self):
        """Test Luhn validation with invalid card numbers."""
        invalid_cards = [
            "4111111111111112",  # Wrong check digit
            "1234567890123456",  # Random number
            "1234",              # Too short
        ]

        for card in invalid_cards:
            assert not validate_luhn(card), f"Card {card} should be invalid"

    def test_validate_ssn_valid(self):
        """Test SSN validation with valid SSNs."""
        valid_ssns = [
            "123-45-6789",
            "123456789",
            "123 45 6789",
        ]

        for ssn in valid_ssns:
            assert validate_ssn(ssn), f"SSN {ssn} should be valid"

    def test_validate_ssn_invalid(self):
        """Test SSN validation with invalid SSNs."""
        invalid_ssns = [
            "000-45-6789",  # Area cannot be 000
            "666-45-6789",  # Area cannot be 666
            "900-45-6789",  # Area cannot be 900-999
            "123-00-6789",  # Group cannot be 00
            "123-45-0000",  # Serial cannot be 0000
        ]

        for ssn in invalid_ssns:
            assert not validate_ssn(ssn), f"SSN {ssn} should be invalid"

    def test_validate_email_valid(self):
        """Test email validation with valid emails."""
        valid_emails = [
            "test@example.com",
            "user.name@company.co.uk",
            "admin+tag@domain.org",
        ]

        for email in valid_emails:
            assert validate_email(email), f"Email {email} should be valid"

    def test_validate_email_invalid(self):
        """Test email validation with invalid emails."""
        invalid_emails = [
            ".test@example.com",   # Starts with dot
            "test@example.com.",   # Ends with dot
            "test..name@example.com",  # Double dot
        ]

        for email in invalid_emails:
            assert not validate_email(email), f"Email {email} should be invalid"

    def test_validate_phone_valid(self):
        """Test phone validation with valid numbers."""
        valid_phones = [
            "555-123-4567",
            "(555) 123-4567",
            "+1-555-123-4567",
        ]

        for phone in valid_phones:
            assert validate_phone(phone), f"Phone {phone} should be valid"

    def test_validate_phone_invalid(self):
        """Test phone validation with invalid numbers."""
        invalid_phones = [
            "123",        # Too short
            "12345",      # Still too short
        ]

        for phone in invalid_phones:
            assert not validate_phone(phone), f"Phone {phone} should be invalid"


class TestPatternDetector:
    """Tests for PatternDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a pattern detector instance."""
        return PatternDetector()

    def test_detect_email(self, detector):
        """Test email detection."""
        text = "Contact us at support@example.com for help."
        entities = detector.detect(text)

        emails = [e for e in entities if e.entity_type == EntityType.EMAIL]
        assert len(emails) == 1
        assert emails[0].text == "support@example.com"

    def test_detect_multiple_emails(self, detector):
        """Test detection of multiple emails."""
        text = "Email john@example.com or jane@example.org"
        entities = detector.detect(text)

        emails = [e for e in entities if e.entity_type == EntityType.EMAIL]
        assert len(emails) == 2

    def test_detect_ssn(self, detector):
        """Test SSN detection."""
        text = "SSN: 123-45-6789"
        entities = detector.detect(text)

        ssns = [e for e in entities if e.entity_type == EntityType.SSN]
        assert len(ssns) == 1
        assert "123-45-6789" in ssns[0].text

    def test_detect_ssn_with_context_boost(self, detector):
        """Test that SSN context boosts confidence."""
        text_with_context = "Social Security Number: 123-45-6789"
        text_without_context = "Reference: 123-45-6789"

        entities_with = detector.detect(text_with_context)
        entities_without = detector.detect(text_without_context)

        ssn_with = [e for e in entities_with if e.entity_type == EntityType.SSN]
        ssn_without = [e for e in entities_without if e.entity_type == EntityType.SSN]

        assert len(ssn_with) == 1
        assert len(ssn_without) == 1
        assert ssn_with[0].confidence > ssn_without[0].confidence

    def test_detect_credit_card(self, detector):
        """Test credit card detection."""
        text = "Card number: 4111111111111111"
        entities = detector.detect(text)

        cards = [e for e in entities if e.entity_type == EntityType.CREDIT_CARD]
        assert len(cards) == 1
        assert cards[0].text == "4111111111111111"

    def test_detect_credit_card_with_separators(self, detector):
        """Test credit card with separators."""
        text = "Card: 4111-1111-1111-1111"
        entities = detector.detect(text)

        cards = [e for e in entities if e.entity_type == EntityType.CREDIT_CARD]
        assert len(cards) == 1

    def test_detect_phone_us(self, detector):
        """Test US phone number detection."""
        text = "Call us at 555-123-4567 for help"
        entities = detector.detect(text)

        phones = [e for e in entities if e.entity_type == EntityType.PHONE]
        assert len(phones) >= 1

    def test_detect_ip_address(self, detector):
        """Test IP address detection."""
        text = "Server IP: 192.168.1.100"
        entities = detector.detect(text)

        ips = [e for e in entities if e.entity_type == EntityType.IP_ADDRESS]
        assert len(ips) == 1
        assert ips[0].text == "192.168.1.100"

    def test_detect_url(self, detector):
        """Test URL detection."""
        text = "Visit https://www.example.com/page for more info."
        entities = detector.detect(text)

        urls = [e for e in entities if e.entity_type == EntityType.URL]
        assert len(urls) == 1
        assert "example.com" in urls[0].text

    def test_detect_empty_text(self, detector):
        """Test detection on empty text."""
        entities = detector.detect("")
        assert entities == []

    def test_detect_no_patterns(self, detector):
        """Test detection when no patterns match."""
        text = "This is a simple sentence."
        entities = detector.detect(text)
        assert len(entities) == 0

    def test_entity_positions(self, detector):
        """Test that entity positions are correct."""
        text = "Email: test@example.com here"
        entities = detector.detect(text)

        email = entities[0]
        assert text[email.start:email.end] == email.text

    def test_add_custom_pattern(self, detector):
        """Test adding a custom pattern."""
        import re

        from veil.detection.patterns import Pattern

        custom_pattern = Pattern(
            name="custom_id",
            entity_type=EntityType.CUSTOM,
            regex=re.compile(r"ID-[0-9]{6}"),
            confidence=0.95,
        )

        detector.add_pattern(custom_pattern)

        text = "Your ID-123456 is registered."
        entities = detector.detect(text)

        custom = [e for e in entities if e.entity_type == EntityType.CUSTOM]
        assert len(custom) == 1
        assert custom[0].text == "ID-123456"

    def test_remove_pattern(self, detector):
        """Test removing a pattern."""
        # First verify email detection works
        text = "test@example.com"
        assert any(e.entity_type == EntityType.EMAIL for e in detector.detect(text))

        # Remove email pattern
        removed = detector.remove_pattern("email")
        assert removed

        # Now email should not be detected
        assert not any(e.entity_type == EntityType.EMAIL for e in detector.detect(text))
