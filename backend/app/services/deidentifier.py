"""
De-identification Service — HIPAA Safe Harbor

Detects and redacts the 18 HIPAA Safe Harbor identifier categories
(45 CFR 164.514(b)(2)) from clinical text using a hybrid strategy:

- Deterministic regex detectors for structured identifiers (SSN, phone/fax,
  email, URL, IP, ZIP, dates, MRN, account/license/vehicle/device numbers).
  These are fast, reproducible, and carry a confidence of 1.0.
- GPT-4o (LLM) detection for identifiers that lack fixed structure (names,
  geographic subdivisions smaller than a state, biometric references, and any
  other unique identifying characteristic). These carry a model-supplied
  confidence score.

This module defines the core types, redaction tokens, and regex pattern
constants. Detection, merging, redaction application, reporting, and review
logic build on these in later steps.

The detection core is pure Python (no I/O) so it can be property-tested
without a database or network.

Implements the de-identification-service spec.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Identifier categories (18 HIPAA Safe Harbor categories + control flags)
# ---------------------------------------------------------------------------

class IdentifierCategory(str, Enum):
    """The Safe Harbor identifier categories the Deidentifier can detect.

    Values are used directly to build redaction tokens (e.g. ``NAME`` -> ``[NAME]``).
    """

    NAME = "NAME"              # Names
    GEO = "GEO"                # Geographic subdivision smaller than a state
    DATE = "DATE"              # Dates (except year) related to an individual
    AGE = "AGE"                # Ages over 89 -> "90+"
    PHONE = "PHONE"            # Telephone and fax numbers
    EMAIL = "EMAIL"            # Email addresses
    SSN = "SSN"                # Social Security numbers
    ZIP = "ZIP"                # ZIP / postal codes (geographic)
    MRN = "MRN"                # Medical record numbers
    HEALTH_PLAN = "HEALTH_PLAN"  # Health plan beneficiary numbers
    ACCOUNT = "ACCOUNT"        # Account numbers
    LICENSE = "LICENSE"        # Certificate / license numbers
    VEHICLE = "VEHICLE"        # Vehicle identifiers (VIN / plate)
    DEVICE = "DEVICE"          # Device identifiers and serial numbers
    URL = "URL"                # Web URLs
    IP = "IP"                  # IP addresses
    BIOMETRIC = "BIOMETRIC"    # Biometric identifiers
    PHOTO = "PHOTO"            # Full-face photos — flagged, not processable in text
    OTHER = "OTHER"            # Any other unique identifying number/characteristic/code


# Typed redaction token per category, e.g. IdentifierCategory.NAME -> "[NAME]"
REDACTION_TOKENS: dict[IdentifierCategory, str] = {
    category: f"[{category.value}]" for category in IdentifierCategory
}


# Detection method marker. "regex" for deterministic detectors, "llm" for GPT-4o.
DetectionMethod = str  # Literal["regex", "llm"]


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Redaction:
    """A single detected identifier occurrence.

    Attributes:
        category: The Safe Harbor category of the detected identifier.
        start: Inclusive character offset of the span in the source text.
        end: Exclusive character offset of the span in the source text.
        original_text: The exact source substring, i.e. ``text[start:end]``.
        token: The replacement token inserted in the output.
        method: Detection method — "regex" or "llm".
        confidence: Detector certainty in [0.0, 1.0]. Regex detections are 1.0.
        preserved_year: For DATE redactions, the four-digit year kept in output.
    """

    category: IdentifierCategory
    start: int
    end: int
    original_text: str
    token: str
    method: DetectionMethod
    confidence: float
    preserved_year: Optional[str] = None


@dataclass
class ReviewDecision:
    """A reviewer's action on a flagged (low-confidence) redaction.

    Attributes:
        redaction_index: Index into the result's redaction list.
        action: One of "approve", "reject", or "edit".
        replacement: Replacement text — required when ``action == "edit"``.
    """

    redaction_index: int
    action: str  # "approve" | "reject" | "edit"
    replacement: Optional[str] = None


@dataclass
class DeidentificationReport:
    """Structured summary of a de-identification operation.

    Attributes:
        method: Always "HIPAA Safe Harbor" for this engine.
        category_counts: Mapping of category value -> count of applied redactions.
        total_redactions: Total number of redactions applied to the output.
        low_confidence: Redactions with confidence below the review threshold.
    """

    method: str = "HIPAA Safe Harbor"
    category_counts: dict[str, int] = field(default_factory=dict)
    total_redactions: int = 0
    low_confidence: list[Redaction] = field(default_factory=list)


@dataclass
class DeidentificationResult:
    """Result of running the full de-identification pipeline on some text.

    Attributes:
        deidentified_text: The output text with identifiers replaced by tokens.
        redactions: The redactions applied to produce the output.
        report: The per-category report for the operation.
        status: "deidentified" (no review needed) or "needs_review".
    """

    deidentified_text: str
    redactions: list[Redaction]
    report: DeidentificationReport
    status: str  # "deidentified" | "needs_review"


# ---------------------------------------------------------------------------
# Regex pattern constants for structured identifiers
#
# Patterns are module-level so tests can import and exercise them directly.
# Each is compiled case-insensitively where relevant. Precedence and conflict
# resolution (e.g. SSN before generic digits, DATE before ZIP) are handled by
# the detection layer and span merging in later steps.
# ---------------------------------------------------------------------------

# Social Security number: 3-2-4 digits, optional separators (space or hyphen).
SSN_PATTERN = re.compile(
    r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"
)

# North American phone / fax number, optional country code, separators, and
# parenthesised area code.
PHONE_PATTERN = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# Email address.
EMAIL_PATTERN = re.compile(
    r"[^@\s]+@[^@\s]+\.[^@\s]+"
)

# URL with http(s):// or www. prefix.
URL_PATTERN = re.compile(
    r"\b(?:https?://|www\.)\S+",
    re.IGNORECASE,
)

# IPv4 address (octet range is validated in the detector, not the regex).
IP_PATTERN = re.compile(
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
)

# ZIP / ZIP+4 postal code.
ZIP_PATTERN = re.compile(
    r"\b\d{5}(?:-\d{4})?\b"
)

# Dates: numeric MM/DD/YYYY (and D-M-Y variants) plus ISO YYYY-MM-DD.
DATE_NUMERIC_PATTERN = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
)

# ISO date YYYY-MM-DD.
DATE_ISO_PATTERN = re.compile(
    r"\b\d{4}-\d{1,2}-\d{1,2}\b"
)

# Named-month dates, e.g. "January 15, 2023" or "15 Jan 2023".
DATE_NAMED_PATTERN = re.compile(
    r"\b(?:"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"
    r"|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r",?\s+\d{4}"
    r")\b",
    re.IGNORECASE,
)

# Age over 89: matches 90-199 followed by a year/age indicator.
AGE_OVER_89_PATTERN = re.compile(
    r"\b(9\d|1\d\d)\s*(?:years?(?:\s+old)?|yrs?|y/?o)\b",
    re.IGNORECASE,
)

# Medical record number. Default keyword-anchored pattern; configurable at
# the Deidentifier level for site-specific MRN formats.
DEFAULT_MRN_PATTERN = re.compile(
    r"\bMRN[:#]?\s*\w+\b",
    re.IGNORECASE,
)

# Account number (keyword-anchored alphanumeric).
ACCOUNT_PATTERN = re.compile(
    r"\b(?:acct|account)\s*(?:no\.?|number|#|:)?\s*\w+\b",
    re.IGNORECASE,
)

# Certificate / license number (keyword-anchored alphanumeric).
LICENSE_PATTERN = re.compile(
    r"\b(?:license|licence|cert(?:ificate)?)\s*(?:no\.?|number|#|:)?\s*\w+\b",
    re.IGNORECASE,
)

# Vehicle identifier: 17-char VIN, or keyword-anchored plate.
VEHICLE_PATTERN = re.compile(
    r"\b(?:[A-HJ-NPR-Z0-9]{17}"
    r"|(?:vin|plate|license\s*plate)\s*(?:no\.?|number|#|:)?\s*\w+)\b",
    re.IGNORECASE,
)

# Device identifier / serial number (keyword-anchored alphanumeric).
DEVICE_PATTERN = re.compile(
    r"\b(?:device|serial)\s*(?:no\.?|number|#|:)?\s*\w+\b",
    re.IGNORECASE,
)


# Maps each structured category to its compiled pattern. The MRN entry uses the
# module default; the Deidentifier may override it per instance.
STRUCTURED_PATTERNS: dict[IdentifierCategory, re.Pattern[str]] = {
    IdentifierCategory.SSN: SSN_PATTERN,
    IdentifierCategory.PHONE: PHONE_PATTERN,
    IdentifierCategory.EMAIL: EMAIL_PATTERN,
    IdentifierCategory.URL: URL_PATTERN,
    IdentifierCategory.IP: IP_PATTERN,
    IdentifierCategory.ZIP: ZIP_PATTERN,
    IdentifierCategory.MRN: DEFAULT_MRN_PATTERN,
    IdentifierCategory.ACCOUNT: ACCOUNT_PATTERN,
    IdentifierCategory.LICENSE: LICENSE_PATTERN,
    IdentifierCategory.VEHICLE: VEHICLE_PATTERN,
    IdentifierCategory.DEVICE: DEVICE_PATTERN,
}


# ---------------------------------------------------------------------------
# Detection precedence
#
# When two structured detectors match overlapping spans (e.g. a ZIP pattern
# matching a fragment of a date, or a generic digit run overlapping an SSN),
# the higher-precedence category wins. Precedence is enforced by
# ``_resolve_precedence`` below. The ordering places specific, delimiter-rich
# identifiers (EMAIL, URL) and structurally distinctive ones (SSN, DATE) ahead
# of the greedy 5-digit ZIP matcher, satisfying:
#   - SSN before generic digit runs
#   - DATE before ZIP
# ---------------------------------------------------------------------------

_STRUCTURED_PRECEDENCE: tuple[IdentifierCategory, ...] = (
    IdentifierCategory.EMAIL,
    IdentifierCategory.URL,
    IdentifierCategory.SSN,
    IdentifierCategory.DATE,
    IdentifierCategory.IP,
    IdentifierCategory.PHONE,
    IdentifierCategory.MRN,
    IdentifierCategory.ACCOUNT,
    IdentifierCategory.LICENSE,
    IdentifierCategory.VEHICLE,
    IdentifierCategory.DEVICE,
    IdentifierCategory.ZIP,
)

_PRECEDENCE_RANK: dict[IdentifierCategory, int] = {
    category: index for index, category in enumerate(_STRUCTURED_PRECEDENCE)
}

# Matches a four-digit year (19xx / 20xx) inside a date string for preservation.
_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


def _make_redaction(
    category: IdentifierCategory,
    start: int,
    end: int,
    text: str,
    preserved_year: Optional[str] = None,
) -> Redaction:
    """Build a regex Redaction whose ``original_text`` equals ``text[start:end]``.

    All regex detections carry ``method="regex"`` and ``confidence=1.0`` per
    Requirements 1.9 and 3.5.
    """

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


def _detect_with_pattern(
    text: str,
    category: IdentifierCategory,
    pattern: re.Pattern[str],
) -> list[Redaction]:
    """Generic detector: emit a Redaction for every match of ``pattern``."""

    return [
        _make_redaction(category, m.start(), m.end(), text)
        for m in pattern.finditer(text)
    ]


# --- per-category detector functions ---------------------------------------

def detect_ssn(text: str) -> list[Redaction]:
    """Detect Social Security numbers (Req 1.1).

    Rejects spans whose numeric groups are entirely zero (invalid SSNs).
    """

    out: list[Redaction] = []
    for m in SSN_PATTERN.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) != 9:
            continue
        area, group, serial = digits[:3], digits[3:5], digits[5:]
        if area == "000" or group == "00" or serial == "0000":
            continue
        out.append(_make_redaction(IdentifierCategory.SSN, m.start(), m.end(), text))
    return out


def detect_phone(text: str) -> list[Redaction]:
    """Detect North American phone / fax numbers (Req 1.2)."""

    return _detect_with_pattern(text, IdentifierCategory.PHONE, PHONE_PATTERN)


def detect_email(text: str) -> list[Redaction]:
    """Detect email addresses (Req 1.3)."""

    return _detect_with_pattern(text, IdentifierCategory.EMAIL, EMAIL_PATTERN)


def detect_url(text: str) -> list[Redaction]:
    """Detect URLs (Req 1.4)."""

    return _detect_with_pattern(text, IdentifierCategory.URL, URL_PATTERN)


def detect_ip(text: str) -> list[Redaction]:
    """Detect IPv4 addresses (Req 1.5).

    Each dotted octet must be in the range 0-255 to qualify.
    """

    out: list[Redaction] = []
    for m in IP_PATTERN.finditer(text):
        octets = m.group().split(".")
        if len(octets) == 4 and all(o.isdigit() and int(o) <= 255 for o in octets):
            out.append(_make_redaction(IdentifierCategory.IP, m.start(), m.end(), text))
    return out


def detect_zip(text: str) -> list[Redaction]:
    """Detect 5-digit and ZIP+4 postal codes (Req 1.6)."""

    return _detect_with_pattern(text, IdentifierCategory.ZIP, ZIP_PATTERN)


def detect_mrn(text: str, pattern: Optional[re.Pattern[str]] = None) -> list[Redaction]:
    """Detect medical record numbers (Req 1.7).

    Uses the module default MRN pattern unless a site-specific ``pattern`` is
    supplied (see ``Deidentifier.__init__``).
    """

    return _detect_with_pattern(
        text, IdentifierCategory.MRN, pattern or DEFAULT_MRN_PATTERN
    )


def detect_account(text: str) -> list[Redaction]:
    """Detect account numbers (Req 1.8)."""

    return _detect_with_pattern(text, IdentifierCategory.ACCOUNT, ACCOUNT_PATTERN)


def detect_license(text: str) -> list[Redaction]:
    """Detect certificate / license numbers (Req 1.8)."""

    return _detect_with_pattern(text, IdentifierCategory.LICENSE, LICENSE_PATTERN)


def detect_vehicle(text: str) -> list[Redaction]:
    """Detect vehicle identifiers — VIN / plate (Req 1.8)."""

    return _detect_with_pattern(text, IdentifierCategory.VEHICLE, VEHICLE_PATTERN)


def detect_device(text: str) -> list[Redaction]:
    """Detect device identifiers / serial numbers (Req 1.8)."""

    return _detect_with_pattern(text, IdentifierCategory.DEVICE, DEVICE_PATTERN)


def detect_dates(text: str) -> list[Redaction]:
    """Detect dates that include a month and a day (Req 2.1).

    Runs the ISO, numeric, and named-month patterns. When a four-digit year is
    present it is captured in ``preserved_year`` so downstream redaction can
    keep the year while removing the month and day. Date detection is included
    here so it takes precedence over the greedy ZIP matcher.
    """

    out: list[Redaction] = []
    for pattern in (DATE_ISO_PATTERN, DATE_NUMERIC_PATTERN, DATE_NAMED_PATTERN):
        for m in pattern.finditer(text):
            year_match = _YEAR_PATTERN.search(m.group())
            preserved_year = year_match.group() if year_match else None
            out.append(
                _make_redaction(
                    IdentifierCategory.DATE, m.start(), m.end(), text, preserved_year
                )
            )
    return out


def _resolve_precedence(candidates: list[Redaction]) -> list[Redaction]:
    """Reduce overlapping candidate spans to a non-overlapping set.

    Candidates are ranked by earliest start, then longest span, then category
    precedence. A candidate is kept only if it does not overlap an already
    accepted (higher-priority) span. This enforces SSN-over-generic-digits and
    DATE-over-ZIP precedence. Non-overlapping spans of different categories are
    all retained.
    """

    ranked = sorted(
        candidates,
        key=lambda r: (
            r.start,
            -(r.end - r.start),
            _PRECEDENCE_RANK.get(r.category, len(_PRECEDENCE_RANK)),
        ),
    )
    accepted: list[Redaction] = []
    for candidate in ranked:
        overlaps = any(
            not (candidate.end <= a.start or candidate.start >= a.end)
            for a in accepted
        )
        if not overlaps:
            accepted.append(candidate)
    accepted.sort(key=lambda r: r.start)
    return accepted


# ---------------------------------------------------------------------------
# Span merging helpers
# ---------------------------------------------------------------------------

_MAX_RANK = len(_PRECEDENCE_RANK)


def _merge_redaction_group(group: list[Redaction]) -> Redaction:
    """Collapse a cluster of mutually overlapping Redactions into one.

    The returned Redaction covers ``[min(start), max(end))`` — the contiguous
    union of the group's covered characters.

    Category selection prefers the **deterministic regex detection**: when the
    group contains any regex-detected span, the merged redaction takes its
    category, token, method, and confidence. Regex detectors identify the 18
    structured Safe Harbor categories by fixed patterns, so their label is
    authoritative over an overlapping LLM guess (e.g. an SSN the model tagged as
    OTHER stays ``[SSN]``). Only when no regex span is present does the LLM's
    category win. Within the chosen pool the widest span wins, ties broken by
    detection precedence.

    ``original_text`` is reconstructed by laying each contributor's text at its
    offset within the union (overlaps agree because they share the same source).
    A preserved year is carried over when the chosen category is DATE and any
    contributor preserved one.
    """

    start = min(r.start for r in group)
    end = max(r.end for r in group)

    # Prefer regex detections; fall back to the whole group (LLM-only spans).
    regex_spans = [r for r in group if r.method == "regex"]
    pool = regex_spans if regex_spans else group

    # Widest span first; break ties by highest precedence (lowest rank).
    chosen = max(
        pool,
        key=lambda r: (
            r.end - r.start,
            -_PRECEDENCE_RANK.get(r.category, _MAX_RANK),
        ),
    )

    # Reconstruct the covered text from the contributing spans.
    chars = [""] * (end - start)
    for r in group:
        for offset, ch in enumerate(r.original_text):
            pos = r.start - start + offset
            if 0 <= pos < len(chars):
                chars[pos] = ch
    original_text = "".join(chars)

    preserved_year: Optional[str] = None
    if chosen.category == IdentifierCategory.DATE:
        for r in group:
            if r.category == IdentifierCategory.DATE and r.preserved_year:
                preserved_year = r.preserved_year
                break

    return Redaction(
        category=chosen.category,
        start=start,
        end=end,
        original_text=original_text,
        token=REDACTION_TOKENS[chosen.category],
        method=chosen.method,
        # Carry the chosen detection's confidence: a regex win restores the
        # certain 1.0 so a structured identifier is not dragged into review by
        # an overlapping low-confidence LLM span.
        confidence=chosen.confidence,
        preserved_year=preserved_year,
    )


# ---------------------------------------------------------------------------
# Contextual (LLM / GPT-4o) detection
#
# The LLM detects identifiers that lack a fixed structure: names, geographic
# subdivisions smaller than a state, biometric references, full-face photo
# references, and any other unique identifying characteristic. Its returned
# categories are restricted to the set below; anything else is coerced to
# OTHER so a detected identifier is never silently dropped on a bad label.
# ---------------------------------------------------------------------------

# Categories GPT-4o is allowed to return (Req 3.1, 3.3).
_LLM_ALLOWED_CATEGORIES: frozenset[IdentifierCategory] = frozenset(
    {
        IdentifierCategory.NAME,
        IdentifierCategory.GEO,
        IdentifierCategory.BIOMETRIC,
        IdentifierCategory.PHOTO,
        IdentifierCategory.OTHER,
    }
)

# Confidence assigned when the model omits or malforms the score. Chosen below
# the default review threshold (0.85) so an unscored contextual hit is surfaced
# for human review rather than silently trusted.
_DEFAULT_LLM_CONFIDENCE = 0.5

# Instruction for GPT-4o. Requests strict JSON so the response can be parsed
# deterministically; categories are restricted to the contextual set.
CONTEXTUAL_SYSTEM_PROMPT = (
    "You are a HIPAA Safe Harbor de-identification assistant. Identify protected "
    "health information in the clinical text that lacks a fixed structure:\n"
    "- NAME: names of patients, relatives, providers, or employers.\n"
    "- GEO: geographic subdivisions smaller than a state (street address, city, "
    "county, precinct).\n"
    "- BIOMETRIC: biometric identifiers (finger or voice prints, retinal scans).\n"
    "- PHOTO: references to full-face photographs or comparable images.\n"
    "- OTHER: any other unique identifying characteristic or code.\n\n"
    "Return ONLY strict JSON: a list of objects, each with these keys:\n"
    '  "category": one of NAME, GEO, BIOMETRIC, PHOTO, OTHER\n'
    '  "text": the exact substring copied from the input\n'
    '  "start": integer character offset where the substring begins\n'
    '  "end": integer character offset where the substring ends (exclusive)\n'
    '  "confidence": a number between 0.0 and 1.0\n\n'
    "Do not include Markdown, commentary, or any text outside the JSON array."
)


def _strip_code_fences(content: str) -> str:
    """Remove a leading ```/```json fence and its trailing fence, if present."""

    cleaned = content.strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.split("\n")
    # Drop the opening fence line (e.g. "```" or "```json").
    lines = lines[1:]
    # Drop the closing fence line if present.
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_llm_response(content: Any) -> list[dict]:
    """Defensively parse the model response into a list of entry dicts.

    Handles JSON wrapped in Markdown fences, a bare JSON array, or a JSON object
    that nests the array under a common key. Returns an empty list if nothing
    parseable is found (Error Handling: malformed JSON — discard unparseable,
    keep valid).
    """

    if not isinstance(content, str) or not content.strip():
        return []
    cleaned = _strip_code_fences(content)
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return []

    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    if isinstance(data, dict):
        for key in ("spans", "identifiers", "results", "entries", "redactions"):
            value = data.get(key)
            if isinstance(value, list):
                return [entry for entry in value if isinstance(entry, dict)]
        # A single entry object.
        return [data]
    return []


def _coerce_llm_category(raw: Any) -> IdentifierCategory:
    """Map a model-supplied category label to an allowed contextual category.

    Unknown or out-of-set labels fall back to OTHER so a detected span is never
    dropped merely because of an unexpected label (Req 3.1, 3.3).
    """

    if isinstance(raw, str):
        try:
            category = IdentifierCategory(raw.strip().upper())
        except ValueError:
            return IdentifierCategory.OTHER
        if category in _LLM_ALLOWED_CATEGORIES:
            return category
    return IdentifierCategory.OTHER


def _coerce_llm_confidence(raw: Any) -> float:
    """Coerce a model-supplied confidence to a float clamped to [0.0, 1.0].

    Missing or non-numeric values fall back to ``_DEFAULT_LLM_CONFIDENCE``.
    """

    if isinstance(raw, bool):  # bool is an int subclass; reject it explicitly.
        return _DEFAULT_LLM_CONFIDENCE
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_LLM_CONFIDENCE
    if value != value:  # NaN guard.
        return _DEFAULT_LLM_CONFIDENCE
    return max(0.0, min(1.0, value))


def _verify_or_relocate(
    text: str, returned_text: str, start: Any, end: Any
) -> tuple[Optional[int], Optional[int]]:
    """Validate model offsets against the source, re-locating if they disagree.

    If ``text[start:end]`` equals the returned substring, the offsets are used
    as-is. Otherwise the returned substring is located with ``str.find``; spans
    that cannot be located are discarded (return ``(None, None)``) per the
    Error Handling table.
    """

    if (
        isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and 0 <= start < end <= len(text)
        and text[start:end] == returned_text
    ):
        return start, end

    index = text.find(returned_text)
    if index == -1:
        return None, None
    return index, index + len(returned_text)


# ---------------------------------------------------------------------------
# Deidentifier orchestrator
# ---------------------------------------------------------------------------

class Deidentifier:
    """HIPAA Safe Harbor de-identification engine.

    This step implements the deterministic structured (regex) detection layer.
    Contextual (LLM) detection, span merging, redaction application, reporting,
    and review are added in later steps.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        review_threshold: float = 0.85,
        mrn_pattern: Optional[str] = None,
        openai_client: Optional[Any] = None,
    ) -> None:
        self.openai_api_key = openai_api_key
        self.review_threshold = review_threshold
        self._mrn_pattern: re.Pattern[str] = (
            re.compile(mrn_pattern, re.IGNORECASE) if mrn_pattern else DEFAULT_MRN_PATTERN
        )
        # Dependency-injected OpenAI client. When provided (e.g. a fake in
        # tests), contextual detection runs offline with no network access.
        self._openai_client = openai_client

    def _get_openai_client(self) -> Optional[Any]:
        """Return the OpenAI client to use, or ``None`` when unavailable.

        Prefers the injected client. Otherwise a real ``OpenAI`` client is
        constructed from ``openai_api_key``; if no key is configured, contextual
        detection is skipped (regex-only) rather than failing.
        """

        if self._openai_client is not None:
            return self._openai_client
        if not self.openai_api_key:
            return None
        try:
            from openai import OpenAI

            return OpenAI(api_key=self.openai_api_key)
        except Exception as exc:  # pragma: no cover - import/config failure
            logger.error("Failed to construct OpenAI client: %s", exc)
            return None

    def detect_structured(self, text: str) -> list[Redaction]:
        """Run all regex detectors and resolve precedence.

        Returns a list of non-overlapping Redactions, each with
        ``method="regex"``, ``confidence=1.0``, and
        ``text[start:end] == original_text``. Precedence ensures SSNs win over
        generic digit runs and dates win over ZIP codes (Req 1.1-1.9, 3.5).
        """

        candidates: list[Redaction] = []
        candidates += detect_ssn(text)
        candidates += detect_dates(text)
        candidates += detect_email(text)
        candidates += detect_url(text)
        candidates += detect_ip(text)
        candidates += detect_phone(text)
        candidates += detect_mrn(text, self._mrn_pattern)
        candidates += detect_account(text)
        candidates += detect_license(text)
        candidates += detect_vehicle(text)
        candidates += detect_device(text)
        candidates += detect_zip(text)
        return _resolve_precedence(candidates)

    def detect_contextual(
        self, text: str, client: Optional[Any] = None
    ) -> list[Redaction]:
        """Detect contextual identifiers with GPT-4o (Req 3.1-3.4).

        Sends ``text`` to GPT-4o (model ``gpt-4o``) with a prompt instructing
        detection of names, geographic subdivisions smaller than a state,
        biometric identifiers, full-face photo references, and any other unique
        identifying characteristic. The model is asked for strict JSON: a list
        of ``{category, text, start, end, confidence}`` objects.

        For every returned span the offsets are verified against the source
        (``text[start:end] == text``); a mismatch triggers re-location via
        ``str.find`` and spans that cannot be located are discarded. Full-face
        photograph references surface as a ``PHOTO`` flag (Req 3.3). Each
        returned Redaction carries ``method="llm"`` and the model-supplied
        confidence clamped to ``[0.0, 1.0]``.

        This method fails gracefully: on any API error, missing client, or
        malformed JSON it logs and returns whatever valid spans it could parse
        (possibly ``[]``) without raising, so upstream regex redactions are
        retained and the job can be marked ``needs_review`` (Req 3.4).

        Args:
            text: The source text to scan.
            client: Optional per-call OpenAI client override (dependency
                injection). Falls back to the injected/constructed client.

        Returns:
            A list of ``method="llm"`` Redactions (never raises).
        """

        if not text:
            return []

        active_client = client if client is not None else self._get_openai_client()
        if active_client is None:
            logger.warning(
                "No OpenAI client available; skipping contextual detection "
                "(regex redactions retained, job needs review)."
            )
            return []

        try:
            response = active_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": CONTEXTUAL_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0,
            )
            content = response.choices[0].message.content
        except Exception as exc:
            # Req 3.4: log the error and keep going. Regex redactions are
            # retained upstream; the job is marked needs_review.
            logger.error("GPT-4o contextual detection failed: %s", exc)
            return []

        redactions: list[Redaction] = []
        for entry in _parse_llm_response(content):
            redaction = self._build_llm_redaction(text, entry)
            if redaction is not None:
                redactions.append(redaction)
        return redactions

    @staticmethod
    def _build_llm_redaction(text: str, entry: dict) -> Optional[Redaction]:
        """Build one LLM Redaction from a parsed entry, or ``None`` to discard.

        Discards entries without a usable ``text`` field and entries whose
        substring cannot be located in the source. The resulting Redaction
        satisfies the metadata invariant: ``text[start:end] == original_text``,
        ``method == "llm"``, and ``0.0 <= confidence <= 1.0`` (Req 3.2).
        """

        if not isinstance(entry, dict):
            return None

        returned_text = entry.get("text")
        if not isinstance(returned_text, str) or not returned_text:
            return None

        start, end = _verify_or_relocate(
            text, returned_text, entry.get("start"), entry.get("end")
        )
        if start is None or end is None:
            return None

        category = _coerce_llm_category(entry.get("category"))
        confidence = _coerce_llm_confidence(entry.get("confidence"))

        return Redaction(
            category=category,
            start=start,
            end=end,
            original_text=text[start:end],
            token=REDACTION_TOKENS[category],
            method="llm",
            confidence=confidence,
        )

    @staticmethod
    def cap_age(age: int) -> str:
        """Cap ages over 89 to the Safe Harbor value ``"90+"`` (Req 2.3, 2.4).

        HIPAA Safe Harbor requires that ages over 89 be aggregated into a single
        ``90+`` category, while ages of 89 or below are retained unchanged.

        Args:
            age: The age in years to evaluate.

        Returns:
            ``"90+"`` when ``age > 89``; otherwise the unchanged decimal string
            of ``age`` (i.e. ``str(age)``).
        """

        return "90+" if age > 89 else str(age)

    @staticmethod
    def merge_spans(spans: list[Redaction]) -> list[Redaction]:
        """Merge overlapping Redactions into disjoint spans (Req 4.2).

        Overlapping spans are combined into a single Redaction covering the
        union of their character ranges. The result is a list of pairwise
        non-overlapping Redactions, sorted by start offset, whose covered
        character set equals the union of the inputs' covered characters.

        Adjacent-but-not-overlapping spans (``a.end == b.start``) are left as
        separate redactions: they neither overlap nor lose any covered
        character, so the union invariant still holds.

        Args:
            spans: Arbitrary, possibly overlapping Redactions.

        Returns:
            A start-ordered list of pairwise non-overlapping Redactions.
        """

        if not spans:
            return []

        ordered = sorted(spans, key=lambda r: (r.start, r.end))
        groups: list[list[Redaction]] = [[ordered[0]]]
        current_end = ordered[0].end

        for redaction in ordered[1:]:
            if redaction.start < current_end:
                # Overlaps the running cluster — extend it.
                groups[-1].append(redaction)
                current_end = max(current_end, redaction.end)
            else:
                # Disjoint from the cluster — start a new one.
                groups.append([redaction])
                current_end = redaction.end

        return [_merge_redaction_group(group) for group in groups]

    @staticmethod
    def _effective_token(redaction: Redaction) -> str:
        """Return the token actually inserted for a redaction.

        DATE redactions with a preserved year emit a year-retaining token
        (e.g. ``[DATE-2023]``) so the year survives while month and day are
        removed (Req 4.5). All other redactions use their typed token.
        """

        if (
            redaction.category == IdentifierCategory.DATE
            and redaction.preserved_year
        ):
            return f"[DATE-{redaction.preserved_year}]"
        return redaction.token

    @staticmethod
    def apply_redactions(text: str, spans: list[Redaction]) -> str:
        """Replace each detected span with its typed redaction token (Req 4.1-4.5).

        Spans are applied in descending start-offset order so that rewriting one
        span never invalidates the offsets of the spans still to be applied
        (Req 4.3). DATE spans that preserve a year emit a year-retaining token
        (Req 4.5). The output contains no original identifier text from any
        applied redaction, except a year intentionally preserved by a DATE
        redaction (Req 4.4).

        Spans are expected to be non-overlapping (see ``merge_spans``). As a
        safeguard, a span that overlaps a region already rewritten to its right
        is skipped so partial/duplicate replacement cannot corrupt the output.

        Args:
            text: The source text.
            spans: Redactions to apply (ideally already merged/disjoint).

        Returns:
            The de-identified text.
        """

        result = text
        # Leftmost start offset of the region already rewritten to the right.
        boundary = len(text)

        for redaction in sorted(spans, key=lambda r: r.start, reverse=True):
            start, end = redaction.start, redaction.end
            if start < 0 or end > len(text) or start >= end:
                continue
            if end > boundary:
                # Overlaps an already-applied span; skip to preserve offsets.
                continue
            token = Deidentifier._effective_token(redaction)
            result = result[:start] + token + result[end:]
            boundary = start

        return result

    @staticmethod
    def build_report(
        spans: list[Redaction], threshold: float
    ) -> DeidentificationReport:
        """Summarise applied redactions into a DeidentificationReport.

        Produces the per-category counts, the total, and the low-confidence
        list for a completed de-identification operation (Req 5.1-5.5).

        Counts are keyed by the category's string value (e.g. ``"NAME"``) so the
        report serialises cleanly to JSON. The per-category counts sum to
        ``total_redactions``, which equals the number of redactions supplied
        (i.e. the redactions actually applied to the output) — the invariant of
        Property 8 (Req 5.1, 5.2, 5.4).

        A redaction is placed in ``low_confidence`` if and only if its
        confidence is *strictly* below ``threshold`` (Req 5.3, Property 9). The
        report method is always ``"HIPAA Safe Harbor"`` (Req 5.5).

        Args:
            spans: The redactions applied to the output text.
            threshold: The review threshold; redactions below it are flagged.

        Returns:
            A populated DeidentificationReport.
        """

        category_counts: dict[str, int] = {}
        low_confidence: list[Redaction] = []

        for redaction in spans:
            key = redaction.category.value
            category_counts[key] = category_counts.get(key, 0) + 1
            if redaction.confidence < threshold:
                low_confidence.append(redaction)

        return DeidentificationReport(
            method="HIPAA Safe Harbor",
            category_counts=category_counts,
            total_redactions=len(spans),
            low_confidence=low_confidence,
        )

    def deidentify(self, text: str) -> DeidentificationResult:
        """Run the full de-identification pipeline on ``text`` (Req 5, 6.1, 6.7).

        Pipeline:
        1. ``detect_structured`` — deterministic regex detectors (confidence 1.0).
        2. ``detect_contextual`` — GPT-4o contextual detection (fails gracefully
           to ``[]``, so regex redactions are always retained; Req 3.4).
        3. ``merge_spans`` — combine overlapping detections into disjoint spans.
        4. ``apply_redactions`` — produce the de-identified text.
        5. ``build_report`` — per-category counts, total, and low-confidence list.

        Status is ``"needs_review"`` when the report contains at least one
        low-confidence redaction and ``"deidentified"`` otherwise (Req 6.1, 6.7,
        Property 10).

        Args:
            text: The source clinical text to de-identify.

        Returns:
            A DeidentificationResult with the output text, the applied
            redactions, the report, and the derived status.
        """

        structured = self.detect_structured(text)
        contextual = self.detect_contextual(text)
        merged = self.merge_spans(structured + contextual)

        deidentified_text = self.apply_redactions(text, merged)
        report = self.build_report(merged, self.review_threshold)
        status = "needs_review" if report.low_confidence else "deidentified"

        return DeidentificationResult(
            deidentified_text=deidentified_text,
            redactions=merged,
            report=report,
            status=status,
        )

    # -----------------------------------------------------------------------
    # Human-in-the-loop review (Req 6.2-6.6)
    # -----------------------------------------------------------------------

    # Valid reviewer actions on a flagged redaction.
    _REVIEW_ACTIONS: frozenset[str] = frozenset({"approve", "reject", "edit"})

    @staticmethod
    def _low_confidence_indices(result: DeidentificationResult) -> set[int]:
        """Return the indices of ``result.redactions`` flagged for review.

        A redaction is low-confidence when it appears in the report's
        ``low_confidence`` list. Membership is resolved by object identity so a
        redaction that merely *equals* a flagged one (same field values) is not
        misclassified.
        """

        flagged_ids = {id(r) for r in result.report.low_confidence}
        return {
            index
            for index, redaction in enumerate(result.redactions)
            if id(redaction) in flagged_ids
        }

    def _decision_map(
        self,
        result: DeidentificationResult,
        decisions: list[ReviewDecision],
    ) -> dict[int, ReviewDecision]:
        """Validate ``decisions`` and index them by ``redaction_index``.

        Raises:
            ValueError: if a decision targets an out-of-range redaction, uses an
                unknown action, or is an ``"edit"`` without replacement text
                (Error Handling: edit missing replacement -> validation error).
        """

        mapping: dict[int, ReviewDecision] = {}
        for decision in decisions:
            index = decision.redaction_index
            if not (0 <= index < len(result.redactions)):
                raise ValueError(
                    f"Review decision references out-of-range redaction index {index}"
                )
            if decision.action not in self._REVIEW_ACTIONS:
                raise ValueError(
                    f"Unknown review action {decision.action!r}; "
                    f"expected one of {sorted(self._REVIEW_ACTIONS)}"
                )
            if decision.action == "edit" and (
                decision.replacement is None or decision.replacement == ""
            ):
                raise ValueError(
                    "Review action 'edit' requires a non-empty replacement text"
                )
            mapping[index] = decision
        return mapping

    def apply_review(
        self,
        result: DeidentificationResult,
        decisions: list[ReviewDecision],
    ) -> DeidentificationResult:
        """Recompute the output text honouring each reviewer decision (Req 6.2-6.4).

        Each decision targets a redaction by its index into
        ``result.redactions`` and yields the text placed at that span:

        - ``approve``  -> keep the redaction's token (Req 6.2).
        - ``reject``   -> restore the ``original_text`` at that span (Req 6.3).
        - ``edit``     -> insert the reviewer-supplied ``replacement`` (Req 6.4);
          a missing/empty replacement is a validation error.

        Redactions without a decision keep their token.

        The output is rebuilt directly from ``result.deidentified_text`` by
        walking its clear segments (whose lengths equal the original clear
        segments) and substituting each redaction's token with the reviewed
        text. This needs no separate copy of the source and is robust even when
        clear text happens to contain token-like substrings.

        The returned result's status reflects the finalization gate: it is
        ``"deidentified"`` when every flagged redaction has a decision and
        ``"needs_review"`` otherwise (Req 6.5, 6.6).

        Args:
            result: The de-identification result to review.
            decisions: The reviewer decisions to apply.

        Returns:
            A new DeidentificationResult with the recomputed text and status.

        Raises:
            ValueError: for an out-of-range index, unknown action, or an
                ``"edit"`` decision missing its replacement text.
        """

        decision_map = self._decision_map(result, decisions)

        deid = result.deidentified_text
        redactions = result.redactions
        # Redactions were applied left-to-right in start order and are disjoint,
        # so walking by exact segment lengths reconstructs the layout precisely.
        order = sorted(range(len(redactions)), key=lambda i: redactions[i].start)

        parts: list[str] = []
        cursor = 0          # position within the de-identified text
        prev_end = 0        # position within the original-text coordinate space

        for index in order:
            redaction = redactions[index]
            token = self._effective_token(redaction)

            # Clear text before this redaction (unchanged, so same length here).
            clear_len = redaction.start - prev_end
            parts.append(deid[cursor : cursor + clear_len])
            cursor += clear_len

            # Skip over the token that currently occupies this span.
            cursor += len(token)

            parts.append(self._reviewed_text(redaction, decision_map.get(index)))
            prev_end = redaction.end

        # Trailing clear text after the last redaction.
        parts.append(deid[cursor:])
        reviewed_text = "".join(parts)

        status = (
            "deidentified"
            if self.can_finalize(result, decisions)
            else "needs_review"
        )

        return DeidentificationResult(
            deidentified_text=reviewed_text,
            redactions=result.redactions,
            report=result.report,
            status=status,
        )

    def _reviewed_text(
        self,
        redaction: Redaction,
        decision: Optional[ReviewDecision],
    ) -> str:
        """Return the text to place at a span given its (optional) decision.

        No decision or ``approve`` keeps the token; ``reject`` restores the
        original text; ``edit`` uses the reviewer replacement (Req 6.2-6.4).
        """

        if decision is None or decision.action == "approve":
            return self._effective_token(redaction)
        if decision.action == "reject":
            return redaction.original_text
        # action == "edit"; replacement validated non-empty in _decision_map.
        return decision.replacement or ""

    def can_finalize(
        self,
        result: DeidentificationResult,
        decisions: list[ReviewDecision],
    ) -> bool:
        """Return whether the job may be finalized (Req 6.5, 6.6).

        Finalization is permitted if and only if every low-confidence redaction
        has an associated review decision. Jobs with no flagged redactions are
        always finalizable.
        """

        decided = {decision.redaction_index for decision in decisions}
        flagged = self._low_confidence_indices(result)
        return flagged.issubset(decided)

    def finalize(
        self,
        result: DeidentificationResult,
        decisions: list[ReviewDecision],
    ) -> DeidentificationResult:
        """Attempt to finalize a reviewed job (Req 6.5, 6.6).

        Applies the review decisions and gates the status: finalization succeeds
        and the status becomes ``"deidentified"`` only when every low-confidence
        redaction has a decision; otherwise finalization is rejected and the
        status remains ``"needs_review"``.

        Args:
            result: The de-identification result to finalize.
            decisions: The reviewer decisions collected for the job.

        Returns:
            A new DeidentificationResult with the reviewed text and gated status.

        Raises:
            ValueError: for invalid decisions (see ``apply_review``).
        """

        return self.apply_review(result, decisions)
