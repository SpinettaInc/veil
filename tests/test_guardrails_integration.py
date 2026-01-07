"""Tests for Guardrails AI integration."""

import pytest

from veil.integrations.guardrails import (
    GUARDRAILS_AVAILABLE,
    VeilPIIValidator,
    VeilAnonymizer,
    create_veil_guard,
)

# Skip all tests if Guardrails AI is not available
pytestmark = pytest.mark.skipif(
    not GUARDRAILS_AVAILABLE,
    reason="Guardrails AI not installed"
)


if GUARDRAILS_AVAILABLE:
    from guardrails import Guard, OnFailAction


class TestVeilPIIValidator:
    """Tests for VeilPIIValidator."""

    def test_validator_detects_email(self):
        """Test validator detects email addresses."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="balanced",
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("Contact me at test@example.com")

        assert result.validation_passed is True
        assert "[EMAIL" in result.validated_output
        assert "test@example.com" not in result.validated_output

    def test_validator_detects_phone(self):
        """Test validator detects phone numbers."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="paranoid",
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("Call me at 555-123-4567")

        assert result.validation_passed is True

    def test_validator_detects_ssn(self):
        """Test validator detects SSN."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="balanced",
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("SSN: 123-45-6789")

        assert result.validation_passed is True
        assert "123-45-6789" not in result.validated_output

    def test_validator_noop_reports_but_keeps_text(self):
        """Test NOOP action reports PII but keeps original text."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="balanced",
                on_fail=OnFailAction.NOOP
            )
        )

        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is False
        assert result.validated_output == "Email: test@example.com"
        assert len(result.validation_summaries) > 0

    def test_validator_passes_clean_text(self):
        """Test validator passes text without PII."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="paranoid",
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("Hello world, this is a test message.")

        assert result.validation_passed is True
        assert result.validated_output == "Hello world, this is a test message."

    def test_validator_paranoid_profile(self):
        """Test paranoid profile detects more entities."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="paranoid",
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("John Smith works at Acme Corp in New York")

        # Paranoid should detect person, org, location
        assert result.validation_passed is True
        # Check that entities were replaced
        original_text = "John Smith works at Acme Corp in New York"
        assert result.validated_output != original_text

    def test_validator_minimal_profile(self):
        """Test minimal profile is less aggressive."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="minimal",
                on_fail=OnFailAction.NOOP
            )
        )

        # With minimal profile, common names might not be detected
        result = guard.validate("Email me at test@example.com")

        # Email should still be detected even in minimal mode
        assert result.validation_passed is False

    def test_validator_faker_replacement(self):
        """Test faker replacement mode."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="balanced",
                replacement_mode="faker",
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is True
        # Faker mode should produce a realistic-looking email
        assert "@" in result.validated_output
        assert "test@example.com" not in result.validated_output

    def test_validator_token_replacement(self):
        """Test token replacement mode."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="balanced",
                replacement_mode="token",
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is True
        assert "[EMAIL" in result.validated_output

    def test_validator_hybrid_detection_mode(self):
        """Test hybrid detection mode."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="balanced",
                detection_mode="hybrid",
                use_presidio=True,
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("Contact John at john@test.com")

        assert result.validation_passed is True
        assert "john@test.com" not in result.validated_output

    def test_validator_standard_detection_mode(self):
        """Test standard detection mode (no Presidio)."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="balanced",
                detection_mode="standard",
                use_presidio=False,
                on_fail=OnFailAction.FIX
            )
        )

        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is True
        assert "test@example.com" not in result.validated_output

    def test_validator_min_entities_threshold(self):
        """Test min_entities threshold."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="balanced",
                min_entities=5,  # Require at least 5 entities
                on_fail=OnFailAction.NOOP
            )
        )

        # Only 1 entity, should pass
        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is True

    def test_validator_specific_entity_types(self):
        """Test filtering by specific entity types."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="paranoid",
                entity_types=["EMAIL"],  # Only detect emails
                on_fail=OnFailAction.NOOP
            )
        )

        # Should detect email but not SSN
        result = guard.validate("Email: test@example.com, SSN: 123-45-6789")

        assert result.validation_passed is False
        # Check that it found email
        error_str = str(result.validation_summaries[0])
        assert "EMAIL" in error_str


class TestVeilAnonymizer:
    """Tests for VeilAnonymizer (always anonymize)."""

    def test_anonymizer_always_anonymizes(self):
        """Test anonymizer always processes text."""
        guard = Guard().use(VeilAnonymizer(profile="paranoid"))

        result = guard.validate("John Smith at john@example.com")

        assert result.validation_passed is True
        assert "John Smith" not in result.validated_output
        assert "john@example.com" not in result.validated_output

    def test_anonymizer_passes_clean_text(self):
        """Test anonymizer passes clean text unchanged."""
        guard = Guard().use(VeilAnonymizer(profile="balanced"))

        result = guard.validate("Hello world")

        assert result.validation_passed is True
        assert result.validated_output == "Hello world"

    def test_anonymizer_with_faker(self):
        """Test anonymizer with faker replacement."""
        guard = Guard().use(
            VeilAnonymizer(
                profile="balanced",
                replacement_mode="faker"
            )
        )

        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is True
        assert "@" in result.validated_output
        assert "test@example.com" not in result.validated_output


class TestCreateVeilGuard:
    """Tests for create_veil_guard convenience function."""

    def test_create_guard_default(self):
        """Test creating guard with defaults."""
        guard = create_veil_guard()

        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is True
        assert "test@example.com" not in result.validated_output

    def test_create_guard_paranoid(self):
        """Test creating guard with paranoid profile."""
        guard = create_veil_guard(profile="paranoid")

        result = guard.validate("John Smith works at Acme")

        assert result.validation_passed is True

    def test_create_guard_faker_mode(self):
        """Test creating guard with faker mode."""
        guard = create_veil_guard(replacement_mode="faker")

        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is True
        assert "@" in result.validated_output

    def test_create_guard_noop_action(self):
        """Test creating guard with NOOP action."""
        guard = create_veil_guard(on_fail=OnFailAction.NOOP)

        result = guard.validate("Email: test@example.com")

        assert result.validation_passed is False
        assert result.validated_output == "Email: test@example.com"


class TestGuardrailsAvailability:
    """Tests for GUARDRAILS_AVAILABLE flag."""

    def test_guardrails_available(self):
        """Test GUARDRAILS_AVAILABLE is True when installed."""
        assert GUARDRAILS_AVAILABLE is True


class TestMultiplePII:
    """Tests for text with multiple PII entities."""

    def test_multiple_entities(self):
        """Test handling multiple PII entities."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="paranoid",
                on_fail=OnFailAction.FIX
            )
        )

        text = """
        Patient: John Smith
        Email: john.smith@hospital.org
        Phone: 555-123-4567
        SSN: 123-45-6789
        Address: 123 Main St, New York, NY 10001
        """

        result = guard.validate(text)

        assert result.validation_passed is True
        # Original PII should be removed
        assert "John Smith" not in result.validated_output
        assert "john.smith@hospital.org" not in result.validated_output
        assert "555-123-4567" not in result.validated_output
        assert "123-45-6789" not in result.validated_output

    def test_medical_record(self):
        """Test with medical record text."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="paranoid",
                on_fail=OnFailAction.FIX
            )
        )

        text = "Patient Jane Doe, DOB: 1985-03-15, diagnosed with flu"

        result = guard.validate(text)

        assert result.validation_passed is True

    def test_mixed_language(self):
        """Test with mixed language text."""
        guard = Guard().use(
            VeilPIIValidator(
                profile="paranoid",
                on_fail=OnFailAction.FIX
            )
        )

        text = "連絡先: test@example.com, 電話: 090-1234-5678"

        result = guard.validate(text)

        assert result.validation_passed is True
        assert "test@example.com" not in result.validated_output
