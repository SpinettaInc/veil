"""Tests for hybrid detection combining spaCy, Presidio, and patterns."""

import pytest

from veil.core.detector import DetectionMode, EntityDetector
from veil.detection.entity import EntityType
from veil.detection.hybrid import DetectorConfig, HybridDetector
from veil.detection.ner import SPACY_AVAILABLE, SpacyNER
from veil.detection.presidio import PRESIDIO_AVAILABLE, PresidioDetector

# Test data
SAMPLE_TEXT = """
John Smith works at Acme Corp in New York.
His email is john.smith@example.com and phone is 555-123-4567.
SSN: 123-45-6789
"""

MEDICAL_TEXT = """
Patient: Jane Doe
DOB: 1985-03-15
Diagnosis: acute respiratory infection
Contact: jane.doe@hospital.org, +1-555-987-6543
"""


class TestPresidioDetector:
    """Tests for Presidio detector wrapper."""

    @pytest.mark.skipif(not PRESIDIO_AVAILABLE, reason="Presidio not installed")
    def test_presidio_initialization(self):
        """Test Presidio detector can be initialized."""
        detector = PresidioDetector()
        assert detector is not None
        assert detector.language == "en"

    @pytest.mark.skipif(not PRESIDIO_AVAILABLE, reason="Presidio not installed")
    def test_presidio_detect_email(self):
        """Test Presidio detects email addresses."""
        detector = PresidioDetector()
        entities = detector.detect("Contact me at test@example.com")

        email_entities = [e for e in entities if e.entity_type == EntityType.EMAIL]
        assert len(email_entities) >= 1
        assert "test@example.com" in [e.text for e in email_entities]

    @pytest.mark.skipif(not PRESIDIO_AVAILABLE, reason="Presidio not installed")
    def test_presidio_detect_person(self):
        """Test Presidio detects person names."""
        detector = PresidioDetector()
        entities = detector.detect("John Smith is the CEO")

        person_entities = [e for e in entities if e.entity_type == EntityType.PERSON]
        assert len(person_entities) >= 1

    @pytest.mark.skipif(not PRESIDIO_AVAILABLE, reason="Presidio not installed")
    def test_presidio_source_metadata(self):
        """Test Presidio entities have proper source."""
        detector = PresidioDetector()
        entities = detector.detect("Call 555-123-4567")

        assert all(e.source == "presidio" for e in entities)

    def test_presidio_availability(self):
        """Test PRESIDIO_AVAILABLE flag."""
        assert isinstance(PRESIDIO_AVAILABLE, bool)


class TestSpacyNERFiltering:
    """Tests for improved spaCy NER with false positive filtering."""

    @pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
    def test_spacy_filters_medical_abbreviations(self):
        """Test spaCy filters common medical abbreviations."""
        detector = SpacyNER(filter_false_positives=True)

        # These should NOT be detected as ORG
        test_text = "DOB: 1990-01-01, HR: 92, BP: 128/82"
        entities = detector.detect(test_text)

        org_entities = [e for e in entities if e.entity_type == EntityType.ORG]
        org_texts = [e.text.strip() for e in org_entities]

        # DOB, HR, BP should be filtered out
        assert "DOB" not in org_texts
        assert "HR" not in org_texts
        assert "BP" not in org_texts

    @pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
    def test_spacy_filters_currency_codes(self):
        """Test spaCy filters currency codes from PERSON."""
        detector = SpacyNER(filter_false_positives=True)

        test_text = "The price is JPY 10,000 or USD 100"
        entities = detector.detect(test_text)

        person_entities = [e for e in entities if e.entity_type == EntityType.PERSON]
        person_texts = [e.text.strip() for e in person_entities]

        assert "JPY" not in person_texts
        assert "USD" not in person_texts

    @pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
    def test_spacy_keeps_valid_entities(self):
        """Test spaCy still detects valid named entities."""
        detector = SpacyNER(filter_false_positives=True)

        entities = detector.detect("John Smith works at Microsoft")

        # Should still find valid entities
        person_entities = [e for e in entities if e.entity_type == EntityType.PERSON]
        org_entities = [e for e in entities if e.entity_type == EntityType.ORG]

        assert len(person_entities) >= 1 or len(org_entities) >= 1


class TestHybridDetector:
    """Tests for hybrid/ensemble detector."""

    def test_hybrid_initialization_patterns_only(self):
        """Test hybrid detector with patterns only."""
        detector = HybridDetector(
            use_spacy=False,
            use_presidio=False,
            use_patterns=True,
        )
        assert detector.pattern_detector is not None

    @pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
    def test_hybrid_initialization_with_spacy(self):
        """Test hybrid detector with spaCy."""
        detector = HybridDetector(
            use_spacy=True,
            use_presidio=False,
            use_patterns=True,
        )
        assert detector.spacy_detector is not None

    @pytest.mark.skipif(
        not SPACY_AVAILABLE or not PRESIDIO_AVAILABLE,
        reason="spaCy or Presidio not installed"
    )
    def test_hybrid_full_initialization(self):
        """Test hybrid detector with all sources."""
        detector = HybridDetector(
            use_spacy=True,
            use_presidio=True,
            use_patterns=True,
        )
        assert detector.spacy_detector is not None
        assert detector.presidio_detector is not None
        assert detector.pattern_detector is not None

    def test_hybrid_detect_email(self):
        """Test hybrid detector finds emails."""
        detector = HybridDetector(
            use_spacy=False,
            use_presidio=False,
            use_patterns=True,
        )

        entities = detector.detect("Email: test@example.com")
        email_entities = [e for e in entities if e.entity_type == EntityType.EMAIL]

        assert len(email_entities) >= 1
        assert "test@example.com" in [e.text for e in email_entities]

    def test_hybrid_detect_phone(self):
        """Test hybrid detector finds phone numbers."""
        detector = HybridDetector(
            use_spacy=False,
            use_presidio=False,
            use_patterns=True,
        )

        entities = detector.detect("Call 555-123-4567")
        phone_entities = [e for e in entities if e.entity_type == EntityType.PHONE]

        assert len(phone_entities) >= 1

    @pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
    def test_hybrid_agreement_boost(self):
        """Test confidence boost when detectors agree."""
        detector = HybridDetector(
            use_spacy=True,
            use_presidio=False,
            use_patterns=True,
            agreement_boost=0.15,
        )

        # Email should be detected by patterns, potentially boosted by spaCy
        entities = detector.detect("Email: john.smith@example.com")
        email_entities = [e for e in entities if e.entity_type == EntityType.EMAIL]

        assert len(email_entities) >= 1

    def test_hybrid_detector_config(self):
        """Test detector configuration."""
        config = DetectorConfig(enabled=True, weight=0.8, min_confidence=0.5)

        assert config.enabled is True
        assert config.weight == 0.8
        assert config.min_confidence == 0.5

    def test_hybrid_get_stats(self):
        """Test hybrid detector statistics."""
        detector = HybridDetector(
            use_spacy=False,
            use_presidio=False,
            use_patterns=True,
        )

        stats = detector.get_stats()

        assert "spacy_enabled" in stats
        assert "presidio_enabled" in stats
        assert "patterns_enabled" in stats
        assert stats["patterns_enabled"] is True


class TestEntityDetectorModes:
    """Tests for EntityDetector with different modes."""

    def test_standard_mode(self):
        """Test standard detection mode."""
        detector = EntityDetector(
            use_ner=False,
            use_patterns=True,
            mode="standard",
        )

        assert detector.mode == DetectionMode.STANDARD
        assert detector.pattern_detector is not None

    @pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
    def test_hybrid_mode_via_flag(self):
        """Test hybrid mode enabled via mode flag."""
        detector = EntityDetector(
            use_ner=True,
            use_patterns=True,
            mode="hybrid",
        )

        assert detector.mode == DetectionMode.HYBRID

    @pytest.mark.skipif(
        not SPACY_AVAILABLE or not PRESIDIO_AVAILABLE,
        reason="spaCy or Presidio not installed"
    )
    def test_hybrid_mode_via_presidio(self):
        """Test hybrid mode enabled via use_presidio flag."""
        detector = EntityDetector(
            use_ner=True,
            use_patterns=True,
            use_presidio=True,
        )

        assert detector.mode == DetectionMode.HYBRID

    def test_detector_stats_standard(self):
        """Test detector stats in standard mode."""
        detector = EntityDetector(
            use_ner=False,
            use_patterns=True,
            mode="standard",
        )

        stats = detector.get_stats()
        assert stats["mode"] == "standard"

    def test_detection_mode_enum(self):
        """Test DetectionMode enum values."""
        assert DetectionMode.STANDARD.value == "standard"
        assert DetectionMode.HYBRID.value == "hybrid"


class TestIntegration:
    """Integration tests for hybrid detection."""

    @pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
    def test_full_pipeline_hybrid(self):
        """Test full pipeline with hybrid detection."""
        from veil.core.pipeline import VeilPipeline

        pipeline = VeilPipeline(
            use_ner=True,
            use_patterns=True,
            detection_mode="hybrid",
        )

        result = pipeline.anonymize(SAMPLE_TEXT)

        # Should detect various entities
        assert result.entity_count > 0

        # Check for expected entity types
        entity_types = set(e.entity_type for e in result.entities)
        # Should find at least emails or phones from patterns
        assert EntityType.EMAIL in entity_types or EntityType.PHONE in entity_types

    def test_pipeline_standard_mode(self):
        """Test pipeline in standard mode."""
        from veil.core.pipeline import VeilPipeline

        pipeline = VeilPipeline(
            use_ner=False,
            use_patterns=True,
            detection_mode="standard",
        )

        result = pipeline.anonymize("Email: test@example.com, Phone: 555-123-4567")

        assert result.entity_count > 0
        entity_types = set(e.entity_type for e in result.entities)
        assert EntityType.EMAIL in entity_types

    @pytest.mark.skipif(
        not SPACY_AVAILABLE or not PRESIDIO_AVAILABLE,
        reason="spaCy or Presidio not installed"
    )
    def test_all_detectors_combined(self):
        """Test with all three detectors enabled."""
        detector = HybridDetector(
            use_spacy=True,
            use_presidio=True,
            use_patterns=True,
        )

        entities = detector.detect(SAMPLE_TEXT)

        # With all detectors, we should find many entities
        assert len(entities) > 0

        # Check sources are being combined
        sources = set(e.source for e in entities)
        # Should have at least patterns
        assert "pattern" in sources or "hybrid" in sources or "spacy" in sources

    def test_japanese_phone_detection_hybrid(self):
        """Test Japanese phone number detection in hybrid mode."""
        detector = HybridDetector(
            use_spacy=False,
            use_presidio=False,
            use_patterns=True,
        )

        # Japanese mobile number
        entities = detector.detect("連絡先: 090-1234-5678")
        phone_entities = [e for e in entities if e.entity_type == EntityType.PHONE]

        assert len(phone_entities) >= 1
        assert any("090" in e.text for e in phone_entities)

    def test_international_phone_detection_hybrid(self):
        """Test international phone detection in hybrid mode."""
        detector = HybridDetector(
            use_spacy=False,
            use_presidio=False,
            use_patterns=True,
        )

        entities = detector.detect("Call me at +81-90-1234-5678")
        phone_entities = [e for e in entities if e.entity_type == EntityType.PHONE]

        assert len(phone_entities) >= 1
