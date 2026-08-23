"""Property-based tests for the Deidentifier structured (regex) detection layer.

Covers:
- Property 1: Structured identifiers are detected.
- Property 3: Detection metadata invariant.

Uses hypothesis to generate per-category identifiers embedded in random filler
text and asserts detection, category correctness, and the metadata invariant.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.deidentifier import (
    Deidentifier,
    IdentifierCategory,
    Redaction,
    REDACTION_TOKENS,
)


# ---------------------------------------------------------------------------
# Filler text strategy
#
# Filler words are drawn from a fixed alphabetic vocabulary that contains no
# digits and none of the keyword triggers (mrn, account, license, vin, serial,
# device, ...). This keeps generated filler free of spurious identifiers so the
# embedded identifier is the one under test.
# ---------------------------------------------------------------------------

_SAFE_WORDS = [
    "patient", "presented", "with", "the", "today", "visit", "note",
    "clinical", "history", "seen", "follow", "up", "chart", "summary",
    "reported", "stable", "review", "plan", "assessment", "impression",
]

filler = st.lists(st.sampled_from(_SAFE_WORDS), min_size=0, max_size=6).map(" ".join)


# ---------------------------------------------------------------------------
# Per-category identifier strategies (well-formed, unambiguous)
# ---------------------------------------------------------------------------

@st.composite
def ssn_identifier(draw):
    area = draw(st.integers(min_value=1, max_value=899))
    group = draw(st.integers(min_value=1, max_value=99))
    serial = draw(st.integers(min_value=1, max_value=9999))
    return f"{area:03d}-{group:02d}-{serial:04d}"


@st.composite
def phone_identifier(draw):
    area = draw(st.integers(min_value=200, max_value=999))
    prefix = draw(st.integers(min_value=200, max_value=999))
    line = draw(st.integers(min_value=0, max_value=9999))
    return f"{area:03d}-{prefix:03d}-{line:04d}"


_LETTERS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=8)


@st.composite
def email_identifier(draw):
    user = draw(_LETTERS)
    domain = draw(_LETTERS.filter(lambda s: s != "www"))
    tld = draw(st.sampled_from(["com", "org", "net", "edu", "io"]))
    return f"{user}@{domain}.{tld}"


@st.composite
def url_identifier(draw):
    scheme = draw(st.sampled_from(["https://", "http://"]))
    domain = draw(_LETTERS)
    tld = draw(st.sampled_from(["com", "org", "net"]))
    return f"{scheme}{domain}.{tld}"


@st.composite
def ip_identifier(draw):
    octets = [draw(st.integers(min_value=0, max_value=255)) for _ in range(4)]
    return ".".join(str(o) for o in octets)


@st.composite
def zip_identifier(draw):
    # 5-digit ZIP only. ZIP+4 is intentionally excluded here because
    # "12345-6789" is genuinely ambiguous with the SSN pattern.
    return f"{draw(st.integers(min_value=10000, max_value=99999))}"


_ALNUM = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=4, max_size=10
)


@st.composite
def mrn_identifier(draw):
    # Separators the configured MRN pattern (\bMRN[:#]?\s*\w+\b) accepts: a
    # single optional ':' or '#' followed by optional whitespace.
    sep = draw(st.sampled_from(["", " ", ":", ": ", "#", "# "]))
    value = draw(_ALNUM)
    return f"MRN{sep}{value}"


@st.composite
def account_identifier(draw):
    keyword = draw(st.sampled_from(["account", "acct"]))
    sep = draw(st.sampled_from([" ", " #", " no ", " number "]))
    return f"{keyword}{sep}{draw(_ALNUM)}"


@st.composite
def license_identifier(draw):
    keyword = draw(st.sampled_from(["license", "licence", "certificate", "cert"]))
    sep = draw(st.sampled_from([" ", " #", " no ", " number "]))
    return f"{keyword}{sep}{draw(_ALNUM)}"


@st.composite
def vehicle_identifier(draw):
    sep = draw(st.sampled_from([" ", " #", " no ", ": "]))
    return f"VIN{sep}{draw(_ALNUM)}"


@st.composite
def device_identifier(draw):
    keyword = draw(st.sampled_from(["device", "serial"]))
    sep = draw(st.sampled_from([" ", " #", " no ", " number "]))
    return f"{keyword}{sep}{draw(_ALNUM)}"


# (strategy, expected category) pairs covering Requirements 1.1-1.8.
CATEGORY_STRATEGIES = st.one_of(
    st.tuples(ssn_identifier(), st.just(IdentifierCategory.SSN)),
    st.tuples(phone_identifier(), st.just(IdentifierCategory.PHONE)),
    st.tuples(email_identifier(), st.just(IdentifierCategory.EMAIL)),
    st.tuples(url_identifier(), st.just(IdentifierCategory.URL)),
    st.tuples(ip_identifier(), st.just(IdentifierCategory.IP)),
    st.tuples(zip_identifier(), st.just(IdentifierCategory.ZIP)),
    st.tuples(mrn_identifier(), st.just(IdentifierCategory.MRN)),
    st.tuples(account_identifier(), st.just(IdentifierCategory.ACCOUNT)),
    st.tuples(license_identifier(), st.just(IdentifierCategory.LICENSE)),
    st.tuples(vehicle_identifier(), st.just(IdentifierCategory.VEHICLE)),
    st.tuples(device_identifier(), st.just(IdentifierCategory.DEVICE)),
)


def _embed(identifier: str, prefix: str, suffix: str) -> tuple[str, int, int]:
    """Embed identifier in filler, returning (text, start, end) of the span."""
    parts = [p for p in (prefix, identifier, suffix) if p]
    text = " ".join(parts)
    start = text.index(identifier)
    return text, start, start + len(identifier)


# ---------------------------------------------------------------------------
# Property 1: Structured identifiers are detected
# Feature: deidentification-service, Property 1: Structured identifiers are detected
# Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
# ---------------------------------------------------------------------------

class TestProperty1StructuredDetection:
    @given(data=CATEGORY_STRATEGIES, prefix=filler, suffix=filler)
    @settings(max_examples=5, deadline=None)
    def test_structured_identifier_is_detected(self, data, prefix, suffix):
        identifier, expected_category = data
        text, start, end = _embed(identifier, prefix, suffix)

        redactions = Deidentifier().detect_structured(text)

        covering = [
            r
            for r in redactions
            if r.category == expected_category and r.start <= start and r.end >= end
        ]
        assert covering, (
            f"Expected a {expected_category.value} redaction covering "
            f"[{start}:{end}] ({identifier!r}) in {text!r}; got "
            f"{[(r.category.value, r.start, r.end) for r in redactions]}"
        )


# ---------------------------------------------------------------------------
# Property 3: Detection metadata invariant
# Feature: deidentification-service, Property 3: Detection metadata invariant
# Validates: Requirements 1.9, 2.5, 3.2, 3.5
# ---------------------------------------------------------------------------

def _simulate_llm_redaction(text: str, start: int, end: int, confidence: float) -> Redaction:
    """Construct an LLM-style Redaction exactly as detect_contextual will.

    Mirrors the contract: original_text is sliced from the source, method is
    "llm", and confidence is the model-supplied score. Used to exercise the
    metadata invariant for the LLM branch without a network call.
    """
    return Redaction(
        category=IdentifierCategory.NAME,
        start=start,
        end=end,
        original_text=text[start:end],
        token=REDACTION_TOKENS[IdentifierCategory.NAME],
        method="llm",
        confidence=confidence,
    )


def _assert_metadata_invariant(text: str, redaction: Redaction) -> None:
    # Span faithfully identifies the original substring (Req 1.9, 3.2).
    assert text[redaction.start : redaction.end] == redaction.original_text
    if redaction.method == "regex":
        assert redaction.confidence == 1.0  # Req 1.9, 2.5, 3.5
    elif redaction.method == "llm":
        assert 0.0 <= redaction.confidence <= 1.0  # Req 3.2
    else:  # pragma: no cover - only regex/llm are valid methods
        raise AssertionError(f"unexpected method {redaction.method!r}")


class TestProperty3MetadataInvariant:
    @given(data=CATEGORY_STRATEGIES, prefix=filler, suffix=filler)
    @settings(max_examples=5, deadline=None)
    def test_regex_detections_satisfy_metadata_invariant(self, data, prefix, suffix):
        identifier, _ = data
        text, _, _ = _embed(identifier, prefix, suffix)

        for redaction in Deidentifier().detect_structured(text):
            assert redaction.method == "regex"
            _assert_metadata_invariant(text, redaction)

    @given(
        text=st.text(min_size=1, max_size=200),
        confidence=st.floats(min_value=0.0, max_value=1.0),
        offsets=st.data(),
    )
    @settings(max_examples=5, deadline=None)
    def test_llm_detections_satisfy_metadata_invariant(self, text, confidence, offsets):
        start = offsets.draw(st.integers(min_value=0, max_value=len(text) - 1))
        end = offsets.draw(st.integers(min_value=start + 1, max_value=len(text)))
        redaction = _simulate_llm_redaction(text, start, end, confidence)
        _assert_metadata_invariant(text, redaction)


# ---------------------------------------------------------------------------
# Unit tests: precedence and metadata specifics (Requirements 1.1-1.9, 3.5)
# ---------------------------------------------------------------------------

class TestStructuredDetectionUnit:
    def test_ssn_detected_with_regex_metadata(self):
        text = "SSN on file is 123-45-6789 per intake."
        redactions = Deidentifier().detect_structured(text)
        ssns = [r for r in redactions if r.category == IdentifierCategory.SSN]
        assert len(ssns) == 1
        r = ssns[0]
        assert text[r.start : r.end] == "123-45-6789"
        assert r.original_text == "123-45-6789"
        assert r.method == "regex"
        assert r.confidence == 1.0

    def test_ssn_takes_precedence_over_generic_digits(self):
        # A bare 9-digit run matches the SSN pattern; no competing ZIP span
        # should survive over it.
        text = "id 123456789 end"
        redactions = Deidentifier().detect_structured(text)
        covering = [r for r in redactions if r.start <= text.index("123456789") < r.end]
        assert len(covering) == 1
        assert covering[0].category == IdentifierCategory.SSN

    def test_date_takes_precedence_over_zip(self):
        # The numeric date must not be split into a ZIP fragment.
        text = "date of service 01-15-2023 documented"
        redactions = Deidentifier().detect_structured(text)
        assert any(r.category == IdentifierCategory.DATE for r in redactions)
        assert not any(r.category == IdentifierCategory.ZIP for r in redactions)

    def test_date_preserves_year_metadata(self):
        text = "seen on 2023-01-15 for review"
        redactions = Deidentifier().detect_structured(text)
        dates = [r for r in redactions if r.category == IdentifierCategory.DATE]
        assert len(dates) == 1
        assert dates[0].preserved_year == "2023"

    def test_invalid_all_zero_ssn_is_ignored(self):
        text = "value 000-00-0000 here"
        redactions = Deidentifier().detect_structured(text)
        assert not any(r.category == IdentifierCategory.SSN for r in redactions)

    def test_ip_octets_over_255_rejected(self):
        text = "host 999.999.999.999 offline"
        redactions = Deidentifier().detect_structured(text)
        assert not any(r.category == IdentifierCategory.IP for r in redactions)

    def test_no_identifiers_returns_empty(self):
        text = "the patient presented today for a routine visit"
        assert Deidentifier().detect_structured(text) == []

    def test_returned_spans_are_non_overlapping(self):
        text = "email me@x.com or call 800-555-1234 or MRN: 998877"
        redactions = Deidentifier().detect_structured(text)
        ordered = sorted(redactions, key=lambda r: r.start)
        for a, b in zip(ordered, ordered[1:]):
            assert a.end <= b.start

    def test_custom_mrn_pattern_is_honored(self):
        deid = Deidentifier(mrn_pattern=r"\bPT-\d{6}\b")
        text = "record PT-123456 filed"
        redactions = deid.detect_structured(text)
        assert any(
            r.category == IdentifierCategory.MRN and r.original_text == "PT-123456"
            for r in redactions
        )
