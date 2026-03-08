# Requirements Document

## Introduction

This document specifies the requirements for migrating an AWS Lambda-based backend to a FastAPI application deployable on EC2 instances. The migration will convert Lambda handler functions into FastAPI route handlers while preserving all existing business logic, data models, and AWS service integrations.

## Glossary

- **Lambda_Handler**: AWS Lambda function entry point that processes API Gateway events
- **FastAPI_Application**: ASGI web application framework for building APIs with Python
- **Route_Handler**: FastAPI endpoint function that processes HTTP requests
- **EC2_Instance**: Amazon Elastic Compute Cloud virtual server
- **Uvicorn**: ASGI server implementation for running FastAPI applications
- **API_Gateway_Event**: AWS-specific event structure passed to Lambda functions
- **HTTP_Request**: Standard HTTP request object used by FastAPI
- **Session_Manager**: Component managing user session state and lifecycle
- **DynamoDB_Client**: AWS SDK client for DynamoDB database operations
- **Bedrock_Client**: AWS SDK client for Amazon Bedrock AI services
- **Polly_Client**: AWS SDK client for Amazon Polly text-to-speech
- **Transcribe_Client**: AWS SDK client for Amazon Transcribe speech-to-text
- **Translate_Client**: AWS SDK client for Amazon Translate translation services
- **S3_Client**: AWS SDK client for Amazon S3 storage operations

## Requirements

### Requirement 1: Remove Lambda Handler Architecture

**User Story:** As a developer, I want to remove AWS Lambda-specific handler code, so that the application can run on standard compute instances.

#### Acceptance Criteria

1. THE Migration_Process SHALL remove all lambda_handler function definitions from the codebase
2. THE Migration_Process SHALL remove all API Gateway event parsing logic
3. THE Migration_Process SHALL remove all Lambda context object dependencies
4. THE Migration_Process SHALL preserve all business logic from Lambda handlers
5. THE Migration_Process SHALL preserve all AWS service client integrations (DynamoDB, Bedrock, Polly, Transcribe, Translate, S3)

### Requirement 2: Create FastAPI Application Entry Point

**User Story:** As a developer, I want a main.py file with FastAPI application setup, so that I can run the backend as a standard web server.

#### Acceptance Criteria

1. THE Migration_Process SHALL create a main.py file in the backend/src directory
2. THE FastAPI_Application SHALL initialize with proper CORS middleware configuration
3. THE FastAPI_Application SHALL include request logging middleware
4. THE FastAPI_Application SHALL include error handling middleware
5. THE FastAPI_Application SHALL configure Uvicorn server to listen on host 0.0.0.0 and port 8000
6. THE FastAPI_Application SHALL support graceful shutdown

### Requirement 3: Convert Chat Handler to FastAPI Route

**User Story:** As a developer, I want the chat Lambda handler converted to a FastAPI POST endpoint, so that clients can send chat messages via HTTP.

#### Acceptance Criteria

1. THE FastAPI_Application SHALL expose a POST /chat endpoint
2. WHEN a POST request is received at /chat, THE Route_Handler SHALL accept ChatRequest in the request body
3. THE Route_Handler SHALL preserve all session management logic from the Lambda handler
4. THE Route_Handler SHALL preserve all rate limiting logic from the Lambda handler
5. THE Route_Handler SHALL preserve all AI response generation logic using Bedrock
6. THE Route_Handler SHALL preserve all translation logic using Amazon Translate
7. THE Route_Handler SHALL preserve all scheme extraction and recommendation logic
8. THE Route_Handler SHALL return ChatResponse with HTTP status 200 on success
9. IF rate limit is exceeded, THEN THE Route_Handler SHALL return HTTP status 429
10. IF validation fails, THEN THE Route_Handler SHALL return HTTP status 400

### Requirement 4: Convert Eligibility Handler to FastAPI Route

**User Story:** As a developer, I want the eligibility Lambda handler converted to a FastAPI POST endpoint, so that clients can check scheme eligibility via HTTP.

#### Acceptance Criteria

1. THE FastAPI_Application SHALL expose a POST /eligibility endpoint
2. WHEN a POST request is received at /eligibility, THE Route_Handler SHALL accept EligibilityRequest in the request body
3. THE Route_Handler SHALL preserve all rule-based eligibility evaluation logic
4. THE Route_Handler SHALL preserve all data privacy and anonymization logic
5. THE Route_Handler SHALL preserve all alternative scheme recommendation logic
6. THE Route_Handler SHALL return EligibilityResponse with HTTP status 200 on success
7. IF scheme is not found, THEN THE Route_Handler SHALL return HTTP status 404
8. IF validation fails, THEN THE Route_Handler SHALL return HTTP status 400

### Requirement 5: Convert Schemes Handler to FastAPI Routes

**User Story:** As a developer, I want the schemes Lambda handler converted to FastAPI GET endpoints, so that clients can retrieve scheme information via HTTP.

#### Acceptance Criteria

1. THE FastAPI_Application SHALL expose a GET /schemes endpoint for listing schemes
2. THE FastAPI_Application SHALL expose a GET /schemes/{schemeId} endpoint for scheme details
3. WHEN a GET request is received at /schemes, THE Route_Handler SHALL support category, limit, offset, and language query parameters
4. WHEN a GET request is received at /schemes/{schemeId}, THE Route_Handler SHALL support language query parameter
5. THE Route_Handler SHALL preserve all caching logic with 5-minute TTL
6. THE Route_Handler SHALL preserve all translation logic for multilingual support
7. THE Route_Handler SHALL preserve all pagination logic
8. THE Route_Handler SHALL return scheme data with HTTP status 200 on success
9. IF scheme is not found, THEN THE Route_Handler SHALL return HTTP status 404

### Requirement 6: Convert Session Handler to FastAPI Routes

**User Story:** As a developer, I want the session Lambda handler converted to FastAPI endpoints, so that clients can manage sessions via HTTP.

#### Acceptance Criteria

1. THE FastAPI_Application SHALL expose a GET /session/info endpoint
2. THE FastAPI_Application SHALL expose a DELETE /session endpoint
3. WHEN a GET request is received at /session/info, THE Route_Handler SHALL extract session ID from X-Session-Id header
4. WHEN a DELETE request is received at /session, THE Route_Handler SHALL extract session ID from X-Session-Id header
5. THE Route_Handler SHALL preserve all session information retrieval logic
6. THE Route_Handler SHALL preserve all session deletion logic
7. THE Route_Handler SHALL return session information with HTTP status 200 on success
8. IF session ID is missing, THEN THE Route_Handler SHALL return HTTP status 400

### Requirement 7: Convert Voice Handlers to FastAPI Routes

**User Story:** As a developer, I want the voice Lambda handlers converted to FastAPI POST endpoints, so that clients can use voice features via HTTP.

#### Acceptance Criteria

1. THE FastAPI_Application SHALL expose a POST /voice/text-to-speech endpoint
2. THE FastAPI_Application SHALL expose a POST /voice/speech-to-text endpoint
3. WHEN a POST request is received at /voice/text-to-speech, THE Route_Handler SHALL accept TextToSpeechRequest in the request body
4. WHEN a POST request is received at /voice/speech-to-text, THE Route_Handler SHALL accept VoiceToTextRequest in the request body
5. THE Route_Handler SHALL preserve all Amazon Polly integration logic
6. THE Route_Handler SHALL preserve all Amazon Transcribe integration logic
7. THE Route_Handler SHALL preserve all S3 temporary storage logic
8. THE Route_Handler SHALL preserve all audio format validation logic
9. THE Route_Handler SHALL return audio data or transcript with HTTP status 200 on success
10. IF audio quality is too low, THEN THE Route_Handler SHALL return HTTP status 400

### Requirement 8: Preserve Shared Module Functionality

**User Story:** As a developer, I want all shared utilities and models preserved, so that the migrated application maintains the same functionality.

#### Acceptance Criteria

1. THE Migration_Process SHALL preserve all Pydantic models from shared.models
2. THE Migration_Process SHALL preserve all utility functions from shared.utils
3. THE Migration_Process SHALL preserve all session management logic from shared.session_manager
4. THE Migration_Process SHALL preserve all data privacy functions from shared.data_privacy
5. THE Migration_Process SHALL adapt error handling decorators to work with FastAPI
6. THE Migration_Process SHALL adapt response creation functions to return FastAPI Response objects
7. THE Migration_Process SHALL preserve all AWS client initialization functions

### Requirement 9: Configure Dependencies

**User Story:** As a developer, I want a requirements.txt file with all necessary dependencies, so that I can install the application on EC2.

#### Acceptance Criteria

1. THE Migration_Process SHALL create or update requirements.txt in the backend directory
2. THE requirements.txt SHALL include fastapi with version specification
3. THE requirements.txt SHALL include uvicorn with version specification and standard extras
4. THE requirements.txt SHALL include python-multipart for form data support
5. THE requirements.txt SHALL preserve all existing dependencies (boto3, pydantic, langdetect, bleach, python-dateutil, hypothesis)
6. THE requirements.txt SHALL specify compatible version ranges for all dependencies

### Requirement 10: Enable EC2 Deployment

**User Story:** As a developer, I want the application to run on EC2 instances, so that I can deploy without Lambda constraints.

#### Acceptance Criteria

1. THE FastAPI_Application SHALL start successfully with the command: uvicorn main:app --host 0.0.0.0 --port 8000
2. THE FastAPI_Application SHALL accept HTTP requests on port 8000
3. THE FastAPI_Application SHALL support environment variable configuration for AWS credentials
4. THE FastAPI_Application SHALL support environment variable configuration for DynamoDB table names
5. THE FastAPI_Application SHALL support environment variable configuration for S3 bucket names
6. THE FastAPI_Application SHALL support environment variable configuration for AWS region
7. THE FastAPI_Application SHALL log startup information including host and port

### Requirement 11: Maintain API Compatibility

**User Story:** As a frontend developer, I want the API endpoints to maintain the same request/response format, so that existing clients continue to work without changes.

#### Acceptance Criteria

1. THE FastAPI_Application SHALL accept the same request body schemas as Lambda handlers
2. THE FastAPI_Application SHALL return the same response body schemas as Lambda handlers
3. THE FastAPI_Application SHALL use the same HTTP status codes as Lambda handlers
4. THE FastAPI_Application SHALL support the same query parameters as Lambda handlers
5. THE FastAPI_Application SHALL support the same headers as Lambda handlers (X-Session-Id, X-Correlation-Id)
6. THE FastAPI_Application SHALL maintain the same error response format

### Requirement 12: Preserve Security Features

**User Story:** As a security engineer, I want all security features preserved, so that the migrated application maintains the same security posture.

#### Acceptance Criteria

1. THE FastAPI_Application SHALL preserve all input sanitization logic
2. THE FastAPI_Application SHALL preserve all rate limiting logic
3. THE FastAPI_Application SHALL preserve all PII detection and anonymization logic
4. THE FastAPI_Application SHALL preserve all data minimization validation
5. THE FastAPI_Application SHALL preserve all security event logging
6. THE FastAPI_Application SHALL preserve all request validation using Pydantic models
7. THE FastAPI_Application SHALL include CORS configuration with appropriate origins
