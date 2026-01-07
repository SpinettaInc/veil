"""Tests for replacement strategies."""

import pytest

from veil.core.mapper import MappingStore
from veil.detection.entity import Entity, EntityType
from veil.replacement.token import TokenReplacer
from veil.replacement.engine import ReplacementEngine, ReplacementMode, create_engine


class TestTokenReplacer:
    """Tests for token-based replacement."""

    @pytest.fixture
    def replacer(self):
        """Create a token replacer."""
        return TokenReplacer()

    @pytest.fixture
    def mapping_store(self):
        """Create an empty mapping store."""
        return MappingStore()

    def test_generate_person_token(self, replacer, mapping_store):
        """Test generating token for person."""
        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        token = replacer.generate_replacement(entity, mapping_store)

        assert token == "[PERSON_1]"

    def test_generate_org_token(self, replacer, mapping_store):
        """Test generating token for organization."""
        entity = Entity(
            text="Acme Corp",
            entity_type=EntityType.ORG,
            start=0,
            end=9,
        )

        token = replacer.generate_replacement(entity, mapping_store)

        assert token == "[ORG_1]"

    def test_sequential_tokens(self, replacer, mapping_store):
        """Test tokens are numbered sequentially."""
        entities = [
            Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4),
            Entity(text="Jane", entity_type=EntityType.PERSON, start=10, end=14),
        ]

        token1 = replacer.generate_replacement(entities[0], mapping_store)
        mapping_store.add(entities[0].text, token1, EntityType.PERSON)

        token2 = replacer.generate_replacement(entities[1], mapping_store)

        assert token1 == "[PERSON_1]"
        assert token2 == "[PERSON_2]"

    def test_same_entity_same_token(self, replacer, mapping_store):
        """Test same entity text gets same token."""
        entity1 = Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4)
        entity2 = Entity(text="John", entity_type=EntityType.PERSON, start=20, end=24)

        token1 = replacer.generate_replacement(entity1, mapping_store)
        mapping_store.add(entity1.text, token1, EntityType.PERSON)

        token2 = replacer.generate_replacement(entity2, mapping_store)

        assert token1 == token2 == "[PERSON_1]"

    def test_angle_bracket_style(self, mapping_store):
        """Test angle bracket style."""
        replacer = TokenReplacer(bracket_style="angle")
        entity = Entity(text="Test", entity_type=EntityType.PERSON, start=0, end=4)

        token = replacer.generate_replacement(entity, mapping_store)

        assert token == "<PERSON_1>"

    def test_curly_bracket_style(self, mapping_store):
        """Test curly bracket style."""
        replacer = TokenReplacer(bracket_style="curly")
        entity = Entity(text="Test", entity_type=EntityType.PERSON, start=0, end=4)

        token = replacer.generate_replacement(entity, mapping_store)

        assert token == "{PERSON_1}"

    def test_is_token(self, replacer):
        """Test token detection."""
        assert replacer.is_token("[PERSON_1]")
        assert replacer.is_token("[ORG_42]")
        assert not replacer.is_token("John Smith")
        assert not replacer.is_token("[INVALID]")  # No underscore
        assert not replacer.is_token("")

    def test_parse_token(self, replacer):
        """Test parsing tokens."""
        result = replacer.parse_token("[PERSON_1]")
        assert result == ("PERSON", 1)

        result = replacer.parse_token("[ORG_42]")
        assert result == ("ORG", 42)

        result = replacer.parse_token("invalid")
        assert result is None


class TestFakerReplacer:
    """Tests for faker-based replacement."""

    @pytest.fixture
    def mapping_store(self):
        """Create an empty mapping store."""
        return MappingStore()

    def test_faker_import(self):
        """Test faker can be imported."""
        pytest.importorskip("faker")

        from veil.replacement.faker_gen import FakerReplacer, FAKER_AVAILABLE
        assert FAKER_AVAILABLE

    def test_generate_person_replacement(self, mapping_store):
        """Test generating fake person name."""
        pytest.importorskip("faker")
        from veil.replacement.faker_gen import FakerReplacer

        replacer = FakerReplacer(seed=42)
        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        replacement = replacer.generate_replacement(entity, mapping_store)

        # Should be a real-looking name, not a token
        assert "[" not in replacement
        assert "]" not in replacement
        assert " " in replacement  # Two-word name

    def test_generate_email_replacement(self, mapping_store):
        """Test generating fake email."""
        pytest.importorskip("faker")
        from veil.replacement.faker_gen import FakerReplacer

        replacer = FakerReplacer(seed=42)
        entity = Entity(
            text="john@example.com",
            entity_type=EntityType.EMAIL,
            start=0,
            end=16,
        )

        replacement = replacer.generate_replacement(entity, mapping_store)

        assert "@" in replacement
        assert "." in replacement

    def test_generate_ssn_replacement(self, mapping_store):
        """Test generating fake SSN."""
        pytest.importorskip("faker")
        from veil.replacement.faker_gen import FakerReplacer

        replacer = FakerReplacer(seed=42)
        entity = Entity(
            text="123-45-6789",
            entity_type=EntityType.SSN,
            start=0,
            end=11,
        )

        replacement = replacer.generate_replacement(entity, mapping_store)

        # Should maintain format
        assert "-" in replacement
        parts = replacement.split("-")
        assert len(parts) == 3

    def test_generate_org_replacement(self, mapping_store):
        """Test generating fake organization."""
        pytest.importorskip("faker")
        from veil.replacement.faker_gen import FakerReplacer

        replacer = FakerReplacer(seed=42)
        entity = Entity(
            text="Acme Corp",
            entity_type=EntityType.ORG,
            start=0,
            end=9,
        )

        replacement = replacer.generate_replacement(entity, mapping_store)

        # Should be a company-like name
        assert len(replacement) > 0
        assert "[" not in replacement

    def test_reproducible_with_seed(self, mapping_store):
        """Test that same seed produces same results."""
        pytest.importorskip("faker")
        from veil.replacement.faker_gen import FakerReplacer

        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        replacer1 = FakerReplacer(seed=42)
        result1 = replacer1.generate_replacement(entity, mapping_store)

        mapping_store.clear()

        replacer2 = FakerReplacer(seed=42)
        result2 = replacer2.generate_replacement(entity, mapping_store)

        assert result1 == result2


class TestSemanticReplacer:
    """Tests for semantic embedding-based replacement."""

    @pytest.fixture
    def mapping_store(self):
        """Create an empty mapping store."""
        return MappingStore()

    def test_fallback_pool_replacement(self, mapping_store):
        """Test fallback pool is used when embeddings unavailable."""
        from veil.replacement.semantic import SemanticReplacer

        # Create replacer without embeddings
        replacer = SemanticReplacer(embeddings=None, use_fallback=True)

        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        replacement = replacer.generate_replacement(entity, mapping_store)

        # Should get a name from fallback pool
        assert replacement is not None
        assert len(replacement) > 0
        assert "[" not in replacement or "_" in replacement

    def test_org_fallback_pool(self, mapping_store):
        """Test organization fallback pool."""
        from veil.replacement.semantic import SemanticReplacer

        replacer = SemanticReplacer(embeddings=None, use_fallback=True)

        entity = Entity(
            text="Acme Corp",
            entity_type=EntityType.ORG,
            start=0,
            end=9,
        )

        replacement = replacer.generate_replacement(entity, mapping_store)

        # Should get a company name from fallback pool
        assert replacement is not None
        assert len(replacement) > 0

    def test_gpe_fallback_pool(self, mapping_store):
        """Test location fallback pool."""
        from veil.replacement.semantic import SemanticReplacer

        replacer = SemanticReplacer(embeddings=None, use_fallback=True)

        entity = Entity(
            text="New York",
            entity_type=EntityType.GPE,
            start=0,
            end=8,
        )

        replacement = replacer.generate_replacement(entity, mapping_store)

        assert replacement is not None
        assert replacement != "New York"

    def test_used_replacements_tracking(self, mapping_store):
        """Test that replacements are tracked to avoid duplicates."""
        from veil.replacement.semantic import SemanticReplacer

        replacer = SemanticReplacer(embeddings=None, use_fallback=True)

        replacements = set()
        for i in range(5):
            entity = Entity(
                text=f"Person{i}",
                entity_type=EntityType.PERSON,
                start=0,
                end=7,
            )
            replacement = replacer.generate_replacement(entity, mapping_store)
            replacements.add(replacement)

        # All replacements should be unique
        assert len(replacements) == 5

    def test_clear_used(self, mapping_store):
        """Test clearing used replacements."""
        from veil.replacement.semantic import SemanticReplacer

        replacer = SemanticReplacer(embeddings=None, use_fallback=True)

        entity = Entity(
            text="John",
            entity_type=EntityType.PERSON,
            start=0,
            end=4,
        )

        replacement1 = replacer.generate_replacement(entity, mapping_store)
        replacer.clear_used()
        mapping_store.clear()

        # After clearing, the same replacement could be generated again
        replacement2 = replacer.generate_replacement(entity, mapping_store)

        # Can't guarantee same due to random.choice, but should work
        assert replacement1 is not None
        assert replacement2 is not None


class TestReplacementEngine:
    """Tests for unified replacement engine."""

    @pytest.fixture
    def mapping_store(self):
        """Create an empty mapping store."""
        return MappingStore()

    def test_token_mode(self, mapping_store):
        """Test token mode."""
        engine = ReplacementEngine(mode=ReplacementMode.TOKEN)

        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        replacement = engine.replace(entity, mapping_store)

        assert replacement == "[PERSON_1]"

    def test_faker_mode(self, mapping_store):
        """Test faker mode."""
        pytest.importorskip("faker")

        engine = ReplacementEngine(
            mode=ReplacementMode.FAKER,
            faker_seed=42,
        )

        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        replacement = engine.replace(entity, mapping_store)

        assert "[" not in replacement
        assert len(replacement) > 0

    def test_semantic_mode(self, mapping_store):
        """Test semantic mode."""
        engine = ReplacementEngine(mode=ReplacementMode.SEMANTIC)

        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        replacement = engine.replace(entity, mapping_store)

        assert replacement is not None
        assert len(replacement) > 0

    def test_replace_all(self, mapping_store):
        """Test replacing all entities in text."""
        engine = ReplacementEngine(mode=ReplacementMode.TOKEN)

        text = "John Smith works at Acme Corp"
        entities = [
            Entity(text="John Smith", entity_type=EntityType.PERSON, start=0, end=10),
            Entity(text="Acme Corp", entity_type=EntityType.ORG, start=20, end=29),
        ]

        result = engine.replace_all(text, entities, mapping_store)

        assert "[PERSON_" in result
        assert "[ORG_" in result
        assert "John Smith" not in result
        assert "Acme Corp" not in result

    def test_set_mode(self, mapping_store):
        """Test changing modes."""
        engine = ReplacementEngine(mode=ReplacementMode.TOKEN)
        assert engine.mode == ReplacementMode.TOKEN

        pytest.importorskip("faker")
        engine.set_mode(ReplacementMode.FAKER)
        assert engine.mode == ReplacementMode.FAKER

    def test_get_stats(self, mapping_store):
        """Test getting engine statistics."""
        engine = ReplacementEngine(mode=ReplacementMode.TOKEN)

        stats = engine.get_stats()

        assert stats["mode"] == "token"
        assert stats["replacer_type"] == "TokenReplacer"

    def test_create_engine_factory(self):
        """Test factory function."""
        engine = create_engine("token")
        assert engine.mode == ReplacementMode.TOKEN

        pytest.importorskip("faker")
        engine = create_engine("faker")
        assert engine.mode == ReplacementMode.FAKER

    def test_create_engine_invalid_mode(self):
        """Test factory with invalid mode."""
        with pytest.raises(ValueError):
            create_engine("invalid")

    def test_existing_mapping_reused(self, mapping_store):
        """Test that existing mappings are reused."""
        engine = ReplacementEngine(mode=ReplacementMode.TOKEN)

        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        # First replacement
        replacement1 = engine.replace(entity, mapping_store)
        mapping_store.add(entity.text, replacement1, EntityType.PERSON)

        # Second call should return same
        replacement2 = engine.replace(entity, mapping_store)

        assert replacement1 == replacement2


class TestPipelineWithReplacementModes:
    """Integration tests for pipeline with different replacement modes."""

    def test_pipeline_token_mode(self):
        """Test pipeline with token mode."""
        from veil.core.pipeline import VeilPipeline

        pipeline = VeilPipeline(
            use_ner=False,
            use_patterns=True,
            replacement_mode="token",
        )

        result = pipeline.anonymize("Email: john@example.com")

        assert "[EMAIL_" in result.anonymized_text
        assert "john@example.com" not in result.anonymized_text

    def test_pipeline_faker_mode(self):
        """Test pipeline with faker mode."""
        pytest.importorskip("faker")
        from veil.core.pipeline import VeilPipeline

        pipeline = VeilPipeline(
            use_ner=False,
            use_patterns=True,
            replacement_mode="faker",
            faker_seed=42,
        )

        result = pipeline.anonymize("Email: john@example.com")

        # Should have a fake email, not a token
        assert "[EMAIL_" not in result.anonymized_text
        assert "john@example.com" not in result.anonymized_text
        assert "@" in result.anonymized_text  # Still looks like email

    def test_pipeline_semantic_mode(self):
        """Test pipeline with semantic mode."""
        from veil.core.pipeline import VeilPipeline

        pipeline = VeilPipeline(
            use_ner=False,
            use_patterns=True,
            replacement_mode="semantic",
        )

        result = pipeline.anonymize("SSN: 123-45-6789")

        assert "123-45-6789" not in result.anonymized_text

    def test_pipeline_set_replacement_mode(self):
        """Test changing replacement mode on pipeline."""
        pytest.importorskip("faker")
        from veil.core.pipeline import VeilPipeline

        pipeline = VeilPipeline(replacement_mode="token")
        assert pipeline._replacement_mode == "token"

        pipeline.set_replacement_mode("faker")
        assert pipeline._replacement_mode == "faker"

    def test_pipeline_invalid_mode(self):
        """Test pipeline with invalid mode falls back to token."""
        from veil.core.pipeline import VeilPipeline

        pipeline = VeilPipeline(replacement_mode="invalid")

        # Should fall back to token mode
        assert pipeline.replacement_engine.mode == ReplacementMode.TOKEN
