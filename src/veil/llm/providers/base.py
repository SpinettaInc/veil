"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A chat message.

    Attributes:
        role: The role (system, user, assistant)
        content: The message content
    """

    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """Response from an LLM.

    Attributes:
        content: The response text
        model: The model that generated the response
        usage: Token usage information
        raw_response: The raw response from the API
    """

    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: Any | None = None


@dataclass
class LLMConfig:
    """Configuration for an LLM provider.

    Attributes:
        api_key: API key for the provider
        model: Model name to use
        base_url: Optional base URL for the API
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        extra: Additional provider-specific options
    """

    api_key: str = ""
    model: str = ""
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    extra: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM providers must implement this interface.
    """

    def __init__(self, config: LLMConfig):
        """Initialize the provider.

        Args:
            config: Provider configuration
        """
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def available_models(self) -> list[str]:
        """List of available models."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat request to the LLM.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional provider-specific options

        Returns:
            LLMResponse with the model's response
        """
        pass

    def chat_stream(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Stream a chat response from the LLM.

        Default implementation just yields the full response.
        Providers can override for true streaming.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional provider-specific options

        Yields:
            Chunks of the response text
        """
        response = self.chat(messages, **kwargs)
        yield response.content

    def validate_config(self) -> bool:
        """Validate the provider configuration.

        Returns:
            True if configuration is valid
        """
        return bool(self.config.api_key and self.config.model)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.config.model})"
