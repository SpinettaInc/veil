"""Tests for the Entity data model."""

import pytest

from veil.detection.entity import Entity, EntityType, merge_overlapping_entities


class TestEntity:
    """Tests for Entity class."""

    def test_entity_creation(self):
        """Test basic entity creation."""
        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
        )

        assert entity.text == "John Smith"
        assert entity.entity_type == EntityType.PERSON
        assert entity.start == 0
        assert entity.end == 10
        assert entity.confidence == 1.0
        assert entity.source == "unknown"

    def test_entity_with_all_fields(self):
        """Test entity with all optional fields."""
        entity = Entity(
            text="Acme Corp",
            entity_type=EntityType.ORG,
            start=20,
            end=29,
            confidence=0.85,
            source="spacy",
            context="works at Acme Corp in",
            metadata={"label": "ORG"},
        )

        assert entity.confidence == 0.85
        assert entity.source == "spacy"
        assert "Acme Corp" in entity.context
        assert entity.metadata["label"] == "ORG"

    def test_entity_length(self):
        """Test entity length property."""
        entity = Entity(
            text="John",
            entity_type=EntityType.PERSON,
            start=5,
            end=9,
        )

        assert entity.length == 4

    def test_entity_validation_negative_start(self):
        """Test that negative start position raises error."""
        with pytest.raises(ValueError, match="start position cannot be negative"):
            Entity(
                text="test",
                entity_type=EntityType.PERSON,
                start=-1,
                end=4,
            )

    def test_entity_validation_end_before_start(self):
        """Test that end < start raises error."""
        with pytest.raises(ValueError, match="end position must be >= start"):
            Entity(
                text="test",
                entity_type=EntityType.PERSON,
                start=10,
                end=5,
            )

    def test_entity_validation_confidence_bounds(self):
        """Test that confidence outside 0-1 raises error."""
        with pytest.raises(ValueError, match="confidence must be between"):
            Entity(
                text="test",
                entity_type=EntityType.PERSON,
                start=0,
                end=4,
                confidence=1.5,
            )

    def test_entity_overlaps(self):
        """Test overlap detection."""
        e1 = Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4)
        e2 = Entity(text="John Smith", entity_type=EntityType.PERSON, start=0, end=10)
        e3 = Entity(text="works", entity_type=EntityType.PERSON, start=11, end=16)

        assert e1.overlaps(e2)
        assert e2.overlaps(e1)
        assert not e1.overlaps(e3)
        assert not e3.overlaps(e1)

    def test_entity_contains(self):
        """Test containment detection."""
        e1 = Entity(text="John Smith", entity_type=EntityType.PERSON, start=0, end=10)
        e2 = Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4)

        assert e1.contains(e2)
        assert not e2.contains(e1)

    def test_entity_to_dict(self):
        """Test serialization to dict."""
        entity = Entity(
            text="John",
            entity_type=EntityType.PERSON,
            start=0,
            end=4,
            confidence=0.9,
            source="test",
        )

        data = entity.to_dict()

        assert data["text"] == "John"
        assert data["entity_type"] == "PERSON"
        assert data["start"] == 0
        assert data["end"] == 4
        assert data["confidence"] == 0.9

    def test_entity_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "text": "Acme",
            "entity_type": "ORG",
            "start": 5,
            "end": 9,
            "confidence": 0.85,
            "source": "pattern",
        }

        entity = Entity.from_dict(data)

        assert entity.text == "Acme"
        assert entity.entity_type == EntityType.ORG
        assert entity.confidence == 0.85


class TestMergeOverlappingEntities:
    """Tests for merge_overlapping_entities function."""

    def test_empty_list(self):
        """Test merging empty list."""
        result = merge_overlapping_entities([])
        assert result == []

    def test_no_overlaps(self):
        """Test when no entities overlap."""
        entities = [
            Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4),
            Entity(text="works", entity_type=EntityType.PERSON, start=5, end=10),
        ]

        result = merge_overlapping_entities(entities)

        assert len(result) == 2

    def test_overlapping_keeps_higher_confidence(self):
        """Test that higher confidence entity wins."""
        entities = [
            Entity(
                text="John",
                entity_type=EntityType.PERSON,
                start=0,
                end=4,
                confidence=0.8,
            ),
            Entity(
                text="John Smith",
                entity_type=EntityType.PERSON,
                start=0,
                end=10,
                confidence=0.9,
            ),
        ]

        result = merge_overlapping_entities(entities)

        assert len(result) == 1
        assert result[0].text == "John Smith"
        assert result[0].confidence == 0.9

    def test_overlapping_keeps_longer_on_tie(self):
        """Test that longer entity wins on confidence tie."""
        entities = [
            Entity(
                text="John",
                entity_type=EntityType.PERSON,
                start=0,
                end=4,
                confidence=0.9,
            ),
            Entity(
                text="John Smith",
                entity_type=EntityType.PERSON,
                start=0,
                end=10,
                confidence=0.9,
            ),
        ]

        result = merge_overlapping_entities(entities)

        assert len(result) == 1
        assert result[0].text == "John Smith"

    def test_result_sorted_by_position(self):
        """Test that result is sorted by start position."""
        entities = [
            Entity(text="Corp", entity_type=EntityType.ORG, start=20, end=24),
            Entity(text="John", entity_type=EntityType.PERSON, start=0, end=4),
            Entity(text="NYC", entity_type=EntityType.GPE, start=30, end=33),
        ]

        result = merge_overlapping_entities(entities)

        assert result[0].start == 0
        assert result[1].start == 20
        assert result[2].start == 30


class TestEntityType:
    """Tests for EntityType enum."""

    def test_entity_type_values(self):
        """Test that common entity types exist."""
        assert EntityType.PERSON.value == "PERSON"
        assert EntityType.ORG.value == "ORG"
        assert EntityType.EMAIL.value == "EMAIL"
        assert EntityType.SSN.value == "SSN"

    def test_entity_type_from_string(self):
        """Test creating EntityType from string."""
        assert EntityType("PERSON") == EntityType.PERSON
        assert EntityType("ORG") == EntityType.ORG
