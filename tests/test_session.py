"""Session-level guarantees: identity across turns, reconstruction, proxy hygiene.

Covers the leak paths found in review: fail-open detection, LLM-mangled
tokens, one person getting several tokens, caller-supplied raw history, and
tokens split across stream chunks.
"""

import threading
from collections.abc import Iterator

import pytest

from veil.core.detector import DetectionUnavailableError, EntityDetector
from veil.core.mapper import MappingStore, normalize_original
from veil.core.pipeline import VeilPipeline
from veil.detection.entity import Entity, EntityType
from veil.detection.ner import SPACY_AVAILABLE
from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message
from veil.llm.proxy import VeilProxy
from veil.weighting.config import DetectionProfile, WeightConfig, get_profile_config
from veil.weighting.tfidf import DocumentStats, GlobalRarityScorer


def _pipeline(**kwargs: object) -> VeilPipeline:
    return VeilPipeline(use_ner=False, **kwargs)  # type: ignore[arg-type]


class TestMappingIdentity:
    def test_case_titles_and_possessives_share_one_key(self):
        for a, b in [
            ("John Smith", "john smith"),
            ("Dr. John Smith", "John Smith"),
            ("John Smith's", "John Smith"),
            ("John  Smith", "John Smith"),
        ]:
            assert normalize_original(a, EntityType.PERSON) == normalize_original(
                b, EntityType.PERSON
            )

    def test_partial_name_resolves_to_existing_person(self):
        store = MappingStore()
        store.add("John Smith", "[PERSON_1]", EntityType.PERSON)
        assert store.get_replacement_for("Smith", EntityType.PERSON) == "[PERSON_1]"
        # A bare surname mislabelled ORG/GPE by NER still joins the person ...
        assert store.get_replacement_for("Smith", EntityType.ORG) == "[PERSON_1]"
        # ... but a multi-word organisation does not
        assert store.get_replacement_for("Smith Holdings", EntityType.ORG) is None
        assert store.get_replacement_for("Smith", EntityType.EMAIL) is None

    def test_ambiguous_partial_name_gets_no_match(self):
        store = MappingStore()
        store.add("John Smith", "[PERSON_1]", EntityType.PERSON)
        store.add("Jane Smith", "[PERSON_2]", EntityType.PERSON)
        assert store.get_replacement_for("Smith", EntityType.PERSON) is None

    def test_fuller_name_later_promotes_canonical_original(self):
        store = MappingStore()
        store.add("Smith", "[PERSON_1]", EntityType.PERSON)
        assert store.get_replacement_for("John Smith", EntityType.PERSON) == "[PERSON_1]"
        entry = store.get_entry_by_replacement("[PERSON_1]")
        assert entry is not None
        assert entry.original == "John Smith"
        assert "Smith" in entry.aliases

    def test_alias_keeps_canonical_for_reconstruction(self):
        store = MappingStore()
        store.add("John Smith", "[PERSON_1]", EntityType.PERSON)
        store.add("Smith", "[PERSON_1]", EntityType.PERSON)
        assert store.get_original("[PERSON_1]") == "John Smith"
        assert len(store) == 1

    def test_end_to_end_one_token_per_person(self):
        pipe = _pipeline()
        text = "Smith called. Then john smith's report arrived; JOHN SMITH signed it."
        # Inject entities directly: no NER in this pipeline
        ents = [
            Entity("Smith", EntityType.PERSON, 0, 5),
            Entity("john smith", EntityType.PERSON, 19, 29),
            Entity("JOHN SMITH", EntityType.PERSON, 50, 60),
        ]
        out = pipe.replacement_engine.replace_all(text, ents, pipe.mapping_store)
        assert out.count("[PERSON_1]") == 3 and "[PERSON_2]" not in out


class TestReconstruction:
    @pytest.fixture
    def pipe(self) -> VeilPipeline:
        p = _pipeline()
        p.anonymize("Mail ana@k.io, card 4111111111111111, ip 10.0.0.1")
        return p

    @pytest.mark.parametrize(
        "mangled",
        ["[EMAIL_1]", "EMAIL_1", "[email_1]", "[Email 1]", "<EMAIL_1>", "{email-1}", "[EMAIL-1]"],
    )
    def test_llm_variants_are_restored(self, pipe, mangled):
        assert pipe.reconstruct(f"Write to {mangled} today").reconstructed_text == (
            "Write to ana@k.io today"
        )

    def test_number_boundary_and_surrounding_text(self, pipe):
        out = pipe.reconstruct("EMAIL_1's box, EMAIL_10, [EMAIL_1]: x").reconstructed_text
        assert out == "ana@k.io's box, EMAIL_10, ana@k.io: x"

    def test_many_tokens_round_trip(self):
        pipe = _pipeline()
        text = " ".join(f"u{i}@ex{i}.com" for i in range(1, 25))
        result = pipe.anonymize(text)
        assert "[EMAIL_24]" in result.anonymized_text
        assert pipe.reconstruct(result.anonymized_text).reconstructed_text == text

    def test_input_containing_a_token_is_not_clobbered(self):
        pipe = _pipeline()
        text = "Ticket [EMAIL_1] was about ana@k.io"
        result = pipe.anonymize(text)
        assert result.anonymized_text == "Ticket [EMAIL_1] was about [EMAIL_2]"
        assert pipe.reconstruct(result.anonymized_text).reconstructed_text == text

    def test_faker_values_never_collide_with_input(self):
        faker = pytest.importorskip("faker")
        assert faker
        pipe = _pipeline(replacement_mode="faker", faker_seed=1)
        text = "Mail ana@k.io or bob@k.io"
        pipe.anonymize(text)
        for entry in pipe.mapping_store:
            assert entry.replacement not in text


class TestFailClosed:
    def test_missing_model_raises_by_default(self):
        with pytest.raises(DetectionUnavailableError):
            EntityDetector(spacy_model="en_core_web_does_not_exist")

    def test_non_strict_flags_degraded(self):
        det = EntityDetector(spacy_model="en_core_web_does_not_exist", strict=False)
        assert det.degraded and det.degradation_reasons
        pipe = VeilPipeline(spacy_model="en_core_web_does_not_exist", strict=False)
        assert pipe.anonymize("Priya Raghunathan").degraded is True


class EchoProvider(LLMProvider):
    """Records what the proxy sends and answers with tokens."""

    def __init__(self, stream_chunks: list[str] | None = None) -> None:
        super().__init__(LLMConfig(api_key="x", model="echo"))
        self.seen: list[list[str]] = []
        self.stream_chunks = stream_chunks or []

    @property
    def name(self) -> str:
        return "echo"

    @property
    def available_models(self) -> list[str]:
        return ["echo"]

    def chat(self, messages: list[Message], **kwargs: object) -> LLMResponse:
        self.seen.append([m.content for m in messages])
        return LLMResponse(content="Sure [PERSON_1], I emailed EMAIL_1.", model="echo")

    def chat_stream(self, messages: list[Message], **kwargs: object) -> Iterator[str]:
        self.seen.append([m.content for m in messages])
        yield from self.stream_chunks

    def validate_config(self) -> bool:
        return True


@pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
class TestProxyHygiene:
    @pytest.fixture
    def proxy(self):
        try:
            provider = EchoProvider(
                ["Hi [PER", "SON_1], your ", "email EMAIL", "_1 is set. ", "Bye"]
            )
            return VeilProxy(provider, detection_mode="standard", use_presidio=False)
        except OSError:
            pytest.skip("no spaCy model installed")

    def test_provider_only_sees_anonymized_turns(self, proxy):
        proxy.chat("I am Ana Kowalski, ana@k.io")
        proxy.chat("Thanks!")
        sent = proxy.provider.seen[-1]
        assert not any("Kowalski" in m or "ana@k.io" in m for m in sent)
        assert sent[0] == "I am [PERSON_1], [EMAIL_1]"

    def test_caller_supplied_raw_history_is_sanitized(self, proxy):
        proxy.chat("I am Ana Kowalski, ana@k.io")
        raw = [Message(role="user", content="I am Ana Kowalski, ana@k.io")]
        proxy.chat("Again", conversation_history=raw)
        assert proxy.provider.seen[-1][0] == "I am [PERSON_1], [EMAIL_1]"

    def test_stream_reconstructs_tokens_split_across_chunks(self, proxy):
        proxy.chat("I am Ana Kowalski, ana@k.io")
        chunks = list(proxy.chat_stream("More"))
        assert "".join(chunks) == "Hi Ana Kowalski, your email ana@k.io is set. Bye"

    def test_clear_session_drops_history(self, proxy):
        proxy.chat("I am Ana Kowalski")
        proxy.clear_session()
        assert proxy.history == [] and len(proxy.pipeline.mapping_store) == 0

    def test_degraded_pipeline_refuses_to_send(self):
        provider = EchoProvider()
        proxy = VeilProxy(provider, detection_mode="standard", use_presidio=False, strict=False)
        proxy.pipeline = VeilPipeline(spacy_model="en_core_web_does_not_exist", strict=False)
        with pytest.raises(DetectionUnavailableError):
            proxy.chat("Priya Raghunathan")
        assert provider.seen == []

    @pytest.mark.parametrize(
        "buffer,expected_prefix",
        [
            ("Hello [PER", "Hello "),
            ("Hello PERSON_", "Hello "),
            ("Hello [PERSON_1] and", "Hello [PERSON_1] and"),
            ("all done.", "all done."),
        ],
    )
    def test_safe_flush_length(self, buffer, expected_prefix):
        assert buffer[: VeilProxy._safe_flush_length(buffer)] == expected_prefix


class TestProfilesFromYaml:
    def test_builtin_profiles_come_from_yaml(self):
        for profile in DetectionProfile:
            assert get_profile_config(profile).source == profile.value

    def test_custom_profile_with_custom_pattern(self, tmp_path):
        path = tmp_path / "corp.yaml"
        path.write_text(
            "threshold: 0.5\n"
            "entity_weights:\n  EMPLOYEE_ID: 0.95\n"
            "custom_patterns:\n"
            "  - name: employee_id\n    entity_type: EMPLOYEE_ID\n"
            '    regex: "\\\\bEMP-\\\\d{5}\\\\b"\n    confidence: 0.95\n'
        )
        config = WeightConfig.from_yaml(path)
        assert config.custom_weights == {"EMPLOYEE_ID": 0.95}
        pipe = VeilPipeline(use_ner=False, weight_config=config)
        result = pipe.anonymize("Badge EMP-48213 is active")
        assert result.anonymized_text == "Badge [EMPLOYEE_ID_1] is active"
        assert pipe.reconstruct("Badge EMPLOYEE_ID_1").reconstructed_text == "Badge EMP-48213"

    def test_unknown_weight_name_is_rejected(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("entity_weights:\n  NOT_A_TYPE: 1.0\n")
        with pytest.raises(ValueError, match="NOT_A_TYPE"):
            WeightConfig.from_yaml(path)

    def test_round_trip_to_dict(self):
        config = get_profile_config(DetectionProfile.BALANCED)
        again = WeightConfig.from_dict(config.to_dict())
        assert again.entity_weights == config.entity_weights
        assert again.threshold == config.threshold


class TestCorpusRarity:
    def test_common_word_scores_lower_than_rare_name_in_short_text(self):
        zipf = {"the": 7.7, "john": 5.5, "raghunathan": 0.5}
        scorer = GlobalRarityScorer(zipf_fn=lambda t: zipf.get(t, 0.0))
        stats = DocumentStats.from_text("the john raghunathan")
        assert (
            scorer.score("the", stats)
            < scorer.score("john", stats)
            < scorer.score("raghunathan", stats)
        )

    def test_without_frequency_source_behaviour_is_unchanged(self):
        scorer = GlobalRarityScorer(use_wordfreq=False)
        assert scorer.zipf_fn is None


class TestThreadSafety:
    def test_concurrent_adds_keep_store_consistent(self):
        store = MappingStore()
        errors: list[BaseException] = []

        def worker(n: int) -> None:
            try:
                for i in range(200):
                    store.add(f"user{n}-{i}@x.io", f"[EMAIL_{n}_{i}]", EntityType.EMAIL)
                    store.get_replacement(f"user{n}-{i}@x.io")
                    list(store)
            except BaseException as exc:  # pragma: no cover - reported below
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(store) == 8 * 200
