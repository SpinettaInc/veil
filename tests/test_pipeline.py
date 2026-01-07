"""Tests for the main Veil pipeline."""

import pytest

from veil.core.pipeline import VeilPipeline, anonymize
from veil.detection.entity import EntityType


class TestVeilPipeline:
    """Tests for VeilPipeline class."""

    @pytest.fixture
    def pipeline(self):
        """Create a pipeline with patterns only (no NER for faster tests)."""
        return VeilPipeline(use_ner=False, use_patterns=True)

    def test_pipeline_creation(self, pipeline):
        """Test pipeline is created successfully."""
        assert pipeline is not None
        assert pipeline.mapping_store is not None
        assert pipeline.detector is not None
        assert pipeline.replacement_engine is not None

    def test_anonymize_email(self, pipeline):
        """Test anonymizing email addresses."""
        text = "Contact me at test@example.com"
        result = pipeline.anonymize(text)

        assert "[EMAIL_1]" in result.anonymized_text
        assert "test@example.com" not in result.anonymized_text
        assert result.entity_count == 1

    def test_anonymize_multiple_entities(self, pipeline):
        """Test anonymizing multiple entities."""
        text = "Email: a@b.com and b@c.com, IP: 192.168.1.1"
        result = pipeline.anonymize(text)

        assert result.entity_count >= 3
        assert "[EMAIL_1]" in result.anonymized_text
        assert "[EMAIL_2]" in result.anonymized_text
        assert "[IP_ADDRESS_1]" in result.anonymized_text

    def test_anonymize_preserves_structure(self, pipeline):
        """Test that anonymization preserves text structure."""
        text = "Call (555) 123-4567 for support."
        result = pipeline.anonymize(text)

        # Should have phone replaced but structure preserved
        assert "Call" in result.anonymized_text
        assert "for support." in result.anonymized_text

    def test_anonymize_empty_text(self, pipeline):
        """Test anonymizing empty text."""
        result = pipeline.anonymize("")

        assert result.anonymized_text == ""
        assert result.entity_count == 0

    def test_anonymize_no_entities(self, pipeline):
        """Test anonymizing text with no entities."""
        text = "This is a simple sentence."
        result = pipeline.anonymize(text)

        assert result.anonymized_text == text
        assert result.entity_count == 0

    def test_replacements_dict(self, pipeline):
        """Test that replacements dictionary is populated."""
        text = "Email: test@example.com"
        result = pipeline.anonymize(text)

        assert "test@example.com" in result.replacements
        assert result.replacements["test@example.com"] == "[EMAIL_1]"

    def test_reconstruct(self, pipeline):
        """Test reconstructing anonymized text."""
        text = "Email: test@example.com"
        anon_result = pipeline.anonymize(text)

        recon_result = pipeline.reconstruct(anon_result.anonymized_text)

        assert recon_result.reconstructed_text == text
        assert recon_result.replacements_made == 1

    def test_reconstruct_empty_text(self, pipeline):
        """Test reconstructing empty text."""
        result = pipeline.reconstruct("")

        assert result.reconstructed_text == ""
        assert result.replacements_made == 0

    def test_process_convenience_method(self, pipeline):
        """Test the process convenience method."""
        text = "Contact: user@domain.com"
        anonymized, replacements = pipeline.process(text)

        assert "[EMAIL_1]" in anonymized
        assert "user@domain.com" in replacements

    def test_clear_mappings(self, pipeline):
        """Test clearing mappings."""
        text = "test@example.com"
        pipeline.anonymize(text)

        assert len(pipeline.mapping_store) > 0

        pipeline.clear_mappings()

        assert len(pipeline.mapping_store) == 0

    def test_get_mapping(self, pipeline):
        """Test getting a specific mapping."""
        text = "test@example.com"
        pipeline.anonymize(text)

        replacement = pipeline.get_mapping("test@example.com")
        assert replacement == "[EMAIL_1]"

        original = pipeline.get_original("[EMAIL_1]")
        assert original == "test@example.com"

    def test_get_stats(self, pipeline):
        """Test getting pipeline stats."""
        text = "test@example.com and 192.168.1.1"
        pipeline.anonymize(text)

        stats = pipeline.get_stats()

        assert "detector" in stats
        assert "mappings" in stats
        assert stats["mappings"]["total_mappings"] >= 1

    def test_mapping_persists_across_calls(self, pipeline):
        """Test that mappings persist across multiple anonymize calls."""
        # First call
        result1 = pipeline.anonymize("test@example.com is here")
        token1 = result1.replacements.get("test@example.com")

        # Second call with same email
        result2 = pipeline.anonymize("Contact test@example.com")

        # Should use same token
        assert token1 in result2.anonymized_text

    def test_entity_types_filter(self, pipeline):
        """Test filtering by entity types."""
        text = "test@example.com and 192.168.1.1"

        # Only detect emails
        result = pipeline.anonymize(text, entity_types=[EntityType.EMAIL])

        assert "[EMAIL_1]" in result.anonymized_text
        # IP should not be replaced
        assert "192.168.1.1" in result.anonymized_text


class TestAnonymizeFunction:
    """Tests for the convenience anonymize function."""

    def test_anonymize_function(self):
        """Test standalone anonymize function."""
        text = "Email: user@example.com"
        anonymized, replacements = anonymize(text, use_ner=False)

        assert "[EMAIL_1]" in anonymized
        assert "user@example.com" in replacements

    def test_anonymize_function_no_ner(self):
        """Test anonymize with NER disabled."""
        text = "John Smith at test@example.com"
        anonymized, replacements = anonymize(text, use_ner=False)

        # Email should be detected (pattern)
        assert "[EMAIL_1]" in anonymized
        # Person may or may not be detected depending on patterns


class TestPipelineWithNER:
    """Tests for pipeline with NER enabled.

    These tests are skipped if spaCy is not available.
    """

    @pytest.fixture
    def ner_pipeline(self):
        """Create a pipeline with NER enabled."""
        try:
            return VeilPipeline(use_ner=True, use_patterns=True)
        except (ImportError, OSError):
            pytest.skip("spaCy not available")

    def test_detect_person(self, ner_pipeline):
        """Test detecting person names with NER."""
        text = "John Smith works at the company."
        result = ner_pipeline.anonymize(text)

        # Should detect person name
        if result.entity_count > 0:
            assert "[PERSON_1]" in result.anonymized_text
            assert "John Smith" in result.replacements

    def test_detect_organization(self, ner_pipeline):
        """Test detecting organizations with NER."""
        text = "Microsoft announced new products."
        result = ner_pipeline.anonymize(text)

        # Organization detection depends on spaCy model
        # Just verify no errors occur
        assert result.anonymized_text is not None

    def test_combined_ner_and_patterns(self, ner_pipeline):
        """Test combining NER and pattern detection."""
        text = "John Smith's email is john@example.com"
        result = ner_pipeline.anonymize(text)

        # Should detect both person (NER) and email (pattern)
        assert "[EMAIL_1]" in result.anonymized_text
        # Person detection depends on model quality
