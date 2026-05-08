from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from enum import Enum
import json
from app.config import settings


class FilterType(str, Enum):
    """Filter type enum."""
    DIAGNOSIS = "Diagnosis"
    PROCEDURE = "Procedure"
    MEDICATION = "Medication"
    DEMOGRAPHICS = "Demographics"
    OBSERVATION = "Observation"


class ComparisonOp(str, Enum):
    """Comparison operator enum."""
    EQUALS = "Equals"
    CONTAINS = "Contains"
    GREATER_THAN = "GreaterThan"
    LESS_THAN = "LessThan"
    BETWEEN = "Between"


class CohortFilter(BaseModel):
    """Cohort filter criteria."""
    filter_type: FilterType
    field: str
    operator: ComparisonOp
    value: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility."""
        return {
            "filter_type": self.filter_type.value if isinstance(self.filter_type, Enum) else self.filter_type,
            "field": self.field,
            "operator": self.operator.value if isinstance(self.operator, Enum) else self.operator,
            "value": self.value
        }


class VariableRequest(BaseModel):
    """Variable request for dataset."""
    name: str
    source: str  # "subjects", "procedures", "observations", "imaging"
    field: str
    aggregation: Optional[str] = None  # "mean", "count", "history", etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility."""
        return {
            "name": self.name,
            "source": self.source,
            "field": self.field,
            "aggregation": self.aggregation
        }


class TimeRange(BaseModel):
    """Time range filter."""
    start: Optional[str] = None
    end: Optional[str] = None
    relative: Optional[str] = None  # e.g., "6 months", "1 year"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility."""
        return {
            "start": self.start,
            "end": self.end,
            "relative": self.relative
        }


class ParsedIntent(BaseModel):
    """Parsed intent from natural language query."""
    cohort_criteria: List[CohortFilter]
    variables: List[VariableRequest]
    time_range: Optional[TimeRange] = None
    confidence: float  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing code."""
        return {
            "cohort_criteria": [c.to_dict() for c in self.cohort_criteria],
            "variables": [v.to_dict() for v in self.variables],
            "time_range": self.time_range.to_dict() if self.time_range else None,
            "confidence": self.confidence
        }


class NLParserService:
    """Natural Language Parser service using LLM."""
    
    def __init__(self):
        """Initialize NL Parser with LLM client."""
        self.llm_provider = settings.llm_provider
        
        # Demo mode - works without API keys
        if not settings.openai_api_key and not settings.anthropic_api_key:
            self.demo_mode = True
            self.client = None
            return
        
        self.demo_mode = False
        
        if self.llm_provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=settings.openai_api_key)
        elif self.llm_provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=settings.anthropic_api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
    
    def _get_available_tables(self) -> Dict[str, List[str]]:
        """Get available tables and their columns from DuckDB."""
        try:
            from app.database import get_duckdb_connection
            conn = get_duckdb_connection()
            tables = conn.execute("SHOW TABLES").fetchall()
            result = {}
            for (table_name,) in tables:
                try:
                    cols = conn.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'").fetchall()
                    result[table_name] = [c[0] for c in cols]
                except Exception:
                    result[table_name] = []
            conn.close()
            return result
        except Exception:
            return {}
    
    def parse(self, query_text: str, context: Optional[Dict[str, Any]] = None) -> ParsedIntent:
        """
        Parse natural language query into structured intent.
        
        Args:
            query_text: Natural language query from user
            context: Optional context (available data sources, user history)
        
        Returns:
            ParsedIntent with cohort criteria, variables, and confidence score
        """
        # Demo mode - use pattern matching
        if self.demo_mode:
            return self._demo_parse(query_text)
        
        # Create prompt for LLM
        prompt = self._create_prompt(query_text, context)
        
        # Call LLM
        if self.llm_provider == "openai":
            response = self._call_openai(prompt)
        else:
            response = self._call_anthropic(prompt)
        
        # Parse LLM response
        parsed_intent = self._parse_llm_response(response)
        
        return parsed_intent
    
    def _demo_parse(self, query_text: str) -> ParsedIntent:
        """Demo parser for when no API key is available."""
        query_lower = query_text.lower()
        
        # Default variables — always include basic demographics
        cohort_criteria = []
        variables = [
            VariableRequest(name="subject_id", source="subjects", field="subject_id"),
            VariableRequest(name="sex", source="subjects", field="sex"),
            VariableRequest(name="date_of_birth", source="subjects", field="date_of_birth"),
        ]
        
        # --- Diagnosis matching ---
        diagnosis_patterns = {
            "parkinson": "parkinson",
            "g20": "parkinson",
            "diabetes": "diabetes",
            "e11": "diabetes",
            "hypertension": "hypertension",
            "heart failure": "heart failure",
            "cardiac": "cardiac",
            "pneumonia": "pneumonia",
            "sepsis": "sepsis",
            "renal": "renal",
            "kidney": "kidney",
            "anemia": "anemia",
            "atrial fibrillation": "atrial fibrillation",
            "copd": "obstructive pulmonary",
            "stroke": "cerebrovascular",
            "cancer": "neoplasm",
            "tumor": "neoplasm",
        }
        
        matched_diagnosis = None
        for pattern, search_value in diagnosis_patterns.items():
            if pattern in query_lower:
                matched_diagnosis = search_value
                cohort_criteria.append(
                    CohortFilter(
                        filter_type=FilterType.DIAGNOSIS,
                        field="diagnosis_codes",
                        operator=ComparisonOp.CONTAINS,
                        value=search_value
                    )
                )
                break
        
        # If a diagnosis was matched, include diagnosis list in output
        if matched_diagnosis:
            variables.append(
                VariableRequest(name="diagnoses", source="subjects", field="diagnosis_codes")
            )
        
        # --- Procedure matching ---
        if "dbs" in query_lower or "deep brain" in query_lower:
            cohort_criteria.append(
                CohortFilter(
                    filter_type=FilterType.PROCEDURE,
                    field="procedure_type",
                    operator=ComparisonOp.EQUALS,
                    value="DBS"
                )
            )
            variables.append(
                VariableRequest(name="procedures", source="procedures", field="procedure_name", aggregation="history")
            )
            variables.append(
                VariableRequest(name="procedure_date", source="procedures", field="procedure_date", aggregation="history")
            )
        
        if "surgery" in query_lower or "procedure" in query_lower or "surgical" in query_lower:
            if not any(c.filter_type == FilterType.PROCEDURE for c in cohort_criteria):
                cohort_criteria.append(
                    CohortFilter(
                        filter_type=FilterType.PROCEDURE,
                        field="procedure_type",
                        operator=ComparisonOp.EQUALS,
                        value=""
                    )
                )
            variables.append(
                VariableRequest(name="procedures", source="procedures", field="procedure_name", aggregation="history")
            )
            variables.append(
                VariableRequest(name="procedure_count", source="procedures", field="procedure_name", aggregation="count")
            )
        
        # --- Lab / observation matching ---
        if "lab" in query_lower or "labs" in query_lower or "test" in query_lower:
            variables.append(
                VariableRequest(name="lab_count", source="observations", field="observation_value", aggregation="count")
            )
        
        # --- Medication matching ---
        if "medication" in query_lower or "drug" in query_lower or "prescription" in query_lower:
            variables.append(
                VariableRequest(name="medication_count", source="observations", field="observation_value", aggregation="count")
            )
        
        # --- Imaging matching ---
        if "mri" in query_lower or "imaging" in query_lower or "ct" in query_lower:
            variables.append(
                VariableRequest(name="imaging_modality", source="imaging", field="feature_value")
            )
        
        # --- If user asks for "all data" or "everything" ---
        if "all data" in query_lower or "everything" in query_lower or "all information" in query_lower:
            variables.extend([
                VariableRequest(name="diagnoses", source="subjects", field="diagnosis_codes"),
                VariableRequest(name="procedures", source="procedures", field="procedure_name", aggregation="history"),
                VariableRequest(name="procedure_count", source="procedures", field="procedure_name", aggregation="count"),
                VariableRequest(name="lab_count", source="observations", field="observation_value", aggregation="count"),
            ])
        
        # If no criteria found, return all subjects
        if not cohort_criteria:
            cohort_criteria.append(
                CohortFilter(
                    filter_type=FilterType.DEMOGRAPHICS,
                    field="subject_id",
                    operator=ComparisonOp.CONTAINS,
                    value=""  # Match all
                )
            )
        
        return ParsedIntent(
            cohort_criteria=cohort_criteria,
            variables=variables,
            time_range=None,
            confidence=0.85  # Demo mode confidence
        )
    
    def _create_prompt(self, query_text: str, context: Optional[Dict[str, Any]]) -> str:
        """Create prompt for LLM, including available database schema."""
        # Dynamically discover available tables in DuckDB
        available_tables = self._get_available_tables()
        
        tables_description = ""
        if available_tables:
            tables_description = "\n\nAvailable tables in the database:\n"
            for table_name, columns in available_tables.items():
                tables_description += f"  - {table_name}: {', '.join(columns)}\n"
        
        prompt = f"""You are a biomedical research query parser. Parse the following natural language query into structured components.

Query: "{query_text}"
{tables_description}
Extract the following information:
1. Cohort criteria: What filters define the patient/subject population?
   - Filter types: Diagnosis, Procedure, Medication, Demographics, Observation
   - For each filter, identify: field, operator (Equals, Contains, GreaterThan, LessThan, Between), and value

2. Variables: What data should be included in the dataset?
   - For each variable, identify: name, source (subjects/procedures/observations/imaging OR any table name from the available tables above), field, aggregation (if any)

3. Time range: Any temporal constraints? (start date, end date, or relative like "6 months")

4. Confidence: Your confidence in this parsing (0.0 to 1.0)

IMPORTANT: If the query references data that matches a specific uploaded table (not the standard subjects/procedures/observations/imaging), use that table name as the "source" value.

Respond ONLY with valid JSON in this exact format:
{{
  "cohort_criteria": [
    {{
      "filter_type": "Diagnosis|Procedure|Medication|Demographics|Observation",
      "field": "field_name",
      "operator": "Equals|Contains|GreaterThan|LessThan|Between",
      "value": "value"
    }}
  ],
  "variables": [
    {{
      "name": "variable_name",
      "source": "subjects|procedures|observations|imaging|<table_name>",
      "field": "field_name",
      "aggregation": "mean|count|history|null"
    }}
  ],
  "time_range": {{
    "start": "YYYY-MM-DD or null",
    "end": "YYYY-MM-DD or null",
    "relative": "6 months|1 year|null"
  }},
  "confidence": 0.0-1.0
}}

Examples:
Query: "Parkinson's patients with DBS surgery"
{{
  "cohort_criteria": [
    {{"filter_type": "Diagnosis", "field": "diagnosis_codes", "operator": "Contains", "value": "G20"}},
    {{"filter_type": "Procedure", "field": "procedure_code", "operator": "Equals", "value": "DBS"}}
  ],
  "variables": [],
  "time_range": null,
  "confidence": 0.95
}}

Query: "Patients over 65 with diabetes, include medication history"
{{
  "cohort_criteria": [
    {{"filter_type": "Demographics", "field": "age", "operator": "GreaterThan", "value": "65"}},
    {{"filter_type": "Diagnosis", "field": "diagnosis_codes", "operator": "Contains", "value": "E11"}}
  ],
  "variables": [
    {{"name": "medication_history", "source": "procedures", "field": "medication", "aggregation": "history"}}
  ],
  "time_range": null,
  "confidence": 0.90
}}

Now parse the query above."""
        
        return prompt
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a biomedical research query parser. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        return response.choices[0].message.content
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0.1,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
    
    def _parse_llm_response(self, response: str) -> ParsedIntent:
        """Parse LLM response into ParsedIntent."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # Parse JSON
            data = json.loads(response)
            
            # Convert to ParsedIntent
            cohort_criteria = [CohortFilter(**f) for f in data.get("cohort_criteria", [])]
            variables = [VariableRequest(**v) for v in data.get("variables", [])]
            time_range = TimeRange(**data["time_range"]) if data.get("time_range") else None
            confidence = data.get("confidence", 0.5)
            
            return ParsedIntent(
                cohort_criteria=cohort_criteria,
                variables=variables,
                time_range=time_range,
                confidence=confidence
            )
        except Exception as e:
            # If parsing fails, return low confidence result
            return ParsedIntent(
                cohort_criteria=[],
                variables=[],
                time_range=None,
                confidence=0.0
            )
