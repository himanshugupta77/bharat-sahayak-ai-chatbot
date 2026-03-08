# Implementation Plan: Lambda to FastAPI Migration

## Overview

This implementation plan converts the Bharat Sahayak backend from AWS Lambda functions to a FastAPI application deployable on EC2 instances. The migration preserves all existing functionality, business logic, AWS service integrations, and security features while transitioning from serverless event-driven architecture to a traditional web server model.

## Tasks

- [x] 1. Set up FastAPI application structure and core configuration
  - Create backend/src/main.py with FastAPI application initialization
  - Configure application metadata (title, description, version)
  - Set up CORS middleware with appropriate origins
  - Implement request logging middleware for structured JSON logging
  - Implement global error handling middleware
  - Create health check endpoint (GET /health)
  - Update backend/requirements.txt to include fastapi, uvicorn[standard], and python-multipart
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

- [ ]* 1.1 Write property test for CORS configuration
  - **Property 17: CORS Configuration**
  - **Validates: Requirements 2.2, 12.7**

- [ ]* 1.2 Write property test for request logging
  - **Property 18: Request Logging**
  - **Validates: Requirements 2.3**

- [ ]* 1.3 Write property test for error handling middleware
  - **Property 19: Error Handling**
  - **Validates: Requirements 2.4, 8.5**

- [x] 2. Convert chat Lambda handler to FastAPI route
  - [x] 2.1 Create backend/src/routes/chat.py with POST /chat endpoint
    - Remove lambda_handler function signature
    - Replace API Gateway event parsing with FastAPI Request and ChatRequest model
    - Extract session ID from X-Session-Id header using FastAPI Header dependency
    - Extract source IP from request.client.host for rate limiting
    - Preserve all session management logic (create, retrieve, update)
    - Preserve rate limiting logic (10 requests per 60 seconds per IP using DynamoDB)
    - Preserve AI response generation using Amazon Bedrock
    - Preserve translation logic using Amazon Translate
    - Preserve scheme extraction and recommendation logic
    - Return ChatResponse with appropriate HTTP status codes (200, 400, 429)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [ ]* 2.2 Write property test for chat endpoint request schema compatibility
    - **Property 1: API Request Schema Compatibility**
    - **Validates: Requirements 11.1, 3.2**

  - [ ]* 2.3 Write property test for chat endpoint response schema compatibility
    - **Property 2: API Response Schema Compatibility**
    - **Validates: Requirements 11.2, 3.8**

  - [ ]* 2.4 Write property test for chat endpoint functional equivalence
    - **Property 6: Chat Endpoint Functional Equivalence**
    - **Validates: Requirements 1.4, 3.3, 3.5, 3.6, 3.7**

  - [ ]* 2.5 Write property test for rate limiting preservation
    - **Property 13: Rate Limiting Preservation**
    - **Validates: Requirements 3.4, 12.2**

  - [ ]* 2.6 Write unit tests for chat endpoint
    - Test successful chat request with valid message
    - Test empty message returns 400
    - Test rate limit exceeded returns 429 with retry-after header
    - Test session creation when X-Session-Id not provided
    - Test session expiration warning in response
    - _Requirements: 3.8, 3.9, 3.10_

- [x] 3. Convert eligibility Lambda handler to FastAPI route
  - [x] 3.1 Create backend/src/routes/eligibility.py with POST /eligibility endpoint
    - Remove lambda_handler function signature
    - Replace API Gateway event parsing with FastAPI Request and EligibilityRequest model
    - Preserve rule-based eligibility evaluation engine
    - Preserve data privacy and anonymization logic (anonymize_user_info)
    - Preserve data minimization validation (validate_data_minimization)
    - Preserve alternative scheme recommendation logic
    - Preserve audit logging (log_data_access)
    - Return EligibilityResponse with appropriate HTTP status codes (200, 400, 404)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ]* 3.2 Write property test for eligibility endpoint request schema compatibility
    - **Property 1: API Request Schema Compatibility**
    - **Validates: Requirements 11.1, 4.2**

  - [ ]* 3.3 Write property test for eligibility endpoint response schema compatibility
    - **Property 2: API Response Schema Compatibility**
    - **Validates: Requirements 11.2, 4.6**

  - [ ]* 3.4 Write property test for eligibility endpoint functional equivalence
    - **Property 7: Eligibility Endpoint Functional Equivalence**
    - **Validates: Requirements 1.4, 4.3, 4.5**

  - [ ]* 3.5 Write property test for PII detection and anonymization preservation
    - **Property 14: PII Detection and Anonymization Preservation**
    - **Validates: Requirements 4.4, 12.3**

  - [ ]* 3.6 Write property test for data minimization preservation
    - **Property 15: Data Minimization Preservation**
    - **Validates: Requirements 12.4**

  - [ ]* 3.7 Write unit tests for eligibility endpoint
    - Test successful eligibility check with valid request
    - Test scheme not found returns 404
    - Test validation failure returns 400
    - Test prohibited field in request returns 400
    - Test PII anonymization in logs
    - _Requirements: 4.6, 4.7, 4.8_

- [x] 4. Convert schemes Lambda handler to FastAPI routes
  - [x] 4.1 Create backend/src/routes/schemes.py with GET /schemes and GET /schemes/{schemeId} endpoints
    - Remove lambda_handler function with routing logic
    - Create separate route handlers for list and detail endpoints
    - Replace query parameter extraction with FastAPI Query parameters (category, limit, offset, language)
    - Replace path parameter extraction with FastAPI path parameter (schemeId)
    - Preserve module-level cache variables for 5-minute TTL caching
    - Preserve translation logic for multilingual support
    - Preserve pagination logic (limit, offset)
    - Return scheme data with appropriate HTTP status codes (200, 404)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [ ]* 4.2 Write property test for schemes endpoint query parameter compatibility
    - **Property 5: Query Parameter Compatibility**
    - **Validates: Requirements 11.4, 5.3, 5.4**

  - [ ]* 4.3 Write property test for schemes endpoint response schema compatibility
    - **Property 2: API Response Schema Compatibility**
    - **Validates: Requirements 11.2, 5.8**

  - [ ]* 4.4 Write property test for schemes endpoint functional equivalence
    - **Property 8: Schemes Endpoint Functional Equivalence**
    - **Validates: Requirements 1.4, 5.5, 5.6, 5.7**

  - [ ]* 4.5 Write property test for cache behavior preservation
    - **Property 21: Cache Behavior Preservation**
    - **Validates: Requirements 5.5**

  - [ ]* 4.6 Write unit tests for schemes endpoints
    - Test GET /schemes returns list with pagination
    - Test GET /schemes with category filter
    - Test GET /schemes with language parameter
    - Test GET /schemes/{schemeId} returns scheme details
    - Test GET /schemes/{schemeId} with non-existent ID returns 404
    - Test caching behavior (cache hit within TTL)
    - _Requirements: 5.8, 5.9_

- [x] 5. Convert session Lambda handler to FastAPI routes
  - [x] 5.1 Create backend/src/routes/session.py with GET /session/info and DELETE /session endpoints
    - Remove lambda_handler function with routing logic
    - Create separate route handlers for info and delete operations
    - Extract session ID from X-Session-Id header using FastAPI Header dependency
    - Preserve session information retrieval logic (get_session_info)
    - Preserve session deletion logic (delete_session_data)
    - Preserve session expiration warning logic
    - Return session information or deletion confirmation with appropriate HTTP status codes (200, 400)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [ ]* 5.2 Write property test for session endpoint header compatibility
    - **Property 4: Header Compatibility**
    - **Validates: Requirements 11.5, 6.3, 6.4**

  - [ ]* 5.3 Write property test for session endpoint functional equivalence
    - **Property 9: Session Endpoint Functional Equivalence**
    - **Validates: Requirements 1.4, 6.5, 6.6**

  - [ ]* 5.4 Write property test for session management preservation
    - **Property 22: Session Management Preservation**
    - **Validates: Requirements 8.3**

  - [ ]* 5.5 Write unit tests for session endpoints
    - Test GET /session/info with valid session ID
    - Test GET /session/info without X-Session-Id header returns 400
    - Test DELETE /session with valid session ID
    - Test session expiration warning when TTL < 5 minutes
    - _Requirements: 6.7, 6.8_

- [x] 6. Convert voice Lambda handlers to FastAPI routes
  - [x] 6.1 Create backend/src/routes/voice.py with POST /voice/text-to-speech and POST /voice/speech-to-text endpoints
    - Remove lambda_handler functions from separate voice handlers
    - Create route handler for text-to-speech with TextToSpeechRequest model
    - Create route handler for speech-to-text with VoiceToTextRequest model
    - Preserve Amazon Polly integration (voice mapping, engine selection, SSML support)
    - Preserve Amazon Transcribe integration (language detection, audio format support)
    - Preserve S3 temporary storage logic with 1-hour TTL
    - Preserve audio format validation (webm, mp3, wav)
    - Return audio data or transcript with appropriate HTTP status codes (200, 400)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10_

  - [ ]* 6.2 Write property test for voice endpoint request schema compatibility
    - **Property 1: API Request Schema Compatibility**
    - **Validates: Requirements 11.1, 7.3, 7.4**

  - [ ]* 6.3 Write property test for voice endpoint response schema compatibility
    - **Property 2: API Response Schema Compatibility**
    - **Validates: Requirements 11.2, 7.9**

  - [ ]* 6.4 Write property test for voice endpoints functional equivalence
    - **Property 10: Voice Endpoints Functional Equivalence**
    - **Validates: Requirements 1.4, 7.5, 7.6, 7.7**

  - [ ]* 6.5 Write property test for audio format validation preservation
    - **Property 23: Audio Format Validation Preservation**
    - **Validates: Requirements 7.8**

  - [ ]* 6.6 Write unit tests for voice endpoints
    - Test POST /voice/text-to-speech with valid request
    - Test POST /voice/speech-to-text with valid audio
    - Test invalid audio format returns 400
    - Test low quality audio returns 400
    - Test language detection in speech-to-text
    - _Requirements: 7.9, 7.10_

- [x] 7. Checkpoint - Ensure all routes are working
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Adapt shared utilities for FastAPI
  - [x] 8.1 Update backend/src/shared/utils.py response creation functions
    - Modify create_response() to return FastAPI JSONResponse instead of API Gateway dict
    - Preserve all utility functions (sanitization, validation, timestamp generation)
    - Preserve all AWS client initialization functions with @lru_cache decorators
    - Remove Lambda-specific error handling decorator
    - _Requirements: 1.1, 1.2, 1.3, 8.5, 8.6, 8.7_

  - [ ]* 8.2 Write property test for input sanitization preservation
    - **Property 12: Input Sanitization Preservation**
    - **Validates: Requirements 12.1, 12.6**

  - [ ]* 8.3 Write property test for AWS service integration preservation
    - **Property 11: AWS Service Integration Preservation**
    - **Validates: Requirements 1.5, 8.7**

  - [ ]* 8.4 Write unit tests for adapted utilities
    - Test create_response returns FastAPI JSONResponse
    - Test sanitization functions work unchanged
    - Test AWS client initialization functions work unchanged
    - _Requirements: 8.5, 8.6, 8.7_

- [x] 9. Verify shared modules preservation
  - [x] 9.1 Verify backend/src/shared/models.py Pydantic models are unchanged
    - Confirm all request models (ChatRequest, EligibilityRequest, etc.) unchanged
    - Confirm all response models (ChatResponse, EligibilityResponse, etc.) unchanged
    - Confirm all internal models (SessionMetadata, Message, etc.) unchanged
    - _Requirements: 8.1_

  - [x] 9.2 Verify backend/src/shared/session_manager.py functions are unchanged
    - Confirm create_session, get_session_info, delete_session_data unchanged
    - Confirm all DynamoDB operations unchanged
    - _Requirements: 8.3_

  - [x] 9.3 Verify backend/src/shared/data_privacy.py functions are unchanged
    - Confirm detect_pii, sanitize_pii, anonymize_user_info unchanged
    - Confirm validate_data_minimization unchanged
    - _Requirements: 8.4_

  - [ ]* 9.4 Write unit tests for shared modules preservation
    - Test Pydantic models validate correctly
    - Test session manager functions work with DynamoDB
    - Test data privacy functions detect and anonymize PII
    - _Requirements: 8.1, 8.3, 8.4_

- [x] 10. Register all routes in main.py
  - Import all route modules (chat, eligibility, schemes, session, voice)
  - Register route handlers with FastAPI app
  - Configure Uvicorn server settings (host 0.0.0.0, port 8000)
  - Add graceful shutdown handler
  - Add startup logging with host and port information
  - _Requirements: 2.1, 2.5, 2.6, 10.1, 10.2, 10.7_

- [ ]* 10.1 Write property test for HTTP status code preservation
  - **Property 3: HTTP Status Code Preservation**
  - **Validates: Requirements 11.3, 3.8, 3.9, 3.10, 4.6, 4.7, 4.8, 5.8, 5.9, 6.7, 6.8, 7.9, 7.10**

- [ ]* 10.2 Write property test for error response format preservation
  - **Property 20: Error Response Format Preservation**
  - **Validates: Requirements 11.6**

- [ ]* 10.3 Write property test for security event logging preservation
  - **Property 16: Security Event Logging Preservation**
  - **Validates: Requirements 12.5**

- [x] 11. Configure environment variables and deployment
  - [x] 11.1 Create backend/.env.example with all required environment variables
    - DYNAMODB_TABLE
    - S3_TEMP_BUCKET
    - BEDROCK_MODEL_ID
    - AWS_REGION
    - LOG_LEVEL
    - _Requirements: 10.3, 10.4, 10.5, 10.6_

  - [x] 11.2 Create backend/systemd/bharat-sahayak.service file for systemd
    - Configure service to run uvicorn with appropriate settings
    - Set working directory and environment variables
    - Configure restart policy and logging
    - _Requirements: 10.1, 10.2_

  - [x] 11.3 Create backend/scripts/deploy.sh deployment script
    - Install dependencies from requirements.txt
    - Set up environment variables
    - Start application with uvicorn
    - _Requirements: 10.1, 10.2_

  - [ ]* 11.4 Write unit tests for deployment configuration
    - Test application starts successfully with uvicorn command
    - Test environment variables are loaded correctly
    - Test health check endpoint responds
    - _Requirements: 10.1, 10.2, 10.7_

- [x] 12. Verify Lambda code removal
  - [x] 12.1 Search codebase for lambda_handler functions and remove them
    - Remove all lambda_handler function definitions
    - Remove all API Gateway event parsing code
    - Remove all Lambda context dependencies
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 12.2 Write migration verification tests
    - Test no lambda_handler functions exist in codebase
    - Test no API Gateway event parsing (event['body'], event['headers'])
    - Test no Lambda context usage
    - Test all endpoints are registered in FastAPI app
    - _Requirements: 1.1, 1.2, 1.3_

- [ ] 13. Final checkpoint - Run all tests and verify deployment
  - Run all unit tests and ensure 100% pass rate
  - Run all property tests with minimum 100 iterations
  - Test local deployment with uvicorn
  - Verify all endpoints respond correctly
  - Verify AWS service integrations work
  - Verify security features (rate limiting, PII detection, input sanitization)
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties across all inputs
- Unit tests validate specific examples and edge cases
- All business logic, AWS service integrations, and security features must be preserved
- API compatibility with existing frontend clients must be maintained
- The migration removes Lambda-specific code while preserving all functionality
