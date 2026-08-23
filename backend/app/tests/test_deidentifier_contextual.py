"""Unit tests for the Deidentifier contextual (GPT-4o / LLM) detector.

Covers Task 5.2:
- PHOTO flag emission for full-face photograph references (Req 3.3).
- API-failure fallback path — detect_contextual returns [] without raising,
  so upstream regex redactions are retained and the job needs review (Req 3.4).
- Malformed / partial JSON handling — discard unparseable entries, keep valid
  ones (Error Handling).
- Offset mismatch re-location and discard (Error Handling).

A deterministic fake OpenAI client is injected into the Deidentifier so these
tests run offline with no network access (Req 3.1).
"""
import pytest

from app.services.deidentifier import Deidentifier, IdentifierCategory


# ---------------------------------------------------------------------------
# Deterministic fake OpenAI client
#
# Mimics the minimal surface the detector uses:
#   client.chat.completions.create(...).choices[0].message.content
# The content returned is whatever canned string the test supplies. A client
# configured with ``raise_exc`` simulates an API failure/timeout.
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
    def __init__(self, content, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content, raise_exc=None):
        self.completions = _FakeCompletions(content, raise_exc)


class FakeOpenAIClient:
    """Injectable stand-in for the OpenAI client used by detect_contextual."""

    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)

    @property
    def last_call(self):
        return self.chat.completions.calls[-1] if self.chat.completions.calls else None


def _deid(content=None, raise_exc=None):
    """Build a Deidentifier wired to a fake client returning ``content``."""
    return Deidentifier(openai_client=FakeOpenAIClient(content=content, raise_exc=raise_exc))


# ---------------------------------------------------------------------------
# PHOTO flag emission (Req 3.3)
# ---------------------------------------------------------------------------

class TestPhotoFlagEmission:
    def test_full_face_photo_reference_emits_photo_flag(self):
        text = "A full-face photograph is attached to the chart."
        photo_ref = "full-face photograph"
        start = text.index(photo_ref)
        content = (
            '[{"category": "PHOTO", "text": "full-face photograph", '
            f'"start": {start}, "end": {start + len(photo_ref)}, '
            '"confidence": 0.9}]'
        )
        redactions = _deid(content).detect_contextual(text)

        photos = [r for r in redactions if r.category == IdentifierCategory.PHOTO]
        assert len(photos) == 1
        photo = photos[0]
        assert photo.original_text == photo_ref
        assert photo.token == "[PHOTO]"
        assert photo.method == "llm"
        assert text[photo.start : photo.end] == photo.original_text

    def test_photo_flag_relocated_when_offsets_missing(self):
        # Model omits offsets; the detector must still locate the reference.
        text = "Patient consented; a full-face photo is on file."
        content = (
            '[{"category": "PHOTO", "text": "full-face photo", "confidence": 0.8}]'
        )
        redactions = _deid(content).detect_contextual(text)

        photos = [r for r in redactions if r.category == IdentifierCategory.PHOTO]
        assert len(photos) == 1
        assert photos[0].original_text == "full-face photo"


# ---------------------------------------------------------------------------
# API-failure fallback path (Req 3.4)
# ---------------------------------------------------------------------------

class TestApiFailureFallback:
    def test_api_exception_returns_empty_without_raising(self):
        text = "Dr. Alice Smith saw the patient in Springfield."
        deid = _deid(raise_exc=RuntimeError("simulated API timeout"))

        # Must not raise; regex redactions are retained upstream.
        result = deid.detect_contextual(text)
        assert result == []

    def test_no_client_and_no_key_skips_gracefully(self):
        # No injected client and no API key -> regex-only, no contextual spans.
        deid = Deidentifier()
        assert deid.detect_contextual("Patient John Doe in Boston.") == []

    def test_api_failure_does_not_affect_regex_detection(self):
        # detect_structured still works when the LLM path fails.
        text = "SSN 123-45-6789 for the patient."
        deid = _deid(raise_exc=ConnectionError("network down"))
        assert deid.detect_contextual(text) == []
        structured = deid.detect_structured(text)
        assert any(r.category == IdentifierCategory.SSN for r in structured)


# ---------------------------------------------------------------------------
# Malformed / partial JSON handling (Error Handling table)
# ---------------------------------------------------------------------------

class TestMalformedJsonHandling:
    def test_completely_invalid_json_returns_empty(self):
        text = "Patient seen today."
        assert _deid("this is not json at all").detect_contextual(text) == []

    def test_partial_json_keeps_valid_entries_discards_invalid(self):
        text = "Dr. Alice Smith and nurse Bob Jones attended."
        # First entry valid; second entry is not an object (should be dropped);
        # third entry lacks a usable text field (should be dropped).
        a_start = text.index("Alice Smith")
        content = (
            "["
            '{"category": "NAME", "text": "Alice Smith", '
            f'"start": {a_start}, "end": {a_start + len("Alice Smith")}, '
            '"confidence": 0.95},'
            '"not-an-object",'
            '{"category": "NAME", "confidence": 0.9}'
            "]"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 1
        assert redactions[0].original_text == "Alice Smith"
        assert redactions[0].category == IdentifierCategory.NAME

    def test_json_wrapped_in_markdown_fence_is_parsed(self):
        text = "Contact Jane Roe for details."
        j_start = text.index("Jane Roe")
        content = (
            "```json\n"
            "["
            '{"category": "NAME", "text": "Jane Roe", '
            f'"start": {j_start}, "end": {j_start + len("Jane Roe")}, '
            '"confidence": 0.9}'
            "]\n"
            "```"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 1
        assert redactions[0].original_text == "Jane Roe"

    def test_object_with_nested_list_is_parsed(self):
        text = "Seen by Sam Lee."
        s_start = text.index("Sam Lee")
        content = (
            '{"spans": ['
            '{"category": "NAME", "text": "Sam Lee", '
            f'"start": {s_start}, "end": {s_start + len("Sam Lee")}, '
            '"confidence": 0.88}'
            "]}"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 1
        assert redactions[0].original_text == "Sam Lee"

    def test_unknown_category_coerced_to_other(self):
        text = "Reference marker XYZ-999 noted."
        m_start = text.index("XYZ-999")
        content = (
            "["
            '{"category": "MADE_UP", "text": "XYZ-999", '
            f'"start": {m_start}, "end": {m_start + len("XYZ-999")}, '
            '"confidence": 0.7}'
            "]"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 1
        assert redactions[0].category == IdentifierCategory.OTHER

    def test_missing_confidence_gets_default(self):
        text = "Patient Mary Major admitted."
        m_start = text.index("Mary Major")
        content = (
            "["
            '{"category": "NAME", "text": "Mary Major", '
            f'"start": {m_start}, "end": {m_start + len("Mary Major")}}}'
            "]"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 1
        assert 0.0 <= redactions[0].confidence <= 1.0

    def test_out_of_range_confidence_is_clamped(self):
        text = "Patient Ann Poe seen."
        a_start = text.index("Ann Poe")
        content = (
            "["
            '{"category": "NAME", "text": "Ann Poe", '
            f'"start": {a_start}, "end": {a_start + len("Ann Poe")}, '
            '"confidence": 5.0}'
            "]"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 1
        assert redactions[0].confidence == 1.0


# ---------------------------------------------------------------------------
# Offset mismatch: re-location and discard (Error Handling table)
# ---------------------------------------------------------------------------

class TestOffsetMismatchHandling:
    def test_wrong_offsets_are_relocated_via_find(self):
        text = "The provider is Dr. Grace Hopper."
        correct_start = text.index("Grace Hopper")
        # Deliberately wrong offsets (point at "The provider").
        content = (
            "["
            '{"category": "NAME", "text": "Grace Hopper", '
            '"start": 0, "end": 12, "confidence": 0.92}'
            "]"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 1
        r = redactions[0]
        # Offsets re-located so the span faithfully covers the real substring.
        assert r.start == correct_start
        assert r.end == correct_start + len("Grace Hopper")
        assert text[r.start : r.end] == "Grace Hopper"

    def test_span_not_present_in_text_is_discarded(self):
        text = "The note mentions no names."
        content = (
            "["
            '{"category": "NAME", "text": "Nonexistent Person", '
            '"start": 4, "end": 22, "confidence": 0.9}'
            "]"
        )
        redactions = _deid(content).detect_contextual(text)
        assert redactions == []

    def test_out_of_bounds_offsets_relocate_when_text_present(self):
        text = "Care coordinated by Nurse Kim."
        content = (
            "["
            '{"category": "NAME", "text": "Nurse Kim", '
            '"start": 999, "end": 1010, "confidence": 0.9}'
            "]"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 1
        assert redactions[0].original_text == "Nurse Kim"
        assert text[redactions[0].start : redactions[0].end] == "Nurse Kim"

    def test_metadata_invariant_holds_for_all_returned_spans(self):
        text = "Dr. Alice Smith in Metropolis; photo of Bob attached."
        a_start = text.index("Alice Smith")
        m_start = text.index("Metropolis")
        content = (
            "["
            '{"category": "NAME", "text": "Alice Smith", '
            f'"start": {a_start}, "end": {a_start + len("Alice Smith")}, '
            '"confidence": 0.95},'
            '{"category": "GEO", "text": "Metropolis", '
            f'"start": {m_start}, "end": {m_start + len("Metropolis")}, '
            '"confidence": 0.8}'
            "]"
        )
        redactions = _deid(content).detect_contextual(text)
        assert len(redactions) == 2
        for r in redactions:
            assert text[r.start : r.end] == r.original_text
            assert r.method == "llm"
            assert 0.0 <= r.confidence <= 1.0


# ---------------------------------------------------------------------------
# Prompt / model wiring sanity (Req 3.1)
# ---------------------------------------------------------------------------

class TestModelWiring:
    def test_uses_gpt_4o_model_and_sends_text(self):
        text = "Patient Carol Danvers seen."
        c_start = text.index("Carol Danvers")
        content = (
            "["
            '{"category": "NAME", "text": "Carol Danvers", '
            f'"start": {c_start}, "end": {c_start + len("Carol Danvers")}, '
            '"confidence": 0.9}'
            "]"
        )
        fake = FakeOpenAIClient(content=content)
        deid = Deidentifier(openai_client=fake)
        deid.detect_contextual(text)

        call = fake.last_call
        assert call is not None
        assert call["model"] == "gpt-4o"
        # The source text is forwarded to the model as the user message.
        assert any(m["content"] == text for m in call["messages"])

    def test_empty_text_skips_model_call(self):
        fake = FakeOpenAIClient(content="[]")
        deid = Deidentifier(openai_client=fake)
        assert deid.detect_contextual("") == []
        assert fake.last_call is None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
