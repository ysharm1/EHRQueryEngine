"""
Public Dataset Search Service

Searches for publicly available biomedical datasets matching a query.
Uses OpenAI to intelligently match queries to known open datasets,
then supplements with a curated static catalog.
"""

from typing import List, Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


# Curated catalog of major open biomedical datasets
DATASET_CATALOG = [
    {
        "id": "ppmi",
        "name": "Parkinson's Progression Markers Initiative (PPMI)",
        "description": "Longitudinal study of Parkinson's disease with clinical, imaging, biomarker, and genetic data from 1,400+ participants.",
        "subjects": "1,400+",
        "url": "https://www.ppmi-info.org/access-data-specimens/download-data",
        "access": "Registration required (free)",
        "tags": ["parkinson", "neurology", "mri", "biomarker", "longitudinal", "dbs"],
        "format": "CSV, DICOM",
        "organization": "Michael J. Fox Foundation",
    },
    {
        "id": "ukbiobank",
        "name": "UK Biobank",
        "description": "Large-scale biomedical database with genetic, lifestyle, and health data from 500,000 UK participants.",
        "subjects": "500,000",
        "url": "https://www.ukbiobank.ac.uk/enable-your-research/apply-for-access",
        "access": "Application required",
        "tags": ["genetics", "imaging", "longitudinal", "diabetes", "hypertension", "cancer", "cardiovascular"],
        "format": "CSV, BGEN, DICOM",
        "organization": "UK Biobank",
    },
    {
        "id": "mimic",
        "name": "MIMIC-IV (Medical Information Mart for Intensive Care)",
        "description": "De-identified EHR data from ICU patients at Beth Israel Deaconess Medical Center, 2008–2019.",
        "subjects": "40,000+",
        "url": "https://physionet.org/content/mimiciv/",
        "access": "PhysioNet credentialing (free)",
        "tags": ["icu", "ehr", "clinical", "medications", "procedures", "observations", "critical care"],
        "format": "CSV",
        "organization": "PhysioNet / MIT",
    },
    {
        "id": "adni",
        "name": "Alzheimer's Disease Neuroimaging Initiative (ADNI)",
        "description": "Multi-site study tracking Alzheimer's progression with MRI, PET, genetics, and cognitive assessments.",
        "subjects": "2,000+",
        "url": "https://adni.loni.usc.edu/data-samples/access-data/",
        "access": "Registration required (free)",
        "tags": ["alzheimer", "dementia", "mri", "pet", "neurology", "cognitive", "imaging"],
        "format": "CSV, DICOM, NIFTI",
        "organization": "LONI / NIH",
    },
    {
        "id": "tcga",
        "name": "The Cancer Genome Atlas (TCGA)",
        "description": "Genomic, transcriptomic, and clinical data for 33 cancer types from 11,000+ patients.",
        "subjects": "11,000+",
        "url": "https://portal.gdc.cancer.gov/",
        "access": "Open access (some controlled)",
        "tags": ["cancer", "genomics", "tumor", "oncology", "rna", "dna", "clinical"],
        "format": "CSV, VCF, BAM",
        "organization": "NCI / NIH",
    },
    {
        "id": "nhanes",
        "name": "National Health and Nutrition Examination Survey (NHANES)",
        "description": "Cross-sectional survey of US population health, nutrition, and lab data since 1960.",
        "subjects": "5,000+ per cycle",
        "url": "https://www.cdc.gov/nchs/nhanes/",
        "access": "Fully open",
        "tags": ["nutrition", "diabetes", "hypertension", "obesity", "demographics", "lab", "survey"],
        "format": "SAS, CSV",
        "organization": "CDC / NCHS",
    },
    {
        "id": "physionet",
        "name": "PhysioNet (Multiple Datasets)",
        "description": "Repository of physiological and clinical data including ECG, EEG, ICU records, and waveforms.",
        "subjects": "Varies by dataset",
        "url": "https://physionet.org/about/database/",
        "access": "Free with registration",
        "tags": ["ecg", "eeg", "waveform", "icu", "cardiac", "sleep", "clinical"],
        "format": "CSV, WFDB, EDF",
        "organization": "PhysioNet / MIT",
    },
    {
        "id": "clinicaltrials",
        "name": "ClinicalTrials.gov",
        "description": "Registry of clinical studies worldwide. Some trials share de-identified participant data.",
        "subjects": "Varies",
        "url": "https://clinicaltrials.gov/",
        "access": "Open registry; data sharing varies",
        "tags": ["clinical trial", "intervention", "treatment", "drug", "surgery", "randomized"],
        "format": "XML, CSV",
        "organization": "NIH / NLM",
    },
    {
        "id": "openneuro",
        "name": "OpenNeuro",
        "description": "Open platform for sharing neuroimaging data (MRI, fMRI, EEG, MEG) in BIDS format.",
        "subjects": "Varies by dataset",
        "url": "https://openneuro.org/",
        "access": "Fully open",
        "tags": ["mri", "fmri", "eeg", "meg", "neuroimaging", "brain", "neurology"],
        "format": "NIFTI, EDF, BIDS",
        "organization": "OpenNeuro",
    },
    {
        "id": "hmp",
        "name": "Human Microbiome Project (HMP)",
        "description": "Characterization of the human microbiome across body sites from healthy adults.",
        "subjects": "300+",
        "url": "https://hmpdacc.org/",
        "access": "Open access",
        "tags": ["microbiome", "genomics", "gut", "bacteria", "16s", "metagenomics"],
        "format": "FASTQ, CSV",
        "organization": "NIH",
    },
]


def search_public_datasets(query: str) -> List[Dict[str, Any]]:
    """
    Search the dataset catalog for matches to the query.
    Uses LLM if available, otherwise falls back to keyword matching.
    """
    if not query.strip():
        return DATASET_CATALOG[:5]

    # Try LLM-powered search first
    if settings.openai_api_key:
        try:
            return _llm_search(query)
        except Exception as e:
            logger.warning(f"LLM dataset search failed, falling back to keyword: {e}")

    return _keyword_search(query)


def _keyword_search(query: str) -> List[Dict[str, Any]]:
    """Simple keyword-based search."""
    query_lower = query.lower()
    scored = []

    for dataset in DATASET_CATALOG:
        score = 0
        searchable = " ".join([
            dataset["name"].lower(),
            dataset["description"].lower(),
            " ".join(dataset["tags"]),
        ])

        for word in query_lower.split():
            if len(word) > 2 and word in searchable:
                score += 1

        if score > 0:
            scored.append((score, dataset))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [d for _, d in scored[:5]]

    # Always return at least 2 results
    if len(results) < 2:
        for d in DATASET_CATALOG:
            if d not in results:
                results.append(d)
            if len(results) >= 3:
                break

    return results


def _llm_search(query: str) -> List[Dict[str, Any]]:
    """Use OpenAI to rank datasets by relevance to the query."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)

    catalog_summary = "\n".join([
        f"- {d['id']}: {d['name']} — {d['description'][:100]} [tags: {', '.join(d['tags'][:5])}]"
        for d in DATASET_CATALOG
    ])

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a biomedical research assistant. Given a research query, identify the most relevant public datasets from the provided catalog. Return ONLY a JSON array of dataset IDs, ordered by relevance, max 4 items. Example: [\"ppmi\", \"adni\"]"
            },
            {
                "role": "user",
                "content": f"Research query: \"{query}\"\n\nAvailable datasets:\n{catalog_summary}\n\nReturn the IDs of the most relevant datasets as a JSON array."
            }
        ],
        temperature=0,
        max_tokens=100,
    )

    import json
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

    ids = json.loads(raw)
    id_map = {d["id"]: d for d in DATASET_CATALOG}
    results = [id_map[i] for i in ids if i in id_map]

    # Fill to at least 2
    if len(results) < 2:
        for d in DATASET_CATALOG:
            if d not in results:
                results.append(d)
            if len(results) >= 3:
                break

    return results
