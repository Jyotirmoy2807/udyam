from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class AdvisorState(str, Enum):
    GREETING = "GREETING"
    PROFILE_COLLECTION = "PROFILE_COLLECTION"
    RECOMMEND = "RECOMMEND"
    QUOTE_HANDOFF = "QUOTE_HANDOFF"
    HANDOFF_TO_HUMAN = "HANDOFF_TO_HUMAN"


# 35 Business Types directly from smb_leads.csv mapped to 4 core segments
BUSINESS_TYPE_TO_SEGMENT = {
    # Micro retail & services (10)
    "Bakery": "micro",
    "Boutique": "micro",
    "Hardware store": "micro",
    "Kirana store": "micro",
    "Mobile repair shop": "micro",
    "Optician": "micro",
    "Pharmacy": "micro",
    "Salon": "micro",
    "Stationery shop": "micro",
    "Sweet shop": "micro",

    # Professional offices (10)
    "Architecture studio": "professional_offices",
    "CA firm": "professional_offices",
    "Coaching centre": "professional_offices",
    "Dental clinic": "professional_offices",
    "Diagnostic lab": "professional_offices",
    "Insurance agency": "professional_offices",
    "Law office": "professional_offices",
    "Physiotherapy clinic": "professional_offices",
    "Real estate agency": "professional_offices",
    "Travel agency": "professional_offices",

    # Small multi-site businesses (8)
    "Apparel retail chain": "small_multi_site",
    "Bakery chain": "small_multi_site",
    "Budget hotel group": "small_multi_site",
    "Electronics retail chain": "small_multi_site",
    "Gym chain": "small_multi_site",
    "Pharmacy chain": "small_multi_site",
    "Pre-school chain": "small_multi_site",
    "Restaurant chain": "small_multi_site",

    # Small manufacturers (7)
    "Auto-parts unit": "small_manufacturers",
    "Food processing unit": "small_manufacturers",
    "Furniture workshop": "small_manufacturers",
    "Packaging unit": "small_manufacturers",
    "Plastic moulding unit": "small_manufacturers",
    "Printing press": "small_manufacturers",
    "Textile unit": "small_manufacturers",
}

# City to Tier lookup (Tier 1 vs Tier 2) from historical data
CITY_TO_TIER = {
    "Ahmedabad": 1,
    "Bengaluru": 1,
    "Chennai": 1,
    "Delhi": 1,
    "Hyderabad": 1,
    "Kolkata": 1,
    "Mumbai": 1,
    "Pune": 1,
    "Surat": 1,
    "Bhopal": 2,
    "Bhubaneswar": 2,
    "Chandigarh": 2,
    "Coimbatore": 2,
    "Guwahati": 2,
    "Indore": 2,
    "Jaipur": 2,
    "Kochi": 2,
    "Lucknow": 2,
    "Ludhiana": 2,
    "Nagpur": 2,
    "Patna": 2,
    "Visakhapatnam": 2,
}


@dataclass
class ConversationContext:
    conversation_id: UUID = field(default_factory=uuid4)
    lead_id: UUID = field(default_factory=uuid4)
    state: AdvisorState = AdvisorState.GREETING
    lang: str = "en"
    question_count: int = 0
    max_questions: int = 7

    # Slots
    business_type: str | None = None
    segment: str | None = None
    city: str | None = None
    tier: int = 2
    employees: int | None = None
    sites: int | None = None
    has_gstin: bool | None = None

    # Optional slots
    current_internet: str | None = None
    current_provider: str | None = None
    monthly_spend: int | None = None
    needs: list[str] = field(default_factory=list)
    mobile_lines: int | None = None

    # Active bundle & allowed constraints for guardrails
    current_bundle: list[dict[str, Any]] = field(default_factory=list)
    allowed_products: set[str] = field(default_factory=set)
    allowed_numbers: set[int] = field(default_factory=set)

    def is_profile_complete(self) -> bool:
        """Required slots: business_type, city, employees, sites, has_gstin."""
        return (
            self.business_type is not None
            and self.city is not None
            and self.employees is not None
            and self.sites is not None
            and self.has_gstin is not None
        )

    def next_missing_required_slot(self) -> str | None:
        if self.business_type is None:
            return "business_type"
        if self.city is None:
            return "city"
        if self.employees is None:
            return "employees"
        if self.sites is None:
            return "sites"
        if self.has_gstin is None:
            return "has_gstin"
        return None

    def update_slots(self, fields: dict[str, Any]) -> None:
        for k, v in fields.items():
            if hasattr(self, k) and v is not None:
                setattr(self, k, v)

        # Auto infer segment if business_type updated
        if self.business_type and not self.segment:
            self.segment = BUSINESS_TYPE_TO_SEGMENT.get(self.business_type, "micro")

        # Auto infer tier if city updated
        if self.city:
            clean_city = self.city.strip().title()
            self.tier = CITY_TO_TIER.get(clean_city, 2)
