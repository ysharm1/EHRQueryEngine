# QueryAble — Direction & SBIR Framing

> Working reference for product direction, market, and grant framing (NLM/NIH SBIR).
> Companion to VISION.md.

## One-line description
QueryAble is an automated "honest broker" for clinical research data: it de-identifies
a clinic's records to HIPAA Safe Harbor standard, hosts the clean data, and lets
researchers query it in plain English — turning a weeks-long manual process into hours,
without an enterprise contract.

## Problem
Secondary use of clinical data for research is gated by two bottlenecks:
1. **Legal** — data must be de-identified before use; today this is manual, done by
   scarce "honest broker" staff at large academic centers, and unavailable to most
   mid-size institutions.
2. **Access** — even de-identified data requires SQL and a data team to query.

Mid-size research groups, community/specialty clinics, and individual investigators
wait weeks and lack the tooling the big platforms sell only to pharma and large systems.

## Market (paraphrased from public reports; see citations in pitch)
- De-identified health data market ~$8B (2025), growing ~10%/yr toward $14–20B early 2030s.
- Distinct, fast-growing sub-market: de-identification **assurance** (~$0.4B, ~12% CAGR).
- Incumbents (TriNetX, Truveta, Datavant, IQVIA) serve pharma and large national
  networks; academic centers use manual honest-broker services. The mid-market is
  underserved.

## Product model (three stages)
1. **Stage 1 — De-identify + host, per clinic (now, mostly built).** Each clinic's data
   is de-identified and hosted; the clinic queries its own data.
2. **Stage 2 — Opt-in cross-clinic query (near-term build).** A governed centralized pool:
   clinics opt in to contribute de-identified data; authorized researchers query across
   the opted-in clinics. Guardrails: sharing controls, researcher roles, audit logging,
   small-cohort suppression.
3. **Stage 3 — Unified research network (vision).** Pooled queryable database across
   partner clinics; optional federated "data never leaves" tier for institutions that
   require it.

Architecture choice: **centralized pool gated by per-clinic opt-in** (not federated) —
it extends what is already built and reaches a demonstrable product fastest.

## What is built today
- HIPAA Safe Harbor de-identification: regex detectors (SSN, phone, email, URL, IP, ZIP,
  dates, MRN, account/license/vehicle/device) + GPT-4o contextual detection (names, geo,
  biometric, photo), span merging with regex-precedence, year-preserving dates, age
  capping, human review, tamper-evident audit log, downloadable compliance certificate.
- Clinical data extraction from PDFs; encounter/visit data model.
- Natural-language + advanced-filter query with full provenance.
- 14 correctness properties validated via property-based tests; full backend + frontend
  test suites passing; deployed on Render.

## The moat (and the SBIR research core)
The defensible, research-grade differentiators — not yet built — are exactly what make a
strong SBIR aim:
1. **Residual re-identification risk metrics** — quantify actual re-ID risk of an output,
   beyond checklist Safe Harbor.
2. **Privacy–utility trade-off scoring** — measure information retention / downstream
   task utility per de-identified export.
3. **Path to Expert Determination** — produce the statistical evidence a qualified expert
   needs, lowering the cost of higher-utility de-identification.

## Illustrative SBIR Specific Aims (draft framing)
- **Aim 1:** Validate hybrid regex+LLM de-identification on heterogeneous real clinical
  text; report PHI-detection recall/precision against an annotated benchmark (e.g. i2b2/n2c2).
- **Aim 2:** Develop and validate residual re-identification risk and privacy–utility
  metrics for de-identified outputs, with configurable policy thresholds.
- **Aim 3:** Demonstrate a governed cross-institution query with cell-size suppression and
  auditability, producing the artifacts (residual-risk characterization, lineage) that
  compliance/IRB offices require.

## Business
- **Model:** SaaS, services-led onboarding early (automated over time).
- **Wedge:** de-identification speed + affordability vs. the manual honest-broker wait.
- **Motion:** land one research group bottom-up → survive security/compliance review →
  convert pilot to subscription → expand across the institution.
- **Proof to obtain:** a PHI-detection recall number and one named reference customer.

## Non-code gates (must not skip)
- **BAA** with each clinic before any real PHI flows.
- **DUA with a pooling opt-in clause** in every clinic contract from day one.
- **Expert Determination** for the pooled dataset once multiple clinics contribute.
- **HIPAA-eligible LLM endpoint** (Azure OpenAI / OpenAI BAA) before real PHI touches the
  contextual detector. Standard consumer OpenAI API is not HIPAA-eligible.

## Pilot plan
- **Phase 1 (now):** design-partner pilot on synthetic / already-de-identified data
  (e.g. MIMIC). Proves the end-to-end loop; no BAA required.
- **Phase 2 (after BAA + HIPAA-eligible LLM + validation number + security hardening):**
  same partner on real de-identified data, cleared by their compliance office.

## Immediate next steps
1. Confirm live Render deploy healthy with OPENAI_API_KEY set; set SEED_ADMIN_PASSWORD.
2. 5–10 customer-discovery calls (start with Barrow) to validate the honest-broker pain.
3. Attorney-drafted BAA/DUA (with pooling opt-in clause).
4. Build the de-identification validation harness; produce a recall number on an
   annotated dataset.
5. Spec + build Stage 2 (opt-in pooled cross-clinic query).
