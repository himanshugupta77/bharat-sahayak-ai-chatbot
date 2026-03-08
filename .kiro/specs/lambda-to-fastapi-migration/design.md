# Design Document: Lambda to FastAPI Migration

## Overview

This design document specifies the technical approach for migrating the Bharat Sahayak backend from AWS Lambda functions to a FastAPI application deployable on EC2 instances. The migration preserves all existing functionality, business logic, and AWS service integrations while transitioning from a serverless event-driven architecture to a traditional web server model.

### Migration Goals

- Remove Lambda-specific code (lambda_handler functions, API Gateway event parsing, Lambda context dependencies)
- Create a FastAPI application with equivalent endpoints and functionality
- Preserve all business logic, AWS service integrations, and security features
- Maintain API compatibility with existing frontend clients
- Enable deployment on EC2 instances using Uvicorn ASGI server

### Key Constraints

- Zero breaking changes to API contracts (request/response schemas, status codes, headers)
- All AWS service integrations must continue working (DynamoDB, Bedrock, Polly, Transcribe, Translate, S3)
- Security features must be preserved (input sanitization, rate limiting, PII detection, data minimization)
- Session management and caching behavior must remain identical
- Error handling and logging must maintain the same structure

## Architecture

### Current Architecture (Lambda-based)

```
API Gateway → Lambda Functions → AWS Services
                                  ├─ DynamoDB
                                  ├─ Bedrock
                                  ├─ Translate
                                  ├─ Polly
                                  ├─ Transcribe
                                  └─ S3
```

Each Lambda function:
- Receives API Gateway events with specific structure
- Parses event.body, event.headers, event.queryStringParameters
- Uses Lambda context for request metadata
- Returns API Gateway response format

### Target Architecture (FastAPI-based)

```
HTTP Client → FastAPI App → AWS Services
              (Uvicorn)      ├─ DynamoDB
                             ├─ Bedrock
                             ├─ Translate
                             ├─ Polly
                             ├─ Transcribe
                             └─ S3
```

FastAPI application:
- Receives standard HTTP requests
- Uses Pydantic models for request/response validation
- Leverages FastAPI dependency injection for shared resources
- Returns FastAPI Response objects
- Runs on Uvicorn ASGI server on EC2


### Migration Strategy

1. **Create FastAPI Application Entry Point** (main.py)
   - Initialize FastAPI app with metadata
   - Configure CORS middleware for cross-origin requests
   - Add request logging middleware
   - Add error handling middleware
   - Define Uvicorn server configuration

2. **Convert Lambda Handlers to FastAPI Routes**
   - Transform lambda_handler functions into FastAPI route handlers
   - Replace API Gateway event parsing with FastAPI request objects
   - Replace Lambda context with FastAPI dependencies
   - Maintain identical business logic

3. **Adapt Shared Utilities**
   - Modify error handling decorator to work with FastAPI exceptions
   - Adapt response creation functions for FastAPI Response objects
   - Preserve all AWS client initialization and utility functions

4. **Preserve Security and Privacy Features**
   - Keep all input sanitization logic
   - Maintain rate limiting using DynamoDB
   - Preserve PII detection and anonymization
   - Keep data minimization validation

## Components and Interfaces

### 1. FastAPI Application (main.py)

**Location:** `backend/src/main.py`

**Responsibilities:**
- Initialize FastAPI application
- Configure middleware (CORS, logging, error handling)
- Register all route handlers
- Configure Uvicorn server settings

**Key Components:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Bharat Sahayak API",
    description="Government welfare scheme discovery platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Custom middleware for logging and error handling
# Route registrations
# Uvicorn configuration
```

**Environment Variables:**
- `DYNAMODB_TABLE`: DynamoDB table name
- `S3_TEMP_BUCKET`: S3 bucket for temporary audio files
- `BEDROCK_MODEL_ID`: Bedrock model identifier
- `AWS_REGION`: AWS region
- `LOG_LEVEL`: Logging level (default: INFO)


### 2. Chat Route Handler

**Endpoint:** `POST /chat`

**Migration Changes:**
- Remove `lambda_handler(event, context)` signature
- Replace with `@app.post("/chat")` decorator and FastAPI route function
- Replace `parse_request_body(event)` with FastAPI `ChatRequest` parameter
- Replace `get_session_id_from_event(event)` with FastAPI `Header` dependency
- Replace `create_response()` with FastAPI `Response` return
- Preserve all business logic: session management, rate limiting, Bedrock calls, translation, scheme extraction

**Request Model:** `ChatRequest` (unchanged)
**Response Model:** `ChatResponse` (unchanged)

**Rate Limiting:**
- Preserve DynamoDB-based rate limiting (10 requests per 60 seconds per IP)
- Extract source IP from FastAPI `Request.client.host`
- Return 429 status with retry-after header when limit exceeded

### 3. Eligibility Route Handler

**Endpoint:** `POST /eligibility`

**Migration Changes:**
- Convert lambda_handler to FastAPI route handler
- Use FastAPI request validation with `EligibilityRequest` model
- Preserve rule-based eligibility evaluation engine
- Preserve data privacy and anonymization logic
- Maintain alternative scheme recommendation logic

**Request Model:** `EligibilityRequest` (unchanged)
**Response Model:** `EligibilityResponse` (unchanged)

**Data Privacy:**
- Preserve `anonymize_user_info()` call before processing
- Preserve `validate_data_minimization()` check
- Preserve `log_data_access()` for audit trail

### 4. Schemes Route Handlers

**Endpoints:**
- `GET /schemes` - List schemes with filtering and pagination
- `GET /schemes/{schemeId}` - Get scheme details

**Migration Changes:**
- Convert single lambda_handler with routing logic to two FastAPI route handlers
- Replace query parameter extraction from `event['queryStringParameters']` with FastAPI `Query` parameters
- Replace path parameter extraction from `event['pathParameters']` with FastAPI path parameters
- Preserve Lambda memory caching with module-level cache variables
- Preserve translation logic for multilingual support

**Query Parameters:**
- `/schemes`: category (optional), limit (default: 50), offset (default: 0), language (default: en)
- `/schemes/{schemeId}`: language (default: en)

**Caching:**
- Preserve 5-minute TTL for scheme list cache
- Preserve per-scheme caching
- Use module-level variables for cache storage (equivalent to Lambda memory)


### 5. Session Route Handlers

**Endpoints:**
- `GET /session/info` - Get session information and expiration status
- `DELETE /session` - Delete session data immediately

**Migration Changes:**
- Convert single lambda_handler with routing to two FastAPI route handlers
- Replace header extraction from `event['headers']` with FastAPI `Header` dependency
- Preserve session management logic from shared.session_manager
- Maintain session expiration warning logic

**Headers:**
- `X-Session-Id`: Required session identifier

### 6. Voice Route Handlers

**Endpoints:**
- `POST /voice/text-to-speech` - Generate speech audio using Amazon Polly
- `POST /voice/speech-to-text` - Transcribe audio using Amazon Transcribe

**Migration Changes:**
- Convert two separate lambda_handlers to two FastAPI route handlers
- Preserve Amazon Polly integration with voice mapping and engine selection
- Preserve Amazon Transcribe integration with language detection
- Preserve S3 temporary storage logic with 1-hour TTL
- Preserve audio format validation

**Request Models:**
- `TextToSpeechRequest` (unchanged)
- `VoiceToTextRequest` (unchanged)

**Response Models:**
- `TextToSpeechResponse` (unchanged)
- `VoiceToTextResponse` (unchanged)

### 7. Middleware Components

#### CORS Middleware
- Allow all origins (configurable via environment)
- Allow credentials
- Allow all methods and headers
- Preserve existing CORS behavior from API Gateway

#### Request Logging Middleware
- Log request start with correlation ID
- Log request completion with duration
- Log source IP, method, path, status code
- Preserve structured JSON logging format

#### Error Handling Middleware
- Catch all unhandled exceptions
- Return standardized error responses
- Log errors with correlation ID and stack trace
- Preserve error response format from Lambda handlers


### 8. Shared Utilities Adaptation

#### Error Handling Decorator

**Current (Lambda):**
```python
@handle_exceptions
def lambda_handler(event, context):
    # Returns API Gateway response dict
    return create_response(200, body)
```

**Migrated (FastAPI):**
```python
# Remove decorator, use FastAPI exception handlers instead
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Return FastAPI Response
    return JSONResponse(status_code=500, content=error_body)
```

#### Response Creation Functions

**Current:**
```python
def create_response(status_code, body, headers=None):
    return {
        'statusCode': status_code,
        'headers': headers or {},
        'body': json.dumps(body)
    }
```

**Migrated:**
```python
def create_response(status_code, body, headers=None):
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=headers
    )
```

#### AWS Client Initialization
- Preserve all `@lru_cache` decorated client getter functions
- No changes needed (boto3 clients work identically)

#### Utility Functions
- Preserve all sanitization functions
- Preserve all validation functions
- Preserve all timestamp and ID generation functions
- Preserve all logging functions

### 9. Shared Models

**No Changes Required:**
- All Pydantic models remain identical
- FastAPI uses Pydantic natively for request/response validation
- Models: ChatRequest, ChatResponse, EligibilityRequest, EligibilityResponse, etc.

### 10. Session Manager

**No Changes Required:**
- All session management functions remain identical
- DynamoDB operations work the same way
- Functions: create_session, get_session_info, delete_session_data, etc.

### 11. Data Privacy Module

**No Changes Required:**
- All privacy functions remain identical
- PII detection and sanitization logic unchanged
- Functions: detect_pii, sanitize_pii, anonymize_user_info, etc.


## Data Models

### Request/Response Models (Unchanged)

All Pydantic models from `shared/models.py` remain identical:

- `ChatRequest`: message, language
- `ChatResponse`: response, language, schemes, sessionId, sessionExpiring, sessionTimeRemaining
- `EligibilityRequest`: schemeId, userInfo
- `EligibilityResponse`: eligible, explanation, schemeDetails, alternativeSchemes
- `TextToSpeechRequest`: text, language, lowBandwidth
- `TextToSpeechResponse`: audioData, format, duration, sizeBytes
- `VoiceToTextRequest`: audioData, format
- `VoiceToTextResponse`: transcript, detectedLanguage, confidence
- `UserInfo`: age, gender, income, state, category, occupation, ownsLand, landSize, hasDisability, isBPL
- `SchemeCard`: id, name, description, eligibilitySummary, applicationSteps
- `SchemeDetails`: name, benefits, applicationProcess, requiredDocuments
- `EligibilityCriterion`: criterion, required, userValue, met
- `EligibilityExplanation`: criteria, summary
- `ErrorResponse`: error, message, field, requestId, timestamp, retryAfter

### Internal Models (Unchanged)

- `SessionMetadata`: sessionId, language, createdAt, lastAccessedAt, messageCount, ttl
- `Message`: messageId, role, content, timestamp, language, schemes
- `EligibilityRule`: criterion, type, requirement, evaluator
- `Scheme`: schemeId, name, description, category, eligibilityRules, benefits, etc.

### API Gateway Event → FastAPI Request Mapping

| Lambda (API Gateway Event) | FastAPI Equivalent |
|----------------------------|-------------------|
| `event['body']` | `request: ModelName` (automatic parsing) |
| `event['headers']['X-Session-Id']` | `session_id: str = Header(None, alias="X-Session-Id")` |
| `event['queryStringParameters']['limit']` | `limit: int = Query(50)` |
| `event['pathParameters']['schemeId']` | `scheme_id: str` (path parameter) |
| `event['requestContext']['identity']['sourceIp']` | `request.client.host` |
| `event['requestContext']['requestId']` | Generated correlation ID |
| `context` (Lambda context) | Not needed (removed) |


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: API Request Schema Compatibility

*For any* endpoint in the FastAPI application, when a request is made with the same body structure as the Lambda handler accepted, the FastAPI endpoint SHALL accept and validate the request successfully.

**Validates: Requirements 11.1, 3.2, 4.2, 7.3, 7.4**

### Property 2: API Response Schema Compatibility

*For any* successful request to a FastAPI endpoint, the response body structure SHALL match exactly the structure returned by the equivalent Lambda handler.

**Validates: Requirements 11.2, 3.8, 4.6, 5.8, 6.7, 7.9**

### Property 3: HTTP Status Code Preservation

*For any* request scenario (success, validation error, not found, rate limit, server error), the FastAPI endpoint SHALL return the same HTTP status code as the Lambda handler would have returned.

**Validates: Requirements 11.3, 3.8, 3.9, 3.10, 4.6, 4.7, 4.8, 5.8, 5.9, 6.7, 6.8, 7.9, 7.10**

### Property 4: Header Compatibility

*For any* request that includes headers (X-Session-Id, X-Correlation-Id), the FastAPI endpoint SHALL extract and process these headers identically to the Lambda handler.

**Validates: Requirements 11.5, 6.3, 6.4**

### Property 5: Query Parameter Compatibility

*For any* endpoint that accepts query parameters (category, limit, offset, language), the FastAPI endpoint SHALL process these parameters with the same defaults and validation as the Lambda handler.

**Validates: Requirements 11.4, 5.3, 5.4**

### Property 6: Chat Endpoint Functional Equivalence

*For any* valid chat request with message and language, the FastAPI /chat endpoint SHALL produce a response with the same AI-generated content, scheme recommendations, and session handling as the Lambda chat handler.

**Validates: Requirements 1.4, 3.3, 3.5, 3.6, 3.7**

### Property 7: Eligibility Endpoint Functional Equivalence

*For any* valid eligibility request with schemeId and userInfo, the FastAPI /eligibility endpoint SHALL produce the same eligibility decision, criteria evaluation, and alternative recommendations as the Lambda eligibility handler.

**Validates: Requirements 1.4, 4.3, 4.5**

### Property 8: Schemes Endpoint Functional Equivalence

*For any* schemes list or detail request, the FastAPI /schemes endpoints SHALL return the same scheme data, apply the same translations, and use the same pagination logic as the Lambda schemes handler.

**Validates: Requirements 1.4, 5.5, 5.6, 5.7**

### Property 9: Session Endpoint Functional Equivalence

*For any* session info or deletion request, the FastAPI /session endpoints SHALL retrieve or delete session data identically to the Lambda session handler.

**Validates: Requirements 1.4, 6.5, 6.6**

### Property 10: Voice Endpoints Functional Equivalence

*For any* text-to-speech or speech-to-text request, the FastAPI /voice endpoints SHALL produce the same audio output or transcript using the same AWS service integrations as the Lambda voice handlers.

**Validates: Requirements 1.4, 7.5, 7.6, 7.7**


### Property 11: AWS Service Integration Preservation

*For any* AWS service call (DynamoDB, Bedrock, Translate, Polly, Transcribe, S3), the FastAPI application SHALL use the same boto3 client initialization and produce the same service interactions as the Lambda handlers.

**Validates: Requirements 1.5, 8.7**

### Property 12: Input Sanitization Preservation

*For any* user input (message, text, userInfo fields), the FastAPI application SHALL apply the same sanitization logic (HTML escaping, null byte removal, length validation) as the Lambda handlers.

**Validates: Requirements 12.1, 12.6**

### Property 13: Rate Limiting Preservation

*For any* sequence of requests from the same IP address, the FastAPI application SHALL enforce the same rate limit (10 requests per 60 seconds) using DynamoDB tracking as the Lambda chat handler.

**Validates: Requirements 3.4, 12.2**

### Property 14: PII Detection and Anonymization Preservation

*For any* user information or message content containing PII (Aadhaar, PAN, phone, email), the FastAPI application SHALL detect and anonymize the PII identically to the Lambda handlers.

**Validates: Requirements 4.4, 12.3**

### Property 15: Data Minimization Preservation

*For any* eligibility request, the FastAPI application SHALL validate that only essential fields are present and reject requests with prohibited fields, identical to the Lambda eligibility handler.

**Validates: Requirements 12.4**

### Property 16: Security Event Logging Preservation

*For any* security-relevant event (rate limit exceeded, PII detected, validation failure), the FastAPI application SHALL log the event with the same structured format as the Lambda handlers.

**Validates: Requirements 12.5**

### Property 17: CORS Configuration

*For any* cross-origin request, the FastAPI application SHALL include CORS headers (Access-Control-Allow-Origin, Access-Control-Allow-Methods, Access-Control-Allow-Headers) in the response.

**Validates: Requirements 2.2, 12.7**

### Property 18: Request Logging

*For any* request to the FastAPI application, the system SHALL log the request start, completion, duration, status code, and correlation ID in structured JSON format.

**Validates: Requirements 2.3**

### Property 19: Error Handling

*For any* unhandled exception in a FastAPI route handler, the error handling middleware SHALL catch the exception, log it with correlation ID and stack trace, and return a standardized error response.

**Validates: Requirements 2.4, 8.5**

### Property 20: Error Response Format Preservation

*For any* error condition (validation, not found, rate limit, server error), the FastAPI application SHALL return an error response with the same structure (error, message, field, requestId, timestamp, retryAfter) as the Lambda handlers.

**Validates: Requirements 11.6**


### Property 21: Cache Behavior Preservation

*For any* schemes list request within 5 minutes of a previous request, the FastAPI application SHALL return cached data without querying DynamoDB, identical to the Lambda schemes handler caching behavior.

**Validates: Requirements 5.5**

### Property 22: Session Management Preservation

*For any* session operation (create, retrieve, update, delete), the FastAPI application SHALL use the same DynamoDB operations and TTL logic as the Lambda handlers.

**Validates: Requirements 8.3**

### Property 23: Audio Format Validation Preservation

*For any* voice request with an audio format parameter, the FastAPI application SHALL validate the format against the same allowed values (webm, mp3, wav) and reject invalid formats with the same error message as the Lambda voice handlers.

**Validates: Requirements 7.8**

## Error Handling

### Error Categories

1. **Validation Errors (400)**
   - Invalid request body structure
   - Missing required fields
   - Field value out of range
   - Invalid format (language code, scheme ID, audio format)
   - Empty or whitespace-only input
   - Input exceeds maximum length

2. **Authentication/Authorization Errors (401/403)**
   - Not applicable in current design (no authentication)

3. **Not Found Errors (404)**
   - Scheme not found
   - Session not found (returns exists: false instead of 404)

4. **Rate Limiting Errors (429)**
   - Too many requests from same IP
   - Includes retry-after header with seconds to wait

5. **Server Errors (500)**
   - AWS service errors (DynamoDB, Bedrock, Translate, Polly, Transcribe, S3)
   - Unexpected exceptions
   - Configuration errors (missing environment variables)

### Error Response Format

All errors return a standardized JSON structure:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message",
  "field": "fieldName",  // Optional, for validation errors
  "requestId": "correlation-id",  // Optional
  "timestamp": 1234567890,
  "retryAfter": 60  // Optional, for rate limiting
}
```

### Error Handling Strategy

1. **FastAPI Exception Handlers**
   - Register global exception handler for `Exception`
   - Register specific handlers for `RequestValidationError`, `HTTPException`
   - Log all errors with correlation ID and stack trace

2. **Validation Errors**
   - FastAPI automatically validates request bodies using Pydantic models
   - Custom validation errors raised as `ValueError` in utility functions
   - Caught by exception handler and converted to 400 response

3. **AWS Service Errors**
   - Caught by exception handler
   - Logged with service name and error details
   - Converted to 500 response with generic message (don't expose internal details)

4. **Rate Limiting**
   - Implemented as dependency function
   - Raises `HTTPException(429)` when limit exceeded
   - Includes retry-after header


## Testing Strategy

### Dual Testing Approach

The migration requires both unit tests and property-based tests to ensure correctness:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

Both approaches are complementary and necessary for comprehensive coverage. Unit tests catch concrete bugs in specific scenarios, while property tests verify general correctness across a wide range of inputs.

### Unit Testing

**Focus Areas:**
- Specific endpoint examples (successful requests with known inputs/outputs)
- Edge cases (empty input, maximum length, boundary values)
- Error conditions (missing headers, invalid formats, not found scenarios)
- Integration points (middleware execution order, exception handler registration)
- Configuration (environment variable loading, AWS client initialization)

**Example Unit Tests:**
- Test POST /chat with valid message returns 200 with ChatResponse
- Test POST /chat with empty message returns 400
- Test POST /chat without X-Session-Id header creates new session
- Test GET /schemes with category filter returns only matching schemes
- Test GET /schemes/{schemeId} with non-existent ID returns 404
- Test POST /eligibility with prohibited field returns 400
- Test rate limiting: 11th request within 60 seconds returns 429
- Test CORS headers present in all responses
- Test error handler catches unhandled exceptions and returns 500

**Unit Test Organization:**
```
backend/src/tests/
├── test_main.py              # Application initialization, middleware
├── test_chat_routes.py       # Chat endpoint tests
├── test_eligibility_routes.py # Eligibility endpoint tests
├── test_schemes_routes.py    # Schemes endpoint tests
├── test_session_routes.py    # Session endpoint tests
├── test_voice_routes.py      # Voice endpoint tests
└── test_migration.py         # Migration-specific tests
```

### Property-Based Testing

**Configuration:**
- Use Hypothesis library (already in requirements.txt)
- Minimum 100 iterations per property test
- Each test references its design document property

**Property Test Tag Format:**
```python
# Feature: lambda-to-fastapi-migration, Property 1: API Request Schema Compatibility
```

**Property Test Examples:**

1. **API Request Schema Compatibility (Property 1)**
   - Generate random valid ChatRequest, EligibilityRequest, etc.
   - Send to FastAPI endpoint
   - Verify request is accepted (not 400)

2. **API Response Schema Compatibility (Property 2)**
   - Generate random valid requests
   - Send to both Lambda handler (mocked) and FastAPI endpoint
   - Verify response structures match

3. **HTTP Status Code Preservation (Property 3)**
   - Generate random requests (valid and invalid)
   - Compare status codes from Lambda vs FastAPI

4. **Input Sanitization Preservation (Property 12)**
   - Generate random strings with HTML, null bytes, control characters
   - Verify sanitization produces same output

5. **PII Detection Preservation (Property 14)**
   - Generate random text with and without PII patterns
   - Verify detection and anonymization match

6. **Rate Limiting Preservation (Property 13)**
   - Generate random sequences of requests from same IP
   - Verify rate limit enforcement matches

7. **Cache Behavior Preservation (Property 21)**
   - Generate random scheme requests
   - Verify caching behavior (cache hits within TTL, misses after)

**Property Test Organization:**
```
backend/src/tests/properties/
├── test_api_compatibility.py      # Properties 1-5
├── test_functional_equivalence.py # Properties 6-10
├── test_security_preservation.py  # Properties 12-16
├── test_infrastructure.py         # Properties 17-20
└── test_caching_sessions.py       # Properties 21-23
```


### Migration Verification Tests

**Purpose:** Verify that the migration was successful and no functionality was lost.

**Test Categories:**

1. **Endpoint Existence Tests**
   - Verify all endpoints are registered
   - Verify correct HTTP methods
   - Verify path parameters and query parameters

2. **Lambda Code Removal Tests**
   - Verify no `lambda_handler` functions exist in codebase
   - Verify no API Gateway event parsing (`event['body']`, `event['headers']`)
   - Verify no Lambda context usage

3. **Shared Module Preservation Tests**
   - Verify all Pydantic models unchanged
   - Verify all utility functions unchanged
   - Verify all AWS client functions unchanged

4. **Dependency Tests**
   - Verify requirements.txt includes fastapi, uvicorn, python-multipart
   - Verify all existing dependencies preserved
   - Verify application starts successfully

5. **Integration Tests**
   - Test complete request/response flow for each endpoint
   - Test with real AWS services (using test environment)
   - Test error scenarios end-to-end

### Test Execution

**Local Testing:**
```bash
# Run unit tests
pytest backend/src/tests/ -v

# Run property tests
pytest backend/src/tests/properties/ -v --hypothesis-show-statistics

# Run with coverage
pytest backend/src/tests/ --cov=backend/src --cov-report=html
```

**CI/CD Testing:**
- Run all tests on every commit
- Require 100% pass rate before merge
- Generate coverage reports
- Run property tests with increased iterations (1000+) on main branch

### Test Data

**Fixtures:**
- Sample ChatRequest, EligibilityRequest, etc.
- Sample scheme data
- Sample session data
- Sample AWS service responses (mocked)

**Generators (for property tests):**
- Random valid Pydantic models
- Random strings with various characteristics (PII, HTML, control chars)
- Random IP addresses for rate limiting
- Random timestamps for caching tests

## Deployment Considerations

### EC2 Instance Requirements

**Minimum Specifications:**
- Instance Type: t3.medium or larger
- vCPUs: 2+
- Memory: 4GB+
- Storage: 20GB+ EBS volume
- Network: Enhanced networking enabled

**Operating System:**
- Amazon Linux 2023 or Ubuntu 22.04 LTS
- Python 3.11 or 3.12 installed

### Installation Steps

1. **Install Dependencies**
```bash
cd backend
pip install -r requirements.txt
```

2. **Configure Environment Variables**
```bash
export DYNAMODB_TABLE=bharat-sahayak-table
export S3_TEMP_BUCKET=bharat-sahayak-temp
export BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
export AWS_REGION=ap-south-1
export LOG_LEVEL=INFO
```

3. **Start Application**
```bash
cd backend/src
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Production Configuration

**Uvicorn Settings:**
- Workers: 4-8 (based on CPU cores)
- Worker class: uvicorn.workers.UvicornWorker
- Timeout: 60 seconds
- Keep-alive: 5 seconds
- Max requests per worker: 10000 (restart workers periodically)

**Process Management:**
- Use systemd service for automatic restart
- Configure health check endpoint
- Set up log rotation

**Security:**
- Run as non-root user
- Configure security groups (allow port 8000 from load balancer only)
- Enable AWS IAM role for EC2 instance (no hardcoded credentials)
- Use AWS Systems Manager Parameter Store for sensitive configuration

**Monitoring:**
- CloudWatch Logs for application logs
- CloudWatch Metrics for request rate, latency, errors
- CloudWatch Alarms for error rate thresholds
- X-Ray for distributed tracing (optional)

### Load Balancing

**Application Load Balancer:**
- Target group: EC2 instances on port 8000
- Health check: GET /health (to be implemented)
- Health check interval: 30 seconds
- Healthy threshold: 2
- Unhealthy threshold: 3
- Timeout: 5 seconds

**Auto Scaling:**
- Minimum instances: 2
- Maximum instances: 10
- Target CPU utilization: 70%
- Scale-out cooldown: 300 seconds
- Scale-in cooldown: 600 seconds


## Migration Checklist

### Phase 1: Setup and Configuration

- [ ] Create main.py with FastAPI application initialization
- [ ] Configure CORS middleware
- [ ] Implement request logging middleware
- [ ] Implement error handling middleware
- [ ] Update requirements.txt with fastapi, uvicorn, python-multipart
- [ ] Create .env.example with required environment variables

### Phase 2: Route Migration

- [ ] Convert chat handler to POST /chat route
- [ ] Convert eligibility handler to POST /eligibility route
- [ ] Convert schemes handler to GET /schemes and GET /schemes/{schemeId} routes
- [ ] Convert session handler to GET /session/info and DELETE /session routes
- [ ] Convert voice handlers to POST /voice/text-to-speech and POST /voice/speech-to-text routes

### Phase 3: Utility Adaptation

- [ ] Adapt error handling decorator to FastAPI exception handlers
- [ ] Adapt response creation functions for FastAPI Response objects
- [ ] Verify AWS client initialization functions work unchanged
- [ ] Verify all utility functions work unchanged

### Phase 4: Testing

- [ ] Write unit tests for each endpoint
- [ ] Write property tests for API compatibility
- [ ] Write property tests for functional equivalence
- [ ] Write property tests for security preservation
- [ ] Write migration verification tests
- [ ] Run all tests and achieve 100% pass rate

### Phase 5: Deployment Preparation

- [ ] Create systemd service file
- [ ] Create deployment scripts
- [ ] Document environment variables
- [ ] Create health check endpoint
- [ ] Test local deployment with uvicorn
- [ ] Test EC2 deployment in staging environment

### Phase 6: Production Deployment

- [ ] Deploy to production EC2 instances
- [ ] Configure load balancer
- [ ] Configure auto scaling
- [ ] Set up monitoring and alarms
- [ ] Verify all endpoints working
- [ ] Monitor error rates and latency
- [ ] Remove Lambda functions after successful migration

## Rollback Plan

If issues are discovered after deployment:

1. **Immediate Rollback**
   - Switch load balancer target group back to Lambda functions
   - Investigate issues in staging environment

2. **Issue Categories and Responses**
   - **High error rate**: Rollback immediately
   - **Performance degradation**: Scale up EC2 instances, then investigate
   - **Specific endpoint failure**: Disable endpoint, rollback if critical
   - **AWS service integration issue**: Check IAM permissions, rollback if unresolvable

3. **Post-Rollback Actions**
   - Analyze logs and metrics
   - Reproduce issue in staging
   - Fix issue and re-test
   - Plan new deployment

## Success Criteria

The migration is considered successful when:

1. **Functional Criteria**
   - All endpoints return correct responses for valid requests
   - All error scenarios return appropriate status codes and messages
   - All AWS service integrations work correctly
   - Session management works identically to Lambda version
   - Caching behavior matches Lambda version

2. **Performance Criteria**
   - Average response time ≤ Lambda version + 50ms
   - 99th percentile response time ≤ Lambda version + 100ms
   - Error rate ≤ 0.1%
   - Throughput ≥ Lambda version

3. **Security Criteria**
   - All input sanitization working
   - Rate limiting enforced correctly
   - PII detection and anonymization working
   - Security event logging working
   - No security vulnerabilities introduced

4. **Operational Criteria**
   - Application starts successfully on EC2
   - Health checks passing
   - Logs being written to CloudWatch
   - Metrics being reported to CloudWatch
   - Auto scaling working correctly
   - Zero downtime during deployment

5. **Testing Criteria**
   - All unit tests passing
   - All property tests passing (100 iterations minimum)
   - All migration verification tests passing
   - Integration tests passing with real AWS services

## Appendix: FastAPI vs Lambda Comparison

### Request Handling

| Aspect | Lambda | FastAPI |
|--------|--------|---------|
| Entry point | `lambda_handler(event, context)` | `@app.post("/path")` decorated function |
| Request body | `json.loads(event['body'])` | Automatic Pydantic validation |
| Headers | `event['headers']['X-Header']` | `Header(alias="X-Header")` dependency |
| Query params | `event['queryStringParameters']['param']` | `Query()` parameter |
| Path params | `event['pathParameters']['param']` | Function parameter |
| Response | Dict with statusCode, headers, body | Return Pydantic model or Response object |

### Middleware

| Aspect | Lambda | FastAPI |
|--------|--------|---------|
| CORS | API Gateway configuration | `CORSMiddleware` |
| Logging | Decorator on handler | Middleware function |
| Error handling | Decorator on handler | Exception handlers |
| Rate limiting | Inside handler logic | Dependency function |

### Deployment

| Aspect | Lambda | FastAPI |
|--------|--------|---------|
| Runtime | AWS Lambda | Uvicorn ASGI server |
| Scaling | Automatic | Auto Scaling Group |
| Cold starts | Yes (100-1000ms) | No |
| Timeout | 15 minutes max | Configurable (no limit) |
| Memory | 128MB - 10GB | EC2 instance memory |
| Cost model | Per request + duration | Per instance hour |

