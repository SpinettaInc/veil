"""Tests for replacement strategies."""

import pytest

from veil.core.mapper import MappingStore
from veil.detection.entity import Entity, EntityType
from veil.replacement.token import TokenReplacer, apply_replacements


class TestTokenReplacer:
    """Tests for TokenReplacer class."""

    @pytest.fixture
    def replacer(self):
        """Create a token replacer."""
        return TokenReplacer()

    @pytest.fixture
    def store(self):
        """Create a mapping store."""
        return MappingStore()

    def test_generate_first_replacement(self, replacer, store):
        """Test generating first replacement for a type."""
        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        replacement = replacer.generate_replacement(entity, store)

        assert replacement == "[PERSON_1]"

    def test_generate_sequential_replacements(self, replacer, store):
        """Test generating sequential replacements."""
        e1 = Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4)
        e2 = Entity(text="Jane", entity_type=EntityType.PERSON, start=10, end=14)

        # First replacement
        r1 = replacer.generate_replacement(e1, store)
        store.add(e1.text, r1, e1.entity_type)

        # Second replacement
        r2 = replacer.generate_replacement(e2, store)

        assert r1 == "[PERSON_1]"
        assert r2 == "[PERSON_2]"

    def test_reuse_existing_replacement(self, replacer, store):
        """Test that same original text gets same replacement."""
        entity = Entity(
            text="John",
            entity_type=EntityType.PERSON,
            start=0,
            end=4,
        )

        # Add first mapping
        store.add("John", "[PERSON_1]", EntityType.PERSON)

        # Should return existing replacement
        replacement = replacer.generate_replacement(entity, store)

        assert replacement == "[PERSON_1]"

    def test_different_types_separate_numbering(self, replacer, store):
        """Test that different types have separate numbering."""
        e1 = Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4)
        e2 = Entity(text="Acme", entity_type=EntityType.ORG, start=10, end=14)

        r1 = replacer.generate_replacement(e1, store)
        store.add(e1.text, r1, e1.entity_type)

        r2 = replacer.generate_replacement(e2, store)

        assert r1 == "[PERSON_1]"
        assert r2 == "[ORG_1]"

    def test_angle_bracket_style(self, store):
        """Test angle bracket style."""
        replacer = TokenReplacer(bracket_style="angle")
        entity = Entity(
            text="John",
            entity_type=EntityType.PERSON,
            start=0,
            end=4,
        )

        replacement = replacer.generate_replacement(entity, store)

        assert replacement == "<PERSON_1>"

    def test_curly_bracket_style(self, store):
        """Test curly bracket style."""
        replacer = TokenReplacer(bracket_style="curly")
        entity = Entity(
            text="John",
            entity_type=EntityType.PERSON,
            start=0,
            end=4,
        )

        replacement = replacer.generate_replacement(entity, store)

        assert replacement == "{PERSON_1}"

    def test_is_token(self, replacer):
        """Test token detection."""
        assert replacer.is_token("[PERSON_1]")
        assert replacer.is_token("[ORG_123]")
        assert not replacer.is_token("John Smith")
        assert not replacer.is_token("[INVALID]")  # No underscore
        assert not replacer.is_token("")

    def test_parse_token(self, replacer):
        """Test token parsing."""
        result = replacer.parse_token("[PERSON_1]")
        assert result == ("PERSON", 1)

        result = replacer.parse_token("[ORG_42]")
        assert result == ("ORG", 42)

        result = replacer.parse_token("not a token")
        assert result is None


class TestApplyReplacements:
    """Tests for apply_replacements function."""

    @pytest.fixture
    def replacer(self):
        """Create a token replacer."""
        return TokenReplacer()

    @pytest.fixture
    def store(self):
        """Create a mapping store."""
        return MappingStore()

    def test_apply_single_replacement(self, replacer, store):
        """Test applying single replacement."""
        text = "John Smith is here."
        entities = [
            Entity(
                text="John Smith",
                entity_type=EntityType.PERSON,
                start=0,
                end=10,
            ),
        ]

        result = apply_replacements(text, entities, replacer, store)

        assert result == "[PERSON_1] is here."
        assert store.get_replacement("John Smith") == "[PERSON_1]"

    def test_apply_multiple_replacements(self, replacer, store):
        """Test applying multiple replacements."""
        text = "John works at Acme Corp."
        entities = [
            Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4),
            Entity(text="Acme Corp", entity_type=EntityType.ORG, start=14, end=23),
        ]

        result = apply_replacements(text, entities, replacer, store)

        assert "[PERSON_1]" in result
        assert "[ORG_1]" in result
        assert result == "[PERSON_1] works at [ORG_1]."

    def test_apply_preserves_positions(self, replacer, store):
        """Test that replacements preserve relative positions."""
        text = "A B C D E"
        entities = [
            Entity(text="A", entity_type=EntityType.PERSON, start=0, end=1),
            Entity(text="C", entity_type=EntityType.PERSON, start=4, end=5),
            Entity(text="E", entity_type=EntityType.PERSON, start=8, end=9),
        ]

        result = apply_replacements(text, entities, replacer, store)

        # Should maintain structure (tokens numbered in processing order: end to start)
        assert " B " in result
        assert " D " in result
        assert result.count("[PERSON_") == 3

    def test_apply_empty_entities(self, replacer, store):
        """Test applying with no entities."""
        text = "Hello world"
        result = apply_replacements(text, [], replacer, store)

        assert result == text

    def test_apply_empty_text(self, replacer, store):
        """Test applying to empty text."""
        result = apply_replacements("", [], replacer, store)
        assert result == ""

    def test_apply_same_entity_twice(self, replacer, store):
        """Test that same entity text gets same replacement."""
        text = "John met John."
        entities = [
            Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4),
            Entity(text="John", entity_type=EntityType.PERSON, start=9, end=13),
        ]

        result = apply_replacements(text, entities, replacer, store)

        assert result == "[PERSON_1] met [PERSON_1]."
        # Should only have one mapping
        assert len(store) == 1
