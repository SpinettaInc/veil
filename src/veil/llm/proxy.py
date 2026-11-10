"""Veil LLM Proxy - Privacy-preserving LLM interaction.

This module provides the core proxy functionality that:
1. Anonymizes user input before sending to LLM
2. Sends anonymized text to the LLM
3. Reconstructs the response with original values
"""

import re
from collections.abc import Collection, Generator, Sequence
from dataclasses import dataclass, field
from typing import Any

from veil.audit import AuditLogger
from veil.core.detector import DetectionUnavailableError
from veil.core.mapper import token_identity
from veil.core.pipeline import AnonymizationResult, VeilPipeline
from veil.llm.providers.base import LLMProvider, Message
from veil.weighting.config import parse_profile


@dataclass
class ProxyResponse:
    """Response from the Veil proxy.

    Attributes:
        original_input: Original user input
        anonymized_input: Input after anonymization
        raw_response: Raw LLM response (with tokens)
        reconstructed_response: Response with original values restored
        entities_found: Number of entities detected
        mappings: Entity to token mappings used
    """

    original_input: str
    anonymized_input: str
    raw_response: str
    reconstructed_response: str
    entities_found: int = 0
    mappings: dict[str, str] = field(default_factory=dict)

    @property
    def was_anonymized(self) -> bool:
        return self.entities_found > 0


class VeilProxy:
    """Privacy-preserving LLM proxy.

    Wraps an LLM provider with Veil's anonymization and reconstruction
    capabilities to protect sensitive information.

    Example:
        >>> from veil.llm.providers import OpenAIProvider, LLMConfig
        >>> config = LLMConfig(api_key="sk-...", model="gpt-4o-mini")
        >>> provider = OpenAIProvider(config)
        >>> proxy = VeilProxy(provider, profile="paranoid")
        >>>
        >>> response = proxy.chat("My email is john@example.com, help me write a message")
        >>> print(response.reconstructed_response)

    Attributes:
        provider: The LLM provider to use
        pipeline: The Veil pipeline for anonymization
        system_prompt: Optional system prompt to prepend
    """

    def __init__(
        self,
        provider: LLMProvider,
        profile: str = "balanced",
        detection_mode: str = "hybrid",
        replacement_mode: str = "token",
        use_presidio: bool = True,
        system_prompt: str | None = None,
        strict: bool = True,
        allow_degraded: bool = False,
        audit: AuditLogger | None = None,
    ):
        """Initialize the Veil proxy.

        Args:
            provider: LLM provider to wrap
            profile: Detection profile (paranoid, balanced, minimal)
            detection_mode: Detection mode (standard, hybrid)
            replacement_mode: Replacement mode (token, faker, semantic)
            use_presidio: Whether to use Presidio detection
            system_prompt: Optional system prompt
        """
        self.provider = provider
        self.system_prompt = system_prompt
        self.allow_degraded = allow_degraded
        # Conversation history as the provider saw it (anonymized user turns,
        # raw model turns). Callers never need to keep their own copy.
        self.history: list[Message] = []

        self._profile = parse_profile(profile)

        # Create pipeline
        self.pipeline = VeilPipeline(
            use_ner=True,
            use_patterns=True,
            use_presidio=use_presidio,
            profile=self._profile,
            detection_mode=detection_mode,
            replacement_mode=replacement_mode,
            strict=strict,
            audit=audit,
        )

    def _prepare_messages(
        self, user_input: str, conversation_history: list[Message] | None
    ) -> tuple[list[Message], "AnonymizationResult"]:
        """Anonymize the input and assemble the outbound message list.

        Everything that leaves for the provider goes through the pipeline:
        the new user turn, the system prompt, and every turn of a
        caller-supplied history. Callers naturally hold the *original* user
        turns and the *reconstructed* assistant turns, both of which contain
        the data being protected; for text that only contains tokens the pass
        is a no-op.
        """
        if self.pipeline.detector.degraded and not self.allow_degraded:
            raise DetectionUnavailableError(
                "Refusing to send: detection is degraded ("
                + "; ".join(self.pipeline.detector.degradation_reasons)
                + "). Fix the installation or pass allow_degraded=True."
            )
        anon_result = self.pipeline.anonymize(user_input)

        messages: list[Message] = []
        if self.system_prompt:
            messages.append(Message(role="system", content=self._anonymized(self.system_prompt)))

        if conversation_history is None:
            messages.extend(self.history)
        else:
            messages.extend(
                Message(role=m.role, content=self._anonymized(m.content))
                for m in conversation_history
            )
        messages.append(Message(role="user", content=anon_result.anonymized_text))
        return messages, anon_result

    def _anonymized(self, text: str) -> str:
        return self.pipeline.anonymize(text).anonymized_text

    def _record_turn(self, anonymized_input: str, raw_response: str) -> None:
        self.history.append(Message(role="user", content=anonymized_input))
        self.history.append(Message(role="assistant", content=raw_response))
        if self.pipeline.audit is not None:
            self.pipeline.audit.log_event(
                "llm_request",
                provider=self.provider.name,
                model=self.provider.config.model,
                turns=len(self.history) // 2,
                response_chars=len(raw_response),
            )

    def _build_response(
        self, user_input: str, anon_result: "AnonymizationResult", raw_response: str
    ) -> ProxyResponse:
        return ProxyResponse(
            original_input=user_input,
            anonymized_input=anon_result.anonymized_text,
            raw_response=raw_response,
            reconstructed_response=self.pipeline.reconstruct(raw_response).reconstructed_text,
            entities_found=anon_result.entity_count,
            mappings=anon_result.replacements,
        )

    def chat(
        self,
        user_input: str,
        conversation_history: list[Message] | None = None,
        **kwargs: Any,
    ) -> ProxyResponse:
        """Send a chat message through the privacy proxy.

        Args:
            user_input: The user's message
            conversation_history: Optional previous messages; anonymized
                before sending. Omit it to use the proxy's own ``history``.
            **kwargs: Additional LLM options

        Returns:
            ProxyResponse with anonymized/reconstructed data
        """
        messages, anon_result = self._prepare_messages(user_input, conversation_history)

        llm_response = self.provider.chat(messages, **kwargs)
        self._record_turn(anon_result.anonymized_text, llm_response.content)
        return self._build_response(user_input, anon_result, llm_response.content)

    def chat_stream(
        self,
        user_input: str,
        conversation_history: list[Message] | None = None,
        **kwargs: Any,
    ) -> Generator[str, None, ProxyResponse]:
        """Stream a chat response through the privacy proxy.

        Chunks are yielded already reconstructed. Because a replacement such
        as "[PERSON_1]" (or a fake name in faker mode) can be split across
        provider chunks, a possibly incomplete replacement at the end of the
        buffer is held back until the next chunk (or the end of the stream)
        resolves it.

        Args:
            user_input: The user's message
            conversation_history: Optional previous messages
            **kwargs: Additional LLM options

        Yields:
            Reconstructed chunks of the response

        Returns:
            ProxyResponse with full reconstructed response
        """
        messages, anon_result = self._prepare_messages(user_input, conversation_history)
        replacements = [entry.replacement for entry in self.pipeline.mapping_store]
        identities = [token_identity(r) for r in replacements]
        token_types = {ident[0] for ident in identities if ident is not None}
        literals = [r for r, ident in zip(replacements, identities) if ident is None]

        full_response = ""
        pending = ""
        try:
            for chunk in self.provider.chat_stream(messages, **kwargs):
                full_response += chunk
                pending += chunk
                safe_len = self._safe_flush_length(pending, literals, token_types)
                if safe_len:
                    yield self.pipeline.reconstruct(pending[:safe_len]).reconstructed_text
                    pending = pending[safe_len:]
            if pending:
                yield self.pipeline.reconstruct(pending).reconstructed_text
        finally:
            # The user turn was sent even if the stream failed or the caller
            # stopped reading; keep whatever came back so the next turn has it.
            if full_response:
                self._record_turn(anon_result.anonymized_text, full_response)

        return self._build_response(user_input, anon_result, full_response)

    # An unclosed bracket and its content, or a trailing run of uppercase
    # letters/digits that could be the start of a bare "PERSON_1"
    _PARTIAL_TOKEN_RE = re.compile(r"(?:[\[<{][^\]>}]{0,40}|[A-Z][A-Z_]{0,30}[\s_-]?\d{0,6})$")
    _WORD_START_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]")
    _TAIL_WINDOW = 48

    @classmethod
    def _safe_flush_length(
        cls,
        buffer: str,
        literals: Sequence[str] = (),
        token_types: Collection[str] = (),
    ) -> int:
        """Length of the prefix that cannot end inside a replacement.

        Held back at the end of the buffer:

        - an unclosed bracket, or trailing uppercase that may be a bare token;
        - a tail that, ignoring case and separators, is the start of a token
          of one of ``token_types`` ("Person_", "credit card", "person 1" —
          models rewrite tokens, and reconstruction accepts these forms);
        - a tail that is the start of one of ``literals`` (faker/semantic
          values), and the cut never falls inside a complete literal.
        """
        m = cls._PARTIAL_TOKEN_RE.search(buffer)
        cut = m.start() if m else len(buffer)

        if token_types:
            window_start = max(0, len(buffer) - cls._TAIL_WINDOW)
            for word in cls._WORD_START_RE.finditer(buffer, window_start, cut):
                if cls._may_become_token(buffer[word.start() :], token_types):
                    cut = word.start()
                    break

        for literal in literals:
            for k in range(min(len(literal) - 1, len(buffer)), 0, -1):
                if buffer.endswith(literal[:k]):
                    cut = min(cut, len(buffer) - k)
                    break
        moved = True
        while moved:
            moved = False
            for literal in literals:
                for i in range(max(0, cut - len(literal) + 1), cut):
                    if buffer.startswith(literal, i):
                        cut, moved = i, True
                        break
        return cut

    @staticmethod
    def _may_become_token(tail: str, token_types: Collection[str]) -> bool:
        """Whether ``tail`` could still grow into "<TYPE> <number>"."""
        normalized = re.sub(r"[\s_-]+", "_", tail).upper()
        name = normalized.rstrip("0123456789")
        has_number = len(name) < len(normalized)
        name = name.rstrip("_")
        whole = normalized.rstrip("_")  # the type itself may end in a digit ("SKU2")
        if not whole or not re.fullmatch(r"[A-Z0-9_]+", whole):
            return False
        if any(t.startswith(whole) for t in token_types):
            return True
        # "person_1" may still become "person_12"
        return has_number and name in token_types

    def clear_session(self) -> None:
        """Clear the current session: mappings and conversation history.

        Call this when starting a new conversation.
        """
        self.pipeline.clear_mappings()
        self.history.clear()
        if self.pipeline.audit is not None:
            self.pipeline.audit.log_event("session_clear")
            self.pipeline.audit.new_session()

    def get_stats(self) -> dict[str, Any]:
        """Get proxy statistics.

        Returns:
            Dictionary with proxy and pipeline stats
        """
        return {
            "provider": self.provider.name,
            "model": self.provider.config.model,
            "profile": self._profile.value,
            "pipeline": self.pipeline.get_stats(),
        }
