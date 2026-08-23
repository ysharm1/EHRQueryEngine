"""Property-based tests for the Deidentifier report and status determination.

Covers Task 6:
- Property 8: Report counts are consistent — per-category counts sum to
  ``total_redactions``, which equals the number of redactions applied.
- Property 9: Low-confidence redactions are flagged exactly — a redaction is in
  ``low_confidence`` iff its confidence is strictly below the threshold.
- Property 10: Status determination — status is ``"needs_review"`` iff the
  report has >= 1 low-confidence redaction, else ``"deidentified"``.

The GPT-4o client is replaced with a deterministic fake that returns contextual
spans located in the generated text, so the whole ``deidentify`` pipeline runs
offline and reproducibly (no network).
"""
import json

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.deidentifier import Deidentifier, IdentifierCategory


# ---------------------------------------------------------------------------
# Deterministic fake OpenAI client
#
# Mirrors the minimal surface detect_contextual uses:
#   client.chat.completions.create(...).choices[0].message.content
# The content is a canned JSON string built by the strategy below.
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class FakeOpenAIClient:
    """Injectable stand-in returning a fixed JSON payload for the LLM detector."""

    def __init__(self, content):
        self.chat = _FakeChat(content)


# ---------------------------------------------------------------------------
# Generators
#
# Build a text made of space-separated segments. Some segments are structured
# identifiers (regex-detected, confidence 1.0); some are name-like tokens that
# the fake LLM client "detects" with a random confidence. Segments are always
# space-separated, so detected spans never overlap and merging preserves the
# per-detection count. Contextual categories/confidences are chosen by the
# strategy so the low-confidence and status properties get varied inputs.
# ---------------------------------------------------------------------------

# LLM categories the fake may return (the contextual set, minus PHOTO for
# simplicity — PHOTO behaves identically for reporting purposes).
_LLM_CATEGORIES = ["NAME", "GEO", "BIOMETRIC", "OTHER"]

# Alpha-only, capitalised tokens that match NO structured regex, so the only
# way they become redactions is via the (fake) LLM path.
_name_token = st.builds(
    lambda letters: "N" + "".join(letters),
    st.lists(
        st.sampled_from(list("abcdefghijklmnopqrstuvwxyz")),
        min_size=3,
        max_size=7,
    ),
)


@st.composite
def _ssn_segment(draw):
    """A well-formed SSN string (regex-detected, confidence 1.0)."""
    area = draw(st.integers(min_value=1, max_value=899))
    group = draw(st.integers(min_value=1, max_value=99))
    serial = draw(st.integers(min_value=1, max_value=9999))
    return f"{area:03d}-{group:02d}-{serial:04d}"


@st.composite
def _email_segment(draw):
    """A simple email address (regex-detected, confidence 1.0)."""
    user = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=6))
    host = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=6))
    return f"{user}@{host}.com"


@st.composite
def deidentify_case(draw):
    """Generate a (Deidentifier, text) case with mixed regex + fake-LLM hits.

    Returns a Deidentifier wired to a fake OpenAI client whose contextual spans
    point at the name tokens embedded in ``text``. A random review threshold in
    (0, 1) is used so low-confidence flagging and status vary across examples.
    """
    threshold = draw(st.floats(min_value=0.05, max_value=0.95))
    segment_count = draw(st.integers(min_value=0, max_value=8))

    text_parts: list[str] = []
    llm_spans: list[dict] = []
    cursor = 0  # running offset accounting for a single space between segments

    for _ in range(segment_count):
        kind = draw(st.sampled_from(["ssn", "email", "filler", "name"]))
        if kind == "ssn":
            segment = draw(_ssn_segment())
        elif kind == "email":
            segment = draw(_email_segment())
        elif kind == "filler":
            segment = draw(st.sampled_from(["patient", "seen", "today", "note", "visit"]))
        else:  # name — recorded as an LLM span
            segment = draw(_name_token)

        start = cursor
        end = start + len(segment)

        if kind == "name":
            llm_spans.append(
                {
                    "category": draw(st.sampled_from(_LLM_CATEGORIES)),
                    "text": segment,
                    "start": start,
                    "end": end,
                    "confidence": draw(st.floats(min_value=0.0, max_value=1.0)),
                }
            )

        text_parts.append(segment)
        cursor = end + 1  # +1 for the joining space

    text = " ".join(text_parts)
    client = FakeOpenAIClient(json.dumps(llm_spans))
    deid = Deidentifier(openai_client=client, review_threshold=threshold)
    return deid, text


# ---------------------------------------------------------------------------
# Property 8: Report counts are consistent
# Feature: deidentification-service, Property 8: Report counts are consistent
# Validates: Requirements 5.1, 5.2, 5.4
# ---------------------------------------------------------------------------

class TestProperty8ReportCountsConsistent:
    @given(case=deidentify_case())
    @settings(max_examples=5, deadline=None)
    def test_counts_sum_to_total_equals_applied(self, case):
        deid, text = case
        result = deid.deidentify(text)
        report = result.report

        # Per-category counts sum to the reported total (Req 5.1, 5.2, 5.4).
        assert sum(report.category_counts.values()) == report.total_redactions

        # The total equals the number of redactions actually applied to output.
        assert report.total_redactions == len(result.redactions)

        # Every applied redaction is counted under its category value.
        for redaction in result.redactions:
            assert redaction.category.value in report.category_counts
        assert len(report.category_counts) == len(
            {r.category.value for r in result.redactions}
        )


# ---------------------------------------------------------------------------
# Property 9: Low-confidence redactions are flagged exactly
# Feature: deidentification-service, Property 9: Low-confidence redactions are flagged exactly
# Validates: Requirements 5.3
# ---------------------------------------------------------------------------

class TestProperty9LowConfidenceFlaggedExactly:
    @given(case=deidentify_case())
    @settings(max_examples=5, deadline=None)
    def test_flagged_iff_below_threshold(self, case):
        deid, text = case
        result = deid.deidentify(text)
        threshold = deid.review_threshold
        low_confidence = result.report.low_confidence

        # A redaction is flagged iff its confidence is strictly below threshold.
        for redaction in result.redactions:
            expected_flagged = redaction.confidence < threshold
            assert (redaction in low_confidence) == expected_flagged

        # Nothing extraneous is in the low-confidence list.
        for flagged in low_confidence:
            assert flagged.confidence < threshold
            assert flagged in result.redactions


# ---------------------------------------------------------------------------
# Property 10: Status determination
# Feature: deidentification-service, Property 10: Status determination
# Validates: Requirements 6.1, 6.7
# ---------------------------------------------------------------------------

class TestProperty10StatusDetermination:
    @given(case=deidentify_case())
    @settings(max_examples=5, deadline=None)
    def test_status_reflects_low_confidence_presence(self, case):
        deid, text = case
        result = deid.deidentify(text)

        if result.report.low_confidence:
            assert result.status == "needs_review"
        else:
            assert result.status == "deidentified"


# ---------------------------------------------------------------------------
# Unit tests: specific examples and edge cases for build_report / deidentify
# ---------------------------------------------------------------------------

class TestBuildReportUnit:
    def test_empty_spans_produce_zero_report(self):
        report = Deidentifier.build_report([], threshold=0.85)
        assert report.method == "HIPAA Safe Harbor"
        assert report.category_counts == {}
        assert report.total_redactions == 0
        assert report.low_confidence == []

    def test_method_is_hipaa_safe_harbor(self):
        deid = Deidentifier()
        result = deid.deidentify("SSN 123-45-6789 on file.")
        assert result.report.method == "HIPAA Safe Harbor"

    def test_regex_only_text_is_deidentified_without_review(self):
        # Regex detections carry confidence 1.0, so none are low-confidence.
        deid = Deidentifier()  # no client -> contextual detection skipped
        result = deid.deidentify("Call 800-555-1234 or SSN 123-45-6789.")
        assert result.status == "deidentified"
        assert result.report.low_confidence == []
        assert result.report.total_redactions == len(result.redactions)

    def test_confidence_exactly_at_threshold_not_flagged(self):
        # Strictly-below rule: confidence == threshold is NOT low-confidence.
        content = json.dumps(
            [{"category": "NAME", "text": "Jane Roe", "start": 8,
              "end": 16, "confidence": 0.85}]
        )
        deid = Deidentifier(openai_client=FakeOpenAIClient(content), review_threshold=0.85)
        result = deid.deidentify("Contact Jane Roe today.")
        assert result.report.low_confidence == []
        assert result.status == "deidentified"

    def test_low_confidence_llm_span_triggers_needs_review(self):
        content = json.dumps(
            [{"category": "NAME", "text": "Jane Roe", "start": 8,
              "end": 16, "confidence": 0.4}]
        )
        deid = Deidentifier(openai_client=FakeOpenAIClient(content), review_threshold=0.85)
        result = deid.deidentify("Contact Jane Roe today.")
        assert result.status == "needs_review"
        assert len(result.report.low_confidence) == 1
        assert result.report.low_confidence[0].original_text == "Jane Roe"

    def test_per_category_counts_reflect_applied_redactions(self):
        deid = Deidentifier()
        result = deid.deidentify("SSN 123-45-6789 and email a@b.com here.")
        counts = result.report.category_counts
        assert counts.get("SSN") == 1
        assert counts.get("EMAIL") == 1
        assert sum(counts.values()) == result.report.total_redactions


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__, "-v"])
