"""Tests for the semantic weighting engine."""

import pytest

from veil.detection.entity import Entity, EntityType
from veil.weighting.config import (
    DetectionProfile,
    WeightConfig,
    get_minimal_config,
    get_paranoid_config,
    get_profile_config,
)
from veil.weighting.context import ContextAnalyzer
from veil.weighting.scorer import PrivacyScore, PrivacyScorer
from veil.weighting.tfidf import DocumentStats, GlobalRarityScorer, RarityScorer


class TestWeightConfig:
    """Tests for weight configuration."""

    def test_default_config(self):
        """Test default weight config is created."""
        config = WeightConfig()

        assert config.threshold == 0.5
        assert config.rarity_factor == 0.1
        assert len(config.entity_weights) > 0
        assert len(config.pos_multipliers) > 0
        assert len(config.context_patterns) > 0

    def test_person_weight(self):
        """Test PERSON has high weight."""
        config = WeightConfig()
        weight = config.get_entity_weight(EntityType.PERSON)

        assert weight >= 0.9

    def test_ssn_weight(self):
        """Test SSN has maximum weight."""
        config = WeightConfig()
        weight = config.get_entity_weight(EntityType.SSN)

        assert weight == 1.0

    def test_pos_multipliers(self):
        """Test POS multipliers are set correctly."""
        config = WeightConfig()

        assert config.get_pos_multiplier("PROPN") > 1.0
        assert config.get_pos_multiplier("VERB") < 1.0
        assert config.get_pos_multiplier("UNKNOWN") == 1.0  # Default

    def test_get_profile_paranoid(self):
        """Test paranoid profile has lower threshold."""
        config = get_paranoid_config()

        assert config.threshold < 0.5
        assert config.rarity_factor > 0.1

    def test_get_profile_minimal(self):
        """Test minimal profile has higher threshold."""
        config = get_minimal_config()

        assert config.threshold > 0.5
        assert config.rarity_factor < 0.1


class TestDocumentStats:
    """Tests for document statistics."""

    def test_from_text(self):
        """Test creating stats from text."""
        text = "The quick brown fox jumps over the lazy dog"
        stats = DocumentStats.from_text(text)

        assert stats.total_terms == 9
        assert stats.unique_terms == 8  # "the" appears twice
        assert stats.term_frequency("the") == 2
        assert stats.term_frequency("fox") == 1

    def test_hapax(self):
        """Test hapax legomenon detection."""
        text = "hello world hello"
        stats = DocumentStats.from_text(text)

        assert not stats.is_hapax("hello")  # Appears twice
        assert stats.is_hapax("world")       # Appears once

    def test_normalized_frequency(self):
        """Test normalized term frequency."""
        text = "a a a b b c"
        stats = DocumentStats.from_text(text)

        assert stats.term_frequency_normalized("a") == 0.5
        assert stats.term_frequency_normalized("b") == pytest.approx(1/3, rel=0.01)

    def test_empty_text(self):
        """Test with empty text."""
        stats = DocumentStats.from_text("")

        assert stats.total_terms == 0
        assert stats.unique_terms == 0


class TestRarityScorer:
    """Tests for rarity scoring."""

    @pytest.fixture
    def scorer(self):
        """Create a rarity scorer."""
        return RarityScorer()

    @pytest.fixture
    def doc_stats(self):
        """Create sample document stats."""
        text = "John Smith works at Acme Corporation. John is the CEO."
        return DocumentStats.from_text(text)

    def test_rare_term_scores_higher(self, scorer, doc_stats):
        """Test that rare terms get higher scores."""
        rare_score = scorer.score("corporation", doc_stats)
        common_score = scorer.score("john", doc_stats)

        assert rare_score > common_score

    def test_unknown_term_max_score(self, scorer, doc_stats):
        """Test that unknown terms get maximum score."""
        score = scorer.score("xyzabc", doc_stats)

        assert score == scorer.max_score

    def test_multi_word_scoring(self, scorer, doc_stats):
        """Test scoring multi-word phrases."""
        score = scorer.score_multi_word("John Smith", doc_stats)

        assert 0 < score < 1


class TestGlobalRarityScorer:
    """Tests for global rarity scorer."""

    @pytest.fixture
    def scorer(self):
        """Create a global rarity scorer."""
        return GlobalRarityScorer()

    def test_common_word_penalty(self, scorer):
        """Test common words get penalized."""
        text = "the quick brown fox"
        stats = DocumentStats.from_text(text)

        the_score = scorer.score("the", stats)
        fox_score = scorer.score("fox", stats)

        assert the_score < fox_score

    def test_common_name_penalty(self, scorer):
        """Test common names get slight penalty."""
        text = "John Xyzanthropus met today"
        stats = DocumentStats.from_text(text)

        john_score = scorer.score("john", stats)
        unusual_score = scorer.score("xyzanthropus", stats)

        assert john_score < unusual_score


class TestContextAnalyzer:
    """Tests for context pattern analysis."""

    @pytest.fixture
    def analyzer(self):
        """Create a context analyzer with default patterns."""
        config = WeightConfig()
        return ContextAnalyzer.from_config(config)

    def test_detect_ceo_context(self, analyzer):
        """Test detecting CEO context pattern."""
        text = "CEO of Acme Corp announced today"
        entity = Entity(
            text="Acme Corp",
            entity_type=EntityType.ORG,
            start=7,
            end=16,
        )

        boost = analyzer.calculate_boost(entity, text)

        assert boost > 0

    def test_detect_patient_context(self, analyzer):
        """Test detecting patient context pattern."""
        text = "patient John Smith was diagnosed with flu"
        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=8,
            end=18,
        )

        boost = analyzer.calculate_boost(entity, text)

        assert boost > 0

    def test_no_context_no_boost(self, analyzer):
        """Test no boost when no context patterns match."""
        text = "Hello world this is a test"
        entity = Entity(
            text="world",
            entity_type=EntityType.UNKNOWN,
            start=6,
            end=11,
        )

        boost = analyzer.calculate_boost(entity, text)

        assert boost == 0


class TestPrivacyScorer:
    """Tests for the main privacy scorer."""

    @pytest.fixture
    def scorer(self):
        """Create a balanced profile scorer."""
        return PrivacyScorer(profile=DetectionProfile.BALANCED)

    def test_score_person(self, scorer):
        """Test scoring a person entity."""
        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )
        text = "John Smith works at Acme Corp"

        score = scorer.score_entity(entity, text)

        assert score.total_score > 0.5
        assert score.above_threshold
        assert len(score.contributing_factors) > 0

    def test_score_ssn(self, scorer):
        """Test SSN gets maximum score."""
        entity = Entity(
            text="123-45-6789",
            entity_type=EntityType.SSN,
            start=5,
            end=16,
        )
        text = "SSN: 123-45-6789"

        score = scorer.score_entity(entity, text)

        assert score.total_score >= 0.95
        assert score.above_threshold

    def test_context_boosts_score(self, scorer):
        """Test context patterns boost score."""
        entity = Entity(
            text="Jane Doe",
            entity_type=EntityType.PERSON,
            start=8,
            end=16,
        )

        # Without sensitive context
        text1 = "Hello Jane Doe how are you"
        score1 = scorer.score_entity(entity, text1)

        # With sensitive context
        entity2 = Entity(
            text="Jane Doe",
            entity_type=EntityType.PERSON,
            start=8,
            end=16,
        )
        text2 = "patient Jane Doe was diagnosed"
        score2 = scorer.score_entity(entity2, text2)

        assert score2.context_boost > score1.context_boost

    def test_score_entities_batch(self, scorer):
        """Test scoring multiple entities."""
        entities = [
            Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4),
            Entity(text="test@example.com", entity_type=EntityType.EMAIL, start=20, end=36),
        ]
        text = "John works at email: test@example.com"

        scores = scorer.score_entities(entities, text)

        assert len(scores) == 2
        assert all(isinstance(s, PrivacyScore) for s in scores)

    def test_filter_by_threshold(self, scorer):
        """Test filtering entities by threshold."""
        entities = [
            Entity(text="123-45-6789", entity_type=EntityType.SSN, start=0, end=11),
            Entity(text="hello", entity_type=EntityType.UNKNOWN, start=15, end=20),
        ]
        text = "123-45-6789 and hello world"

        filtered = scorer.filter_by_threshold(entities, text)

        # SSN should pass, generic word should not
        assert len(filtered) >= 1
        assert any(e.entity_type == EntityType.SSN for e in filtered)

    def test_to_dict(self, scorer):
        """Test PrivacyScore serialization."""
        entity = Entity(
            text="John",
            entity_type=EntityType.PERSON,
            start=0,
            end=4,
        )
        text = "John works here"

        score = scorer.score_entity(entity, text)
        data = score.to_dict()

        assert "entity_text" in data
        assert "total_score" in data
        assert "above_threshold" in data
        assert "factors" in data


class TestDetectionProfiles:
    """Tests for detection profiles."""

    def test_paranoid_more_sensitive(self):
        """Test paranoid profile is more sensitive."""
        paranoid = PrivacyScorer(profile=DetectionProfile.PARANOID)
        minimal = PrivacyScorer(profile=DetectionProfile.MINIMAL)

        entity = Entity(
            text="New York",
            entity_type=EntityType.GPE,
            start=0,
            end=8,
        )
        text = "New York is a city"

        paranoid.score_entity(entity, text)
        minimal.score_entity(entity, text)

        # Paranoid should have lower threshold, so more likely above
        assert paranoid.config.threshold < minimal.config.threshold

    def test_balanced_is_default(self):
        """Test balanced is the default profile."""
        scorer = PrivacyScorer()

        assert scorer.config.threshold == 0.5

    def test_profile_config_retrieval(self):
        """Test getting config for each profile."""
        for profile in DetectionProfile:
            config = get_profile_config(profile)
            assert isinstance(config, WeightConfig)
            assert config.threshold > 0
