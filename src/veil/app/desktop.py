"""Veil Desktop App - Privacy-preserving LLM Chat.

A Gradio-based desktop application for chatting with LLMs while
automatically protecting sensitive information.
"""

import gradio as gr
from typing import Generator, List, Optional, Tuple
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

from veil.config.settings import (
    AppSettings,
    get_settings,
    save_settings,
)
from veil.llm.providers.base import LLMConfig, Message
from veil.llm.providers.openai import OpenAIProvider, OPENAI_AVAILABLE
from veil.llm.providers.anthropic import AnthropicProvider, ANTHROPIC_AVAILABLE
from veil.llm.providers.ollama import OllamaProvider
from veil.llm.proxy import VeilProxy


# Provider options
PROVIDERS = {
    "OpenAI": {"available": OPENAI_AVAILABLE, "class": OpenAIProvider},
    "Anthropic": {"available": ANTHROPIC_AVAILABLE, "class": AnthropicProvider},
    "Ollama (Local)": {"available": True, "class": OllamaProvider},
}

# Model options by provider
MODELS = {
    "OpenAI": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1-mini",
    ],
    "Anthropic": [
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "Ollama (Local)": [
        "llama3.2",
        "llama3.1",
        "mistral",
        "mixtral",
        "phi3",
        "gemma2",
        "qwen2.5",
        "codellama",
    ],
}

# Global state
current_proxy: Optional[VeilProxy] = None
conversation_history: List[Message] = []


def create_proxy(settings: AppSettings) -> Optional[VeilProxy]:
    """Create a VeilProxy from settings."""
    global current_proxy

    provider_name = settings.llm.provider
    if provider_name not in PROVIDERS:
        return None

    provider_info = PROVIDERS[provider_name]
    if not provider_info["available"] and provider_name != "Ollama (Local)":
        return None

    # Create config
    config = LLMConfig(
        api_key=settings.llm.api_key,
        model=settings.llm.model,
        base_url=settings.llm.base_url or None,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
    )

    # Create provider
    try:
        provider = provider_info["class"](config)
    except Exception as e:
        print(f"Error creating provider: {e}")
        return None

    # Create proxy
    current_proxy = VeilProxy(
        provider=provider,
        profile=settings.privacy.profile,
        detection_mode=settings.privacy.detection_mode,
        replacement_mode=settings.privacy.replacement_mode,
        use_presidio=settings.privacy.use_presidio,
        system_prompt=settings.system_prompt or None,
    )

    return current_proxy


def chat_response(
    message: str,
    history: List[List[str]],
) -> Tuple[str, str, str, int]:
    """Process a chat message through Veil.

    Returns:
        Tuple of (response, anonymized_input, raw_response, entity_count)
    """
    global current_proxy, conversation_history

    if not current_proxy:
        return (
            "⚠️ Please configure your LLM settings first (click the Settings tab)",
            "",
            "",
            0,
        )

    if not message.strip():
        return "", "", "", 0

    try:
        # Build conversation history from Gradio history
        conv_history = []
        for user_msg, assistant_msg in history:
            if user_msg:
                conv_history.append(Message(role="user", content=user_msg))
            if assistant_msg:
                conv_history.append(Message(role="assistant", content=assistant_msg))

        # Send through proxy
        response = current_proxy.chat(message, conversation_history=conv_history)

        return (
            response.reconstructed_response,
            response.anonymized_input,
            response.raw_response,
            response.entities_found,
        )

    except Exception as e:
        return f"❌ Error: {str(e)}", "", "", 0


def chat_interface(
    message: str,
    history: List[List[str]],
) -> Generator[Tuple[List[List[str]], str, str, str], None, None]:
    """Gradio chat interface handler with streaming display."""
    if not message.strip():
        yield history, "", "", ""
        return

    response, anon_input, raw_resp, entity_count = chat_response(message, history)

    # Build info display
    if entity_count > 0:
        info = f"🔒 {entity_count} entities anonymized"
    else:
        info = "✅ No sensitive data detected"

    # Update history
    history = history + [[message, response]]

    yield history, info, anon_input, raw_resp


def save_llm_settings(
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Save LLM settings."""
    settings = get_settings()
    settings.llm.provider = provider
    settings.llm.api_key = api_key
    settings.llm.model = model
    settings.llm.base_url = base_url
    settings.llm.temperature = temperature
    settings.llm.max_tokens = int(max_tokens)
    save_settings()

    # Recreate proxy
    proxy = create_proxy(settings)
    if proxy:
        return "✅ Settings saved and connected!"
    else:
        return "⚠️ Settings saved but could not connect. Check your API key."


def save_privacy_settings(
    profile: str,
    detection_mode: str,
    replacement_mode: str,
    use_presidio: bool,
    system_prompt: str,
) -> str:
    """Save privacy settings."""
    settings = get_settings()
    settings.privacy.profile = profile.lower()
    settings.privacy.detection_mode = detection_mode.lower()
    settings.privacy.replacement_mode = replacement_mode.lower()
    settings.privacy.use_presidio = use_presidio
    settings.system_prompt = system_prompt
    save_settings()

    # Recreate proxy if exists
    if current_proxy:
        create_proxy(settings)

    return "✅ Privacy settings saved!"


def update_models(provider: str) -> gr.Dropdown:
    """Update model dropdown based on provider."""
    models = MODELS.get(provider, [])
    return gr.Dropdown(choices=models, value=models[0] if models else "")


def clear_chat() -> Tuple[List, str, str, str]:
    """Clear chat history and session."""
    global conversation_history
    conversation_history = []

    if current_proxy:
        current_proxy.clear_session()

    return [], "", "", ""


def test_connection(
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
) -> str:
    """Test LLM connection."""
    if provider == "Ollama (Local)":
        try:
            import requests
            url = base_url or "http://localhost:11434"
            resp = requests.get(f"{url}/api/tags", timeout=5)
            if resp.status_code == 200:
                return "✅ Ollama is running!"
            else:
                return f"❌ Ollama returned status {resp.status_code}"
        except Exception as e:
            return f"❌ Cannot connect to Ollama: {e}"

    if not api_key:
        return "❌ API key is required"

    # Create temp config
    config = LLMConfig(
        api_key=api_key,
        model=model,
        base_url=base_url or None,
    )

    try:
        provider_class = PROVIDERS[provider]["class"]
        prov = provider_class(config)
        # Try a simple request
        response = prov.chat([Message(role="user", content="Hi")])
        if response.content:
            return f"✅ Connected! Model: {response.model}"
        return "✅ Connected!"
    except Exception as e:
        return f"❌ Connection failed: {e}"


def create_app() -> gr.Blocks:
    """Create the Gradio app."""
    settings = get_settings()

    # Try to create proxy from saved settings
    if settings.llm.api_key or settings.llm.provider == "Ollama (Local)":
        create_proxy(settings)

    # Custom CSS
    css = """
    .container { max-width: 1200px; margin: auto; }
    .header { text-align: center; padding: 20px; }
    .info-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .anon-box {
        background: #f0f4f8;
        border-left: 4px solid #667eea;
        padding: 10px;
        font-family: monospace;
        font-size: 0.9em;
    }
    """

    with gr.Blocks(
        title="Veil - Privacy-Preserving LLM Chat",
        css=css,
        theme=gr.themes.Soft(),
    ) as app:
        # Header
        gr.Markdown(
            """
            # 🛡️ Veil - Privacy-Preserving LLM Chat

            Chat with AI while automatically protecting your sensitive information.
            Your data is anonymized before being sent to the LLM and reconstructed in responses.
            """
        )

        with gr.Tabs():
            # Chat Tab
            with gr.Tab("💬 Chat"):
                with gr.Row():
                    with gr.Column(scale=3):
                        chatbot = gr.Chatbot(
                            label="Conversation",
                            height=500,
                        )

                        with gr.Row():
                            msg_input = gr.Textbox(
                                label="Your message",
                                placeholder="Type your message here... (sensitive data will be automatically protected)",
                                lines=2,
                                scale=4,
                            )
                            send_btn = gr.Button("Send", variant="primary", scale=1)

                        with gr.Row():
                            clear_btn = gr.Button("🗑️ Clear Chat", size="sm")
                            status_text = gr.Textbox(
                                label="Status",
                                interactive=False,
                                scale=2,
                            )

                    with gr.Column(scale=2):
                        gr.Markdown("### 🔍 Anonymization Details")

                        anon_input_display = gr.Textbox(
                            label="Anonymized Input (sent to LLM)",
                            lines=4,
                            interactive=False,
                        )

                        raw_response_display = gr.Textbox(
                            label="Raw LLM Response (before reconstruction)",
                            lines=6,
                            interactive=False,
                        )

                # Event handlers
                send_btn.click(
                    chat_interface,
                    inputs=[msg_input, chatbot],
                    outputs=[chatbot, status_text, anon_input_display, raw_response_display],
                ).then(
                    lambda: "",
                    outputs=[msg_input],
                )

                msg_input.submit(
                    chat_interface,
                    inputs=[msg_input, chatbot],
                    outputs=[chatbot, status_text, anon_input_display, raw_response_display],
                ).then(
                    lambda: "",
                    outputs=[msg_input],
                )

                clear_btn.click(
                    clear_chat,
                    outputs=[chatbot, status_text, anon_input_display, raw_response_display],
                )

            # Settings Tab
            with gr.Tab("⚙️ Settings"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 🤖 LLM Configuration")

                        provider_dropdown = gr.Dropdown(
                            label="Provider",
                            choices=list(PROVIDERS.keys()),
                            value=settings.llm.provider or "OpenAI",
                        )

                        api_key_input = gr.Textbox(
                            label="API Key",
                            type="password",
                            value=settings.llm.api_key,
                            placeholder="Enter your API key (not needed for Ollama)",
                        )

                        model_dropdown = gr.Dropdown(
                            label="Model",
                            choices=MODELS.get(settings.llm.provider, MODELS["OpenAI"]),
                            value=settings.llm.model,
                            allow_custom_value=True,
                        )

                        base_url_input = gr.Textbox(
                            label="Base URL (optional)",
                            value=settings.llm.base_url,
                            placeholder="Custom API endpoint (e.g., http://localhost:11434 for Ollama)",
                        )

                        with gr.Row():
                            temperature_slider = gr.Slider(
                                label="Temperature",
                                minimum=0,
                                maximum=2,
                                step=0.1,
                                value=settings.llm.temperature,
                            )
                            max_tokens_input = gr.Number(
                                label="Max Tokens",
                                value=settings.llm.max_tokens,
                                minimum=100,
                                maximum=32000,
                            )

                        with gr.Row():
                            test_btn = gr.Button("🔌 Test Connection")
                            save_llm_btn = gr.Button("💾 Save LLM Settings", variant="primary")

                        llm_status = gr.Textbox(label="Status", interactive=False)

                    with gr.Column():
                        gr.Markdown("### 🔒 Privacy Settings")

                        profile_dropdown = gr.Dropdown(
                            label="Detection Profile",
                            choices=["Paranoid", "Balanced", "Minimal"],
                            value=settings.privacy.profile.title(),
                            info="Paranoid: Maximum protection | Balanced: Good tradeoff | Minimal: Only high-confidence PII",
                        )

                        detection_mode_dropdown = gr.Dropdown(
                            label="Detection Mode",
                            choices=["Hybrid", "Standard"],
                            value=settings.privacy.detection_mode.title(),
                            info="Hybrid: spaCy + Presidio + Patterns | Standard: spaCy + Patterns",
                        )

                        replacement_dropdown = gr.Dropdown(
                            label="Replacement Mode",
                            choices=["Token", "Faker", "Semantic"],
                            value=settings.privacy.replacement_mode.title(),
                            info="Token: [PERSON_1] | Faker: Realistic fakes | Semantic: Similar values",
                        )

                        use_presidio_checkbox = gr.Checkbox(
                            label="Use Presidio (enhanced PII detection)",
                            value=settings.privacy.use_presidio,
                        )

                        system_prompt_input = gr.Textbox(
                            label="System Prompt (optional)",
                            value=settings.system_prompt,
                            lines=4,
                            placeholder="Custom instructions for the AI assistant...",
                        )

                        save_privacy_btn = gr.Button("💾 Save Privacy Settings", variant="primary")
                        privacy_status = gr.Textbox(label="Status", interactive=False)

                # Settings event handlers
                provider_dropdown.change(
                    update_models,
                    inputs=[provider_dropdown],
                    outputs=[model_dropdown],
                )

                test_btn.click(
                    test_connection,
                    inputs=[provider_dropdown, api_key_input, model_dropdown, base_url_input],
                    outputs=[llm_status],
                )

                save_llm_btn.click(
                    save_llm_settings,
                    inputs=[
                        provider_dropdown,
                        api_key_input,
                        model_dropdown,
                        base_url_input,
                        temperature_slider,
                        max_tokens_input,
                    ],
                    outputs=[llm_status],
                )

                save_privacy_btn.click(
                    save_privacy_settings,
                    inputs=[
                        profile_dropdown,
                        detection_mode_dropdown,
                        replacement_dropdown,
                        use_presidio_checkbox,
                        system_prompt_input,
                    ],
                    outputs=[privacy_status],
                )

            # About Tab
            with gr.Tab("ℹ️ About"):
                gr.Markdown(
                    """
                    ## About Veil

                    Veil is a privacy-preserving proxy for Large Language Models. It automatically
                    detects and anonymizes sensitive information before sending your messages to AI,
                    then reconstructs the original values in the response.

                    ### Features

                    - 🔒 **Automatic PII Detection**: Emails, phone numbers, SSNs, names, addresses, and more
                    - 🤖 **Multiple LLM Providers**: OpenAI, Anthropic, and local models via Ollama
                    - 🎯 **Configurable Profiles**: Paranoid, Balanced, or Minimal detection
                    - 🔄 **Smart Reconstruction**: Original values restored in AI responses
                    - 🛡️ **Hybrid Detection**: Combines spaCy NER, Microsoft Presidio, and regex patterns

                    ### How It Works

                    1. You type a message containing sensitive information
                    2. Veil detects and replaces sensitive data with tokens (e.g., `john@email.com` → `[EMAIL_1]`)
                    3. The anonymized message is sent to the LLM
                    4. The LLM's response (containing tokens) is reconstructed with original values
                    5. You see the response with your real information restored

                    ### Privacy

                    - Your sensitive data never leaves your machine
                    - Only anonymized tokens are sent to the LLM provider
                    - Mappings are stored locally and cleared per session

                    ### Open Source

                    Veil is open source software. Visit the repository for more information.
                    """
                )

    return app


def launch_app(
    share: bool = False,
    server_port: int = 7860,
    server_name: str = "127.0.0.1",
) -> None:
    """Launch the Veil desktop app.

    Args:
        share: Whether to create a public link
        server_port: Port to run on
        server_name: Server hostname
    """
    app = create_app()
    app.launch(
        share=share,
        server_port=server_port,
        server_name=server_name,
        show_error=True,
    )


def main() -> None:
    """Entry point for veil-app command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Veil Desktop App - Privacy-preserving LLM Chat"
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public link",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to run on (default: 7860)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )

    args = parser.parse_args()

    print("Starting Veil Desktop App...")
    print(f"Open http://{args.host}:{args.port} in your browser")

    launch_app(
        share=args.share,
        server_port=args.port,
        server_name=args.host,
    )


if __name__ == "__main__":
    main()
