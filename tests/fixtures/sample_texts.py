"""Sample texts for testing entity detection and anonymization."""

# Simple texts with named entities
SIMPLE_PERSON = "John Smith is a software engineer."
SIMPLE_ORG = "Acme Corporation is based in New York."
SIMPLE_MIXED = "John Smith works at Acme Corp in New York City."

# Texts with PII patterns
TEXT_WITH_EMAIL = "Contact me at john.smith@example.com for more info."
TEXT_WITH_PHONE = "Call us at (555) 123-4567 or 1-800-555-0199."
TEXT_WITH_SSN = "His social security number is 123-45-6789."
TEXT_WITH_CREDIT_CARD = "Payment card: 4111111111111111"
TEXT_WITH_IP = "The server IP is 192.168.1.100."

# Complex texts with multiple entities
COMPLEX_TEXT = """
Dear Mr. John Smith,

Thank you for your inquiry about Acme Corporation's services.
We have scheduled a meeting at our New York office on January 15, 2024.

Your account number is 4111-1111-1111-1111.
Please contact us at support@acme.com or call (555) 123-4567.

Best regards,
Jane Doe
Customer Service Manager
Acme Corporation
"""

# Medical/HIPAA text
MEDICAL_TEXT = """
Patient: Mary Johnson
MRN: MRN-12345678
DOB: March 15, 1985

Diagnosis: The patient was diagnosed with Type 2 diabetes.
Prescribed medication: Metformin 500mg twice daily.
Follow-up scheduled with Dr. Robert Wilson.
"""

# Business text
BUSINESS_TEXT = """
CEO John Smith announced that Acme Corp will acquire
TechStartup Inc. for $50 million. The deal is expected
to close by Q4 2024. Contact investor.relations@acme.com
for more information.
"""

# Text with no entities
NO_ENTITIES_TEXT = "This is a simple sentence with no sensitive information."

# Edge cases
EMPTY_TEXT = ""
WHITESPACE_TEXT = "   \n\t  "
REPEATED_ENTITIES = "John Smith met with John Smith to discuss John Smith's project."

# Expected detection results (for validation)
EXPECTED_DETECTIONS = {
    "SIMPLE_PERSON": ["John Smith"],
    "SIMPLE_ORG": ["Acme Corporation", "New York"],
    "TEXT_WITH_EMAIL": ["john.smith@example.com"],
    "TEXT_WITH_SSN": ["123-45-6789"],
}
