"""Basic: anonymize a message, inspect what was found, restore it.

Run: PYTHONPATH=src python examples/01_basic_anonymize.py
"""

from veil import VeilPipeline

pipeline = VeilPipeline()

text = (
    "Hi, I'm Priya Raghunathan (priya.r@example.com, +1 415-555-0199). "
    "My card 4111 1111 1111 1111 was charged twice on 2024-03-15 from IP 203.0.113.7."
)

result = pipeline.anonymize(text)

print("Original :", text)
print("Anonymized:", result.anonymized_text)
print()
print(f"{'entity':<28}{'type':<14}{'confidence':>10}")
for entity in result.entities:
    print(f"{entity.text:<28}{entity.entity_type.value:<14}{entity.confidence:>10.2f}")

# Whatever an LLM says about the tokens can be mapped back to the originals.
reply = "I've refunded the duplicate charge on [CREDIT_CARD_1] and emailed [EMAIL_1]."
print()
print("LLM reply   :", reply)
print("Reconstructed:", pipeline.reconstruct(reply).reconstructed_text)

assert pipeline.reconstruct(result.anonymized_text).reconstructed_text == text
