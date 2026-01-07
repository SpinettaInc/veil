"""Faker-based replacement strategy for generating realistic fake data."""

from typing import Optional
import random

try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False

from veil.core.mapper import MappingStore
from veil.detection.entity import Entity, EntityType


class FakerReplacer:
    """Faker-based replacement strategy.

    Generates realistic fake data to replace sensitive entities,
    making anonymized text more natural for LLM processing.

    Examples:
        - "John Smith" -> "Michael Johnson"
        - "john@example.com" -> "sarah.williams@fakeemail.com"
        - "Acme Corp" -> "Apex Industries"

    Attributes:
        faker: Faker instance for generating data
        seed: Random seed for reproducibility
    """

    def __init__(
        self,
        locale: str = "en_US",
        seed: Optional[int] = None,
    ) -> None:
        """Initialize the Faker replacer.

        Args:
            locale: Locale for generating fake data (e.g., "en_US", "de_DE")
            seed: Random seed for reproducibility

        Raises:
            ImportError: If faker library is not installed
        """
        if not FAKER_AVAILABLE:
            raise ImportError(
                "Faker library is required for FakerReplacer. "
                "Install with: pip install faker"
            )

        self.faker = Faker(locale)
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)

        # Cache for consistent replacements of same entity type
        self._type_counters: dict[EntityType, int] = {}

    def generate_replacement(
        self,
        entity: Entity,
        mapping_store: MappingStore,
    ) -> str:
        """Generate a fake replacement for an entity.

        If the entity's original text already has a mapping, returns
        the existing replacement. Otherwise, generates new fake data.

        Args:
            entity: The entity to replace
            mapping_store: Store for tracking mappings

        Returns:
            Fake replacement string
        """
        # Check if we already have a mapping for this text
        existing = mapping_store.get_replacement(entity.text)
        if existing:
            return existing

        # Generate appropriate fake data based on entity type
        return self._generate_for_type(entity.entity_type, entity.text)

    def _generate_for_type(
        self,
        entity_type: EntityType,
        original: str,
    ) -> str:
        """Generate fake data appropriate for entity type.

        Args:
            entity_type: Type of entity
            original: Original text (used for format matching)

        Returns:
            Fake replacement string
        """
        generators = {
            EntityType.PERSON: self._generate_person,
            EntityType.EMAIL: self._generate_email,
            EntityType.PHONE: self._generate_phone,
            EntityType.SSN: self._generate_ssn,
            EntityType.CREDIT_CARD: self._generate_credit_card,
            EntityType.ORG: self._generate_organization,
            EntityType.GPE: self._generate_location,
            EntityType.LOC: self._generate_location,
            EntityType.DATE: self._generate_date,
            EntityType.MONEY: self._generate_money,
            EntityType.IP_ADDRESS: self._generate_ip,
            EntityType.URL: self._generate_url,
            EntityType.IBAN: self._generate_iban,
            EntityType.PASSPORT: self._generate_passport,
            EntityType.DRIVER_LICENSE: self._generate_driver_license,
            EntityType.BANK_ACCOUNT: self._generate_bank_account,
            EntityType.MEDICAL_RECORD: self._generate_medical_record,
        }

        generator = generators.get(entity_type, self._generate_generic)
        return generator(original)

    def _generate_person(self, original: str) -> str:
        """Generate a fake person name."""
        # Try to match name format (first only, first last, full name)
        parts = original.split()
        if len(parts) == 1:
            return self.faker.first_name()
        elif len(parts) == 2:
            return f"{self.faker.first_name()} {self.faker.last_name()}"
        else:
            return self.faker.name()

    def _generate_email(self, original: str) -> str:
        """Generate a fake email address."""
        return self.faker.email()

    def _generate_phone(self, original: str) -> str:
        """Generate a fake phone number matching original format."""
        # Check format patterns
        if "(" in original:
            return self.faker.phone_number()

        # Simple format: XXX-XXX-XXXX
        if "-" in original and len(original.replace("-", "")) == 10:
            area = str(random.randint(200, 999))
            exchange = str(random.randint(200, 999))
            subscriber = str(random.randint(1000, 9999))
            return f"{area}-{exchange}-{subscriber}"

        return self.faker.phone_number()

    def _generate_ssn(self, original: str) -> str:
        """Generate a fake SSN in same format."""
        # Standard format: XXX-XX-XXXX
        area = str(random.randint(100, 899))
        group = str(random.randint(10, 99))
        serial = str(random.randint(1000, 9999))

        if "-" in original:
            return f"{area}-{group}-{serial}"
        return f"{area}{group}{serial}"

    def _generate_credit_card(self, original: str) -> str:
        """Generate a fake credit card number."""
        # Keep similar format to original
        fake_number = self.faker.credit_card_number()

        # Match spacing/dashes
        if " " in original:
            # Format with spaces
            return " ".join([fake_number[i:i+4] for i in range(0, 16, 4)])
        elif "-" in original:
            # Format with dashes
            return "-".join([fake_number[i:i+4] for i in range(0, 16, 4)])
        return fake_number

    def _generate_organization(self, original: str) -> str:
        """Generate a fake organization name."""
        # Mix of company suffixes for variety
        suffixes = ["Inc.", "Corp.", "LLC", "Ltd.", "Group", "Industries", "Solutions"]
        base_name = self.faker.company().split()[0]  # Take first word
        suffix = random.choice(suffixes)
        return f"{base_name} {suffix}"

    def _generate_location(self, original: str) -> str:
        """Generate a fake location."""
        # Try to match original pattern
        if len(original.split()) == 1:
            return self.faker.city().split()[0]
        return self.faker.city()

    def _generate_date(self, original: str) -> str:
        """Generate a fake date in similar format."""
        fake_date = self.faker.date_object()

        # Try to detect format from original
        if "/" in original:
            if len(original.split("/")[0]) == 4:
                return fake_date.strftime("%Y/%m/%d")
            return fake_date.strftime("%m/%d/%Y")
        elif "-" in original:
            if len(original.split("-")[0]) == 4:
                return fake_date.strftime("%Y-%m-%d")
            return fake_date.strftime("%m-%d-%Y")
        else:
            return fake_date.strftime("%B %d, %Y")

    def _generate_money(self, original: str) -> str:
        """Generate a fake monetary amount."""
        # Detect currency symbol
        if "$" in original:
            amount = random.randint(100, 99999)
            return f"${amount:,}"
        elif "€" in original:
            amount = random.randint(100, 99999)
            return f"€{amount:,}"
        elif "£" in original:
            amount = random.randint(100, 99999)
            return f"£{amount:,}"
        else:
            amount = random.randint(100, 99999)
            return f"${amount:,}"

    def _generate_ip(self, original: str) -> str:
        """Generate a fake IP address."""
        if ":" in original:
            # IPv6
            return self.faker.ipv6()
        return self.faker.ipv4()

    def _generate_url(self, original: str) -> str:
        """Generate a fake URL."""
        return self.faker.url()

    def _generate_iban(self, original: str) -> str:
        """Generate a fake IBAN."""
        return self.faker.iban()

    def _generate_passport(self, original: str) -> str:
        """Generate a fake passport number."""
        # US passport format: 9 alphanumeric characters
        letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
        numbers = "".join(random.choices("0123456789", k=7))
        return f"{letters}{numbers}"

    def _generate_driver_license(self, original: str) -> str:
        """Generate a fake driver's license number."""
        # Generic format: letter + numbers
        letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        numbers = "".join(random.choices("0123456789", k=8))
        return f"{letter}{numbers}"

    def _generate_bank_account(self, original: str) -> str:
        """Generate a fake bank account number."""
        # Generic format: 10-12 digits
        length = len(original.replace("-", "").replace(" ", ""))
        if length < 8:
            length = 10
        return "".join(random.choices("0123456789", k=length))

    def _generate_medical_record(self, original: str) -> str:
        """Generate a fake medical record number."""
        # Format: MRN-XXXXXXX
        numbers = "".join(random.choices("0123456789", k=7))
        return f"MRN-{numbers}"

    def _generate_generic(self, original: str) -> str:
        """Generate a generic fake replacement."""
        # Use word-based replacement for unknown types
        return self.faker.word().title()


def create_faker_replacer(
    locale: str = "en_US",
    seed: Optional[int] = None,
) -> FakerReplacer:
    """Factory function to create a Faker replacer.

    Args:
        locale: Locale for generating fake data
        seed: Random seed for reproducibility

    Returns:
        Configured FakerReplacer instance

    Raises:
        ImportError: If faker library is not installed
    """
    return FakerReplacer(locale=locale, seed=seed)
