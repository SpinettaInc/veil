"""Harder held-out cases: casing, formats, prose noise, logs, and near-miss negatives."""

CASES: list[tuple[str, list[tuple[str, str]]]] = [
    # casing / titles / initials
    ("JOHN SMITH signed the form.", [("JOHN SMITH", "PERSON")]),
    (
        "Ms. A. B. Carter and Mr. Wei Zhang attended.",
        [("A. B. Carter", "PERSON"), ("Wei Zhang", "PERSON")],
    ),
    ("thanks, olivia martínez", [("olivia martínez", "PERSON")]),
    (
        "Re: Follow-up with Dr. Aisha Al-Rashid about Ahmed's results",
        [("Aisha Al-Rashid", "PERSON"), ("Ahmed", "PERSON")],
    ),
    # structured, unusual formatting
    ("SSN 078051120 on file.", [("078051120", "SSN")]),
    ("my visa 4532015112830366 was charged twice", [("4532015112830366", "CREDIT_CARD")]),
    ("Call 555-123-4567 ext. 89 between 9am and 5pm.", [("555-123-4567", "PHONE")]),
    ("Fax: +1 (212) 555-0188", [("+1 (212) 555-0188", "PHONE")]),
    ("DOB 1985-03-15, admitted 15/03/2024.", [("1985-03-15", "DATE"), ("15/03/2024", "DATE")]),
    (
        "Email: JANE.DOE@EXAMPLE.ORG (work) / jane_doe99@gmail.com (home)",
        [("JANE.DOE@EXAMPLE.ORG", "EMAIL"), ("jane_doe99@gmail.com", "EMAIL")],
    ),
    ("Lives at 221B Baker Street, London.", [("221B Baker Street", "LOC"), ("London", "LOC")]),
    (
        "Gateway 10.0.0.1, host 172.16.254.3, and 8.8.8.8 for DNS.",
        [("10.0.0.1", "IP_ADDRESS"), ("172.16.254.3", "IP_ADDRESS"), ("8.8.8.8", "IP_ADDRESS")],
    ),
    (
        "See http://example.com/u/42 and https://x.io/a?b=c&d=e.",
        [("http://example.com/u/42", "URL"), ("https://x.io/a?b=c&d=e", "URL")],
    ),
    ("Bank account 12345678 sort code 40-47-84.", [("12345678", "BANK_ACCOUNT")]),
    (
        "IBAN FR76 3000 6000 0112 3456 7890 189 is valid.",
        [("FR76 3000 6000 0112 3456 7890 189", "IBAN")],
    ),
    ("Patient ID MRN 00987654; NHS number withheld.", [("MRN 00987654", "MEDICAL_RECORD")]),
    # prose with mixed noise
    (
        "ERROR 2024-01-15T10:30:00Z user=kbrown ip=10.0.0.5 failed login from Toronto",
        [("2024-01-15", "DATE"), ("10.0.0.5", "IP_ADDRESS"), ("Toronto", "LOC")],
    ),
    (
        "Invoice INV-2024-0093 for Globex Corporation, attention Hank Scorpio, due 2024-02-01.",
        [("Globex Corporation", "ORG"), ("Hank Scorpio", "PERSON"), ("2024-02-01", "DATE")],
    ),
    (
        "Sincerely,\nMarcus Aurelius Chen\nSenior Analyst | Initech\nm.chen@initech.example | 415-555-0100",
        [
            ("Marcus Aurelius Chen", "PERSON"),
            ("Initech", "ORG"),
            ("m.chen@initech.example", "EMAIL"),
            ("415-555-0100", "PHONE"),
        ],
    ),
    (
        "Alice told Bob that Alice would meet Bob at Bob's place.",
        [("Alice", "PERSON"), ("Bob", "PERSON")],
    ),
    # near-miss negatives
    ("call 911 in an emergency", []),
    ("The 1990s were great; 50% off everything.", []),
    ("ISBN 978-3-16-148410-0 is out of print.", []),
    ("Flight BA2490 departs from gate 12 at 08:45.", []),
    ("Windows 11 and iPhone 15 Pro ship with 8GB of RAM.", []),
    ("Take exit 42 onto Highway 101 north.", []),
    ("The 2024 Olympics drew 10 million viewers.", []),
    ("Use commit a3f5c9d or tag v1.2.3; the PR is #4521.", []),
    ("Room 404 is next to room 405 on floor 4.", []),
    ("Set MAX_RETRIES=5 and TIMEOUT_MS=30000 in the .env file.", []),
    ("The GDP grew by 2.5 percent in the third quarter.", []),
    ("Monday at 9am works; otherwise Tuesday afternoon.", []),
    ("SELECT id, total FROM orders WHERE total > 1000 LIMIT 50;", []),
    ("Your one-time code is 483920. It expires in 10 minutes.", []),
]
