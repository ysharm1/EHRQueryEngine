# QueryAble — Product Vision

> Positioned to win where current tools stop short, and to work across institutions.

## The core gap others leave open

Most HIPAA-compliant anonymization tools (John Snow Labs, AWS Comprehend Medical,
Azure Health, Presidio, Philter, etc.) focus on one piece: detecting and removing
the 18 Safe Harbor identifiers from clinical text, often with strong F1 scores on
benchmarks.

They generally do **not** deliver:

- Natural-language access that turns a research question into a precise cohort
- Explicit, measurable residual re-identification risk (beyond checklist compliance)
- Quantified utility loss for downstream research or AI/ML training
- Full provenance + audit artifacts that compliance offices and IRBs actually accept
- A private/controlled deployment model that keeps patient-level data inside the institution
- A clean path from raw heterogeneous EHR data to analysis-ready or AI-training-ready
  output in one governed pipeline

Safe Harbor is a blunt checklist. Expert Determination (the higher-utility,
risk-based path) remains expensive, manual, and rare. Institutions therefore either
over-redact (destroying research value) or under-document residual risk (creating
liability). Mid-to-large research groups and AI teams sit on valuable data they
cannot safely unlock at scale.

## QueryAble's differentiated vision

QueryAble is the **institutional layer that turns raw clinical data into trustworthy,
usable research and AI-ready datasets.**

A researcher or data scientist asks a plain-English question. The system:

1. **Parses intent and retrieves the matching cohort** across structured fields and
   notes (schema-aware, with precision/recall guarantees).
2. **Applies de-identification that is residual-risk-aware** (not just Safe Harbor checklist).
3. **Measures and reports the privacy–utility trade-off** for that specific output.
4. **Produces a structured, fully provenance-tracked, audit-logged dataset** ready
   for analysis or model training.
5. **Generates the compliance documentation** (what was transformed, residual risk
   characterization, lineage) that institutions require before release or secondary use.

### Key design principles that address what others miss

- **Privacy-utility as a first-class, measurable product feature** — residual risk
  metrics + utility scores (information retention, downstream task performance) for
  every export. Configurable policies so institutions can choose the trade-off
  appropriate to the use case.
- **Path to Expert Determination support** — not just Safe Harbor. Produce the
  statistical evidence and audit trail a qualified expert needs, lowering the cost
  and friction of higher-utility de-identification.
- **Data never has to leave for the hard parts** — private/VPC/air-gapped deployment
  first. Query parsing can operate on schema metadata only where possible;
  patient-level data stays inside institutional boundaries.
- **End-to-end research/AI data readiness** — structured output + preserved clinical
  signal + full lineage, optimized for both traditional analysis and native model training.
- **Institutional adoption mechanics** — automatic generation of audit, provenance,
  and residual-risk artifacts that satisfy compliance, IRB, and data governance
  offices. This is the practical barrier that kills most tools.

## Who it is for (and how it succeeds across institutions)

Primary buyers are **research institutions, academic medical centers, and health
systems** that already have EHR data and need a governed way to produce research-grade
or AI-training-grade extracts without building the stack themselves. Secondary:
**AI/ML teams and data platforms** that require high-utility, residual-risk-characterized
clinical text.

### Success path

1. **SBIR Phase I validation (current aims)** — prove residual risk + utility
   characterization on real heterogeneous clinical text, query/cohort reliability
   across schemas and note styles, and the exact audit/compliance requirements
   institutions demand. This evidence is the ticket to serious institutional conversations.
2. **Private / controlled deployments** — higher ACV, lower trust friction than pure
   multi-tenant SaaS. Sell the pipeline + compliance packaging.
3. **Optional data participation models later** — once residual-risk documentation is
   trusted, institutions can more safely license or share the resulting datasets;
   QueryAble can participate via revenue share or joint products where appropriate.
4. **Vertical depth where we have access** (transplant, neuro, etc.) to create early
   reference customers and higher-value data products.

## Why this maximizes chances of success

- It attacks the real institutional bottleneck (safe unlock of existing data) rather
  than competing only on PHI detection F1.
- It turns the hardest remaining scientific problems (residual risk quantification and
  utility trade-offs) into the product's core differentiation.
- It aligns with how serious buyers actually buy: private control, auditability, and
  defensible residual-risk documentation first; convenience second.
- It creates a natural bridge from grant-funded validation to commercial private
  deployments and, later, higher-value data participation.

This is no longer "a faster de-identification tool for mid-size research groups." It
is the **governed pipeline that lets institutions safely turn their clinical data into
research and AI assets** — with the measurements and artifacts that current tools leave
missing. That is the version that can travel across institutions.
