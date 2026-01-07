"""Veil LLM Proxy - Privacy-preserving LLM interaction.

This module provides the core proxy functionality that:
1. Anonymizes user input before sending to LLM
2. Sends anonymized text to the LLM
3. Reconstructs the response with original values
"""

from dataclasses import dataclass, field
from typing import Generator, List, Optional

from veil.core.pipeline import VeilPipeline, AnonymizationResult
from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message
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
    mappings: dict = field(default_factory=dict)

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
        system_prompt: Optional[str] = None,
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
        )

    def chat(
        self,
        user_input: str,
        conversation_history: Optional[List[Message]] = None,
        **kwargs,
    ) -> ProxyResponse:
        """Send a chat message through the privacy proxy.

        Args:
            user_input: The user's message
            conversation_history: Optional previous messages
            **kwargs: Additional LLM options

        Returns:
            ProxyResponse with anonymized/reconstructed data
        """
        # Anonymize user input
        anon_result = self.pipeline.anonymize(user_input)

        # Build message list
        messages = []

        # Add system prompt if configured
        if self.system_prompt:
            messages.append(Message(role="system", content=self.system_prompt))

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)

        # Add anonymized user message
        messages.append(Message(role="user", content=anon_result.anonymized_text))

        # Call LLM
        llm_response = self.provider.chat(messages, **kwargs)

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
        conversation_history: Optional[List[Message]] = None,
        **kwargs,
    ) -> Generator[str, None, ProxyResponse]:
        """Stream a chat response through the privacy proxy.

        Note: Streaming returns tokens as they come. Full reconstruction
        happens at the end.

        Args:
            user_input: The user's message
            conversation_history: Optional previous messages
            **kwargs: Additional LLM options

        Yields:
            Chunks of the response (not yet reconstructed)

        Returns:
            ProxyResponse with full reconstructed response
        """
        # Anonymize user input
        anon_result = self.pipeline.anonymize(user_input)

        # Build message list
        messages = []

        if self.system_prompt:
            messages.append(Message(role="system", content=self.system_prompt))

        if conversation_history:
            messages.extend(conversation_history)

        messages.append(Message(role="user", content=anon_result.anonymized_text))

        # Stream response
        full_response = ""
        for chunk in self.provider.chat_stream(messages, **kwargs):
            full_response += chunk
            yield chunk

        # Reconstruct final response
        recon_result = self.pipeline.reconstruct(full_response)

        return ProxyResponse(
            original_input=user_input,
            anonymized_input=anon_result.anonymized_text,
            raw_response=full_response,
            reconstructed_response=recon_result.reconstructed_text,
            entities_found=anon_result.entity_count,
            mappings=anon_result.replacements,
        )

    def clear_session(self) -> None:
        """Clear the current session mappings.

        Call this when starting a new conversation to reset
        the anonymization mappings.
        """
        self.pipeline.clear_mappings()

    def get_stats(self) -> dict:
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
