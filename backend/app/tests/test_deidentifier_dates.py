"""Property-based tests for Deidentifier date handling and age capping.

Covers:
- Property 2: Dates with month and day are detected.
- Property 6: Dates preserve the year.
- Property 7: Age capping.

Uses hypothesis to generate dates across the supported formats (numeric
MM/DD/YYYY and D-M-Y variants, ISO YYYY-MM-DD, and named-month forms) embedded
in random filler text, plus arbitrary integer ages for the capping rule.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.deidentifier import Deidentifier, IdentifierCategory


# ---------------------------------------------------------------------------
# Filler text strategy
#
# Filler words are alphabetic only (no digits, no identifier keyword triggers),
# so the embedded date is the only structured identifier in the generated text.
# ---------------------------------------------------------------------------

_SAFE_WORDS = [
    "patient", "presented", "with", "the", "today", "visit", "note",
    "clinical", "history", "seen", "follow", "up", "chart", "summary",
    "reported", "stable", "review", "plan", "assessment", "impression",
]

filler = st.lists(st.sampled_from(_SAFE_WORDS), min_size=0, max_size=6).map(" ".join)


# ---------------------------------------------------------------------------
# Date strategies across the supported formats.
#
# Years are constrained to 1900-2099 so a four-digit year is always present and
# recognised for preservation (see the module's _YEAR_PATTERN, 19xx/20xx). Days
# are capped at 28 to keep every generated date valid across all months.
# ---------------------------------------------------------------------------

_MONTHS_FULL = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTHS_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

_year = st.integers(min_value=1900, max_value=2099)
_month = st.integers(min_value=1, max_value=12)
_day = st.integers(min_value=1, max_value=28)


@st.composite
def numeric_date(draw):
    """Numeric MM/DD/YYYY and D-M-Y variants with '/' or '-' separators."""
    month = draw(_month)
    day = draw(_day)
    year = draw(_year)
    sep = draw(st.sampled_from(["/", "-"]))
    # Cover both zero-padded and non-padded month/day renderings.
    padded = draw(st.booleans())
    if padded:
        date = f"{month:02d}{sep}{day:02d}{sep}{year}"
    else:
        date = f"{month}{sep}{day}{sep}{year}"
    return date, str(year)


@st.composite
def iso_date(draw):
    """ISO 8601 date YYYY-MM-DD."""
    year = draw(_year)
    month = draw(_month)
    day = draw(_day)
    return f"{year}-{month:02d}-{day:02d}", str(year)


@st.composite
def named_month_date(draw):
    """Named-month forms: 'January 15, 2023' and '15 Jan 2023'."""
    idx = draw(st.integers(min_value=0, max_value=11))
    day = draw(_day)
    year = draw(_year)
    if draw(st.booleans()):
        # "Month DD, YYYY"
        return f"{_MONTHS_FULL[idx]} {day}, {year}", str(year)
    # "DD Mon YYYY"
    return f"{day} {_MONTHS_ABBR[idx]} {year}", str(year)


supported_date = st.one_of(numeric_date(), iso_date(), named_month_date())


def _embed(identifier: str, prefix: str, suffix: str) -> tuple[str, int, int]:
    """Embed identifier in filler, returning (text, start, end) of the span."""
    parts = [p for p in (prefix, identifier, suffix) if p]
    text = " ".join(parts)
    start = text.index(identifier)
    return text, start, start + len(identifier)


# ---------------------------------------------------------------------------
# Property 2: Dates with month and day are detected
# Feature: deidentification-service, Property 2: Dates with month and day are detected
# Validates: Requirements 2.1
# ---------------------------------------------------------------------------

class TestProperty2DateDetection:
    @given(data=supported_date, prefix=filler, suffix=filler)
    @settings(max_examples=10, deadline=None)
    def test_supported_date_is_detected(self, data, prefix, suffix):
        date_str, _ = data
        text, start, end = _embed(date_str, prefix, suffix)

        redactions = Deidentifier().detect_structured(text)

        covering = [
            r
            for r in redactions
            if r.category == IdentifierCategory.DATE
            and r.start <= start
            and r.end >= end
        ]
        assert covering, (
            f"Expected a DATE redaction covering [{start}:{end}] ({date_str!r}) "
            f"in {text!r}; got "
            f"{[(r.category.value, r.start, r.end) for r in redactions]}"
        )


# ---------------------------------------------------------------------------
# Property 6: Dates preserve the year
# Feature: deidentification-service, Property 6: Dates preserve the year
# Validates: Requirements 2.2, 4.5
# ---------------------------------------------------------------------------

class TestProperty6YearPreservation:
    @given(data=supported_date, prefix=filler, suffix=filler)
    @settings(max_examples=10, deadline=None)
    def test_detected_date_preserves_four_digit_year(self, data, prefix, suffix):
        date_str, year = data
        text, start, end = _embed(date_str, prefix, suffix)

        dates = [
            r
            for r in Deidentifier().detect_structured(text)
            if r.category == IdentifierCategory.DATE
            and r.start <= start
            and r.end >= end
        ]
        assert dates, (
            f"Expected a DATE redaction covering ({date_str!r}) in {text!r}"
        )
        # Every detected DATE with a four-digit year captures that year so
        # downstream redaction keeps the year and drops month/day (Req 2.2, 4.5).
        for redaction in dates:
            assert redaction.preserved_year == year, (
                f"Expected preserved_year {year!r} for {date_str!r}, got "
                f"{redaction.preserved_year!r}"
            )


# ---------------------------------------------------------------------------
# Property 7: Age capping
# Feature: deidentification-service, Property 7: Age capping
# Validates: Requirements 2.3, 2.4
# ---------------------------------------------------------------------------

class TestProperty7AgeCapping:
    @given(age=st.integers(min_value=0, max_value=200))
    @settings(max_examples=10, deadline=None)
    def test_cap_age_over_89_returns_ninety_plus(self, age):
        result = Deidentifier.cap_age(age)
        if age > 89:
            assert result == "90+", (
                f"Expected '90+' for age {age}, got {result!r}"
            )
        else:
            assert result == str(age), (
                f"Expected {str(age)!r} for age {age}, got {result!r}"
            )
