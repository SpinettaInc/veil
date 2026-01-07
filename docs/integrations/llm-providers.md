# LLM Providers

Veil supports multiple LLM providers through its provider abstraction layer.

## Supported Providers

| Provider | Package | Models |
|----------|---------|--------|
| OpenAI | `openai` | GPT-4o, GPT-4, GPT-3.5 |
| Anthropic | `anthropic` | Claude 4, Claude 3.5, Claude 3 |
| Ollama | Built-in | Llama, Mistral, Phi, etc. |

## OpenAI

### Installation

```bash
pip install openai
# or
pip install veil[openai]
```

### Configuration

```python
from veil.llm.providers import OpenAIProvider, LLMConfig

config = LLMConfig(
    api_key="sk-...",
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=2048,
)

provider = OpenAIProvider(config)
```

### Available Models

- `gpt-4o` - Latest GPT-4 Omni
- `gpt-4o-mini` - Smaller, faster GPT-4
- `gpt-4-turbo` - GPT-4 Turbo
- `gpt-4` - GPT-4
- `gpt-3.5-turbo` - GPT-3.5
- `o1-mini` - Reasoning model

### Custom Endpoint

For Azure OpenAI or proxies:

```python
config = LLMConfig(
    api_key="your-key",
    model="gpt-4",
    base_url="https://your-resource.openai.azure.com/",
)
```

---

## Anthropic

### Installation

```bash
pip install anthropic
# or
pip install veil[anthropic]
```

### Configuration

```python
from veil.llm.providers import AnthropicProvider, LLMConfig

config = LLMConfig(
    api_key="sk-ant-...",
    model="claude-sonnet-4-20250514",
    temperature=0.7,
    max_tokens=2048,
)

provider = AnthropicProvider(config)
```

### Available Models

- `claude-sonnet-4-20250514` - Claude 4 Sonnet
- `claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet
- `claude-3-5-haiku-20241022` - Claude 3.5 Haiku
- `claude-3-opus-20240229` - Claude 3 Opus

---

## Ollama (Local)

Run LLMs locally without sending data to external services.

### Installation

1. Install Ollama: https://ollama.ai
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```
3. Start the server:
   ```bash
   ollama serve
   ```

### Configuration

```python
from veil.llm.providers import OllamaProvider, LLMConfig

config = LLMConfig(
    api_key="",  # Not needed
    model="llama3.2",
    base_url="http://localhost:11434",  # Default
)

provider = OllamaProvider(config)
```

### Available Models

- `llama3.2` - Meta Llama 3.2
- `llama3.1` - Meta Llama 3.1
- `mistral` - Mistral 7B
- `mixtral` - Mixtral 8x7B
- `phi3` - Microsoft Phi-3
- `gemma2` - Google Gemma 2
- `qwen2.5` - Alibaba Qwen 2.5
- `codellama` - Code Llama

### Custom Ollama Server

```python
config = LLMConfig(
    model="llama3.2",
    base_url="http://192.168.1.100:11434",  # Remote server
)
```

---

## Using with VeilProxy

Wrap any provider with privacy protection:

```python
from veil.llm.proxy import VeilProxy
from veil.llm.providers import OpenAIProvider, LLMConfig

# Create provider
config = LLMConfig(api_key="sk-...", model="gpt-4o-mini")
provider = OpenAIProvider(config)

# Wrap with Veil
proxy = VeilProxy(
    provider=provider,
    profile="balanced",
    detection_mode="hybrid",
)

# Chat with automatic privacy
response = proxy.chat("My SSN is 123-45-6789")
```

## Provider Comparison

| Feature | OpenAI | Anthropic | Ollama |
|---------|--------|-----------|--------|
| Cloud-based | Yes | Yes | No (local) |
| API key required | Yes | Yes | No |
| Streaming | Yes | Yes | Yes |
| Cost | Pay per token | Pay per token | Free |
| Privacy | Data sent to cloud | Data sent to cloud | 100% local |
| Speed | Fast | Fast | Depends on hardware |

## Checking Availability

```python
from veil.llm.providers import OPENAI_AVAILABLE, ANTHROPIC_AVAILABLE

if OPENAI_AVAILABLE:
    print("OpenAI SDK installed")

if ANTHROPIC_AVAILABLE:
    print("Anthropic SDK installed")
```

## Direct Provider Usage

Use providers without the Veil proxy:

```python
from veil.llm.providers import OpenAIProvider, LLMConfig, Message

config = LLMConfig(api_key="sk-...", model="gpt-4o-mini")
provider = OpenAIProvider(config)

# Simple chat
response = provider.chat([
    Message(role="user", content="Hello!")
])
print(response.content)

# Streaming
for chunk in provider.chat_stream([
    Message(role="user", content="Tell me a story")
]):
    print(chunk, end="", flush=True)
```

## Error Handling

```python
from veil.llm.providers import OpenAIProvider, LLMConfig

try:
    config = LLMConfig(api_key="invalid", model="gpt-4")
    provider = OpenAIProvider(config)
    response = provider.chat([Message(role="user", content="Hi")])
except Exception as e:
    print(f"API error: {e}")
```
