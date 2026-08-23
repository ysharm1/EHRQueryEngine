"""Property-based tests for the Deidentifier human-in-the-loop review layer.

Covers Task 7:
- Property 11: Review decisions are applied correctly — after ``apply_review``
  an approved span shows its token, a rejected span shows its original text,
  and an edited span shows the reviewer-supplied replacement.
- Property 12: Finalization gating — ``finalize`` succeeds and sets status
  ``"deidentified"`` iff every low-confidence redaction has a decision;
  otherwise finalization is rejected and the status stays ``"needs_review"``.

Results are built directly from manually constructed, disjoint redactions (no
network) so the review logic is exercised in isolation. Identifiers use an
uppercase/digit marker alphabet while filler uses lowercase words, so no
identifier can coincidentally appear in the surrounding text.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.deidentifier import (
    Deidentifier,
    DeidentificationResult,
    IdentifierCategory,
    Redaction,
    REDACTION_TOKENS,
    ReviewDecision,
)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

# Lowercase-only filler words: no digits, brackets, or the uppercase marker
# characters used to build identifiers, so an identifier never appears in the
# clear text by accident.
_SAFE_WORDS = ["patient", "seen", "today", "note", "visit", "clinical", "history"]

# Non-DATE categories so the effective token always equals ``redaction.token``
# (DATE tokens carry a preserved year, handled/tested elsewhere).
_CATEGORIES = [
    IdentifierCategory.NAME,
    IdentifierCategory.PHONE,
    IdentifierCategory.SSN,
    IdentifierCategory.EMAIL,
    IdentifierCategory.MRN,
    IdentifierCategory.ACCOUNT,
    IdentifierCategory.IP,
    IdentifierCategory.URL,
    IdentifierCategory.GEO,
    IdentifierCategory.OTHER,
]

_ACTION_CHOICES = ["approve", "reject", "edit", "none"]


@st.composite
def review_scenario(draw):
    """Build a (Deidentifier, original_text, result, decisions) scenario.

    Redactions are laid out over space-separated, marker-delimited identifiers,
    each with a random confidence and a random review threshold, so some are
    low-confidence (flagged) and some are not. Decisions are generated per
    redaction with a random action (approve/reject/edit) or omitted entirely,
    giving varied review completeness for the finalization gate.
    """
    threshold = draw(st.floats(min_value=0.05, max_value=0.95))
    count = draw(st.integers(min_value=0, max_value=6))

    text = ""
    redactions: list[Redaction] = []

    for index in range(count):
        if draw(st.booleans()):
            text += draw(st.sampled_from(_SAFE_WORDS)) + " "

        payload = draw(
            st.text(alphabet="ABCDEFGHIJKLMNOP0123456789", min_size=2, max_size=6)
        )
        identifier = f"Q{index}Z{payload}"
        category = draw(st.sampled_from(_CATEGORIES))
        confidence = draw(st.floats(min_value=0.0, max_value=1.0))

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
                confidence=confidence,
                preserved_year=None,
            )
        )

    text += draw(st.sampled_from(_SAFE_WORDS + [""]))

    deid = Deidentifier(review_threshold=threshold)
    deidentified_text = Deidentifier.apply_redactions(text, redactions)
    report = Deidentifier.build_report(redactions, threshold)
    status = "needs_review" if report.low_confidence else "deidentified"
    result = DeidentificationResult(
        deidentified_text=deidentified_text,
        redactions=redactions,
        report=report,
        status=status,
    )

    # Generate a review decision (or none) for each redaction.
    decisions: list[ReviewDecision] = []
    for index in range(len(redactions)):
        action = draw(st.sampled_from(_ACTION_CHOICES))
        if action == "none":
            continue
        if action == "edit":
            suffix = draw(st.text(alphabet="abcdefgh", min_size=1, max_size=5))
            # Distinctive, non-empty replacement that cannot clash with markers.
            decisions.append(ReviewDecision(index, "edit", f"edit{index}{suffix}"))
        else:
            decisions.append(ReviewDecision(index, action))

    return deid, text, result, decisions


def _expected_reviewed_text(deid, original, redactions, decisions):
    """Independently compute the reviewed text from the *original* text.

    Applies each span's reviewed value in descending start order (spans are
    disjoint), mirroring the per-span semantics of Property 11 without reusing
    ``apply_review``'s reconstruction-from-output approach.
    """
    decision_map = {d.redaction_index: d for d in decisions}
    output = original
    for index in sorted(range(len(redactions)), key=lambda i: redactions[i].start, reverse=True):
        redaction = redactions[index]
        decision = decision_map.get(index)
        if decision is None or decision.action == "approve":
            replacement = deid._effective_token(redaction)
        elif decision.action == "reject":
            replacement = redaction.original_text
        else:  # edit
            replacement = decision.replacement
        output = output[: redaction.start] + replacement + output[redaction.end :]
    return output


# ---------------------------------------------------------------------------
# Property 11: Review decisions are applied correctly
# Feature: deidentification-service, Property 11: Review decisions are applied correctly
# Validates: Requirements 6.2, 6.3, 6.4
# ---------------------------------------------------------------------------

class TestProperty11ReviewDecisionsApplied:
    @given(scenario=review_scenario())
    @settings(max_examples=5, deadline=None)
    def test_each_span_reflects_its_decision(self, scenario):
        deid, original, result, decisions = scenario
        reviewed = deid.apply_review(result, decisions)

        # The recomputed text equals an independent original-based substitution:
        # approved -> token, rejected -> original text, edited -> replacement.
        expected = _expected_reviewed_text(deid, original, result.redactions, decisions)
        assert reviewed.deidentified_text == expected

        # Per-span outcome assertions (Req 6.2, 6.3, 6.4).
        decision_map = {d.redaction_index: d for d in decisions}
        for index, redaction in enumerate(result.redactions):
            decision = decision_map.get(index)
            if decision is None or decision.action == "approve":
                # Approved / undecided: the token remains in the output.
                assert deid._effective_token(redaction) in reviewed.deidentified_text
            elif decision.action == "reject":
                # Rejected: the original identifier is restored.
                assert redaction.original_text in reviewed.deidentified_text
            else:  # edit
                # Edited: the reviewer replacement is present.
                assert decision.replacement in reviewed.deidentified_text


# ---------------------------------------------------------------------------
# Property 12: Finalization gating
# Feature: deidentification-service, Property 12: Finalization gating
# Validates: Requirements 6.5, 6.6
# ---------------------------------------------------------------------------

class TestProperty12FinalizationGating:
    @given(scenario=review_scenario())
    @settings(max_examples=5, deadline=None)
    def test_finalize_gated_on_flagged_decisions(self, scenario):
        deid, _original, result, decisions = scenario

        threshold = deid.review_threshold
        flagged_indices = {
            index
            for index, redaction in enumerate(result.redactions)
            if redaction.confidence < threshold
        }
        decided_indices = {d.redaction_index for d in decisions}
        all_flagged_decided = flagged_indices.issubset(decided_indices)

        finalized = deid.finalize(result, decisions)

        if all_flagged_decided:
            # Every flagged redaction was decided -> finalization succeeds.
            assert deid.can_finalize(result, decisions) is True
            assert finalized.status == "deidentified"
        else:
            # At least one flagged redaction is undecided -> rejected.
            assert deid.can_finalize(result, decisions) is False
            assert finalized.status == "needs_review"


# ---------------------------------------------------------------------------
# Unit tests: specific examples and edge cases for apply_review / finalize
# ---------------------------------------------------------------------------

def _result_from(text, redactions, threshold=0.85):
    """Build a DeidentificationResult from a text and manual redactions."""
    report = Deidentifier.build_report(redactions, threshold)
    status = "needs_review" if report.low_confidence else "deidentified"
    return DeidentificationResult(
        deidentified_text=Deidentifier.apply_redactions(text, redactions),
        redactions=redactions,
        report=report,
        status=status,
    )


def _red(category, start, end, text, confidence):
    return Redaction(
        category=category,
        start=start,
        end=end,
        original_text=text[start:end],
        token=REDACTION_TOKENS[category],
        method="llm",
        confidence=confidence,
    )


class TestApplyReviewUnit:
    def test_approve_keeps_token(self):
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 0.4)]
        result = _result_from(text, redactions)
        reviewed = Deidentifier().apply_review(
            result, [ReviewDecision(0, "approve")]
        )
        assert reviewed.deidentified_text == "Contact [NAME] today"

    def test_reject_restores_original(self):
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 0.4)]
        result = _result_from(text, redactions)
        reviewed = Deidentifier().apply_review(
            result, [ReviewDecision(0, "reject")]
        )
        assert reviewed.deidentified_text == "Contact Jane Roe today"

    def test_edit_uses_replacement(self):
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 0.4)]
        result = _result_from(text, redactions)
        reviewed = Deidentifier().apply_review(
            result, [ReviewDecision(0, "edit", "[REDACTED-NAME]")]
        )
        assert reviewed.deidentified_text == "Contact [REDACTED-NAME] today"

    def test_undecided_redaction_keeps_token(self):
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 0.4)]
        result = _result_from(text, redactions)
        reviewed = Deidentifier().apply_review(result, [])
        assert reviewed.deidentified_text == "Contact [NAME] today"

    def test_edit_without_replacement_raises(self):
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 0.4)]
        result = _result_from(text, redactions)
        try:
            Deidentifier().apply_review(result, [ReviewDecision(0, "edit")])
            assert False, "expected ValueError for edit without replacement"
        except ValueError:
            pass

    def test_out_of_range_index_raises(self):
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 0.4)]
        result = _result_from(text, redactions)
        try:
            Deidentifier().apply_review(result, [ReviewDecision(5, "approve")])
            assert False, "expected ValueError for out-of-range index"
        except ValueError:
            pass

    def test_mixed_decisions_across_multiple_spans(self):
        text = "call 800-555-1234 or ssn 123-45-6789 today"
        redactions = [
            _red(IdentifierCategory.PHONE, 5, 17, text, 0.4),
            _red(IdentifierCategory.SSN, 25, 36, text, 0.4),
        ]
        result = _result_from(text, redactions)
        reviewed = Deidentifier().apply_review(
            result,
            [ReviewDecision(0, "reject"), ReviewDecision(1, "edit", "XXX")],
        )
        assert reviewed.deidentified_text == "call 800-555-1234 or ssn XXX today"


class TestFinalizeUnit:
    def test_finalize_succeeds_when_all_flagged_decided(self):
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 0.4)]
        result = _result_from(text, redactions)
        assert result.status == "needs_review"
        finalized = Deidentifier().finalize(result, [ReviewDecision(0, "approve")])
        assert finalized.status == "deidentified"

    def test_finalize_rejected_when_flagged_undecided(self):
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 0.4)]
        result = _result_from(text, redactions)
        finalized = Deidentifier().finalize(result, [])
        assert finalized.status == "needs_review"

    def test_finalize_succeeds_with_no_flagged_redactions(self):
        # High-confidence redaction is not flagged, so no review is required.
        text = "Contact Jane Roe today"
        redactions = [_red(IdentifierCategory.NAME, 8, 16, text, 1.0)]
        result = _result_from(text, redactions)
        assert result.status == "deidentified"
        finalized = Deidentifier().finalize(result, [])
        assert finalized.status == "deidentified"


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__, "-v"])
