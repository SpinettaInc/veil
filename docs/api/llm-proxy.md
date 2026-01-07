# LLM Proxy API Reference

## VeilProxy

Privacy-preserving proxy that wraps LLM providers.

```python
from veil.llm.proxy import VeilProxy
```

### Constructor

```python
VeilProxy(
    provider: LLMProvider,
    profile: str = "balanced",
    detection_mode: str = "hybrid",
    replacement_mode: str = "token",
    use_presidio: bool = True,
    system_prompt: str | None = None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | LLMProvider | required | LLM provider instance |
| `profile` | str | "balanced" | Detection profile |
| `detection_mode` | str | "hybrid" | Detection mode |
| `replacement_mode` | str | "token" | Replacement mode |
| `use_presidio` | bool | True | Enable Presidio |
| `system_prompt` | str | None | System prompt |

### Methods

#### chat

Send a chat message through the privacy proxy.

```python
def chat(
    self,
    user_input: str,
    conversation_history: list[Message] | None = None,
    **kwargs,
) -> ProxyResponse
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_input` | str | User's message |
| `conversation_history` | list[Message] | Previous messages |
| `**kwargs` | dict | Additional LLM options |

**Returns:** `ProxyResponse`

**Example:**

```python
response = proxy.chat("My SSN is 123-45-6789")
print(response.reconstructed_response)
```

---

#### chat_stream

Stream a chat response through the privacy proxy.

```python
def chat_stream(
    self,
    user_input: str,
    conversation_history: list[Message] | None = None,
    **kwargs,
) -> Generator[str, None, ProxyResponse]
```

**Yields:** Response chunks (not yet reconstructed)

**Returns:** `ProxyResponse` with full reconstructed response

**Example:**

```python
gen = proxy.chat_stream("Tell me about yourself")
for chunk in gen:
    print(chunk, end="", flush=True)
```

---

#### clear_session

Clear the current session mappings.

```python
def clear_session(self) -> None
```

---

#### get_stats

Get proxy statistics.

```python
def get_stats(self) -> dict
```

**Returns:**

```python
{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "profile": "balanced",
    "pipeline": {...}
}
```

---

## ProxyResponse

Response from the Veil proxy.

```python
from veil.llm.proxy import ProxyResponse
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `original_input` | str | Original user input |
| `anonymized_input` | str | Input after anonymization |
| `raw_response` | str | Raw LLM response (with tokens) |
| `reconstructed_response` | str | Response with original values |
| `entities_found` | int | Number of entities detected |
| `mappings` | dict | Entity to token mappings |

### Properties

#### was_anonymized

Whether any entities were anonymized.

```python
@property
def was_anonymized(self) -> bool
```

### Example

```python
response = proxy.chat("Email me at john@example.com")

print(response.original_input)
# "Email me at john@example.com"

print(response.anonymized_input)
# "Email me at [EMAIL_1]"

print(response.raw_response)
# "I'll send the email to [EMAIL_1]."

print(response.reconstructed_response)
# "I'll send the email to john@example.com."

print(response.entities_found)
# 1

print(response.was_anonymized)
# True

print(response.mappings)
# {"john@example.com": "[EMAIL_1]"}
```

---

## LLMProvider

Abstract base class for LLM providers.

```python
from veil.llm.providers.base import LLMProvider
```

### Abstract Methods

#### chat

```python
@abstractmethod
def chat(self, messages: list[Message], **kwargs) -> LLMResponse
```

#### chat_stream

```python
def chat_stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]
```

### Properties

#### name

Provider name.

```python
@property
def name(self) -> str
```

---

## LLMConfig

Configuration for LLM providers.

```python
from veil.llm.providers.base import LLMConfig
```

### Constructor

```python
@dataclass
class LLMConfig:
    api_key: str
    model: str = ""
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
```

---

## Message

Chat message.

```python
from veil.llm.providers.base import Message
```

### Constructor

```python
@dataclass
class Message:
    role: str  # "system", "user", "assistant"
    content: str
```

---

## LLMResponse

Response from an LLM provider.

```python
from veil.llm.providers.base import LLMResponse
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `content` | str | Response text |
| `model` | str | Model used |
| `usage` | dict | Token usage stats |

---

## Provider Implementations

### OpenAIProvider

```python
from veil.llm.providers import OpenAIProvider

config = LLMConfig(api_key="sk-...", model="gpt-4o-mini")
provider = OpenAIProvider(config)
```

### AnthropicProvider

```python
from veil.llm.providers import AnthropicProvider

config = LLMConfig(api_key="sk-ant-...", model="claude-sonnet-4-20250514")
provider = AnthropicProvider(config)
```

### OllamaProvider

```python
from veil.llm.providers import OllamaProvider

config = LLMConfig(model="llama3.2", base_url="http://localhost:11434")
provider = OllamaProvider(config)
```
