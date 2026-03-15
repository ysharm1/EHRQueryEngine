# Requirements Document: Research Dataset Builder

## Introduction

The Research Dataset Builder is a platform that enables biomedical researchers to generate structured, analysis-ready datasets from fragmented multimodal data sources using natural language or structured queries. The system integrates clinical data (EHR via FHIR), research systems (REDCap, LIMS), imaging features, pathology outputs, and experimental data into cohesive datasets with reproducible query logic and complete provenance tracking. The platform ensures HIPAA compliance through encrypted storage, role-based access control, and comprehensive audit logging.

## Glossary

- **Query_Orchestrator**: The central component that coordinates the query-to-dataset pipeline
- **NL_Parser**: Natural language parser powered by LLM that translates user queries into structured intent
- **Query_Planner**: Component that converts parsed intent into executable query plans
- **Schema_Mapper**: Component that maps between source schemas and canonical research schema
- **Dataset_Assembly_Engine**: Component that executes queries and assembles multimodal datasets
- **FHIR_Connector**: Component that connects to EHR systems via FHIR APIs
- **Data_Warehouse**: Storage system for analytics (DuckDB/Snowflake/BigQuery)
- **Metadata_Store**: PostgreSQL database storing dataset metadata and provenance
- **Canonical_Schema**: Standardized research schema with subjects, procedures, observations, and imaging tables
- **Cohort**: A subset of subjects matching specified filter criteria
- **Query_Plan**: Structured representation of query execution steps with SQL draft
- **Parsed_Intent**: Structured representation of user query including cohort criteria and variables
- **Export_Engine**: Component that generates dataset files in various formats

## Requirements

### Requirement 1: Natural Language Query Processing

**User Story:** As a biomedical researcher, I want to submit queries in natural language, so that I can generate datasets without learning SQL or complex query syntax.

#### Acceptance Criteria

1. WHEN a user submits a natural language query THEN THE Query_Orchestrator SHALL forward it to the NL_Parser
2. WHEN the NL_Parser receives a query THEN THE NL_Parser SHALL extract cohort criteria, variables, and time ranges into a Parsed_Intent structure
3. WHEN the NL_Parser completes parsing THEN THE NL_Parser SHALL return a confidence score between 0.0 and 1.0
4. IF the confidence score is below 0.7 THEN THE Query_Orchestrator SHALL reject the query with a clarification request
5. WHEN the Parsed_Intent is returned THEN THE Parsed_Intent SHALL include at least one cohort filter or variable request

### Requirement 2: Query Plan Generation

**User Story:** As a system, I want to convert parsed intent into optimized query plans, so that datasets can be generated efficiently from multiple data sources.

#### Acceptance Criteria

1. WHEN the Query_Planner receives a Parsed_Intent THEN THE Query_Planner SHALL generate a Query_Plan with executable steps
2. WHEN generating a Query_Plan THEN THE Query_Planner SHALL include estimated row count for the result set
3. WHEN generating a Query_Plan THEN THE Query_Planner SHALL produce a SQL draft for validation
4. WHEN multiple data sources are involved THEN THE Query_Planner SHALL optimize join order to minimize intermediate result sizes
5. WHEN the Query_Plan is complete THEN THE Query_Plan SHALL list all required data sources

### Requirement 3: Query Safety Validation

**User Story:** As a system administrator, I want all queries to be validated for safety, so that no data modification or malicious operations can occur.

#### Acceptance Criteria

1. WHEN a Query_Plan is generated THEN THE Query_Validator SHALL verify that all operations are read-only
2. WHEN validating a Query_Plan THEN THE Query_Validator SHALL reject queries with data modification operations
3. WHEN validating a Query_Plan THEN THE Query_Validator SHALL detect and reject recursive queries
4. IF the estimated row count exceeds 1,000,000 THEN THE Query_Validator SHALL reject the query
5. WHEN validating a Query_Plan THEN THE Query_Validator SHALL verify that all referenced tables exist
6. WHEN validation passes THEN THE Query_Validator SHALL return a validation result with isSafe set to true
7. IF validation fails THEN THE Query_Validator SHALL return a descriptive error message

### Requirement 4: Cohort Identification

**User Story:** As a researcher, I want to identify cohorts based on multiple criteria, so that I can select the right patient population for my study.

#### Acceptance Criteria

1. WHEN cohort criteria are provided THEN THE Dataset_Assembly_Engine SHALL evaluate all subjects against all criteria
2. WHEN evaluating cohort membership THEN THE Dataset_Assembly_Engine SHALL include only subjects matching ALL criteria
3. WHEN a diagnosis filter is applied THEN THE Dataset_Assembly_Engine SHALL check if the diagnosis code exists in the subject's diagnosis codes list
4. WHEN a procedure filter is applied THEN THE Dataset_Assembly_Engine SHALL verify the subject has the specified procedure code
5. WHEN a demographic filter is applied THEN THE Dataset_Assembly_Engine SHALL compare the subject's demographic field against the filter value
6. WHEN an observation filter is applied THEN THE Dataset_Assembly_Engine SHALL check if any observation matches the type and value criteria
7. WHEN cohort identification completes THEN THE Dataset_Assembly_Engine SHALL return a list of matching subjects

### Requirement 5: Schema Mapping and Transformation

**User Story:** As a data integration specialist, I want to map data from various sources to a canonical schema, so that datasets are consistent and interoperable.

#### Acceptance Criteria

1. WHEN ingesting data from a source THEN THE Schema_Mapper SHALL apply the appropriate schema mapping
2. WHEN a field mapping includes a transformation function THEN THE Schema_Mapper SHALL apply the transformation to the source value
3. WHEN transforming dates THEN THE Schema_Mapper SHALL parse the source date format and convert to ISO 8601
4. WHEN transforming codes THEN THE Schema_Mapper SHALL lookup the code in the specified code system
5. WHEN transforming units THEN THE Schema_Mapper SHALL convert from source unit to target unit
6. WHEN normalizing strings THEN THE Schema_Mapper SHALL apply consistent normalization rules
7. WHEN a new data source is added THEN THE Schema_Mapper SHALL infer field mappings based on field names and types

### Requirement 6: FHIR Data Integration

**User Story:** As a researcher, I want to access EHR data via FHIR APIs, so that I can include clinical data in my research datasets.

#### Acceptance Criteria

1. WHEN connecting to a FHIR endpoint THEN THE FHIR_Connector SHALL authenticate using the provided credentials
2. WHEN querying FHIR resources THEN THE FHIR_Connector SHALL construct valid FHIR search requests with specified parameters
3. WHEN receiving FHIR bundles THEN THE FHIR_Connector SHALL handle pagination to retrieve all matching resources
4. WHEN transforming FHIR resources THEN THE FHIR_Connector SHALL map Patient resources to the subjects table
5. WHEN transforming FHIR resources THEN THE FHIR_Connector SHALL map Condition resources to the observations table
6. WHEN transforming FHIR resources THEN THE FHIR_Connector SHALL map Procedure resources to the procedures table
7. WHEN a transformed subject fails validation THEN THE FHIR_Connector SHALL log the error and continue processing remaining resources
8. IF FHIR authentication fails THEN THE FHIR_Connector SHALL return an error message indicating authentication failure

### Requirement 7: Dataset Assembly

**User Story:** As a researcher, I want to assemble datasets with all requested variables, so that I have complete data for my analysis.

#### Acceptance Criteria

1. WHEN assembling a dataset THEN THE Dataset_Assembly_Engine SHALL collect data for all requested variables
2. WHEN collecting variables THEN THE Dataset_Assembly_Engine SHALL extract values from the appropriate data source for each variable
3. WHEN a variable requires aggregation THEN THE Dataset_Assembly_Engine SHALL apply the specified aggregation function
4. WHEN assembling a dataset THEN THE Dataset_Assembly_Engine SHALL ensure all rows have the same number of columns
5. WHEN assembling a dataset THEN THE Dataset_Assembly_Engine SHALL create a schema definition matching the requested variables
6. WHEN dataset assembly completes THEN THE Dataset_Assembly_Engine SHALL generate metadata including row count, column count, and data sources
7. WHEN dataset assembly completes THEN THE Dataset_Assembly_Engine SHALL create query provenance information

### Requirement 8: Missing Value Handling

**User Story:** As a researcher, I want to handle missing values according to my analysis needs, so that incomplete data doesn't prevent dataset generation.

#### Acceptance Criteria

1. WHEN a variable value is missing THEN THE Dataset_Assembly_Engine SHALL apply the specified missing value strategy
2. WHERE the missing value strategy is UseDefault THEN THE Dataset_Assembly_Engine SHALL substitute the configured default value
3. WHERE the missing value strategy is UseNull THEN THE Dataset_Assembly_Engine SHALL insert NULL in the dataset
4. WHERE the missing value strategy is UseMean THEN THE Dataset_Assembly_Engine SHALL calculate and substitute the mean value for that variable
5. WHERE the missing value strategy is Exclude THEN THE Dataset_Assembly_Engine SHALL omit the row from the final dataset
6. WHEN missing values exceed 20% for any variable THEN THE Dataset_Assembly_Engine SHALL include a warning in the metadata

### Requirement 9: Variable Name Normalization

**User Story:** As a data analyst, I want variable names to be normalized and valid, so that I can use the exported datasets in analysis tools without errors.

#### Acceptance Criteria

1. WHEN normalizing variable names THEN THE Dataset_Assembly_Engine SHALL convert all names to lowercase
2. WHEN normalizing variable names THEN THE Dataset_Assembly_Engine SHALL replace spaces with underscores
3. WHEN normalizing variable names THEN THE Dataset_Assembly_Engine SHALL remove special characters except underscores
4. IF a variable name starts with a digit THEN THE Dataset_Assembly_Engine SHALL prefix it with "col_"
5. IF a variable name is empty THEN THE Dataset_Assembly_Engine SHALL replace it with "col"
6. WHEN normalization completes THEN THE Dataset_Assembly_Engine SHALL ensure all names are valid SQL identifiers

### Requirement 10: Dataset Export

**User Story:** As a researcher, I want to export datasets in multiple formats, so that I can use them in various analysis tools.

#### Acceptance Criteria

1. WHEN a dataset is ready THEN THE Export_Engine SHALL generate files in the requested format
2. WHERE the export format is CSV THEN THE Export_Engine SHALL create a comma-separated values file
3. WHERE the export format is Parquet THEN THE Export_Engine SHALL create a columnar Parquet file
4. WHERE the export format is JSON THEN THE Export_Engine SHALL create a JSON file with array of objects
5. WHEN exporting a dataset THEN THE Export_Engine SHALL generate a schema definition file in JSON format
6. WHEN exporting a dataset THEN THE Export_Engine SHALL generate a query provenance file containing the original query and executed SQL
7. WHEN export completes THEN THE Export_Engine SHALL return download URLs for all generated files

### Requirement 11: Query Reproducibility

**User Story:** As a researcher, I want to reproduce my dataset queries, so that I can verify results and share methods with collaborators.

#### Acceptance Criteria

1. WHEN generating a dataset THEN THE Query_Orchestrator SHALL create a reproducible query file
2. WHEN creating a reproducible query THEN THE Query_Orchestrator SHALL include generation timestamp and user information as comments
3. WHEN creating a reproducible query THEN THE Query_Orchestrator SHALL include the cohort definition SQL
4. WHEN creating a reproducible query THEN THE Query_Orchestrator SHALL include the variable collection SQL
5. WHEN creating a reproducible query THEN THE Query_Orchestrator SHALL include all join operations
6. WHEN the reproducible query is executed THEN THE Data_Warehouse SHALL produce the same results as the original query

### Requirement 12: Data Validation

**User Story:** As a data quality manager, I want all ingested data to be validated, so that only valid data enters the research database.

#### Acceptance Criteria

1. WHEN validating a subject record THEN THE Metadata_Store SHALL verify the subject ID is non-empty
2. WHEN validating a subject record THEN THE Metadata_Store SHALL verify sex is one of M, F, O, or null
3. WHEN validating a subject record THEN THE Metadata_Store SHALL verify diagnosis codes are valid ICD-10 or SNOMED codes
4. WHEN validating a procedure record THEN THE Metadata_Store SHALL verify the subject ID references an existing subject
5. WHEN validating a procedure record THEN THE Metadata_Store SHALL verify the procedure code is valid CPT or SNOMED
6. WHEN validating a procedure record THEN THE Metadata_Store SHALL verify the procedure date is after the subject's date of birth
7. WHEN validating an observation record THEN THE Metadata_Store SHALL verify the observation type is a valid LOINC code
8. WHEN validating a numeric observation THEN THE Metadata_Store SHALL verify the observation unit is present
9. WHEN validating an imaging record THEN THE Metadata_Store SHALL verify the features list is non-empty
10. IF validation fails THEN THE Metadata_Store SHALL log the validation error with row number and field name
11. WHEN validation fails THEN THE Metadata_Store SHALL continue processing remaining records

### Requirement 13: Authentication and Authorization

**User Story:** As a system administrator, I want to control access to the system, so that only authorized users can access sensitive research data.

#### Acceptance Criteria

1. WHEN a user submits a request THEN THE Authentication_Service SHALL validate the session token
2. IF the session token is invalid THEN THE Authentication_Service SHALL reject the request with an unauthorized error
3. IF the session token is expired THEN THE Authentication_Service SHALL reject the request and require re-authentication
4. WHEN a user session is idle for 30 minutes THEN THE Authentication_Service SHALL expire the session
5. WHEN an admin user authenticates THEN THE Authentication_Service SHALL require multi-factor authentication
6. WHEN a user accesses data THEN THE Authentication_Service SHALL verify the user has the required role
7. WHERE role-based access control is enforced THEN THE Authentication_Service SHALL support Admin, Researcher, Data_Analyst, and Read_Only roles

### Requirement 14: Audit Logging

**User Story:** As a compliance officer, I want comprehensive audit logs, so that I can track all data access for HIPAA compliance.

#### Acceptance Criteria

1. WHEN a user submits a query THEN THE Query_Orchestrator SHALL log the user ID, timestamp, and query text
2. WHEN a dataset is generated THEN THE Query_Orchestrator SHALL log the dataset ID, cohort size, variables, and export format
3. WHEN a user authenticates THEN THE Authentication_Service SHALL log the authentication attempt with success or failure status
4. WHEN a user accesses data THEN THE Query_Orchestrator SHALL log the data sources accessed
5. WHEN audit logs are written THEN THE Metadata_Store SHALL use write-once storage to prevent tampering
6. WHEN audit logs are created THEN THE Metadata_Store SHALL retain them for 7 years
7. WHEN audit logs are stored THEN THE Metadata_Store SHALL include integrity verification checksums

### Requirement 15: Data Encryption

**User Story:** As a security officer, I want all data encrypted, so that sensitive health information is protected from unauthorized access.

#### Acceptance Criteria

1. WHEN data is stored in the database THEN THE Data_Warehouse SHALL encrypt it using AES-256 encryption
2. WHEN data is stored in file storage THEN THE Export_Engine SHALL encrypt it using AES-256 encryption
3. WHEN data is transmitted over the network THEN THE API_Gateway SHALL use TLS 1.3 encryption
4. WHEN encryption keys are managed THEN THE System SHALL use AWS KMS or Azure Key Vault
5. WHEN backups are created THEN THE System SHALL encrypt them with separate encryption keys
6. WHEN connecting to FHIR endpoints THEN THE FHIR_Connector SHALL use encrypted connections

### Requirement 16: Error Handling and Recovery

**User Story:** As a user, I want clear error messages and graceful error handling, so that I can understand and resolve issues quickly.

#### Acceptance Criteria

1. IF a FHIR API returns 401 or 403 THEN THE FHIR_Connector SHALL return an error message indicating authentication failure
2. IF a query execution exceeds 5 minutes THEN THE Query_Orchestrator SHALL cancel the query and return a timeout error
3. IF schema mapping fails THEN THE Schema_Mapper SHALL return an error listing unmapped fields
4. IF data validation fails THEN THE Metadata_Store SHALL generate a validation report with error details
5. WHEN an error occurs THEN THE System SHALL log the error with timestamp, component, and error details
6. WHEN a recoverable error occurs THEN THE System SHALL provide suggestions for resolution
7. IF a database connection fails THEN THE System SHALL retry the connection up to 3 times with exponential backoff

### Requirement 17: Performance and Scalability

**User Story:** As a system architect, I want the system to handle large datasets efficiently, so that researchers can work with real-world data volumes.

#### Acceptance Criteria

1. WHEN executing queries THEN THE Query_Orchestrator SHALL complete 95% of queries within 30 seconds
2. WHEN ingesting FHIR resources THEN THE FHIR_Connector SHALL process at least 10,000 resources per minute
3. WHEN assembling datasets THEN THE Dataset_Assembly_Engine SHALL handle datasets with 100,000 rows within 2 minutes
4. WHEN multiple users submit queries THEN THE System SHALL support 1000 concurrent users
5. WHEN storing data THEN THE Data_Warehouse SHALL support at least 10 million subject records
6. WHEN processing queries THEN THE Query_Orchestrator SHALL handle 100 queries per minute
7. WHEN batch inserting data THEN THE Data_Warehouse SHALL use batch sizes of 1000 records

### Requirement 18: Query Timeout and Resource Limits

**User Story:** As a system administrator, I want to prevent resource exhaustion, so that the system remains responsive for all users.

#### Acceptance Criteria

1. WHEN a query is submitted THEN THE Query_Orchestrator SHALL enforce a 5-minute execution timeout
2. IF a query timeout occurs THEN THE Query_Orchestrator SHALL cancel the query execution
3. WHEN a query is cancelled THEN THE Query_Orchestrator SHALL log the query plan and estimated rows
4. IF a result set would exceed 1 million rows THEN THE Query_Validator SHALL reject the query before execution
5. WHEN a query is rejected for size THEN THE Query_Orchestrator SHALL suggest adding filters or reducing scope

### Requirement 19: Data Provenance Tracking

**User Story:** As a researcher, I want complete provenance information for my datasets, so that I can document my methods and ensure reproducibility.

#### Acceptance Criteria

1. WHEN a dataset is created THEN THE Dataset_Assembly_Engine SHALL record the original natural language query
2. WHEN a dataset is created THEN THE Dataset_Assembly_Engine SHALL record the parsed intent structure
3. WHEN a dataset is created THEN THE Dataset_Assembly_Engine SHALL record the executed SQL query
4. WHEN a dataset is created THEN THE Dataset_Assembly_Engine SHALL record the query execution time
5. WHEN a dataset is created THEN THE Dataset_Assembly_Engine SHALL record all data sources used
6. WHEN a dataset is created THEN THE Dataset_Assembly_Engine SHALL record the creation timestamp and user ID
7. WHEN provenance information is stored THEN THE Metadata_Store SHALL ensure it cannot be modified

### Requirement 20: Referential Integrity

**User Story:** As a database administrator, I want referential integrity enforced, so that data relationships remain consistent.

#### Acceptance Criteria

1. WHEN a procedure record is inserted THEN THE Metadata_Store SHALL verify the subject ID exists in the subjects table
2. WHEN an observation record is inserted THEN THE Metadata_Store SHALL verify the subject ID exists in the subjects table
3. WHEN an imaging record is inserted THEN THE Metadata_Store SHALL verify the subject ID exists in the subjects table
4. IF a foreign key reference is invalid THEN THE Metadata_Store SHALL reject the insert operation
5. WHEN referential integrity is violated THEN THE Metadata_Store SHALL return a descriptive error message
