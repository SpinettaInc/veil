# LLM proxy

`VeilProxy` wraps a provider so the model only ever receives anonymized text,
and returns the reply with the originals restored.

```python
import os

from veil.llm.providers import AnthropicProvider, LLMConfig, OllamaProvider, OpenAIProvider
from veil.llm.proxy import VeilProxy

provider = OpenAIProvider(LLMConfig(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini"))
# provider = AnthropicProvider(LLMConfig(api_key=os.environ["ANTHROPIC_API_KEY"], model="..."))
# provider = OllamaProvider(LLMConfig(model="llama3.2", base_url="http://localhost:11434"))

proxy = VeilProxy(
    provider,
    profile="balanced",          # name; unknown names raise ValueError
    detection_mode="hybrid",     # default; needs Presidio unless use_presidio=False
    replacement_mode="token",
    use_presidio=True,
    system_prompt="You are a helpful assistant.",   # anonymized before sending
    strict=True,                 # raise DetectionUnavailableError if a detector is missing
    allow_degraded=False,        # with strict=False, still refuse to send degraded text
    audit=None,                  # AuditLogger: adds llm_request events
)

response = proxy.chat("My e-mail is jane@example.com, draft a reply to Omar Sample")
response.anonymized_input          # what the provider received
response.raw_response              # the model's reply, with tokens
response.reconstructed_response    # the reply for the user
response.entities_found
response.was_anonymized
response.mappings
```

Without Presidio installed, use `detection_mode="standard", use_presidio=False`.

`LLMConfig` fields: `api_key`, `model`, `base_url`, `temperature`,
`max_tokens`, `extra`. Read keys from the environment; never write them into
code. Install the SDKs with `pip install "veil[openai]"` or
`"veil[anthropic]"`; Ollama needs `requests`.

## Conversation

The proxy owns the history in the form the provider saw it: anonymized user
turns and raw model turns. Follow-ups work without the caller keeping a copy.

```python
proxy.chat("My e-mail is jane@example.com")
proxy.chat("Send the report there")     # provider sees [EMAIL_1] again
proxy.history                           # list[Message], anonymized
proxy.clear_session()                   # new conversation: mappings and history
proxy.get_stats()
```

To restore a stored conversation, pass
`conversation_history=[Message(role=..., content=...)]`. Every message in it,
whatever its role, is anonymized before sending, so original turns are safe to
pass.

## Streaming

```python
for chunk in proxy.chat_stream("My SSN is 123-45-6789"):
    print(chunk, end="", flush=True)
```

Chunks arrive already reconstructed. A token or fake value split across
provider chunks is held back until it is complete, so a partial `[PERS` never
reaches the user.

## A custom provider

Any model can sit behind the proxy. Subclass `LLMProvider`:

```python
from collections.abc import Iterator

from veil.llm.providers import LLMConfig, LLMProvider, LLMResponse, Message


class MyProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "mine"

    @property
    def available_models(self) -> list[str]:
        return ["my-model"]

    def chat(self, messages: list[Message], **kwargs: object) -> LLMResponse:
        text = call_my_model([m.to_dict() for m in messages])
        return LLMResponse(content=text, model="my-model")

    def chat_stream(self, messages: list[Message], **kwargs: object) -> Iterator[str]:
        yield from stream_my_model([m.to_dict() for m in messages])


proxy = VeilProxy(MyProvider(LLMConfig(model="my-model")))
```

`examples/04_llm_proxy.py` in the repository is a runnable offline version.

## Choosing a replacement mode for model calls

Use `token`. Models copy tokens faithfully, and reconstruction tolerates the
ways they rewrite them. Fake values get paraphrased, abbreviated or
"corrected", and those variants cannot be mapped back.
