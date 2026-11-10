"""Settings management for Veil desktop app.

Handles loading, saving, and managing user configuration including
API keys, preferences, and LLM settings.
"""

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


def get_config_dir() -> Path:
    """Get the configuration directory for Veil.

    Uses platform-specific locations:
    - Linux: ~/.config/veil
    - macOS: ~/Library/Application Support/veil
    - Windows: %APPDATA%/veil
    """
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif os.name == "posix":
        if "darwin" in os.uname().sysname.lower():  # macOS
            base = Path.home() / "Library" / "Application Support"
        else:  # Linux
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    else:
        base = Path.home()

    config_dir = base / "veil"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / "settings.json"


@dataclass
class LLMSettings:
    """LLM-specific settings.

    Attributes:
        provider: Provider name (openai, anthropic, ollama)
        api_key: API key for the provider
        model: Model name to use
        base_url: Custom base URL (for Ollama or proxies)
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
    """

    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048


@dataclass
class PrivacySettings:
    """Privacy/anonymization settings.

    Attributes:
        profile: Detection profile (paranoid, balanced, minimal)
        detection_mode: Detection mode (standard, hybrid)
        replacement_mode: Replacement mode (token, faker, semantic)
        use_presidio: Whether to use Presidio
    """

    profile: str = "balanced"
    detection_mode: str = "hybrid"
    replacement_mode: str = "token"
    use_presidio: bool = True


@dataclass
class UISettings:
    """UI preferences.

    Attributes:
        theme: UI theme (light, dark, system)
        show_anonymization: Show anonymization details
        auto_clear_session: Clear session on new chat
    """

    theme: str = "system"
    show_anonymization: bool = True
    auto_clear_session: bool = False


def _known(section: type, values: dict[str, Any]) -> dict[str, Any]:
    """Drop keys the section does not define (a newer or hand-edited file)
    instead of discarding the whole file, API key included."""
    names = {f.name for f in fields(section)}
    return {k: v for k, v in values.items() if k in names}


@dataclass
class AppSettings:
    """Complete application settings.

    Attributes:
        llm: LLM provider settings
        privacy: Privacy/anonymization settings
        ui: UI preferences
        system_prompt: Default system prompt
    """

    llm: LLMSettings = field(default_factory=LLMSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)
    ui: UISettings = field(default_factory=UISettings)
    system_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "llm": asdict(self.llm),
            "privacy": asdict(self.privacy),
            "ui": asdict(self.ui),
            "system_prompt": self.system_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        """Create settings from dictionary."""
        return cls(
            llm=LLMSettings(**_known(LLMSettings, data.get("llm", {}))),
            privacy=PrivacySettings(**_known(PrivacySettings, data.get("privacy", {}))),
            ui=UISettings(**_known(UISettings, data.get("ui", {}))),
            system_prompt=data.get("system_prompt", ""),
        )

    def save(self, path: Path | None = None) -> None:
        """Save settings to file.

        Args:
            path: Optional custom path. Uses default if not specified.
        """
        config_file = path or get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # The file holds the API key: owner-only, also when it already exists
        fd = os.open(config_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        try:
            os.chmod(config_file, 0o600)
        except OSError:
            pass

    @classmethod
    def load(cls, path: Path | None = None) -> "AppSettings":
        """Load settings from file.

        Args:
            path: Optional custom path. Uses default if not specified.

        Returns:
            AppSettings instance (defaults if file doesn't exist)
        """
        config_file = path or get_config_file()

        if not config_file.exists():
            return cls()

        try:
            with open(config_file) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            # Return defaults if config is corrupted
            return cls()

    def update_llm(self, **kwargs: Any) -> None:
        """Update LLM settings.

        Args:
            **kwargs: LLM settings to update
        """
        for key, value in kwargs.items():
            if hasattr(self.llm, key):
                setattr(self.llm, key, value)

    def update_privacy(self, **kwargs: Any) -> None:
        """Update privacy settings.

        Args:
            **kwargs: Privacy settings to update
        """
        for key, value in kwargs.items():
            if hasattr(self.privacy, key):
                setattr(self.privacy, key, value)

    def update_ui(self, **kwargs: Any) -> None:
        """Update UI settings.

        Args:
            **kwargs: UI settings to update
        """
        for key, value in kwargs.items():
            if hasattr(self.ui, key):
                setattr(self.ui, key, value)


# Singleton instance
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Get the global settings instance.

    Returns:
        AppSettings singleton
    """
    global _settings
    if _settings is None:
        _settings = AppSettings.load()
    return _settings


def save_settings() -> None:
    """Save the global settings."""
    global _settings
    if _settings is not None:
        _settings.save()


def reset_settings() -> AppSettings:
    """Reset settings to defaults.

    Returns:
        New default AppSettings instance
    """
    global _settings
    _settings = AppSettings()
    _settings.save()
    return _settings
