"""Property-based tests for Deidentifier span merging and redaction application.

Covers:
- Property 5: Overlapping spans are merged into disjoint spans.
- Property 4: No original identifier survives redaction.

Uses hypothesis to generate arbitrary (possibly overlapping) spans for merging
and text-with-redaction sets for redaction application, then asserts the merge
disjointness/union invariant and the no-survival invariant.
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
# Helpers
# ---------------------------------------------------------------------------

def _covered_chars(spans) -> set[int]:
    """Return the set of character offsets covered by the given spans."""
    covered: set[int] = set()
    for span in spans:
        covered.update(range(span.start, span.end))
    return covered


# ---------------------------------------------------------------------------
# Property 5: Overlapping spans are merged into disjoint spans
# Feature: deidentification-service, Property 5: Overlapping spans are merged into disjoint spans
# Validates: Requirements 4.2
# ---------------------------------------------------------------------------

# A fixed base text; generated spans index into it so each redaction's
# original_text faithfully equals text[start:end] (the detection invariant).
_BASE_TEXT = "".join(chr(ord("a") + (i % 26)) for i in range(40))
_ALL_CATEGORIES = list(IdentifierCategory)


@st.composite
def arbitrary_spans(draw):
    """Generate a list of arbitrary, possibly overlapping Redactions.

    Spans are constrained to lie within ``_BASE_TEXT`` so that
    ``original_text == text[start:end]`` holds, and every span is non-empty.
    Overlaps, containment, and adjacency all arise naturally.
    """
    length = len(_BASE_TEXT)
    count = draw(st.integers(min_value=0, max_value=8))
    spans: list[Redaction] = []
    for _ in range(count):
        start = draw(st.integers(min_value=0, max_value=length - 1))
        end = draw(st.integers(min_value=start + 1, max_value=length))
        category = draw(st.sampled_from(_ALL_CATEGORIES))
        preserved_year = draw(st.sampled_from([None, "2023", "1998"]))
        spans.append(
            Redaction(
                category=category,
                start=start,
                end=end,
                original_text=_BASE_TEXT[start:end],
                token=REDACTION_TOKENS[category],
                method="regex",
                confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
                preserved_year=preserved_year,
            )
        )
    return spans


class TestProperty5SpanMerging:
    @given(spans=arbitrary_spans())
    @settings(max_examples=5, deadline=None)
    def test_merge_yields_disjoint_spans_covering_union(self, spans):
        merged = Deidentifier.merge_spans(spans)

        # Pairwise non-overlapping: sorted spans must not overlap their neighbour.
        ordered = sorted(merged, key=lambda r: r.start)
        for left, right in zip(ordered, ordered[1:]):
            assert left.end <= right.start, (
                f"Merged spans overlap: [{left.start}:{left.end}] and "
                f"[{right.start}:{right.end}]"
            )

        # Covered character set is exactly the union of the inputs' coverage.
        assert _covered_chars(merged) == _covered_chars(spans), (
            "Merged coverage does not equal the union of input coverage"
        )

        # Each merged span's reconstructed original_text matches the source and
        # its own span width (the detection invariant is preserved).
        for span in merged:
            assert span.original_text == _BASE_TEXT[span.start : span.end]


# ---------------------------------------------------------------------------
# Property 4: No original identifier survives redaction
# Feature: deidentification-service, Property 4: No original identifier survives redaction
# Validates: Requirements 4.1, 4.3, 4.4
# ---------------------------------------------------------------------------

# Filler words are lowercase-only, contain no digits, brackets, or the uppercase
# marker characters used to build identifiers, so a generated identifier can
# never coincidentally appear in the surrounding text.
_SAFE_WORDS = [
    "patient", "presented", "with", "the", "today", "visit", "note",
    "clinical", "history", "seen", "follow", "up", "chart", "summary",
]

_filler = st.lists(st.sampled_from(_SAFE_WORDS), min_size=0, max_size=3).map(" ".join)

# Non-date identifier categories exercised by the no-survival property.
_NON_DATE_CATEGORIES = [
    IdentifierCategory.NAME,
    IdentifierCategory.PHONE,
    IdentifierCategory.SSN,
    IdentifierCategory.EMAIL,
    IdentifierCategory.MRN,
    IdentifierCategory.ACCOUNT,
    IdentifierCategory.IP,
    IdentifierCategory.URL,
]

# Payload alphabet deliberately excludes the 'Q'/'Z' marker characters so the
# per-identifier delimiter stays unambiguous and non-substring across indices.
_payload = st.text(
    alphabet="ABCDEFGHIJKLMNOP0123456789", min_size=2, max_size=6
)


@st.composite
def text_and_redactions(draw):
    """Build text plus a disjoint redaction set with distinctive identifiers.

    Each identifier is either a date (``M/D/YYYY`` with a preserved year) or a
    marker-delimited alphanumeric token (``Q{i}Z{payload}``). Markers make every
    identifier unique and guarantee it appears nowhere else in the text, so
    "original_text absent from output" is a meaningful assertion. Segments are
    space-separated, so all redaction spans are non-overlapping by construction.
    """
    count = draw(st.integers(min_value=0, max_value=6))
    text = ""
    redactions: list[Redaction] = []

    for index in range(count):
        prefix = draw(_filler)
        if prefix:
            text += prefix + " "

        is_date = draw(st.booleans())
        if is_date:
            month = draw(st.integers(min_value=1, max_value=12))
            day = draw(st.integers(min_value=1, max_value=28))
            year = draw(st.integers(min_value=1900, max_value=2099))
            identifier = f"{month}/{day}/{year}"
            category = IdentifierCategory.DATE
            preserved_year = str(year)
        else:
            payload = draw(_payload)
            identifier = f"Q{index}Z{payload}"
            category = draw(st.sampled_from(_NON_DATE_CATEGORIES))
            preserved_year = None

        start = len(text)
        text += identifier
        end = len(text)
        text += " "  # trailing separator keeps spans disjoint

        redactions.append(
            Redaction(
                category=category,
                start=start,
                end=end,
                original_text=identifier,
                token=REDACTION_TOKENS[category],
                method="regex",
                confidence=1.0,
                preserved_year=preserved_year,
            )
        )

    text += draw(_filler)
    return text, redactions


class TestProperty4NoOriginalSurvives:
    @given(data=text_and_redactions())
    @settings(max_examples=5, deadline=None)
    def test_tokens_present_and_originals_removed(self, data):
        text, redactions = data
        output = Deidentifier.apply_redactions(text, redactions)

        for redaction in redactions:
            # The typed token actually inserted must be present (Req 4.1, 4.5).
            token = Deidentifier._effective_token(redaction)
            assert token in output, (
                f"Expected token {token!r} in output {output!r}"
            )

            # The full original identifier must not survive (Req 4.4)...
            assert redaction.original_text not in output, (
                f"Original {redaction.original_text!r} survived in {output!r}"
            )

            if redaction.category == IdentifierCategory.DATE and redaction.preserved_year:
                # ...except the intentionally preserved year (Req 4.5).
                assert redaction.preserved_year in output, (
                    f"Preserved year {redaction.preserved_year!r} missing from "
                    f"{output!r}"
                )


# ---------------------------------------------------------------------------
# Unit tests: specific examples and edge cases for merge_spans / apply_redactions
# ---------------------------------------------------------------------------

def _r(category, start, end, text, preserved_year=None):
    """Build a Redaction whose original_text equals text[start:end]."""
    return Redaction(
        category=category,
        start=start,
        end=end,
        original_text=text[start:end],
        token=REDACTION_TOKENS[category],
        method="regex",
        confidence=1.0,
        preserved_year=preserved_year,
    )


class TestMergeSpansUnit:
    def test_empty_returns_empty(self):
        assert Deidentifier.merge_spans([]) == []

    def test_single_span_is_preserved(self):
        text = "abcdefghij"
        merged = Deidentifier.merge_spans([_r(IdentifierCategory.NAME, 2, 5, text)])
        assert len(merged) == 1
        assert (merged[0].start, merged[0].end) == (2, 5)
        assert merged[0].original_text == "cde"

    def test_overlapping_spans_merge_to_union(self):
        text = "abcdefghij"
        merged = Deidentifier.merge_spans(
            [_r(IdentifierCategory.NAME, 0, 5, text), _r(IdentifierCategory.SSN, 3, 8, text)]
        )
        assert len(merged) == 1
        assert (merged[0].start, merged[0].end) == (0, 8)
        assert merged[0].original_text == "abcdefgh"

    def test_contained_span_merges_into_outer(self):
        text = "abcdefghij"
        merged = Deidentifier.merge_spans(
            [_r(IdentifierCategory.NAME, 0, 8, text), _r(IdentifierCategory.SSN, 2, 4, text)]
        )
        assert len(merged) == 1
        assert (merged[0].start, merged[0].end) == (0, 8)

    def test_adjacent_spans_stay_separate(self):
        text = "abcdefghij"
        merged = Deidentifier.merge_spans(
            [_r(IdentifierCategory.NAME, 0, 3, text), _r(IdentifierCategory.SSN, 3, 6, text)]
        )
        assert len(merged) == 2
        assert [(m.start, m.end) for m in sorted(merged, key=lambda r: r.start)] == [(0, 3), (3, 6)]

    def test_disjoint_spans_stay_separate(self):
        text = "abcdefghij"
        merged = Deidentifier.merge_spans(
            [_r(IdentifierCategory.NAME, 0, 2, text), _r(IdentifierCategory.SSN, 5, 8, text)]
        )
        assert len(merged) == 2

    def test_merged_category_prefers_widest_span(self):
        text = "abcdefghij"
        merged = Deidentifier.merge_spans(
            [_r(IdentifierCategory.SSN, 0, 2, text), _r(IdentifierCategory.NAME, 1, 9, text)]
        )
        assert len(merged) == 1
        assert merged[0].category == IdentifierCategory.NAME


class TestApplyRedactionsUnit:
    def test_descending_order_keeps_offsets_valid(self):
        text = "call 800-555-1234 or ssn 123-45-6789 today"
        spans = [
            _r(IdentifierCategory.PHONE, 5, 17, text),
            _r(IdentifierCategory.SSN, 25, 36, text),
        ]
        out = Deidentifier.apply_redactions(text, spans)
        assert out == "call [PHONE] or ssn [SSN] today"
        assert "800-555-1234" not in out
        assert "123-45-6789" not in out

    def test_date_token_preserves_year(self):
        text = "seen on 2023-01-15 for review"
        spans = [_r(IdentifierCategory.DATE, 8, 18, text, preserved_year="2023")]
        out = Deidentifier.apply_redactions(text, spans)
        assert out == "seen on [DATE-2023] for review"
        assert "2023" in out
        assert "01-15" not in out

    def test_date_without_preserved_year_uses_plain_token(self):
        text = "note on 01/15 here"
        spans = [_r(IdentifierCategory.DATE, 8, 13, text)]
        out = Deidentifier.apply_redactions(text, spans)
        assert out == "note on [DATE] here"

    def test_no_spans_returns_text_unchanged(self):
        text = "nothing to redact here"
        assert Deidentifier.apply_redactions(text, []) == text

    def test_overlapping_spans_do_not_corrupt_output(self):
        # Overlapping input is a caller error; the safeguard skips the overlap
        # rather than producing torn output.
        text = "abcdefghij"
        spans = [
            _r(IdentifierCategory.NAME, 0, 5, text),
            _r(IdentifierCategory.SSN, 3, 8, text),
        ]
        out = Deidentifier.apply_redactions(text, spans)
        # Exactly one token applied; no partial original fragment left dangling.
        assert out in ("[NAME]fghij", "abc[SSN]ij")


# ---------------------------------------------------------------------------
# Unit tests: regex category wins over an overlapping LLM span (merge_spans)
#
# When a deterministic regex span and an LLM span cover overlapping characters,
# the merged redaction must take the regex category/token/method/confidence.
# This applies to every structured category, not just SSN.
# ---------------------------------------------------------------------------

def _regex(category: IdentifierCategory, start: int, end: int, text: str) -> Redaction:
    return Redaction(
        category=category, start=start, end=end, original_text=text,
        token=REDACTION_TOKENS[category], method="regex", confidence=1.0,
    )


def _llm(category: IdentifierCategory, start: int, end: int, text: str,
         confidence: float = 0.4) -> Redaction:
    return Redaction(
        category=category, start=start, end=end, original_text=text,
        token=REDACTION_TOKENS[category], method="llm", confidence=confidence,
    )


class TestRegexWinsOnOverlap:
    def test_regex_ssn_wins_over_overlapping_llm_other(self):
        # LLM grabbed the wider "SSN 123-45-6789" and mislabeled it OTHER;
        # regex grabbed the number and labeled it SSN. Regex must win.
        llm = _llm(IdentifierCategory.OTHER, 0, 15, "SSN 123-45-6789")
        regex = _regex(IdentifierCategory.SSN, 4, 15, "123-45-6789")
        merged = Deidentifier.merge_spans([llm, regex])
        assert len(merged) == 1
        assert merged[0].category == IdentifierCategory.SSN
        assert merged[0].method == "regex"
        assert merged[0].confidence == 1.0

    def test_regex_wins_for_all_structured_categories(self):
        # Every structured category should win over an overlapping LLM guess.
        for category in [
            IdentifierCategory.SSN,
            IdentifierCategory.PHONE,
            IdentifierCategory.EMAIL,
            IdentifierCategory.URL,
            IdentifierCategory.IP,
            IdentifierCategory.ZIP,
            IdentifierCategory.MRN,
            IdentifierCategory.ACCOUNT,
            IdentifierCategory.LICENSE,
            IdentifierCategory.VEHICLE,
            IdentifierCategory.DEVICE,
            IdentifierCategory.DATE,
        ]:
            regex = _regex(category, 5, 15, "xxxxxxxxxx")
            llm = _llm(IdentifierCategory.OTHER, 0, 15, "yyyyyxxxxxxxxxx")
            merged = Deidentifier.merge_spans([llm, regex])
            assert len(merged) == 1
            assert merged[0].category == category, f"regex {category} should win"
            assert merged[0].method == "regex"

    def test_llm_only_group_keeps_llm_category(self):
        # With no regex span present, the LLM category is retained.
        a = _llm(IdentifierCategory.NAME, 0, 8, "Jane Roe", confidence=0.6)
        b = _llm(IdentifierCategory.GEO, 3, 12, "Roe Boston", confidence=0.5)
        merged = Deidentifier.merge_spans([a, b])
        assert len(merged) == 1
        assert merged[0].method == "llm"
        assert merged[0].category in {IdentifierCategory.NAME, IdentifierCategory.GEO}

    def test_non_overlapping_llm_and_regex_both_kept(self):
        # Disjoint spans are not merged and both keep their own category.
        regex = _regex(IdentifierCategory.SSN, 0, 11, "123-45-6789")
        llm = _llm(IdentifierCategory.NAME, 20, 28, "Jane Roe")
        merged = sorted(Deidentifier.merge_spans([regex, llm]), key=lambda r: r.start)
        assert len(merged) == 2
        assert merged[0].category == IdentifierCategory.SSN
        assert merged[1].category == IdentifierCategory.NAME
