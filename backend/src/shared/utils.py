"""Shared utility functions for Bharat Sahayak backend."""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, TypeVar
from functools import wraps, lru_cache
import random

import boto3
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse

# Configure structured JSON logging
class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add correlation ID if available
        if hasattr(record, 'correlation_id'):
            log_data['correlationId'] = record.correlation_id
        
        # Add request ID if available
        if hasattr(record, 'request_id'):
            log_data['requestId'] = record.request_id
        
        # Add session ID if available
        if hasattr(record, 'session_id'):
            log_data['sessionId'] = record.session_id
        
        # Add performance metrics if available
        if hasattr(record, 'duration_ms'):
            log_data['durationMs'] = record.duration_ms
        
        # Add token usage if available
        if hasattr(record, 'input_tokens'):
            log_data['inputTokens'] = record.input_tokens
        if hasattr(record, 'output_tokens'):
            log_data['outputTokens'] = record.output_tokens
        
        # Add error details if exception
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add any extra fields
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data)

# Configure logging
logger = logging.getLogger()
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logger.setLevel(getattr(logging, log_level))

# Set JSON formatter for CloudWatch
for handler in logger.handlers:
    handler.setFormatter(JSONFormatter())

T = TypeVar('T')


def get_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())


def log_with_context(
    level: str,
    message: str,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    extra_data: Optional[Dict[str, Any]] = None
):
    """
    Log a message with structured context.
    
    Args:
        level: Log level (INFO, WARNING, ERROR, DEBUG)
        message: Log message
        correlation_id: Correlation ID for request tracing
        request_id: API Gateway request ID
        session_id: User session ID
        duration_ms: Operation duration in milliseconds
        extra_data: Additional structured data to include
    """
    log_func = getattr(logger, level.lower(), logger.info)
    
    # Create a log record with extra attributes
    extra = {}
    if correlation_id:
        extra['correlation_id'] = correlation_id
    if request_id:
        extra['request_id'] = request_id
    if session_id:
        extra['session_id'] = session_id
    if duration_ms is not None:
        extra['duration_ms'] = duration_ms
    if extra_data:
        extra['extra_data'] = extra_data
    
    log_func(message, extra=extra)


def log_performance_metric(
    operation: str,
    duration_ms: float,
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Log performance metrics for monitoring.
    
    Args:
        operation: Name of the operation being measured
        duration_ms: Duration in milliseconds
        correlation_id: Correlation ID for request tracing
        metadata: Additional metadata about the operation
    """
    extra_data = {
        'metricType': 'performance',
        'operation': operation,
        'durationMs': duration_ms
    }
    
    if metadata:
        extra_data.update(metadata)
    
    log_with_context(
        'INFO',
        f'Performance metric: {operation} completed in {duration_ms:.2f}ms',
        correlation_id=correlation_id,
        extra_data=extra_data
    )


def log_token_usage(
    operation: str,
    input_tokens: int,
    output_tokens: int,
    correlation_id: Optional[str] = None,
    model_id: Optional[str] = None
):
    """
    Log LLM token usage for cost tracking.
    
    Args:
        operation: Name of the operation (e.g., 'bedrock_invoke')
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        correlation_id: Correlation ID for request tracing
        model_id: Model identifier
    """
    total_tokens = input_tokens + output_tokens
    
    extra_data = {
        'metricType': 'tokenUsage',
        'operation': operation,
        'inputTokens': input_tokens,
        'outputTokens': output_tokens,
        'totalTokens': total_tokens
    }
    
    if model_id:
        extra_data['modelId'] = model_id
    
    # Create log record with token attributes
    extra = {
        'correlation_id': correlation_id,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'extra_data': extra_data
    }
    
    logger.info(
        f'Token usage: {operation} - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}',
        extra=extra
    )


def log_api_call(
    service: str,
    operation: str,
    duration_ms: float,
    correlation_id: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None
):
    """
    Log AWS service API calls for monitoring.
    
    Args:
        service: AWS service name (e.g., 'bedrock', 'translate', 'dynamodb')
        operation: Operation name (e.g., 'InvokeModel', 'TranslateText')
        duration_ms: Duration in milliseconds
        correlation_id: Correlation ID for request tracing
        success: Whether the call succeeded
        error: Error message if failed
    """
    extra_data = {
        'metricType': 'apiCall',
        'service': service,
        'operation': operation,
        'durationMs': duration_ms,
        'success': success
    }
    
    if error:
        extra_data['error'] = error
    
    level = 'INFO' if success else 'ERROR'
    message = f'AWS API call: {service}.{operation} - {"Success" if success else "Failed"} ({duration_ms:.2f}ms)'
    
    log_with_context(
        level,
        message,
        correlation_id=correlation_id,
        duration_ms=duration_ms,
        extra_data=extra_data
    )


def get_dynamodb_table():
    """Get DynamoDB table resource with caching."""
    table_name = os.environ.get('DYNAMODB_TABLE')
    if not table_name:
        raise ValueError("DYNAMODB_TABLE environment variable not set")
    
    dynamodb = boto3.resource('dynamodb')
    return dynamodb.Table(table_name)


@lru_cache(maxsize=1)
def get_bedrock_client():
    """Get Amazon Bedrock client with caching."""
    return boto3.client('bedrock-runtime')


@lru_cache(maxsize=1)
def get_translate_client():
    """Get Amazon Translate client with caching."""
    return boto3.client('translate')


@lru_cache(maxsize=1)
def get_transcribe_client():
    """Get Amazon Transcribe client with caching."""
    return boto3.client('transcribe')


@lru_cache(maxsize=1)
def get_polly_client():
    """Get Amazon Polly client with caching."""
    return boto3.client('polly')


@lru_cache(maxsize=1)
def get_s3_client():
    """Get S3 client with caching."""
    return boto3.client('s3')


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


def generate_message_id() -> str:
    """Generate a unique message ID."""
    return str(uuid.uuid4())


def get_current_timestamp() -> int:
    """Get current Unix timestamp in seconds."""
    return int(datetime.now().timestamp())


def get_ttl_timestamp(hours: int = 24) -> int:
    """Get TTL timestamp (current time + hours)."""
    return int((datetime.now() + timedelta(hours=hours)).timestamp())


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0
) -> T:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
    
    Returns:
        Result of successful function call
    
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                # Calculate delay with exponential backoff
                delay = min(base_delay * (2 ** attempt), max_delay)
                
                # Add jitter to prevent thundering herd
                jitter = delay * 0.1 * (2 * random.random() - 1)
                sleep_time = delay + jitter
                
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {sleep_time:.2f}s..."
                )
                time.sleep(sleep_time)
            else:
                logger.error(f"All {max_retries} retries failed: {e}")
    
    raise last_exception


def log_security_event(event_type: str, details: Dict[str, Any]):
    """Log security-related events."""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'eventType': event_type,
        'severity': 'WARNING',
        'details': details
    }
    
    logger.warning(json.dumps(log_entry))


def create_response(
    status_code: int,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    cache_control: Optional[str] = None
) -> JSONResponse:
    """
    Create a standardized FastAPI JSONResponse with optional caching.
    
    Args:
        status_code: HTTP status code
        body: Response body dictionary
        headers: Optional additional headers
        cache_control: Optional Cache-Control header value
    
    Returns:
        FastAPI JSONResponse object
    """
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Session-Id,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }
    
    # Add cache-control header if specified
    if cache_control:
        default_headers['Cache-Control'] = cache_control
    
    if headers:
        default_headers.update(headers)
    
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=default_headers
    )


def create_error_response(
    status_code: int,
    error_type: str,
    message: str,
    field: Optional[str] = None,
    request_id: Optional[str] = None,
    retry_after: Optional[int] = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        status_code: HTTP status code
        error_type: Error type identifier
        message: Human-readable error message
        field: Optional field name that caused the error
        request_id: Optional request ID for tracking
        retry_after: Optional retry delay in seconds
    
    Returns:
        FastAPI JSONResponse error object
    """
    error_body = {
        'error': error_type,
        'message': message,
        'timestamp': get_current_timestamp()
    }
    
    if field:
        error_body['field'] = field
    if request_id:
        error_body['requestId'] = request_id
    if retry_after:
        error_body['retryAfter'] = retry_after
    
    return create_response(status_code, error_body)


def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.
    
    Args:
        text: Input text
    
    Returns:
        HTML-escaped text
    """
    import html
    return html.escape(text)


def sanitize_input(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize user input by removing dangerous characters and null bytes.
    
    Args:
        text: Input text to sanitize
        max_length: Optional maximum length to enforce
    
    Returns:
        Sanitized text
    
    Raises:
        ValueError: If input is invalid
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string")
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove other control characters except newlines and tabs
    text = ''.join(char for char in text if char == '\n' or char == '\t' or ord(char) >= 32)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Enforce max length if specified
    if max_length and len(text) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length} characters")
    
    # Check for empty input after sanitization
    if not text:
        raise ValueError("Input cannot be empty after sanitization")
    
    return text


def sanitize_text_for_storage(text: str) -> str:
    """
    Sanitize text for safe storage in database.
    Removes dangerous characters and escapes HTML.
    
    Args:
        text: Input text
    
    Returns:
        Sanitized and HTML-escaped text
    """
    # First sanitize input
    text = sanitize_input(text)
    
    # Then escape HTML
    text = sanitize_html(text)
    
    return text


def validate_language_code(language: str) -> str:
    """
    Validate and sanitize language code.
    
    Args:
        language: Language code to validate
    
    Returns:
        Validated language code
    
    Raises:
        ValueError: If language code is invalid
    """
    valid_languages = ['en', 'hi', 'mr', 'ta', 'te', 'bn', 'gu', 'kn', 'ml', 'pa', 'or']
    
    if not isinstance(language, str):
        raise ValueError("Language code must be a string")
    
    language = language.lower().strip()
    
    if language not in valid_languages:
        raise ValueError(f"Invalid language code. Must be one of: {', '.join(valid_languages)}")
    
    return language


def validate_scheme_id(scheme_id: str) -> str:
    """
    Validate and sanitize scheme ID.
    
    Args:
        scheme_id: Scheme ID to validate
    
    Returns:
        Validated scheme ID
    
    Raises:
        ValueError: If scheme ID is invalid
    """
    if not isinstance(scheme_id, str):
        raise ValueError("Scheme ID must be a string")
    
    scheme_id = scheme_id.strip()
    
    # Only allow alphanumeric characters and hyphens
    if not all(c.isalnum() or c == '-' for c in scheme_id):
        raise ValueError("Scheme ID can only contain alphanumeric characters and hyphens")
    
    if len(scheme_id) < 1 or len(scheme_id) > 100:
        raise ValueError("Scheme ID must be between 1 and 100 characters")
    
    return scheme_id


def validate_audio_format(audio_format: str) -> str:
    """
    Validate audio format.
    
    Args:
        audio_format: Audio format to validate
    
    Returns:
        Validated audio format
    
    Raises:
        ValueError: If audio format is invalid
    """
    valid_formats = ['webm', 'mp3', 'wav']
    
    if not isinstance(audio_format, str):
        raise ValueError("Audio format must be a string")
    
    audio_format = audio_format.lower().strip()
    
    if audio_format not in valid_formats:
        raise ValueError(f"Invalid audio format. Must be one of: {', '.join(valid_formats)}")
    
    return audio_format
