import re
from dataclasses import dataclass, field
from typing import Any

# Indic digits mapping to ASCII
_INDIC_DIGITS_MAP = {
    # Devanagari (Hindi, Marathi)
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
    # Bengali / Assamese
    "০": "0", "১": "1", "২": "2", "৩": "3", "৪": "4",
    "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9",
    # Gujarati
    "૦": "0", "૧": "1", "૨": "2", "૩": "3", "૪": "4",
    "૫": "5", "૬": "6", "૭": "7", "૮": "8", "૯": "9",
    # Gurmukhi (Punjabi)
    "੦": "0", "੧": "1", "੨": "2", "੩": "3", "੪": "4",
    "੫": "5", "੬": "6", "੭": "7", "੮": "8", "੯": "9",
    # Tamil
    "௦": "0", "௧": "1", "௨": "2", "௩": "3", "௪": "4",
    "௫": "5", "௬": "6", "௭": "7", "௮": "8", "௯": "9",
    # Telugu
    "౦": "0", "౧": "1", "౨": "2", "౩": "3", "౪": "4",
    "౫": "5", "౬": "6", "౭": "7", "౮": "8", "౯": "9",
    # Kannada
    "೦": "0", "೧": "1", "೨": "2", "೩": "3", "೪": "4",
    "೫": "5", "೬": "6", "೭": "7", "೮": "8", "೯": "9",
    # Malayalam
    "൦": "0", "൧": "1", "൨": "2", "൩": "3", "൪": "4",
    "൫": "5", "൬": "6", "൭": "7", "൮": "8", "൯": "9",
}

_INDIC_TRANSLATION_TABLE = str.maketrans(_INDIC_DIGITS_MAP)


def normalize_indic_digits(text: str) -> str:
    """Converts Indic script digits (Devanagari, Bengali, etc.) to standard ASCII 0-9."""
    return text.translate(_INDIC_TRANSLATION_TABLE)


@dataclass
class GuardrailResult:
    is_valid: bool
    hallucinated_products: list[str] = field(default_factory=list)
    hallucinated_numbers: list[int] = field(default_factory=list)
    sanitized_content: str = ""
    fallback_used: bool = False


# Multilingual deterministic fallback templates
FALLBACK_TEMPLATES = {
    "en": (
        "Based on your requirements, here is your customized Accel Business Digital Bundle. "
        "Please review the verified pricing details above or proceed directly to your official quote."
    ),
    "hi": (
        "आपकी आवश्यकताओं के आधार पर, यह आपका सत्यापित एक्सेल बिजनेस डिजिटल बंडल है। "
        "कृपया ऊपर दिए गए प्रमाणित मूल्य विवरण की समीक्षा करें और अपना आधिकारिक कोटेशन प्राप्त करें।"
    ),
    "mr": (
        "तुमच्या गरजांनुसार, हा तुमचा अधिकृत एक्सेल बिझनेस डिजिटल बंडल आहे. "
        "कृपया वरील प्रमाणित किमती तपासा आणि तुमचे कोटेशन पुढे सुरू ठेवा."
    ),
}


class AdvisorGuardrail:
    """Post-generation guardrail scanning LLM responses for hallucinated product IDs or pricing."""

    def __init__(self, allowed_products: set[str], allowed_numbers: set[int]):
        self.allowed_products = allowed_products
        self.allowed_numbers = allowed_numbers

    def evaluate(self, text: str, lang: str = "en") -> GuardrailResult:
        normalized = normalize_indic_digits(text)

        # 1. Extract product IDs: P followed by 2 digits (e.g. P01, P99)
        found_products = set(re.findall(r"\b(P\d{2})\b", normalized))
        hallucinated_pids = [p for p in found_products if p not in self.allowed_products]

        # 2. Extract rupee numbers and prices:
        # Match patterns like: ₹ 1,299, INR 999, Rs. 2500, ₹999/-, 999 रुपये, etc.
        rupee_patterns = [
            r"(?:₹|INR|Rs\.?|रू|रुपये)\s*([\d,]+)",
            r"([\d,]+)\s*(?:₹|/-|per month|/month|रुपये)",
        ]
        found_numbers: set[int] = set()
        for pat in rupee_patterns:
            matches = re.findall(pat, normalized, flags=re.IGNORECASE)
            for m in matches:
                clean_num = m.replace(",", "").strip()
                if clean_num.isdigit():
                    num_val = int(clean_num)
                    # Ignore trivial numbers like 0, 1, 2, 3 (e.g. days or qty)
                    if num_val >= 100:
                        found_numbers.add(num_val)

        hallucinated_nums = [n for n in found_numbers if n not in self.allowed_numbers]

        if hallucinated_pids or hallucinated_nums:
            fallback = FALLBACK_TEMPLATES.get(lang, FALLBACK_TEMPLATES["en"])
            return GuardrailResult(
                is_valid=False,
                hallucinated_products=sorted(hallucinated_pids),
                hallucinated_numbers=sorted(hallucinated_nums),
                sanitized_content=fallback,
                fallback_used=True,
            )

        return GuardrailResult(
            is_valid=True,
            sanitized_content=text,
            fallback_used=False,
        )


def validate_guardrail(
    response_text: str,
    allowed_products: set[str],
    allowed_numbers: set[int],
    lang: str = "en",
) -> dict[str, Any]:
    guard = AdvisorGuardrail(allowed_products=allowed_products, allowed_numbers=allowed_numbers)
    res = guard.evaluate(response_text, lang=lang)
    return {
        "is_valid": res.is_valid,
        "status": "PASS" if res.is_valid else "FALLBACK",
        "sanitized_text": res.sanitized_content,
        "hallucinated_products": res.hallucinated_products,
        "hallucinated_numbers": res.hallucinated_numbers,
    }
