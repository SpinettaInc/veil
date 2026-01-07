"""Anthropic LLM provider."""

from typing import Generator, List

try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None  # type: ignore

from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message


class AnthropicProvider(LLMProvider):
    """Anthropic API provider.

    Supports Claude models.

    Example:
        >>> config = LLMConfig(
        ...     api_key="sk-ant-...",
        ...     model="claude-sonnet-4-20250514"
        ... )
        >>> provider = AnthropicProvider(config)
        >>> response = provider.chat([Message("user", "Hello!")])
        >>> print(response.content)
    """

    DEFAULT_MODELS = [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]

    def __init__(self, config: LLMConfig):
        """Initialize Anthropic provider.

        Args:
            config: Provider configuration

        Raises:
            ImportError: If anthropic package is not installed
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "Anthropic package not installed. Install with:\n"
                "  pip install anthropic"
            )

        super().__init__(config)

        # Initialize client
        client_kwargs = {"api_key": config.api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url

        self.client = Anthropic(**client_kwargs)

    @property
    def name(self) -> str:
        return "Anthropic"

    @property
    def available_models(self) -> List[str]:
        return self.DEFAULT_MODELS

    def chat(
        self,
        messages: List[Message],
        **kwargs,
    ) -> LLMResponse:
        """Send a chat request to Anthropic.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional options (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with the model's response
        """
        # Separate system message from conversation
        system_message = ""
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                api_messages.append(msg.to_dict())

        # Merge config with kwargs
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        # Call API
        response = self.client.messages.create(
            model=self.config.model,
            messages=api_messages,
            system=system_message if system_message else None,
            temperature=temperature,
            max_tokens=max_tokens,
            **self.config.extra,
        )

        # Extract response
        content = ""
        if response.content:
            content = response.content[0].text

        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }

        return LLMResponse(
            content=content,
            model=response.model,
            usage=usage,
            raw_response=response,
        )

    def chat_stream(
        self,
        messages: List[Message],
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream a chat response from Anthropic.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional options

        Yields:
            Chunks of the response text
        """
        # Separate system message
        system_message = ""
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                api_messages.append(msg.to_dict())

        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        with self.client.messages.stream(
            model=self.config.model,
            messages=api_messages,
            system=system_message if system_message else None,
            temperature=temperature,
            max_tokens=max_tokens,
            **self.config.extra,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def validate_config(self) -> bool:
        """Validate Anthropic configuration."""
        if not self.config.api_key:
            return False
        if not self.config.model:
            return False
        return True
