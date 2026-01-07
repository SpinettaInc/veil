"""Ollama LLM provider for local models."""

import json
from typing import Generator, List, Optional

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM inference.

    Ollama runs models locally on your machine. It supports many open
    models like Llama, Mistral, Phi, etc.

    Example:
        >>> config = LLMConfig(
        ...     model="llama3.2",
        ...     base_url="http://localhost:11434"
        ... )
        >>> provider = OllamaProvider(config)
        >>> response = provider.chat([Message("user", "Hello!")])
        >>> print(response.content)
    """

    DEFAULT_MODELS = [
        "llama3.2",
        "llama3.2:1b",
        "llama3.1",
        "llama3.1:70b",
        "mistral",
        "mixtral",
        "phi3",
        "phi3:mini",
        "gemma2",
        "gemma2:2b",
        "qwen2.5",
        "codellama",
        "deepseek-coder",
    ]

    DEFAULT_URL = "http://localhost:11434"

    def __init__(self, config: LLMConfig):
        """Initialize Ollama provider.

        Args:
            config: Provider configuration. api_key is not required.
                   base_url defaults to http://localhost:11434

        Raises:
            ImportError: If requests package is not installed
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "Requests package not installed. Install with:\n"
                "  pip install requests"
            )

        super().__init__(config)

        self.base_url = config.base_url or self.DEFAULT_URL

    @property
    def name(self) -> str:
        return "Ollama"

    @property
    def available_models(self) -> List[str]:
        """Get list of available models.

        Attempts to fetch from Ollama API, falls back to defaults.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass

        return self.DEFAULT_MODELS

    def chat(
        self,
        messages: List[Message],
        **kwargs,
    ) -> LLMResponse:
        """Send a chat request to Ollama.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional options

        Returns:
            LLMResponse with the model's response
        """
        # Prepare messages
        api_messages = [m.to_dict() for m in messages]

        # Build request
        payload = {
            "model": self.config.model,
            "messages": api_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
            },
        }

        # Add max tokens if specified
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        # Call API
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()

        # Extract response
        content = data.get("message", {}).get("content", "")

        usage = {}
        if "eval_count" in data:
            usage["completion_tokens"] = data["eval_count"]
        if "prompt_eval_count" in data:
            usage["prompt_tokens"] = data["prompt_eval_count"]
        if usage:
            usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get(
                "completion_tokens", 0
            )

        return LLMResponse(
            content=content,
            model=data.get("model", self.config.model),
            usage=usage,
            raw_response=data,
        )

    def chat_stream(
        self,
        messages: List[Message],
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream a chat response from Ollama.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional options

        Yields:
            Chunks of the response text
        """
        api_messages = [m.to_dict() for m in messages]

        payload = {
            "model": self.config.model,
            "messages": api_messages,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
            },
        }

        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                except json.JSONDecodeError:
                    continue

    def validate_config(self) -> bool:
        """Validate Ollama configuration.

        Checks if Ollama is running and the model exists.
        """
        if not self.config.model:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            return response.status_code == 200
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
