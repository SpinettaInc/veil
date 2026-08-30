"""Veil LLM Proxy - Privacy-preserving LLM interaction.

This module provides the core proxy functionality that:
1. Anonymizes user input before sending to LLM
2. Sends anonymized text to the LLM
3. Reconstructs the response with original values
"""

import re
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

from veil.audit import AuditLogger
from veil.core.detector import DetectionUnavailableError
from veil.core.pipeline import AnonymizationResult, VeilPipeline
from veil.llm.providers.base import LLMProvider, Message
from veil.weighting.config import DetectionProfile


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

        # Parse profile
        try:
            self._profile = DetectionProfile(profile.lower())
        except ValueError:
            self._profile = DetectionProfile.BALANCED

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

        Any caller-supplied history is anonymized too: it is the natural
        thing to pass the original turns, and those must not reach the
        provider. Assistant turns are passed through the same pass, which is
        a no-op for text that only contains tokens.
        """
        anon_result = self.pipeline.anonymize(user_input)
        if anon_result.degraded and not self.allow_degraded:
            raise DetectionUnavailableError(
                "Refusing to send: detection is degraded ("
                + "; ".join(self.pipeline.detector.degradation_reasons)
                + "). Fix the installation or pass allow_degraded=True."
            )

        messages: list[Message] = []
        if self.system_prompt:
            messages.append(Message(role="system", content=self.system_prompt))

        history = self.history if conversation_history is None else [
            Message(
                role=m.role,
                content=self.pipeline.anonymize(m.content).anonymized_text
                if m.role == "user"
                else m.content,
            )
            for m in conversation_history
        ]
        messages.extend(history)
        messages.append(Message(role="user", content=anon_result.anonymized_text))
        return messages, anon_result

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

    def chat(
        self,
        user_input: str,
        conversation_history: list[Message] | None = None,
        **kwargs: Any,
    ) -> ProxyResponse:
        """Send a chat message through the privacy proxy.

        Args:
            user_input: The user's message
            conversation_history: Optional previous messages
            **kwargs: Additional LLM options

        Returns:
            ProxyResponse with anonymized/reconstructed data
        """
        messages, anon_result = self._prepare_messages(user_input, conversation_history)

        # Call LLM
        llm_response = self.provider.chat(messages, **kwargs)
        self._record_turn(anon_result.anonymized_text, llm_response.content)

        # Reconstruct response
        recon_result = self.pipeline.reconstruct(llm_response.content)

        return ProxyResponse(
            original_input=user_input,
            anonymized_input=anon_result.anonymized_text,
            raw_response=llm_response.content,
            reconstructed_response=recon_result.reconstructed_text,
            entities_found=anon_result.entity_count,
            mappings=anon_result.replacements,
        )

    def chat_stream(
        self,
        user_input: str,
        conversation_history: list[Message] | None = None,
        **kwargs: Any,
    ) -> Generator[str, None, ProxyResponse]:
        """Stream a chat response through the privacy proxy.

        Chunks are yielded already reconstructed. Because a token such as
        "[PERSON_1]" can be split across provider chunks, a possibly
        incomplete token at the end of the buffer is held back until the
        next chunk (or the end of the stream) resolves it.

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

        full_response = ""
        pending = ""
        for chunk in self.provider.chat_stream(messages, **kwargs):
            full_response += chunk
            pending += chunk
            safe_len = self._safe_flush_length(pending)
            if safe_len:
                yield self.pipeline.reconstruct(pending[:safe_len]).reconstructed_text
                pending = pending[safe_len:]
        if pending:
            yield self.pipeline.reconstruct(pending).reconstructed_text

        self._record_turn(anon_result.anonymized_text, full_response)
        recon_result = self.pipeline.reconstruct(full_response)

        return ProxyResponse(
            original_input=user_input,
            anonymized_input=anon_result.anonymized_text,
            raw_response=full_response,
            reconstructed_response=recon_result.reconstructed_text,
            entities_found=anon_result.entity_count,
            mappings=anon_result.replacements,
        )

    _PARTIAL_TOKEN_RE = re.compile(r"(?:[\[<{][^\]>}]{0,40}|[A-Z][A-Z_]{0,30}[\s_-]?\d{0,6})$")

    @classmethod
    def _safe_flush_length(cls, buffer: str) -> int:
        """Length of the prefix that cannot end inside a token.

        Holds back an unclosed bracket and its content, or a trailing run of
        uppercase letters/digits that could be the start of a bare "PERSON_1".
        """
        m = cls._PARTIAL_TOKEN_RE.search(buffer)
        return m.start() if m else len(buffer)

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
