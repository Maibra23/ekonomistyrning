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
    # Day 10.2: extended Swedish AI artifacts
    r"\bi\s+ett\s+nötskal\b",
    r"\bmed\s+andra\s+ord\b",
    r"\bför\s+att\s+sammanfatta\b",
    r"\bdet\s+bör\s+betonas\s+att\b",
    r"\bsom\s+tidigare\s+nämnts\b",
    r"\bi\s+grund\s+och\s+botten\b",
    r"\bi\s+sammanhanget\b",
    r"\bi\s+det\s+stora\s+hela\b",
    r"\bkort\s+sagt\b",
    r"\bnär\s+allt\s+kommer\s+omkring\b",
]

ALL_AI_TELLS = AI_TELLS_EN + AI_TELLS_SV

# Em dash, en dash, figure dash, horizontal bar, minus sign. The negative
# lookahead protects negative numbers: a dash glued to a following digit
# ("\u221252 303") is a sign, not a sentence dash, and is handled separately.
DASH_PATTERN = re.compile(r"[\u2014\u2013\u2012\u2015\u2212](?!\d)")

# A dash glued directly to a digit is the sign of a negative number
# ("\u221252 303 kr"). It must be preserved as a real minus, never turned into a
# comma (which would make a negative NPV read as positive and break the
# grounding check). We normalize it to an ASCII hyphen-minus so downstream
# number parsing (SWEDISH_NUMBER_PATTERN) recognizes the sign.
NEGATIVE_SIGN_PATTERN = re.compile(r"[-\u2012\u2013\u2014\u2015\u2212](?=\d)")

# Hyphen between spaces (used as a sentence break, not a compound word hyphen)
SPACED_HYPHEN_PATTERN = re.compile(r"\s+-\s+")

# A subtraction between two numbers, e.g. "599 kr - 325 kr" or "35000 - 15328".
# The left side is a number with an optional currency/quantity unit; the right
# side begins with a digit. We convert the operator to the word "minus" so the
# dash-stripping rules below cannot turn the subtraction into a comma (which
# would silently corrupt a calculation shown to the student). All dash glyphs
# the model might emit as the operator are accepted, not only the ASCII hyphen.
SUBTRACTION_PATTERN = re.compile(
    r"(\d(?:[\u00a0 ]?(?:kr|%|st|styck(?:en)?))?)[ \t]+"
    r"[-\u2012\u2013\u2014\u2015\u2212][ \t]+(?=\d)"
)

# LaTeX / math markup the model sometimes emits despite instructions. These are
# stripped before the text is rendered with st.markdown so the student never
# sees raw commands like \text{kr} or \frac{a}{b}.
_LATEX_FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_LATEX_TEXT_CMD = re.compile(
    r"\\(?:text|mathrm|mathbf|mathit|operatorname|mathsf)\s*\{([^{}]*)\}"
)
_LATEX_SPACING = re.compile(r"\\[,;:!]|\\q?quad|\\ ")
_LATEX_DELIMS = re.compile(r"\$\$|\$|\\\(|\\\)|\\\[|\\\]|\\left|\\right")
_LATEX_DECIMAL_BRACE = re.compile(r"\{\s*([.,])\s*\}")
_LATEX_RESIDUAL_CMD = re.compile(r"\\[a-zA-Z]+")
_LATEX_SYMBOLS: tuple[tuple[str, str], ...] = (
    (r"\times", "\u00d7"),
    (r"\cdot", "\u00b7"),
    (r"\div", "/"),
    (r"\approx", "\u2248"),
    (r"\leq", "\u2264"),
    (r"\geq", "\u2265"),
    (r"\le", "\u2264"),
    (r"\ge", "\u2265"),
    (r"\neq", "\u2260"),
    (r"\pm", "\u00b1"),
)

# Markdown ATX headers (# .. ######) at line start, with optional closing
# hashes. The LLM sometimes emits these despite instructions; st.markdown
# renders them in large display fonts, which breaks the uniform text size
# of tutor output. They are demoted to bold body text instead.
HEADER_PATTERN = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", flags=re.MULTILINE)

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
    terminology_corrections: list[tuple[str, str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Default to an empty list when omitted to keep API backwards compatible.
        if self.terminology_corrections is None:
            self.terminology_corrections = []


# Cost related context words used by normalize_swedish_terminology to decide
# whether ambiguous variants like "påslag" are referring to a cost concept.
_COST_CONTEXT_WORDS = frozenset(
    {
        "kostnad",
        "kostnader",
        "kostnaden",
        "pålägg",
        "pålägget",
        "påläggsmetoden",
        "omkostnad",
        "omkostnader",
        "självkostnad",
        "självkostnaden",
        "kalkyl",
        "kalkylen",
    }
)


def _has_cost_context(text: str, match_start: int, match_end: int, window: int = 5) -> bool:
    """Return True when a cost related word appears within `window` tokens of the match."""
    before = text[:match_start].split()[-window:]
    after = text[match_end:].split()[:window]
    surrounding = [token.lower().strip(".,;:!?()\"'") for token in before + after]
    return any(token in _COST_CONTEXT_WORDS for token in surrounding)


def normalize_markdown_headers(text: str) -> str:
    """Demote markdown headers to bold text so all output renders at body size.

    ``## Antagande`` becomes ``**Antagande**``. Existing bold markers inside
    the header text are stripped first so the result never contains ``****``.
    Inline hashes (``rad #5``, ``C#``) are untouched because the pattern only
    matches hashes at line start followed by whitespace.
    """
    def replace(match: re.Match) -> str:
        title = match.group(1).strip().strip("*").strip()
        if not title:
            return ""
        # Trailing newline separates the label from the body text so the
        # label renders as its own paragraph instead of inline bold.
        return f"**{title}**\n"

    return HEADER_PATTERN.sub(replace, text)


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

    # Collapse runs of spaces/tabs but keep newlines: paragraph breaks carry
    # the section structure that st.markdown renders, so flattening them
    # would merge sections into one block of text.
    cleaned = re.sub(r"[^\S\n]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[^\S\n]+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"^[\s,.;:!?]+", "", cleaned)
    return cleaned, found


def strip_latex(text: str) -> str:
    """Remove LaTeX / math markup, leaving readable plain text.

    Models occasionally answer with LaTeX (``\\frac{a}{b}``, ``\\text{kr}``,
    ``\\,`` thin spaces, ``$...$`` delimiters) even though the system prompt
    forbids it. ``st.markdown`` renders only fenced math, so the raw commands
    leak to the student. This converts the common constructs to plain text:

    - ``\\frac{a}{b}`` becomes ``a / b``
    - ``\\text{kr}`` becomes ``kr`` (argument kept)
    - ``\\times`` becomes ``×`` and similar operators to their glyphs
    - thin spaces, ``$`` delimiters and residual ``\\command`` tokens removed
    - ``0{,}562`` (LaTeX decimal comma) becomes ``0,562``
    """
    # Remove inner spacing and \text{...} wrappers first so that the
    # \frac argument braces are clean. Otherwise the nested braces from
    # \text{kr} break the \frac match and the division slash is lost.
    cleaned = _LATEX_SPACING.sub(" ", text)
    cleaned = _LATEX_TEXT_CMD.sub(r"\1", cleaned)
    cleaned = _LATEX_FRAC.sub(r"\1 / \2", cleaned)
    for command, glyph in _LATEX_SYMBOLS:
        cleaned = cleaned.replace(command, glyph)
    cleaned = _LATEX_DELIMS.sub("", cleaned)
    cleaned = _LATEX_DECIMAL_BRACE.sub(r"\1", cleaned)
    cleaned = _LATEX_RESIDUAL_CMD.sub("", cleaned)
    # Drop any leftover math braces and stray escape backslashes now that
    # their commands are gone.
    cleaned = cleaned.replace("{", "").replace("}", "").replace("\\", "")
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.;:!?])", r"\1", cleaned)
    return cleaned


def normalize_dashes(text: str) -> str:
    """Replace em and en dashes with comma plus space.

    Hyphens inside compound words (no spaces around them) are preserved.
    Subtraction between numbers (``599 kr - 325 kr``) is converted to the
    word ``minus`` first so it is not mistaken for a sentence dash, and the
    sign of a negative number (``−52 303 kr``) is kept as a real minus.
    """
    cleaned = SUBTRACTION_PATTERN.sub(r"\1 minus ", text)
    # Preserve negative-number signs before stripping sentence dashes.
    cleaned = NEGATIVE_SIGN_PATTERN.sub("-", cleaned)
    cleaned = DASH_PATTERN.sub(", ", cleaned)
    cleaned = SPACED_HYPHEN_PATTERN.sub(", ", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"[^\S\n]{2,}", " ", cleaned)
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


# Variants that must only be replaced when adjacent to cost related words.
# Keep this list narrow; broad lookups risk false positives in non cost text.
_AMBIGUOUS_VARIANTS = frozenset({"påslag", "pålägg"})


def normalize_swedish_terminology(
    text: str, glossary: dict[str, tuple[str, str | None]]
) -> tuple[str, list[tuple[str, str]]]:
    """Replace known incorrect Swedish variants with their canonical terms.

    Iterates over glossary entries that supply a non-None incorrect variant
    and substitutes occurrences using a word boundary regex. For variants
    flagged as ambiguous, only replace when a cost related context word
    appears within five tokens; otherwise skip to avoid false positives.

    Returns the cleaned text and the list of (incorrect, correct) pairs
    actually applied.
    """
    cleaned = text
    corrections: list[tuple[str, str]] = []

    for canonical, (_english, variant) in glossary.items():
        if not variant:
            continue

        pattern = re.compile(rf"\b{re.escape(variant)}\b", flags=re.IGNORECASE)
        if variant.lower() in _AMBIGUOUS_VARIANTS:
            # Walk matches manually so each one can be context checked.
            new_parts: list[str] = []
            cursor = 0
            applied = False
            for match in pattern.finditer(cleaned):
                new_parts.append(cleaned[cursor : match.start()])
                if _has_cost_context(cleaned, match.start(), match.end()):
                    new_parts.append(canonical)
                    applied = True
                else:
                    new_parts.append(match.group(0))
                cursor = match.end()
            new_parts.append(cleaned[cursor:])
            updated = "".join(new_parts)
            if applied:
                corrections.append((variant, canonical))
                cleaned = updated
        else:
            if pattern.search(cleaned):
                corrections.append((variant, canonical))
                cleaned = pattern.sub(canonical, cleaned)

    return cleaned, corrections


def humanize(
    text: str,
    required_sections: list[str] | None = None,
    glossary: dict[str, tuple[str, str | None]] | None = None,
) -> HumanizeResult:
    """Run the full humanizer pipeline.

    Order: normalize markdown headers, strip AI tells, normalize dashes,
    enforce Swedish numbers, validate structure. Each step is reported in
    transformations_applied.

    Header normalization must run first: strip_ai_tells collapses blank
    lines, after which a header may no longer sit at the start of a line.
    """
    transformations: list[str] = []

    cleaned = normalize_markdown_headers(text)
    if cleaned != text:
        transformations.append("normalize_markdown_headers")

    cleaned, tells = strip_ai_tells(cleaned)
    if tells:
        transformations.append("strip_ai_tells")

    cleaned_no_latex = strip_latex(cleaned)
    if cleaned_no_latex != cleaned:
        transformations.append("strip_latex")
    cleaned = cleaned_no_latex

    terminology_corrections: list[tuple[str, str]] = []
    if glossary is not None:
        cleaned, terminology_corrections = normalize_swedish_terminology(cleaned, glossary)
        if terminology_corrections:
            transformations.append("normalize_swedish_terminology")

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
        terminology_corrections=terminology_corrections,
    )
