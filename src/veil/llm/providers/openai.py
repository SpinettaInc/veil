"""OpenAI LLM provider."""

from collections.abc import Generator
from typing import Any, cast

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore

from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message


class OpenAIProvider(LLMProvider):
    """OpenAI API provider.

    Supports GPT-4, GPT-3.5, and other OpenAI models.
    Also works with OpenAI-compatible APIs (LocalAI, Ollama, etc.)

    Example:
        >>> config = LLMConfig(
        ...     api_key="sk-...",
        ...     model="gpt-4o-mini"
        ... )
        >>> provider = OpenAIProvider(config)
        >>> response = provider.chat([Message("user", "Hello!")])
        >>> print(response.content)
    """

    DEFAULT_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o1-pro",
    ]

    def __init__(self, config: LLMConfig):
        """Initialize OpenAI provider.

        Args:
            config: Provider configuration

        Raises:
            ImportError: If openai package is not installed
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI package not installed. Install with:\n"
                "  pip install openai"
            )

        super().__init__(config)

        # Initialize client
        client_kwargs: dict[str, Any] = {"api_key": config.api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url

        self.client = OpenAI(**client_kwargs)

    @property
    def name(self) -> str:
        return "OpenAI"

    @property
    def available_models(self) -> list[str]:
        return self.DEFAULT_MODELS

    def chat(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat request to OpenAI.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional options (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with the model's response
        """
        # Prepare messages
        api_messages: list[Any] = [m.to_dict() for m in messages]

        # Merge config with kwargs
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        # Call API
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **self.config.extra,
        )

        # Extract response
        content = response.choices[0].message.content or ""
        usage: dict[str, int] = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model=response.model,
            usage=usage,
            raw_response=response,
        )

    def chat_stream(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Stream a chat response from OpenAI.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional options

        Yields:
            Chunks of the response text
        """
        api_messages: list[Any] = [m.to_dict() for m in messages]

        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        stream = self.client.chat.completions.create(
            model=self.config.model,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **self.config.extra,
        )

        for chunk in cast(Any, stream):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def validate_config(self) -> bool:
        """Validate OpenAI configuration."""
        if not self.config.api_key:
            return False
        if not self.config.model:
            return False
        return True
