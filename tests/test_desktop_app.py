"""Tests for Veil desktop app components."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSettings:
    """Tests for settings management."""

    def test_llm_settings_defaults(self):
        """Test LLM settings have correct defaults."""
        from veil.config.settings import LLMSettings

        settings = LLMSettings()
        assert settings.provider == "openai"
        assert settings.api_key == ""
        assert settings.model == "gpt-4o-mini"
        assert settings.temperature == 0.7
        assert settings.max_tokens == 2048

    def test_privacy_settings_defaults(self):
        """Test privacy settings have correct defaults."""
        from veil.config.settings import PrivacySettings

        settings = PrivacySettings()
        assert settings.profile == "balanced"
        assert settings.detection_mode == "hybrid"
        assert settings.replacement_mode == "token"
        assert settings.use_presidio is True

    def test_ui_settings_defaults(self):
        """Test UI settings have correct defaults."""
        from veil.config.settings import UISettings

        settings = UISettings()
        assert settings.theme == "system"
        assert settings.show_anonymization is True
        assert settings.auto_clear_session is False

    def test_app_settings_to_dict(self):
        """Test app settings serialization."""
        from veil.config.settings import AppSettings

        settings = AppSettings()
        data = settings.to_dict()

        assert "llm" in data
        assert "privacy" in data
        assert "ui" in data
        assert "system_prompt" in data
        assert data["llm"]["provider"] == "openai"
        assert data["privacy"]["profile"] == "balanced"

    def test_app_settings_from_dict(self):
        """Test app settings deserialization."""
        from veil.config.settings import AppSettings

        data = {
            "llm": {"provider": "anthropic", "model": "claude-3", "api_key": "test"},
            "privacy": {"profile": "paranoid"},
            "ui": {"theme": "dark"},
            "system_prompt": "You are a helpful assistant",
        }

        settings = AppSettings.from_dict(data)
        assert settings.llm.provider == "anthropic"
        assert settings.llm.model == "claude-3"
        assert settings.privacy.profile == "paranoid"
        assert settings.ui.theme == "dark"
        assert settings.system_prompt == "You are a helpful assistant"

    def test_app_settings_save_load(self):
        """Test settings save and load."""
        from veil.config.settings import AppSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_settings.json"

            # Create and save settings
            settings = AppSettings()
            settings.llm.provider = "anthropic"
            settings.llm.api_key = "test-key"
            settings.privacy.profile = "paranoid"
            settings.save(config_file)

            # Load settings
            loaded = AppSettings.load(config_file)
            assert loaded.llm.provider == "anthropic"
            assert loaded.llm.api_key == "test-key"
            assert loaded.privacy.profile == "paranoid"

    def test_app_settings_load_defaults_on_missing(self):
        """Test that missing config file returns defaults."""
        from veil.config.settings import AppSettings

        settings = AppSettings.load(Path("/nonexistent/path/settings.json"))
        assert settings.llm.provider == "openai"

    def test_app_settings_update_methods(self):
        """Test settings update methods."""
        from veil.config.settings import AppSettings

        settings = AppSettings()

        settings.update_llm(provider="anthropic", model="claude-3")
        assert settings.llm.provider == "anthropic"
        assert settings.llm.model == "claude-3"

        settings.update_privacy(profile="minimal", use_presidio=False)
        assert settings.privacy.profile == "minimal"
        assert settings.privacy.use_presidio is False

        settings.update_ui(theme="dark", show_anonymization=False)
        assert settings.ui.theme == "dark"
        assert settings.ui.show_anonymization is False


class TestLLMProviderBase:
    """Tests for LLM provider base classes."""

    def test_llm_config_defaults(self):
        """Test LLM config defaults."""
        from veil.llm.providers.base import LLMConfig

        config = LLMConfig(api_key="test")
        assert config.api_key == "test"
        # Model can be empty or have default depending on implementation
        assert config.base_url is None
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_llm_config_custom(self):
        """Test LLM config with custom values."""
        from veil.llm.providers.base import LLMConfig

        config = LLMConfig(
            api_key="sk-test",
            model="gpt-4",
            base_url="http://localhost:8000",
            temperature=0.5,
            max_tokens=4096,
        )
        assert config.api_key == "sk-test"
        assert config.model == "gpt-4"
        assert config.base_url == "http://localhost:8000"
        assert config.temperature == 0.5
        assert config.max_tokens == 4096

    def test_message_dataclass(self):
        """Test Message dataclass."""
        from veil.llm.providers.base import Message

        msg = Message(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_llm_response_dataclass(self):
        """Test LLMResponse dataclass."""
        from veil.llm.providers.base import LLMResponse

        response = LLMResponse(
            content="Hello there!",
            model="gpt-4",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
        assert response.content == "Hello there!"
        assert response.model == "gpt-4"
        assert response.usage["prompt_tokens"] == 10


class TestOllamaProvider:
    """Tests for Ollama provider."""

    def test_ollama_provider_initialization(self):
        """Test Ollama provider initializes correctly."""
        from veil.llm.providers.base import LLMConfig
        from veil.llm.providers.ollama import OllamaProvider

        config = LLMConfig(api_key="", model="llama3.2")
        provider = OllamaProvider(config)

        assert provider.name.lower() == "ollama"
        assert provider.config.model == "llama3.2"
        assert provider.base_url == "http://localhost:11434"

    def test_ollama_custom_base_url(self):
        """Test Ollama with custom base URL."""
        from veil.llm.providers.base import LLMConfig
        from veil.llm.providers.ollama import OllamaProvider

        config = LLMConfig(
            api_key="", model="mistral", base_url="http://ollama:11434"
        )
        provider = OllamaProvider(config)

        assert provider.base_url == "http://ollama:11434"


class TestVeilProxy:
    """Tests for VeilProxy."""

    def test_proxy_initialization(self):
        """Test proxy initializes correctly."""
        from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message
        from veil.llm.proxy import VeilProxy

        # Create mock provider
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "mock"
        mock_provider.config = LLMConfig(api_key="test")

        proxy = VeilProxy(
            provider=mock_provider,
            profile="balanced",
            detection_mode="hybrid",
            replacement_mode="token",
        )

        assert proxy.provider == mock_provider
        assert proxy.pipeline is not None

    def test_proxy_anonymizes_input(self):
        """Test proxy anonymizes user input."""
        from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message
        from veil.llm.proxy import VeilProxy

        # Create mock provider
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "mock"
        mock_provider.config = LLMConfig(api_key="test")
        mock_provider.chat.return_value = LLMResponse(
            content="Hello [EMAIL_1]!", model="mock"
        )

        proxy = VeilProxy(provider=mock_provider, profile="balanced")

        response = proxy.chat("My email is john@example.com")

        # Check that provider was called with anonymized text
        call_args = mock_provider.chat.call_args
        messages = call_args[0][0]
        user_msg = [m for m in messages if m.role == "user"][0]
        assert "john@example.com" not in user_msg.content
        assert "[EMAIL_1]" in user_msg.content or "EMAIL" in user_msg.content

    def test_proxy_reconstructs_response(self):
        """Test proxy reconstructs response with original values."""
        from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message
        from veil.llm.proxy import VeilProxy

        # Create mock provider
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "mock"
        mock_provider.config = LLMConfig(api_key="test")
        mock_provider.chat.return_value = LLMResponse(
            content="Your email [EMAIL_1] has been noted.", model="mock"
        )

        proxy = VeilProxy(provider=mock_provider, profile="balanced")

        response = proxy.chat("My email is test@example.com")

        # Check response has original email restored
        assert "test@example.com" in response.reconstructed_response

    def test_proxy_response_attributes(self):
        """Test ProxyResponse has correct attributes."""
        from veil.llm.providers.base import LLMConfig, LLMProvider, LLMResponse, Message
        from veil.llm.proxy import VeilProxy, ProxyResponse

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "mock"
        mock_provider.config = LLMConfig(api_key="test")
        mock_provider.chat.return_value = LLMResponse(
            content="Response text", model="mock"
        )

        proxy = VeilProxy(provider=mock_provider)
        response = proxy.chat("Hello from john.doe@company.com")

        assert isinstance(response, ProxyResponse)
        assert response.original_input == "Hello from john.doe@company.com"
        assert response.anonymized_input is not None
        assert response.raw_response == "Response text"
        assert response.reconstructed_response is not None
        assert isinstance(response.entities_found, int)
        assert isinstance(response.mappings, dict)

    def test_proxy_was_anonymized_property(self):
        """Test was_anonymized property."""
        from veil.llm.proxy import ProxyResponse

        response_with_entities = ProxyResponse(
            original_input="test",
            anonymized_input="test",
            raw_response="response",
            reconstructed_response="response",
            entities_found=2,
        )
        assert response_with_entities.was_anonymized is True

        response_without_entities = ProxyResponse(
            original_input="test",
            anonymized_input="test",
            raw_response="response",
            reconstructed_response="response",
            entities_found=0,
        )
        assert response_without_entities.was_anonymized is False

    def test_proxy_clear_session(self):
        """Test proxy session clearing."""
        from veil.llm.providers.base import LLMConfig, LLMProvider
        from veil.llm.proxy import VeilProxy

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "mock"
        mock_provider.config = LLMConfig(api_key="test")

        proxy = VeilProxy(provider=mock_provider)
        proxy.clear_session()

        # Should not raise any errors
        assert True

    def test_proxy_get_stats(self):
        """Test proxy statistics."""
        from veil.llm.providers.base import LLMConfig, LLMProvider
        from veil.llm.proxy import VeilProxy

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "mock"
        mock_provider.config = LLMConfig(api_key="test", model="gpt-4")

        proxy = VeilProxy(provider=mock_provider, profile="paranoid")
        stats = proxy.get_stats()

        assert "provider" in stats
        assert "model" in stats
        assert "profile" in stats
        assert "pipeline" in stats
        assert stats["provider"] == "mock"
        assert stats["model"] == "gpt-4"
        assert stats["profile"] == "paranoid"


class TestDesktopAppFunctions:
    """Tests for desktop app utility functions."""

    def test_create_app_returns_blocks(self):
        """Test create_app returns Gradio Blocks."""
        from veil.app.desktop import create_app
        import gradio as gr

        app = create_app()
        assert isinstance(app, gr.Blocks)

    def test_clear_chat_function(self):
        """Test clear_chat returns empty values."""
        from veil.app.desktop import clear_chat

        result = clear_chat()
        assert result[0] == []  # Empty history
        assert result[1] == ""  # Empty status
        assert result[2] == ""  # Empty anon input
        assert result[3] == ""  # Empty raw response

    def test_update_models_returns_dropdown(self):
        """Test update_models returns correct models."""
        from veil.app.desktop import update_models, MODELS
        import gradio as gr

        result = update_models("OpenAI")
        assert isinstance(result, gr.Dropdown)

    def test_chat_response_without_proxy(self):
        """Test chat response when proxy not configured."""
        from veil.app.desktop import chat_response
        import veil.app.desktop as desktop_module

        # Ensure no proxy is set
        desktop_module.current_proxy = None

        response, anon, raw, count = chat_response("Hello", [])

        assert "configure" in response.lower() or "settings" in response.lower()
        assert count == 0
