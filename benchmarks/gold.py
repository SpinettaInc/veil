"""Labeled benchmark corpus for Veil detection precision/recall.

Each case is (text, gold) where gold is a list of (substring, entity_type_name).
A substring appearing more than once in the text is expected at every occurrence.
Entity type names are loose groups: LOC covers LOC/GPE/FAC.
"""

CASES: list[tuple[str, list[tuple[str, str]]]] = [
    # --- structured PII ---
    ("Contact me at john.smith@example.com for more info.", [("john.smith@example.com", "EMAIL")]),
    (
        "Send it to Sarah <sarah.o'neil+work@mail.co.uk> by Friday.",
        [("sarah.o'neil+work@mail.co.uk", "EMAIL"), ("Sarah", "PERSON")],
    ),
    ("His social security number is 123-45-6789.", [("123-45-6789", "SSN")]),
    ("SSN: 219 09 9999", [("219 09 9999", "SSN")]),
    ("Payment card: 4111111111111111", [("4111111111111111", "CREDIT_CARD")]),
    ("Card 5500-0000-0000-0004 expires 12/27.", [("5500-0000-0000-0004", "CREDIT_CARD")]),
    ("Amex 3782 822463 10005 was declined.", [("3782 822463 10005", "CREDIT_CARD")]),
    (
        "Call us at (555) 123-4567 or 1-800-555-0199.",
        [("(555) 123-4567", "PHONE"), ("1-800-555-0199", "PHONE")],
    ),
    ("My mobile is +44 7911 123456.", [("+44 7911 123456", "PHONE")]),
    ("Reach me on +61412345678 anytime.", [("+61412345678", "PHONE")]),
    ("Tel: 555.867.5309", [("555.867.5309", "PHONE")]),
    ("The server IP is 192.168.1.100.", [("192.168.1.100", "IP_ADDRESS")]),
    (
        "Connect to 2001:0db8:85a3:0000:0000:8a2e:0370:7334 over v6.",
        [("2001:0db8:85a3:0000:0000:8a2e:0370:7334", "IP_ADDRESS")],
    ),
    (
        "Docs are at https://internal.example.com/wiki/page?id=3.",
        [("https://internal.example.com/wiki/page?id=3", "URL")],
    ),
    ("IBAN: DE89 3704 0044 0532 0130 00", [("DE89 3704 0044 0532 0130 00", "IBAN")]),
    ("Wire to GB29NWBK60161331926819 please.", [("GB29NWBK60161331926819", "IBAN")]),
    ("Passport number C01234567 issued 2019.", [("C01234567", "PASSPORT")]),
    ("Driver's license: D1234567", [("D1234567", "DRIVER_LICENSE")]),
    ("MRN: MRN-12345678", [("MRN-12345678", "MEDICAL_RECORD")]),
    ("Account number 000123456789 at Chase.", [("000123456789", "BANK_ACCOUNT"), ("Chase", "ORG")]),
    (
        "Ship to 742 Evergreen Terrace, Springfield.",
        [("742 Evergreen Terrace", "LOC"), ("Springfield", "LOC")],
    ),
    ("Our office: 1600 Pennsylvania Avenue NW", [("1600 Pennsylvania Avenue", "LOC")]),
    # --- named entities ---
    ("John Smith is a software engineer.", [("John Smith", "PERSON")]),
    ("Acme Corporation is based in New York.", [("Acme Corporation", "ORG"), ("New York", "LOC")]),
    (
        "John Smith works at Acme Corp in New York City.",
        [("John Smith", "PERSON"), ("Acme Corp", "ORG"), ("New York City", "LOC")],
    ),
    (
        "Dr. Robert Wilson will see the patient Mary Johnson.",
        [("Robert Wilson", "PERSON"), ("Mary Johnson", "PERSON")],
    ),
    (
        "Meet Priya Raghunathan and Tomasz Kowalczyk in Berlin.",
        [("Priya Raghunathan", "PERSON"), ("Tomasz Kowalczyk", "PERSON"), ("Berlin", "LOC")],
    ),
    (
        "Best regards,\nJane Doe\nCustomer Service Manager\nAcme Corporation",
        [("Jane Doe", "PERSON"), ("Acme Corporation", "ORG")],
    ),
    (
        "CEO John Smith announced that Acme Corp will acquire TechStartup Inc. for $50 million.",
        [("John Smith", "PERSON"), ("Acme Corp", "ORG"), ("TechStartup Inc.", "ORG")],
    ),
    (
        "Patient: Mary Johnson\nDOB: March 15, 1985\nDiagnosis: Type 2 diabetes.",
        [("Mary Johnson", "PERSON"), ("March 15, 1985", "DATE")],
    ),
    (
        "Please email maria.garcia@hospital.org or call 212-555-0147 about patient Luis Ortega.",
        [
            ("maria.garcia@hospital.org", "EMAIL"),
            ("212-555-0147", "PHONE"),
            ("Luis Ortega", "PERSON"),
        ],
    ),
    # --- hard negatives: nothing should be anonymized ---
    ("This is a simple sentence with no sensitive information.", []),
    ("Order #12345678 shipped yesterday and should arrive in 3-5 days.", []),
    ("We upgraded to version 2.3.1 and the build number is 20240115.", []),
    ("The service listens on port 8080 and retries 3 times.", []),
    ("Revenue grew 12% in Q3 and the year 1999 was a turning point.", []),
    ("The meeting is at 10:30 and lasts 45 minutes.", []),
    ("Use Python 3.12 with pip 24.0 and pytest 8.2.", []),
    ("The invoice total is 1500 units and the SKU is 55512.", []),
    ("Reference the RFC 2616 spec and error code 404.", []),
    ("Population reached 8300000 last year according to the census.", []),
    ("The temperature was 37.5 and the ratio is 16:9.", []),
    ("Set timeout to 30000 milliseconds and batch size 1024.", []),
    ("Chapter 12 covers sections 4.1 through 4.7.", []),
    ("The function returns True when the list has more than 100 items.", []),
]
