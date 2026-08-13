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

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
