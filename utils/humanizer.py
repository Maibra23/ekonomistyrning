"""Layer 2 of the humanizer architecture.

A regex based post processor that runs in milliseconds and removes known
AI tells, normalizes typography (no em or en dashes), enforces Swedish
number formatting, and validates the four section structure.

This module never calls the LLM. See docs/METHODOLOGY.md section 6.5
for the full architecture.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NBSP = "\u00a0"

# AI tells gathered from the humanizer skill plus Swedish equivalents.
# Each entry is a regex pattern that will be matched case insensitively.
AI_TELLS_EN: list[str] = [
    r"\bdelve\s+into\b",
    r"\bdelve\s+in\b",
    r"\bin\s+conclusion\b",
    r"\bit\s+is\s+important\s+to\s+note\s+that\b",
    r"\bit's\s+important\s+to\s+note\s+that\b",
    r"\bi\s+hope\s+this\s+helps\b",
    r"\blet\s+me\s+know\s+if\s+you\b",
    r"\bfeel\s+free\s+to\b",
    r"\bnavigate\s+the\b",
    r"\btapestry\b",
    r"\brobust\s+framework\b",
    r"\bcomprehensive\s+overview\b",
    r"\bwealth\s+of\s+information\b",
    r"\bplays\s+a\s+crucial\s+role\b",
    r"\bin\s+today's\s+fast\s+paced\s+world\b",
]

AI_TELLS_SV: list[str] = [
    r"\bdet\s+är\s+viktigt\s+att\s+notera\s+att\b",
    r"\bsammanfattningsvis\b",
    r"\blåt\s+mig\s+veta\s+om\b",
    r"\btveka\s+inte\s+att\b",
    r"\bhör\s+av\s+dig\s+om\b",
    r"\bi\s+dagens\s+snabbrörliga\s+värld\b",
    r"\bhoppas\s+det(ta)?\s+hjälper\b",
]

ALL_AI_TELLS = AI_TELLS_EN + AI_TELLS_SV

# Em dash, en dash, figure dash, horizontal bar, minus sign
DASH_PATTERN = re.compile(r"[\u2014\u2013\u2012\u2015\u2212]")

# Hyphen between spaces (used as a sentence break, not a compound word hyphen)
SPACED_HYPHEN_PATTERN = re.compile(r"\s+-\s+")

# Number with English thousand and decimal separators: 1,234.56
EN_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])(\d{1,3}(?:,\d{3})+)(?:\.(\d+))?(?![A-Za-z])")

# Plain decimal with period: 12.5 (only when context suggests numeric)
EN_DECIMAL_PATTERN = re.compile(r"(?<![A-Za-z\d])(\d+)\.(\d+)(?![A-Za-z])")

# Number followed by space then "kr" or "%". Use lookahead instead of \b
# because % is a non-word character and \b would not match around it.
NUMBER_UNIT_PATTERN = re.compile(r"(\d)\s+(kr|%)(?![A-Za-z])")


@dataclass
class HumanizeResult:
    """Output of the humanize pipeline."""

    text: str
    tells_found: list[str]
    structure_valid: bool
    missing_sections: list[str]
    transformations_applied: list[str]


def strip_ai_tells(text: str) -> tuple[str, list[str]]:
    """Remove known AI tell phrases. Returns (cleaned_text, tells_found)."""
    found: list[str] = []
    cleaned = text
    for pattern in ALL_AI_TELLS:
        regex = re.compile(pattern, flags=re.IGNORECASE)
        if regex.search(cleaned):
            match = regex.search(cleaned)
            if match:
                found.append(match.group(0).strip())
            cleaned = regex.sub("", cleaned)

    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"^[\s,.;:!?]+", "", cleaned)
    return cleaned, found


def normalize_dashes(text: str) -> str:
    """Replace em and en dashes with comma plus space.

    Hyphens inside compound words (no spaces around them) are preserved.
    """
    cleaned = DASH_PATTERN.sub(", ", text)
    cleaned = SPACED_HYPHEN_PATTERN.sub(", ", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def enforce_swedish_numbers(text: str) -> str:
    """Convert English number formatting to Swedish.

    1,234.56 -> 1 234,56 (with NBSP)
    12.5 -> 12,5 (only when standalone numeric)
    1234 kr -> 1234 kr (NBSP between number and unit)
    """
    def replace_full(match: re.Match) -> str:
        integer_part = match.group(1).replace(",", NBSP)
        decimal_part = match.group(2)
        if decimal_part:
            return f"{integer_part},{decimal_part}"
        return integer_part

    cleaned = EN_NUMBER_PATTERN.sub(replace_full, text)

    def replace_decimal(match: re.Match) -> str:
        return f"{match.group(1)},{match.group(2)}"

    cleaned = EN_DECIMAL_PATTERN.sub(replace_decimal, cleaned)

    def replace_unit_space(match: re.Match) -> str:
        return f"{match.group(1)}{NBSP}{match.group(2)}"

    # Run twice to catch overlapping matches where the first regex
    # consumed the leading character of the next number.
    cleaned = NUMBER_UNIT_PATTERN.sub(replace_unit_space, cleaned)
    cleaned = NUMBER_UNIT_PATTERN.sub(replace_unit_space, cleaned)
    return cleaned


def validate_structure(
    text: str, required_sections: list[str] | None = None
) -> tuple[bool, list[str]]:
    """Verify required section headers are present.

    Looks for either Markdown headers (# Section) or bold text (**Section**)
    or section name followed by colon at start of line.
    """
    if not required_sections:
        return True, []

    missing: list[str] = []
    for section in required_sections:
        patterns = [
            rf"^#+\s*{re.escape(section)}",
            rf"\*\*{re.escape(section)}\*\*",
            rf"^{re.escape(section)}\s*:",
        ]
        found = any(
            re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) for pattern in patterns
        )
        if not found:
            missing.append(section)

    return len(missing) == 0, missing


def humanize(text: str, required_sections: list[str] | None = None) -> HumanizeResult:
    """Run the full humanizer pipeline.

    Order: strip AI tells, normalize dashes, enforce Swedish numbers,
    validate structure. Each step is reported in transformations_applied.
    """
    transformations: list[str] = []

    cleaned, tells = strip_ai_tells(text)
    if tells:
        transformations.append("strip_ai_tells")

    cleaned_no_dash = normalize_dashes(cleaned)
    if cleaned_no_dash != cleaned:
        transformations.append("normalize_dashes")
    cleaned = cleaned_no_dash

    cleaned_swedish = enforce_swedish_numbers(cleaned)
    if cleaned_swedish != cleaned:
        transformations.append("enforce_swedish_numbers")
    cleaned = cleaned_swedish

    is_valid, missing = validate_structure(cleaned, required_sections)

    return HumanizeResult(
        text=cleaned.strip(),
        tells_found=tells,
        structure_valid=is_valid,
        missing_sections=missing,
        transformations_applied=transformations,
    )
