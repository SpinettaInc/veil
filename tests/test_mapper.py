"""Tests for the bidirectional mapping store."""

import pytest

from veil.core.mapper import MappingStore, MappingEntry
from veil.detection.entity import Entity, EntityType


class TestMappingStore:
    """Tests for MappingStore class."""

    @pytest.fixture
    def store(self):
        """Create a fresh mapping store."""
        return MappingStore()

    def test_add_mapping(self, store):
        """Test adding a mapping."""
        entry = store.add(
            original="John Smith",
            replacement="[PERSON_1]",
            entity_type=EntityType.PERSON,
        )

        assert entry.original == "John Smith"
        assert entry.replacement == "[PERSON_1]"
        assert entry.entity_type == EntityType.PERSON
        assert entry.count == 1

    def test_add_duplicate_increments_count(self, store):
        """Test that adding same original increments count."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)
        store.add("John", "[PERSON_1]", EntityType.PERSON)
        store.add("John", "[PERSON_1]", EntityType.PERSON)

        entry = store.get_entry("John")
        assert entry is not None
        assert entry.count == 3

    def test_get_replacement(self, store):
        """Test forward lookup (original -> replacement)."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)

        assert store.get_replacement("John") == "[PERSON_1]"
        assert store.get_replacement("NotFound") is None

    def test_get_original(self, store):
        """Test reverse lookup (replacement -> original)."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)

        assert store.get_original("[PERSON_1]") == "John"
        assert store.get_original("[PERSON_99]") is None

    def test_has_original(self, store):
        """Test checking if original exists."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)

        assert store.has_original("John")
        assert not store.has_original("Jane")

    def test_has_replacement(self, store):
        """Test checking if replacement exists."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)

        assert store.has_replacement("[PERSON_1]")
        assert not store.has_replacement("[PERSON_2]")

    def test_get_by_type(self, store):
        """Test retrieving mappings by entity type."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)
        store.add("Jane", "[PERSON_2]", EntityType.PERSON)
        store.add("Acme", "[ORG_1]", EntityType.ORG)

        persons = store.get_by_type(EntityType.PERSON)
        orgs = store.get_by_type(EntityType.ORG)

        assert len(persons) == 2
        assert len(orgs) == 1
        assert all(e.entity_type == EntityType.PERSON for e in persons)

    def test_count_by_type(self, store):
        """Test counting mappings by type."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)
        store.add("Jane", "[PERSON_2]", EntityType.PERSON)
        store.add("Acme", "[ORG_1]", EntityType.ORG)

        assert store.count_by_type(EntityType.PERSON) == 2
        assert store.count_by_type(EntityType.ORG) == 1
        assert store.count_by_type(EntityType.EMAIL) == 0

    def test_next_token_number(self, store):
        """Test getting next token number for a type."""
        assert store.next_token_number(EntityType.PERSON) == 1

        store.add("John", "[PERSON_1]", EntityType.PERSON)
        assert store.next_token_number(EntityType.PERSON) == 2

        store.add("Jane", "[PERSON_2]", EntityType.PERSON)
        assert store.next_token_number(EntityType.PERSON) == 3

        # Other types start at 1
        assert store.next_token_number(EntityType.ORG) == 1

    def test_clear(self, store):
        """Test clearing all mappings."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)
        store.add("Acme", "[ORG_1]", EntityType.ORG)

        assert len(store) == 2

        store.clear()

        assert len(store) == 0
        assert store.get_replacement("John") is None

    def test_len(self, store):
        """Test length of store."""
        assert len(store) == 0

        store.add("John", "[PERSON_1]", EntityType.PERSON)
        assert len(store) == 1

        store.add("Acme", "[ORG_1]", EntityType.ORG)
        assert len(store) == 2

    def test_contains(self, store):
        """Test 'in' operator."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)

        assert "John" in store
        assert "Jane" not in store

    def test_iter(self, store):
        """Test iteration over mappings."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)
        store.add("Acme", "[ORG_1]", EntityType.ORG)

        entries = list(store)
        assert len(entries) == 2
        assert all(isinstance(e, MappingEntry) for e in entries)

    def test_to_dict(self, store):
        """Test exporting to dictionary."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)
        store.add("Acme", "[ORG_1]", EntityType.ORG)

        data = store.to_dict()

        assert "mappings" in data
        assert len(data["mappings"]) == 2
        assert data["mappings"][0]["original"] == "John"
        assert data["mappings"][0]["entity_type"] == "PERSON"

    def test_from_dict(self, store):
        """Test importing from dictionary."""
        data = {
            "mappings": [
                {
                    "original": "John",
                    "replacement": "[PERSON_1]",
                    "entity_type": "PERSON",
                    "count": 2,
                },
                {
                    "original": "Acme",
                    "replacement": "[ORG_1]",
                    "entity_type": "ORG",
                },
            ]
        }

        new_store = MappingStore.from_dict(data)

        assert len(new_store) == 2
        assert new_store.get_replacement("John") == "[PERSON_1]"
        assert new_store.get_entry("John").count == 2

    def test_get_stats(self, store):
        """Test getting store statistics."""
        store.add("John", "[PERSON_1]", EntityType.PERSON)
        store.add("Jane", "[PERSON_2]", EntityType.PERSON)
        store.add("Acme", "[ORG_1]", EntityType.ORG)

        stats = store.get_stats()

        assert stats["total_mappings"] == 3
        assert stats["by_type"]["PERSON"] == 2
        assert stats["by_type"]["ORG"] == 1

    def test_add_with_entity(self, store):
        """Test adding mapping with full Entity object."""
        entity = Entity(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start=0,
            end=10,
            confidence=0.95,
            source="spacy",
        )

        entry = store.add(
            original="John Smith",
            replacement="[PERSON_1]",
            entity_type=EntityType.PERSON,
            entity=entity,
        )

        assert entry.entity is not None
        assert entry.entity.confidence == 0.95
