"""Regression tests for bugs found in review: fail-closed gaps, leaks through
the proxy, replacement collisions, pattern misses and over-matches."""

import json
import stat
import time
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from veil import VeilPipeline
from veil.cli import app
from veil.config.settings import AppSettings
from veil.core.detector import DetectionUnavailableError, EntityDetector
from veil.core.mapper import MappingStore
from veil.detection.entity import Entity, EntityType, merge_overlapping_entities
from veil.detection.ner import SPACY_AVAILABLE
from veil.detection.patterns import PatternDetector
from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message
from veil.llm.proxy import VeilProxy
from veil.server import UnknownSessionError, VeilService

needs_spacy = pytest.mark.skipif(not SPACY_AVAILABLE, reason="needs spaCy")


def _patterns_only(**kwargs: object) -> VeilPipeline:
    return VeilPipeline(use_ner=False, use_weighting=False, **kwargs)  # type: ignore[arg-type]


def _types(text: str) -> dict[str, str]:
    return {e.text: e.entity_type.value for e in PatternDetector().detect(text)}


class TestFailClosed:
    @needs_spacy
    def test_hybrid_strict_raises_when_spacy_model_missing(self):
        with pytest.raises(DetectionUnavailableError):
            EntityDetector(mode="hybrid", spacy_model="xx_no_such_model", strict=True)

    @needs_spacy
    def test_hybrid_non_strict_is_flagged_degraded(self):
        detector = EntityDetector(mode="hybrid", spacy_model="xx_no_such_model", strict=False)
        assert detector.degraded
        assert detector.degradation_reasons

    def test_unknown_modes_and_profiles_are_rejected(self):
        with pytest.raises(ValueError, match="detection mode"):
            EntityDetector(mode="hybird", use_ner=False)
        with pytest.raises(ValueError, match="Invalid mode"):
            _patterns_only(replacement_mode="fakerr")
        with pytest.raises(ValueError, match="Invalid profile"):
            VeilProxy(RecordingProvider(), profile="paranoia")


class TestMerge:
    def test_loser_of_a_chain_does_not_take_its_neighbour_down(self):
        def ent(start: int, end: int, etype: EntityType, conf: float) -> Entity:
            return Entity(text="x" * (end - start), entity_type=etype, start=start, end=end,
                          confidence=conf)

        a = ent(0, 10, EntityType.PERSON, 0.6)
        b = ent(8, 20, EntityType.PERSON, 0.8)
        c = ent(18, 30, EntityType.EMAIL, 0.9)
        # b loses to c; a only overlapped b, so it must survive
        assert merge_overlapping_entities([a, b, c]) == [a, c]


class TestMappingStore:
    def test_untyped_lookup_finds_non_person_possessive(self):
        store = MappingStore()
        store.add("McDonald's", "[ORG_1]", EntityType.ORG)
        assert store.get_replacement("McDonald's") == "[ORG_1]"
        assert "McDonald's" in store
        assert store.has_original("McDonald's")

    def test_urls_differing_in_case_stay_distinct(self):
        pipe = _patterns_only()
        text = "See https://example.com/Doc/AbC and https://example.com/doc/abc"
        result = pipe.anonymize(text)
        assert result.anonymized_text == "See [URL_1] and [URL_2]"
        assert pipe.reconstruct(result.anonymized_text).reconstructed_text == text


class TestBatchSessions:
    def test_each_document_keeps_its_own_mappings(self):
        pipe = _patterns_only()
        docs = ["Mail a@example.com", "Mail b@example.org"]
        results = pipe.anonymize_batch(docs, separate_sessions=True)
        assert [r.anonymized_text for r in results] == ["Mail [EMAIL_1]", "Mail [EMAIL_1]"]
        assert results[0].replacements == {"a@example.com": "[EMAIL_1]"}
        for doc, result in zip(docs, results):
            restored = pipe.reconstruct(result.anonymized_text, mapping_store=result.mapping_store)
            assert restored.reconstructed_text == doc


class RecordingProvider(LLMProvider):
    def __init__(self, chunks: list[str] | None = None, fail_after: int | None = None) -> None:
        super().__init__(LLMConfig(api_key="x", model="rec"))
        self.sent: list[list[Message]] = []
        self.chunks = chunks or []
        self.fail_after = fail_after

    @property
    def name(self) -> str:
        return "rec"

    @property
    def available_models(self) -> list[str]:
        return ["rec"]

    def chat(self, messages: list[Message], **kwargs: object) -> LLMResponse:
        self.sent.append(list(messages))
        return LLMResponse(content="ok", model="rec")

    def chat_stream(self, messages: list[Message], **kwargs: object) -> Iterator[str]:
        self.sent.append(list(messages))
        for i, chunk in enumerate(self.chunks):
            if self.fail_after is not None and i >= self.fail_after:
                raise RuntimeError("connection lost")
            yield chunk


def _proxy(provider: RecordingProvider, **kwargs: object) -> VeilProxy:
    proxy = VeilProxy(provider, detection_mode="standard", use_presidio=False, **kwargs)  # type: ignore[arg-type]
    return proxy


@needs_spacy
class TestProxyLeaks:
    SECRETS = ("john.smith@acme-corp.com", "536-90-4399")

    def _sent_text(self, provider: RecordingProvider) -> str:
        return "\n".join(m.content for call in provider.sent for m in call)

    def test_system_prompt_is_anonymized(self):
        provider = RecordingProvider()
        proxy = _proxy(provider, system_prompt="The user's SSN is 536-90-4399.")
        proxy.chat("hello there")
        assert "536-90-4399" not in self._sent_text(provider)

    def test_supplied_history_is_anonymized_for_every_role(self):
        provider = RecordingProvider()
        proxy = _proxy(provider)
        history = [
            Message(role="user", content="Write to john.smith@acme-corp.com"),
            Message(role="assistant", content="Done, I wrote to john.smith@acme-corp.com."),
        ]
        proxy.chat("And his SSN is 536-90-4399", conversation_history=history)
        sent = self._sent_text(provider)
        for secret in self.SECRETS:
            assert secret not in sent

    def test_stream_restores_token_rewritten_and_split_by_the_model(self):
        provider = RecordingProvider(chunks=["Mail Em", "ail_", "1 now, ", "then email", " 1."])
        proxy = _proxy(provider)
        out = "".join(proxy.chat_stream("Mail a@example.com"))
        assert out == "Mail a@example.com now, then a@example.com."

    def test_failed_stream_still_records_the_turn(self):
        provider = RecordingProvider(chunks=["partial ", "never"], fail_after=1)
        proxy = _proxy(provider)
        with pytest.raises(RuntimeError):
            list(proxy.chat_stream("Mail a@example.com"))
        assert [m.role for m in proxy.history] == ["user", "assistant"]
        assert proxy.history[0].content == "Mail [EMAIL_1]"


class TestStreamHoldBack:
    def test_literal_split_across_chunks_is_held(self):
        flush = VeilProxy._safe_flush_length
        assert flush("Dear Geor", ["George Lee"]) == len("Dear ")
        # a complete fake value is flushed whole...
        assert flush("Dear George Lee", ["George Lee"]) == len("Dear George Lee")
        # ...and never cut in two by another hold-back ("Lee" could start "LEEDS_1")
        assert flush("Dear George Lee", ["George Lee"], {"LEEDS"}) == len("Dear ")
        assert flush("Dear George Lee, hi.", ["George Lee"]) == len("Dear George Lee, hi.")

    def test_only_tails_that_can_become_a_token_are_held(self):
        flush = VeilProxy._safe_flush_length
        types = {"PERSON", "CREDIT_CARD"}
        assert flush("Hi Person_", (), types) == len("Hi ")
        assert flush("Hi person 1", (), types) == len("Hi ")
        assert flush("pay by credit card", (), types) == len("pay by ")
        assert flush("Hi and", (), types) == len("Hi and")


class TestReplacementCollisions:
    def test_faker_never_gives_two_originals_one_value(self):
        pytest.importorskip("faker")
        cities = ["Paris", "Berlin", "Madrid", "Vienna", "Lisbon", "Dublin", "Sofia", "Oslo",
                  "Rome", "Athens", "Prague", "Warsaw", "Riga", "Bern", "Kyiv", "Minsk"]
        entities, pos, parts = [], 0, []
        for city in cities:
            entities.append(Entity(text=city, entity_type=EntityType.GPE, start=pos,
                                   end=pos + len(city)))
            parts.append(city)
            pos += len(city) + 2
        text = ", ".join(parts)
        for seed in range(10):
            pipe = _patterns_only(replacement_mode="faker", faker_seed=seed)
            out = pipe.replacement_engine.replace_all(text, entities, pipe.mapping_store)
            replacements = [e.replacement for e in pipe.mapping_store]
            assert len(set(replacements)) == len(cities)
            assert pipe.reconstruct(out).reconstructed_text == text

    def test_semantic_numbers_poolless_types(self):
        pipe = _patterns_only(replacement_mode="semantic")
        text = "Mail a@example.com and b@example.org"
        result = pipe.anonymize(text)
        assert len(set(result.replacements.values())) == 2
        assert pipe.reconstruct(result.anonymized_text).reconstructed_text == text

    def test_faker_seed_does_not_reseed_global_random(self):
        pytest.importorskip("faker")
        import random

        random.seed(123)
        expected = random.random()
        random.seed(123)
        _patterns_only(replacement_mode="faker", faker_seed=7)
        assert random.random() == expected


class TestPatterns:
    def test_iban_followed_by_a_short_word(self):
        found = _types("IBAN: ES9121000418450200051332 BIC: CAIXESBB")
        assert found.get("ES9121000418450200051332") == "IBAN"
        found = _types("IBAN ES91 2100 0418 4502 0005 1332 EUR 500")
        assert found.get("ES91 2100 0418 4502 0005 1332") == "IBAN"

    @pytest.mark.parametrize(
        "address", ["2001:db8::8a2e:370:7334", "::1", "fe80::1", "2001:db8:0:0:0:0:2:1"]
    )
    def test_ipv6_is_matched_whole(self, address):
        assert _types(f"Server {address} is down").get(address) == "IP_ADDRESS"

    @pytest.mark.parametrize("text", ["at 10:30:45 today", "std::string x", "a :: b", "cafe::bad"])
    def test_ipv6_lookalikes_are_ignored(self, text):
        assert "IP_ADDRESS" not in _types(text).values()

    @pytest.mark.parametrize("text", ["MRN: 12345678", "MRN #12345678", "MRN-12345678"])
    def test_medical_record_separators(self, text):
        assert "MEDICAL_RECORD" in _types(text).values()

    @pytest.mark.parametrize("number", ["2221000000000009", "30569309025904"])
    def test_more_card_networks(self, number):
        assert _types(f"card {number}").get(number) == "CREDIT_CARD"

    def test_international_phone_keeps_its_country_code(self):
        assert _types("Call +44 7911 123456 now").get("+44 7911 123456") == "PHONE"

    @pytest.mark.parametrize(
        "text",
        [
            "I took 2 steps that way and saw 3 people in court",
            "The capacity is 50000 units",
            "Our hotel has 555 1234 rooms",
            "Order 123456789 shipped",
        ],
    )
    def test_no_match_without_a_real_cue(self, text):
        assert _types(text) == {}

    def test_unformatted_ssn_still_found_with_a_cue(self):
        assert _types("SSN 536904399").get("536904399") == "SSN"

    def test_street_address_still_found(self):
        assert _types("Ship to 1600 Pennsylvania Avenue").get("1600 Pennsylvania Avenue") == "LOC"

    def test_email_scan_is_linear(self):
        started = time.perf_counter()
        assert PatternDetector().detect("a." * 20000 + " x@example.com")
        assert time.perf_counter() - started < 2.0


class TestServer:
    def test_session_id_must_be_a_string(self):
        service = VeilService(pipeline=_patterns_only())
        with pytest.raises(ValueError):
            service.anonymize("hi", ["a"])  # type: ignore[arg-type]

    def test_reconstruct_never_creates_a_session(self):
        service = VeilService(pipeline=_patterns_only())
        with pytest.raises(UnknownSessionError):
            service.reconstruct("[EMAIL_1]", "nope")
        assert service.session_stats("nope") is None

    def test_sessions_round_trip(self):
        service = VeilService(pipeline=_patterns_only())
        a = service.anonymize("Mail a@example.com")
        b = service.anonymize("Mail b@example.org")
        assert service.reconstruct("[EMAIL_1]", a["session_id"])["reconstructed_text"] == (
            "a@example.com"
        )
        assert service.reconstruct("[EMAIL_1]", b["session_id"])["reconstructed_text"] == (
            "b@example.org"
        )


class TestSettings:
    def test_saved_file_is_owner_only(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{}")
        path.chmod(0o644)
        AppSettings().save(path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_unknown_keys_do_not_discard_the_file(self, tmp_path):
        path = tmp_path / "settings.json"
        data = AppSettings().to_dict()
        data["llm"]["model"] = "kept-model"
        data["llm"]["added_in_a_newer_version"] = True
        path.write_text(json.dumps(data))
        assert AppSettings.load(path).llm.model == "kept-model"

    def test_non_object_file_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("[]")
        assert AppSettings.load(path).to_dict() == AppSettings().to_dict()


class TestCli:
    TEXT = (
        "close tag [/foo] and [bold]x[/bold] for a@example.com, a fairly long line of text "
        "that is well past eighty columns so that a wrapping console would break it"
    )

    def test_json_output_is_valid_json_and_keeps_brackets(self):
        result = CliRunner().invoke(app, ["anonymize", self.TEXT, "--json", "--no-ner"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["anonymized"] == self.TEXT.replace("a@example.com", "[EMAIL_1]")

    def test_reconstruct_reads_anonymize_json(self, tmp_path):
        mapping = tmp_path / "m.json"
        runner = CliRunner()
        result = runner.invoke(
            app, ["anonymize", self.TEXT, "--json", "--no-ner", "-o", str(mapping)]
        )
        assert result.exit_code == 0, result.output
        result = runner.invoke(app, ["reconstruct", "write to email_1", "-m", str(mapping)])
        assert result.exit_code == 0, result.output
        assert "write to a@example.com" in result.output

    def test_reconstruct_without_mapping_is_an_error(self):
        assert CliRunner().invoke(app, ["reconstruct", "[EMAIL_1]"]).exit_code == 1


class TestFollowUps:
    def test_repeated_phrase_is_less_rare_than_a_single_mention(self):
        from veil.weighting.tfidf import DocumentStats, RarityScorer

        scorer = RarityScorer()
        once = DocumentStats.from_text("We met in New York. " + "filler words here " * 30)
        often = DocumentStats.from_text("New York is big. " * 30)
        assert scorer.score_multi_word("New York", once) > scorer.score_multi_word(
            "New York", often
        )
        mail = DocumentStats.from_text("write to bob@example.com please " * 30)
        assert scorer.score_multi_word("bob@example.com", mail) < 0.9

    def test_fake_value_is_not_restored_inside_a_longer_word(self):
        store = MappingStore()
        store.add("Lisbon", "West", EntityType.GPE)
        store.add("2024-01-15", "2009-03-21", EntityType.DATE)
        restored, count = store.restore("Westville, Western and West. At 2009-03-21T10:30")
        assert restored == "Westville, Western and Lisbon. At 2024-01-15T10:30"
        assert count == 2

    def test_lowercase_iban(self):
        assert _types("iban es9121000418450200051332 please").get(
            "es9121000418450200051332"
        ) == "IBAN"

    @pytest.mark.parametrize(
        "label,token", [("SKU2", "[SKU2_1]"), ("EMPLOYEE-ID", "[EMPLOYEE_ID_1]")]
    )
    def test_custom_label_with_digits_or_hyphen_round_trips(self, label, token):
        from veil.detection.patterns import pattern_from_dict

        pipe = _patterns_only()
        pipe.add_pattern(
            pattern_from_dict({"name": "code", "regex": r"\bZZ-\d{4}\b", "entity_type": label})
        )
        text = "Item ZZ-1234 is late"
        result = pipe.anonymize(text)
        assert result.anonymized_text == f"Item {token} is late"
        # also when the model drops the brackets
        bare = result.anonymized_text.replace("[", "").replace("]", "")
        assert pipe.reconstruct(bare).reconstructed_text == text

    def test_stats_reports_the_requested_profile(self):
        result = CliRunner().invoke(app, ["stats", "--profile", "paranoid"])
        assert result.exit_code == 0, result.output
        assert "paranoid" in result.output
        assert "Mappings" not in result.output
