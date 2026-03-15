# Implementation Plan: Research Dataset Builder

## Overview

This implementation plan breaks down the Research Dataset Builder into discrete coding tasks. The system enables biomedical researchers to generate structured datasets from multimodal data sources using natural language queries. The architecture includes a React/Next.js frontend, FastAPI backend with query orchestration, PostgreSQL for metadata, DuckDB for analytics, and FHIR connectors for EHR integration. All implementation will use Python for the backend and TypeScript for the frontend.

## Tasks

- [x] 1. Set up project structure and core infrastructure
  - Create directory structure for backend (FastAPI) and frontend (Next.js)
  - Set up Python virtual environment and install core dependencies (FastAPI, SQLAlchemy, Pydantic)
  - Set up Next.js project with TypeScript, TanStack Query, and Tailwind CSS
  - Configure PostgreSQL connection for metadata store
  - Configure DuckDB for analytics data warehouse
  - Set up environment configuration files (.env templates)
  - Create Docker Compose file for local development
  - _Requirements: 17.1, 17.2, 17.3_

- [x] 2. Implement authentication and authorization system
  - [x] 2.1 Create authentication service with JWT token management
    - Implement user authentication endpoints (login, logout, token refresh)
    - Create JWT token generation and validation functions
    - Implement session management with 30-minute timeout
    - _Requirements: 13.1, 13.2, 13.3, 13.4_
  
  - [x] 2.2 Implement role-based access control (RBAC)
    - Define user roles (Admin, Researcher, Data_Analyst, Read_Only)
    - Create authorization middleware for API endpoints
    - Implement role verification functions
    - _Requirements: 13.6, 13.7_
  
  - [ ]* 2.3 Write unit tests for authentication service
    - Test token generation and validation
    - Test session timeout behavior
    - Test role-based access control
    - _Requirements: 13.1, 13.2, 13.4_

- [x] 3. Implement data models and database schema
  - [x] 3.1 Create canonical schema models (Subject, Procedure, Observation, ImagingFeature)
    - Define SQLAlchemy models for subjects table with validation
    - Define SQLAlchemy models for procedures table with foreign key constraints
    - Define SQLAlchemy models for observations table
    - Define SQLAlchemy models for imaging_features table
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 20.1, 20.2, 20.3_
  
  - [x] 3.2 Create metadata and provenance models
    - Define models for dataset metadata storage
    - Define models for query provenance tracking
    - Define models for audit logs
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 14.1, 14.2_
  
  - [x] 3.3 Implement data validation functions
    - Create validation function for Subject records (ID, sex, diagnosis codes, dates)
    - Create validation function for Procedure records (codes, dates, foreign keys)
    - Create validation function for Observation records (LOINC codes, units, values)
    - Create validation function for ImagingFeature records
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 12.10_
  
  - [ ]* 3.4 Write property test for data validation
    - **Property 5: FHIR Transformation Validity** - All transformed FHIR resources must pass validation
    - **Validates: Requirements 12.1-12.11**
  
  - [ ]* 3.5 Write property test for referential integrity
    - **Property 6: Referential Integrity** - All foreign key references must be valid
    - **Validates: Requirements 20.1-20.5**

- [x] 4. Implement Natural Language Parser with LLM integration
  - [x] 4.1 Create NL Parser service with LLM API integration
    - Set up OpenAI or Anthropic API client
    - Create prompt templates for query parsing
    - Implement parse function that extracts cohort criteria and variables
    - Return ParsedIntent structure with confidence scores
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  
  - [x] 4.2 Implement confidence threshold validation
    - Check confidence score against 0.7 threshold
    - Return clarification request for low-confidence queries
    - _Requirements: 1.4_
  
  - [ ]* 4.3 Write unit tests for NL Parser
    - Test intent extraction from various natural language queries
    - Test confidence score calculation
    - Test clarification request generation
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Query Planner
  - [x] 6.1 Create Query Planner service
    - Implement createPlan function that converts ParsedIntent to QueryPlan
    - Generate query steps with operations (Filter, Join, Aggregate, Transform)
    - Optimize join order to minimize intermediate result sizes
    - Estimate result set row count
    - Generate SQL draft from query plan
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ]* 6.2 Write unit tests for Query Planner
    - Test query plan generation for different cohort criteria
    - Test join order optimization
    - Test SQL generation
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 7. Implement Query Validator
  - [x] 7.1 Create Query Validator service
    - Implement validateQuerySafety function
    - Check for read-only operations (reject data modification)
    - Detect and reject recursive queries
    - Validate estimated row count against 1M limit
    - Verify all referenced tables exist
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 18.4_
  
  - [ ]* 7.2 Write property test for query safety
    - **Property 1: Query Safety Invariant** - All executed queries must be read-only
    - **Validates: Requirements 3.1, 3.2_
  
  - [ ]* 7.3 Write unit tests for Query Validator
    - Test rejection of data modification queries
    - Test recursive query detection
    - Test row count limit enforcement
    - Test table existence validation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 8. Implement Schema Mapper
  - [x] 8.1 Create Schema Mapper service
    - Define SchemaMapping and FieldMapping data structures
    - Implement mapToCanonical function with transformation support
    - Implement transformation functions (DateParse, CodeLookup, UnitConversion, StringNormalize)
    - Implement inferMapping function for automatic schema detection
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_
  
  - [ ]* 8.2 Write unit tests for Schema Mapper
    - Test field mapping transformations
    - Test schema inference
    - Test all transformation functions
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 9. Implement FHIR Connector
  - [x] 9.1 Create FHIR Connector service
    - Implement FHIR API client with authentication
    - Implement query function for FHIR search with pagination
    - Handle FHIR bundle parsing
    - Implement transformToCanonical function for FHIR resources
    - Map Patient resources to subjects table
    - Map Condition resources to observations table
    - Map Procedure resources to procedures table
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 15.6_
  
  - [x] 9.2 Implement error handling for FHIR operations
    - Handle authentication failures (401/403)
    - Log validation errors and continue processing
    - _Requirements: 6.7, 6.8, 16.1_
  
  - [ ]* 9.3 Write unit tests for FHIR Connector
    - Test FHIR resource parsing and transformation
    - Test authentication error handling
    - Test pagination handling
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Cohort Identification
  - [x] 11.1 Create cohort identification functions
    - Implement identifyCohort function that filters subjects by criteria
    - Implement evaluateFilter function for each filter type (Diagnosis, Procedure, Medication, Demographics, Observation)
    - Implement comparison operators (Equals, Contains, GreaterThan, LessThan, Between)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_
  
  - [ ]* 11.2 Write property test for cohort consistency
    - **Property 2: Cohort Consistency** - All subjects in cohort must satisfy ALL filter criteria
    - **Validates: Requirements 4.1, 4.2_
  
  - [ ]* 11.3 Write unit tests for cohort identification
    - Test diagnosis filter evaluation
    - Test procedure filter evaluation
    - Test demographic filter evaluation
    - Test observation filter evaluation
    - Test multiple criteria (AND logic)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 12. Implement Dataset Assembly Engine
  - [x] 12.1 Create Dataset Assembly service
    - Implement assemble function that executes query plans
    - Collect data for all requested variables from appropriate sources
    - Implement variable aggregation functions (mean, count, history)
    - Ensure all rows have same number of columns
    - Generate dataset schema definition
    - Generate dataset metadata (row count, column count, data sources)
    - Create query provenance information
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [x] 12.2 Implement missing value handling strategies
    - Implement UseDefault strategy (substitute default value)
    - Implement UseNull strategy (insert NULL)
    - Implement UseMean strategy (calculate and substitute mean)
    - Implement Exclude strategy (omit row from dataset)
    - Generate warning when missing values exceed 20%
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_
  
  - [x] 12.3 Implement variable name normalization
    - Convert names to lowercase
    - Replace spaces with underscores
    - Remove special characters except underscores
    - Prefix names starting with digits with "col_"
    - Replace empty names with "col"
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_
  
  - [ ]* 12.4 Write property test for schema completeness
    - **Property 3: Schema Completeness** - Every row must have exactly same number of columns as schema
    - **Validates: Requirements 7.4_
  
  - [ ]* 12.5 Write property test for normalization idempotency
    - **Property 4 (implied): Normalization Idempotency** - Normalizing twice produces same result
    - **Validates: Requirements 9.1-9.6**
  
  - [ ]* 12.6 Write unit tests for Dataset Assembly
    - Test variable collection from multiple sources
    - Test aggregation functions
    - Test missing value strategies
    - Test variable name normalization
    - _Requirements: 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3_

- [x] 13. Implement Export Engine
  - [x] 13.1 Create Export Engine service
    - Implement CSV export function
    - Implement Parquet export function
    - Implement JSON export function
    - Generate schema definition file (JSON)
    - Generate query provenance file with original query and executed SQL
    - Return download URLs for all generated files
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [x] 13.2 Implement reproducible query generation
    - Generate SQL query with header comments (timestamp, user)
    - Include cohort definition SQL
    - Include variable collection SQL
    - Include join operations
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_
  
  - [ ]* 13.3 Write unit tests for Export Engine
    - Test CSV export format
    - Test Parquet export format
    - Test JSON export format
    - Test schema file generation
    - Test provenance file generation
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [ ] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement Query Orchestrator
  - [x] 15.1 Create Query Orchestrator service
    - Implement processQuery function that coordinates entire pipeline
    - Validate user authentication and authorization
    - Call NL Parser to parse query
    - Validate confidence threshold
    - Load schema mappings for data sources
    - Call Query Planner to create query plan
    - Call Query Validator to validate safety
    - Call Dataset Assembly to execute and assemble dataset
    - Call Export Engine to generate files
    - Return QueryResponse with dataset metadata and download URLs
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2, 7.1, 10.1_
  
  - [x] 15.2 Implement query timeout and resource limits
    - Enforce 5-minute execution timeout
    - Cancel query execution on timeout
    - Log query plan and estimated rows on cancellation
    - Provide suggestions for query optimization
    - _Requirements: 18.1, 18.2, 18.3, 18.5, 16.2_
  
  - [ ]* 15.3 Write integration tests for Query Orchestrator
    - Test end-to-end query flow from NL query to dataset export
    - Test timeout handling
    - Test error propagation from components
    - _Requirements: 1.1, 2.1, 3.1, 7.1, 10.1, 18.1_

- [x] 16. Implement Audit Logging
  - [x] 16.1 Create Audit Log service
    - Log query submissions (user ID, timestamp, query text)
    - Log dataset generation (dataset ID, cohort size, variables, export format)
    - Log authentication attempts (success/failure)
    - Log data source access
    - Use write-once storage with integrity checksums
    - Configure 7-year retention policy
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 19.6_
  
  - [ ]* 16.2 Write unit tests for Audit Logging
    - Test log entry creation
    - Test integrity checksum generation
    - Test log immutability
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [x] 17. Implement data encryption and security
  - [x] 17.1 Configure database encryption
    - Enable AES-256 encryption for PostgreSQL
    - Enable AES-256 encryption for DuckDB
    - Configure encryption for file storage (S3/local)
    - _Requirements: 15.1, 15.2_
  
  - [x] 17.2 Configure TLS for API communications
    - Enable TLS 1.3 for FastAPI endpoints
    - Configure secure session cookies
    - _Requirements: 15.3_
  
  - [x] 17.3 Integrate encryption key management
    - Set up AWS KMS or Azure Key Vault integration
    - Configure separate keys for backups
    - _Requirements: 15.4, 15.5_

- [x] 18. Implement error handling and recovery
  - [x] 18.1 Create centralized error handling middleware
    - Handle FHIR authentication errors with descriptive messages
    - Handle schema mapping failures with unmapped field lists
    - Handle data validation failures with validation reports
    - Handle database connection failures with retry logic (3 attempts, exponential backoff)
    - Log all errors with timestamp, component, and details
    - Provide recovery suggestions for each error type
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_
  
  - [ ]* 18.2 Write unit tests for error handling
    - Test FHIR authentication error handling
    - Test timeout error handling
    - Test schema mapping error handling
    - Test validation error handling
    - Test database retry logic
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.7_

- [x] 19. Implement data provenance tracking
  - [x] 19.1 Create provenance tracking in Dataset Assembly
    - Record original natural language query
    - Record parsed intent structure
    - Record executed SQL query
    - Record query execution time
    - Record all data sources used
    - Record creation timestamp and user ID
    - Ensure provenance information is immutable
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_
  
  - [ ]* 19.2 Write property test for provenance preservation
    - **Property 4: Data Provenance Preservation** - Every dataset must maintain complete provenance
    - **Validates: Requirements 19.1-19.7**

- [ ] 20. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 21. Build frontend React/Next.js application
  - [x] 21.1 Create chat interface for natural language queries
    - Build query input component with text area
    - Implement query submission to backend API
    - Display query processing status
    - Show parsed intent and confidence score
    - Handle clarification requests for low-confidence queries
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [x] 21.2 Create dataset explorer component
    - Display dataset preview with pagination
    - Show dataset metadata (row count, column count, data sources)
    - Display schema information
    - Show query provenance information
    - _Requirements: 7.6, 7.7, 19.1, 19.2, 19.3_
  
  - [x] 21.3 Create dataset export interface
    - Provide export format selection (CSV, Parquet, JSON)
    - Display download links for generated files
    - Show export progress indicator
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.7_
  
  - [x] 21.4 Implement authentication UI
    - Create login page with form
    - Handle JWT token storage and refresh
    - Implement session timeout notification
    - Create logout functionality
    - _Requirements: 13.1, 13.2, 13.3, 13.4_
  
  - [ ]* 21.5 Write frontend component tests
    - Test chat interface interaction
    - Test dataset explorer rendering
    - Test export interface functionality
    - Test authentication flow

- [x] 22. Create API endpoints and wire components together
  - [x] 22.1 Create FastAPI endpoints
    - POST /api/auth/login - User authentication
    - POST /api/auth/logout - User logout
    - POST /api/auth/refresh - Token refresh
    - POST /api/query - Submit natural language query
    - GET /api/dataset/{id} - Get dataset metadata
    - GET /api/dataset/{id}/download - Download dataset files
    - POST /api/fhir/ingest - Trigger FHIR data ingestion
    - GET /api/health - Health check endpoint
    - _Requirements: 1.1, 13.1, 10.7, 6.1_
  
  - [x] 22.2 Wire Query Orchestrator to API endpoints
    - Connect /api/query endpoint to Query Orchestrator
    - Implement request validation and error handling
    - Return appropriate HTTP status codes
    - _Requirements: 1.1, 2.1, 3.1, 7.1_
  
  - [x] 22.3 Wire Authentication Service to API endpoints
    - Connect authentication endpoints to Authentication Service
    - Implement JWT middleware for protected routes
    - Add RBAC checks to endpoints
    - _Requirements: 13.1, 13.2, 13.6, 13.7_
  
  - [ ]* 22.4 Write API integration tests
    - Test end-to-end query submission and dataset generation
    - Test authentication and authorization flows
    - Test FHIR data ingestion
    - Test error responses
    - _Requirements: 1.1, 13.1, 6.1_

- [x] 23. Set up data warehouse and perform initial data loading
  - [x] 23.1 Initialize PostgreSQL metadata store
    - Run database migrations to create tables
    - Create indexes on frequently queried columns
    - Set up database connection pooling
    - _Requirements: 17.1, 17.5_
  
  - [x] 23.2 Initialize DuckDB analytics warehouse
    - Create DuckDB database file
    - Create canonical schema tables (subjects, procedures, observations, imaging_features)
    - Create indexes for query optimization
    - _Requirements: 17.1, 17.5_
  
  - [x] 23.3 Create sample data for testing
    - Generate synthetic subject records
    - Generate synthetic procedure records
    - Generate synthetic observation records
    - Ensure referential integrity in test data
    - _Requirements: 12.1, 12.4, 12.5, 20.1, 20.2_

- [x] 24. Final checkpoint and end-to-end testing
  - [x] 24.1 Run end-to-end integration tests
    - Test complete query flow: NL query → dataset export
    - Test FHIR data ingestion → query → export
    - Test multi-source dataset assembly
    - Test authentication and authorization enforcement
    - Test error handling and recovery scenarios
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 6.1, 7.1, 10.1, 13.1_
  
  - [x] 24.2 Verify security and compliance requirements
    - Verify data encryption at rest and in transit
    - Verify audit logging for all operations
    - Verify RBAC enforcement
    - Verify session timeout behavior
    - _Requirements: 13.1, 13.4, 14.1, 14.2, 15.1, 15.2, 15.3_
  
  - [x] 24.3 Performance testing
    - Test query execution time (target: 95% under 30 seconds)
    - Test FHIR ingestion rate (target: 10,000 resources/minute)
    - Test dataset assembly time (target: 100,000 rows in 2 minutes)
    - Test concurrent user load (target: 1000 concurrent users)
    - _Requirements: 17.1, 17.2, 17.3, 17.4_
  
  - [x] 24.4 Final checkpoint - Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Integration tests verify component interactions and end-to-end flows
- All backend code will be implemented in Python using FastAPI
- All frontend code will be implemented in TypeScript using React/Next.js
- The MVP focuses on CSV uploads, schema mapping, natural language queries, and dataset export
- FHIR integration is included but can be deprioritized if needed for MVP timeline
