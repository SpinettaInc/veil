"""Advanced: the privacy proxy around an LLM, with history and streaming.

Uses a local stand-in provider so it runs offline. Swap in a real one:

    from veil.llm.providers import OpenAIProvider, AnthropicProvider, OllamaProvider, LLMConfig
    provider = OpenAIProvider(LLMConfig(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini"))
    provider = OllamaProvider(LLMConfig(model="llama3.2", base_url="http://localhost:11434"))

Run: PYTHONPATH=src python examples/04_llm_proxy.py
"""

from collections.abc import Iterator

from veil.llm.providers import LLMConfig, LLMProvider, LLMResponse, Message
from veil.llm.proxy import VeilProxy


class EchoAssistant(LLMProvider):
    """Pretends to be a model: refers to people/emails by the tokens it was given."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def available_models(self) -> list[str]:
        return ["echo"]

    def chat(self, messages: list[Message], **kwargs: object) -> LLMResponse:
        last = messages[-1].content
        print(f"   [provider received] {last}")
        return LLMResponse(
            content=f"Noted. I will email EMAIL_1 and cc [PERSON_1]. You said: {last}", model="echo"
        )

    def chat_stream(self, messages: list[Message], **kwargs: object) -> Iterator[str]:
        print(f"   [provider received] {messages[-1].content}")
        # Deliberately split a token across chunks
        yield from ["Sure, [PER", "SON_1]. Your ", "email EMAIL", "_1 is on file."]

    def validate_config(self) -> bool:
        return True


proxy = VeilProxy(
    EchoAssistant(LLMConfig(api_key="unused", model="echo")),
    profile="balanced",
    detection_mode="standard",  # "hybrid" adds Presidio if installed
    use_presidio=False,
)

print("1) First turn — the provider only ever sees tokens:")
r = proxy.chat("I'm Ana Kowalski, reach me at ana.k@example.org")
print("   user sees:", r.reconstructed_response)

print("\n2) Second turn — the proxy keeps the anonymized history itself:")
r = proxy.chat("Did you get my email address?")
print("   user sees:", r.reconstructed_response)
print("   history  :", [m.content for m in proxy.history])

print("\n3) Streaming — chunks arrive reconstructed, even when a token is split:")
print("   ", end="")
for chunk in proxy.chat_stream("Confirm please"):
    print(chunk, end="", flush=True)
print()

proxy.clear_session()
assert proxy.history == []
