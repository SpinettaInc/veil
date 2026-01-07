# Veil

**Privacy-preserving proxy for Large Language Models**

Veil automatically detects and anonymizes sensitive information before sending your data to LLMs, then reconstructs the original values in responses. Your private data never leaves your machine.

## Why Veil?

When you interact with LLMs like ChatGPT, Claude, or other AI services, your prompts are sent to remote servers. This creates privacy risks when your messages contain:

- Personal information (names, emails, phone numbers)
- Financial data (credit cards, bank accounts)
- Identity documents (SSN, passport numbers)
- Medical information
- Company secrets

**Veil solves this** by intercepting your text, replacing sensitive data with tokens, and reconstructing the response with your original values.

```
You: "John Smith, CEO of Acme Corp, needs help with taxes. SSN: 123-45-6789"
         ↓ Veil anonymizes
LLM sees: "[PERSON_1], CEO of [ORG_1], needs help with taxes. SSN: [SSN_1]"
         ↓ LLM responds
LLM: "For [PERSON_1] at [ORG_1], I recommend..."
         ↓ Veil reconstructs
You see: "For John Smith at Acme Corp, I recommend..."
```

## Key Features

<div class="grid cards" markdown>

-   :shield:{ .lg .middle } __Automatic PII Detection__

    ---

    Detects 20+ entity types including emails, phones, SSNs, credit cards, names, and addresses using hybrid detection.

-   :robot:{ .lg .middle } __Multiple LLM Providers__

    ---

    Works with OpenAI, Anthropic, Ollama (local), and 100+ providers via LiteLLM integration.

-   :gear:{ .lg .middle } __Configurable Profiles__

    ---

    Choose from Paranoid, Balanced, or Minimal detection sensitivity based on your needs.

-   :desktop_computer:{ .lg .middle } __Desktop App__

    ---

    Beautiful Gradio-based chat interface with built-in privacy protection and settings management.

</div>

## Quick Example

=== "CLI"

    ```bash
    # Anonymize text
    veil anonymize "My email is john@example.com"
    # Output: My email is [EMAIL_1]

    # Launch desktop app
    veil app
    ```

=== "Python"

    ```python
    from veil import VeilPipeline

    pipeline = VeilPipeline(profile="balanced")

    # Anonymize
    result = pipeline.anonymize("My email is john@example.com")
    print(result.anonymized_text)  # "My email is [EMAIL_1]"

    # Reconstruct
    response = pipeline.reconstruct("Noted your email [EMAIL_1]")
    print(response.reconstructed_text)  # "Noted your email john@example.com"
    ```

=== "LLM Proxy"

    ```python
    from veil.llm.proxy import VeilProxy
    from veil.llm.providers import OpenAIProvider, LLMConfig

    config = LLMConfig(api_key="sk-...", model="gpt-4o-mini")
    provider = OpenAIProvider(config)
    proxy = VeilProxy(provider, profile="balanced")

    # Chat with automatic privacy protection
    response = proxy.chat("My SSN is 123-45-6789")
    print(response.reconstructed_response)
    ```

## Installation

```bash
# Basic installation
pip install -e .

# With desktop app
pip install -e ".[desktop]"

# Download spaCy model
python -m spacy download en_core_web_sm
```

## Next Steps

- [Installation Guide](getting-started/installation.md) - Detailed installation instructions
- [Quick Start](getting-started/quickstart.md) - Get up and running in 5 minutes
- [CLI Reference](guide/cli.md) - Complete command-line documentation
- [Python API](guide/python-api.md) - Use Veil in your Python projects
