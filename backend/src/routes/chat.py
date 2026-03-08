"""Chat route handler for FastAPI."""

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.models import ChatRequest, ChatResponse, SchemeCard
from shared.utils import (
    generate_session_id,
    get_current_timestamp,
    get_ttl_timestamp,
    get_dynamodb_table,
    get_bedrock_client,
    get_translate_client,
    retry_with_backoff,
    log_security_event,
    sanitize_input,
    validate_language_code,
    logger
)
from shared.session_manager import get_session_info
from shared.data_privacy import sanitize_message_content, detect_pii

# Create router
router = APIRouter()

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # seconds

# Module-level cache for scheme data (5-minute TTL)
_schemes_cache: List[Dict[str, Any]] = []
_schemes_cache_timestamp: float = 0
SCHEMES_CACHE_TTL = 300  # 5 minutes

# DynamoDB query result cache
_query_cache: Dict[str, Any] = {}
_query_cache_timestamp: Dict[str, float] = {}
QUERY_CACHE_TTL = 60  # 1 minute


def is_schemes_cache_valid() -> bool:
    """Check if schemes cache is still valid."""
    return (time.time() - _schemes_cache_timestamp) < SCHEMES_CACHE_TTL


def get_cached_schemes() -> Optional[List[Dict[str, Any]]]:
    """Get schemes from cache if valid."""
    if is_schemes_cache_valid() and _schemes_cache:
        logger.info("Returning schemes from memory cache")
        return _schemes_cache
    return None


def set_cached_schemes(schemes: List[Dict[str, Any]]):
    """Store schemes in cache."""
    global _schemes_cache, _schemes_cache_timestamp
    _schemes_cache = schemes
    _schemes_cache_timestamp = time.time()
    logger.info(f"Cached {len(schemes)} schemes in memory")


def get_cached_query_result(cache_key: str) -> Optional[Any]:
    """Get query result from cache if valid."""
    if cache_key in _query_cache:
        timestamp = _query_cache_timestamp.get(cache_key, 0)
        if (time.time() - timestamp) < QUERY_CACHE_TTL:
            logger.info(f"Returning query result from cache: {cache_key}")
            return _query_cache[cache_key]
    return None


def set_cached_query_result(cache_key: str, result: Any):
    """Store query result in cache."""
    _query_cache[cache_key] = result
    _query_cache_timestamp[cache_key] = time.time()
    logger.info(f"Cached query result: {cache_key}")


def check_rate_limit(source_ip: str) -> Optional[JSONResponse]:
    """
    Check rate limit: 10 requests per 60 seconds per IP.
    
    Uses DynamoDB to track request counts per IP address.
    
    Args:
        source_ip: Source IP address
    
    Returns:
        JSONResponse with 429 status if rate limit exceeded, None otherwise
    """
    if source_ip == 'unknown':
        logger.warning("Could not determine source IP for rate limiting")
        return None
    
    table = get_dynamodb_table()
    current_time = get_current_timestamp()
    rate_limit_key = f'RATELIMIT#{source_ip}'
    
    try:
        # Get current request count
        response = table.get_item(
            Key={
                'PK': rate_limit_key,
                'SK': 'COUNTER'
            }
        )
        
        item = response.get('Item', {})
        request_count = item.get('requestCount', 0)
        window_start = item.get('windowStart', current_time)
        
        # Check if window has expired
        if current_time - window_start >= RATE_LIMIT_WINDOW:
            # Reset window
            request_count = 0
            window_start = current_time
        
        # Check if rate limit exceeded
        if request_count >= RATE_LIMIT_REQUESTS:
            time_remaining = RATE_LIMIT_WINDOW - (current_time - window_start)
            
            log_security_event('RateLimitExceeded', {
                'sourceIp': source_ip,
                'requestCount': request_count,
                'timeRemaining': time_remaining
            })
            
            error_body = {
                'error': 'RateLimitExceeded',
                'message': f'Too many requests. Please try again in {time_remaining} seconds.',
                'timestamp': current_time,
                'retryAfter': time_remaining
            }
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=error_body,
                headers={'Retry-After': str(time_remaining)}
            )
        
        # Increment request count
        table.put_item(
            Item={
                'PK': rate_limit_key,
                'SK': 'COUNTER',
                'requestCount': request_count + 1,
                'windowStart': window_start,
                'ttl': get_ttl_timestamp(1)  # Clean up after 1 hour
            }
        )
        
    except Exception as e:
        logger.error(f"Rate limiting check failed: {e}")
        # Continue processing if rate limiting fails
    
    return None


@router.post("/chat", status_code=status.HTTP_200_OK)
async def chat(
    request: Request,
    chat_request: ChatRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """
    Process text-based chat queries with AI.
    
    Args:
        request: FastAPI Request object
        chat_request: Validated ChatRequest from request body
        x_session_id: Optional session ID from X-Session-Id header
    
    Returns:
        ChatResponse with AI-generated response and scheme recommendations
    """
    # Get correlation ID from request state (set by middleware)
    correlation_id = getattr(request.state, 'correlation_id', None)
    
    # Extract source IP for rate limiting
    source_ip = request.client.host if request.client else 'unknown'
    
    # Check rate limit
    rate_limit_response = check_rate_limit(source_ip)
    if rate_limit_response:
        return rate_limit_response
    
    # Sanitize and validate inputs
    try:
        message = sanitize_input(chat_request.message, max_length=1000)
        language = chat_request.language or 'en'
        if language:
            language = validate_language_code(language)
    except ValueError as e:
        error_body = {
            'error': 'ValidationError',
            'message': str(e),
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
    
    # Get or create session ID
    session_id = x_session_id or generate_session_id()
    
    # Get DynamoDB table
    table = get_dynamodb_table()
    
    # Get session context from DynamoDB
    session_context = get_session_context(table, session_id)
    
    # Get relevant schemes from database for context
    schemes_db = get_relevant_schemes(table, limit=15)
    
    # Detect language if not provided
    if not language or language == 'en':
        detected_language = detect_language(message)
        language = detected_language
    
    # Translate to English if needed
    english_message = message
    if language != 'en':
        english_message = translate_text(message, language, 'en', correlation_id)
    
    # Build prompt with context and scheme database
    prompt = build_prompt(english_message, session_context, schemes_db)
    
    # Call Bedrock Claude 3
    ai_response = call_bedrock(prompt, correlation_id)
    
    # Parse response for scheme recommendations
    schemes = extract_schemes(ai_response, schemes_db)
    
    # Translate response back to user language
    translated_response = ai_response
    if language != 'en':
        translated_response = translate_text(ai_response, 'en', language, correlation_id)
    
    # Store message in session
    store_message(table, session_id, message, language, 'user')
    
    # Extract scheme IDs for storage
    scheme_ids = [s.id for s in schemes]
    store_message(table, session_id, translated_response, language, 'assistant', scheme_ids)
    
    # Update session metadata
    update_session_metadata(table, session_id, language)
    
    # Get session expiration info
    session_info = get_session_info(session_id)
    
    # Create response
    response = ChatResponse(
        response=translated_response,
        language=language,
        schemes=schemes,
        sessionId=session_id,
        sessionExpiring=session_info.get('showWarning', False),
        sessionTimeRemaining=session_info.get('timeRemaining')
    )
    
    return response.dict()


def get_session_context(table, session_id: str) -> list:
    """Retrieve session context from DynamoDB."""
    try:
        # Query all messages for this session
        response = table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': f'SESSION#{session_id}',
                ':sk': 'MESSAGE#'
            },
            Limit=10,  # Last 10 messages for context
            ScanIndexForward=False  # Most recent first
        )
        
        messages = response.get('Items', [])
        # Reverse to get chronological order
        return list(reversed(messages))
        
    except Exception as e:
        logger.warning(f"Could not retrieve session context: {e}")
        return []


def get_relevant_schemes(table, category: str = None, limit: int = 10) -> list:
    """
    Retrieve relevant schemes from DynamoDB with memory caching.
    
    Args:
        table: DynamoDB table resource
        category: Optional category filter
        limit: Maximum number of schemes to retrieve
    
    Returns:
        List of scheme dictionaries
    """
    try:
        # Check cache first for non-category queries
        if not category:
            cached_schemes = get_cached_schemes()
            if cached_schemes:
                return cached_schemes[:limit]
        
        # Check query cache for category queries
        if category:
            cache_key = f"category:{category}:{limit}"
            cached_result = get_cached_query_result(cache_key)
            if cached_result:
                return cached_result
        
        # Fetch from DynamoDB
        if category:
            # Query by category using GSI
            response = table.query(
                IndexName='CategoryIndex',
                KeyConditionExpression='category = :cat',
                ExpressionAttributeValues={':cat': category},
                Limit=limit
            )
            items = response.get('Items', [])
            
            # Cache the result
            set_cached_query_result(cache_key, items)
            
        else:
            # Scan for all schemes (limited)
            response = table.scan(
                FilterExpression='begins_with(PK, :pk)',
                ExpressionAttributeValues={':pk': 'SCHEME#'},
                Limit=limit
            )
            items = response.get('Items', [])
            
            # Cache all schemes
            set_cached_schemes(items)
        
        return items
        
    except Exception as e:
        logger.warning(f"Could not retrieve schemes: {e}")
        return []


def detect_language(text: str) -> str:
    """Detect language of input text."""
    try:
        from langdetect import detect, LangDetectException
        
        lang_code = detect(text)
        
        # Map langdetect codes to our supported languages
        lang_map = {
            'en': 'en',
            'hi': 'hi',
            'mr': 'mr',
            'ta': 'ta',
            'te': 'te',
            'bn': 'bn',
            'gu': 'gu',
            'kn': 'kn',
            'ml': 'ml',
            'pa': 'pa',
            'or': 'or'
        }
        
        return lang_map.get(lang_code, 'en')
        
    except (LangDetectException, Exception) as e:
        logger.warning(f"Language detection failed: {e}, defaulting to English")
        return 'en'


def translate_text(text: str, source_lang: str, target_lang: str, correlation_id: Optional[str] = None) -> str:
    """
    Translate text using Amazon Translate with enhanced error handling.
    
    Args:
        text: Text to translate
        source_lang: Source language code
        target_lang: Target language code
        correlation_id: Correlation ID for request tracing
    
    Returns:
        Translated text, or original text if translation fails
    """
    from shared.utils import log_api_call
    
    if source_lang == target_lang:
        return text
    
    try:
        translate_client = get_translate_client()
        
        def _translate():
            start_time = time.time()
            
            logger.info(
                f"Translating from {source_lang} to {target_lang}",
                extra={'correlation_id': correlation_id}
            )
            
            response = translate_client.translate_text(
                Text=text,
                SourceLanguageCode=source_lang,
                TargetLanguageCode=target_lang
            )
            
            duration_ms = (time.time() - start_time) * 1000
            translated = response['TranslatedText']
            
            # Log API call performance
            log_api_call(
                service='translate',
                operation='TranslateText',
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                success=True
            )
            
            # Log translation metrics
            logger.info(
                f"Translation successful: {len(text)} chars -> {len(translated)} chars",
                extra={
                    'correlation_id': correlation_id,
                    'extra_data': {
                        'sourceLang': source_lang,
                        'targetLang': target_lang,
                        'sourceLength': len(text),
                        'targetLength': len(translated)
                    }
                }
            )
            
            return translated
        
        return retry_with_backoff(_translate, max_retries=3)
        
    except Exception as e:
        logger.error(
            f"Translation failed from {source_lang} to {target_lang}: {e}",
            exc_info=True,
            extra={'correlation_id': correlation_id}
        )
        return text  # Return original text if translation fails


def build_prompt(message: str, context: list, schemes_context: list = None) -> str:
    """Build prompt for Bedrock with context and scheme database."""
    system_prompt = """You are Bharat Sahayak, an AI assistant helping Indian citizens discover government welfare schemes.

Your role:
- Understand user needs and recommend relevant government schemes
- Provide accurate, helpful information about eligibility and application processes
- Be respectful, culturally appropriate, and supportive
- Ask clarifying questions when needed

When recommending schemes, provide:
- Scheme name
- Brief description
- Eligibility summary
- Key application steps

Available scheme categories: agriculture, education, health, housing, employment, women, elderly, disability

IMPORTANT: When recommending schemes, format them clearly with the scheme ID in brackets like [SCHEME:scheme-id] so they can be extracted."""

    # Add scheme database context if available
    if schemes_context:
        scheme_info = "\n\nAvailable Government Schemes:\n"
        for scheme in schemes_context[:10]:  # Limit to top 10 schemes
            scheme_info += f"\n- {scheme.get('name', 'Unknown')} (ID: {scheme.get('schemeId', 'unknown')})\n"
            scheme_info += f"  Category: {scheme.get('category', 'general')}\n"
            scheme_info += f"  Description: {scheme.get('description', 'No description')}\n"
            scheme_info += f"  Target: {scheme.get('targetAudience', 'All citizens')}\n"
        
        system_prompt += scheme_info

    # Build conversation history
    conversation = []
    for msg in context:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        conversation.append(f"{role.capitalize()}: {content}")
    
    # Add current message
    conversation.append(f"User: {message}")
    
    full_prompt = f"{system_prompt}\n\nConversation:\n" + "\n".join(conversation) + "\n\nAssistant:"
    
    return full_prompt


def call_bedrock(prompt: str, correlation_id: Optional[str] = None) -> str:
    """
    Call Amazon Bedrock Claude 3 API with enhanced error handling and logging.
    
    Args:
        prompt: The prompt to send to Claude
        correlation_id: Correlation ID for request tracing
    
    Returns:
        AI-generated response text
    """
    from shared.utils import log_token_usage, log_api_call
    
    bedrock_client = get_bedrock_client()
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "top_p": 0.9
    }
    
    def _invoke():
        try:
            start_time = time.time()
            
            logger.info(f"Invoking Bedrock model: {model_id}", extra={'correlation_id': correlation_id})
            
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            
            duration_ms = (time.time() - start_time) * 1000
            response_body = json.loads(response['body'].read())
            
            # Log token usage for cost tracking
            usage = response_body.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            
            log_token_usage(
                operation='bedrock_invoke',
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                correlation_id=correlation_id,
                model_id=model_id
            )
            
            # Log API call performance
            log_api_call(
                service='bedrock',
                operation='InvokeModel',
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                success=True
            )
            
            return response_body['content'][0]['text']
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Log failed API call
            log_api_call(
                service='bedrock',
                operation='InvokeModel',
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                success=False,
                error=str(e)
            )
            
            logger.error(f"Bedrock invocation error: {str(e)}", exc_info=True, extra={'correlation_id': correlation_id})
            raise
    
    try:
        return retry_with_backoff(_invoke, max_retries=3)
    except Exception as e:
        logger.error(f"Bedrock invocation failed after retries: {e}", extra={'correlation_id': correlation_id})
        return "I apologize, but I'm having trouble processing your request right now. Please try again in a moment, or visit https://www.india.gov.in for direct access to government schemes."


def extract_schemes(response: str, schemes_db: list = None) -> List[SchemeCard]:
    """
    Extract scheme recommendations from AI response.
    
    Looks for scheme IDs in the format [SCHEME:scheme-id] and retrieves
    full scheme information from the database.
    """
    schemes = []
    
    # Pattern to match [SCHEME:scheme-id]
    pattern = r'\[SCHEME:([a-z0-9-]+)\]'
    matches = re.findall(pattern, response)
    
    if not matches and schemes_db:
        # Fallback: Try to match scheme names in the response
        for scheme in schemes_db:
            scheme_name = scheme.get('name', '')
            if scheme_name.lower() in response.lower():
                matches.append(scheme.get('schemeId'))
    
    # Retrieve scheme details from database
    if matches and schemes_db:
        table = get_dynamodb_table()
        
        for scheme_id in matches[:5]:  # Limit to 5 schemes
            try:
                # Try to find in provided schemes_db first
                scheme_data = next(
                    (s for s in schemes_db if s.get('schemeId') == scheme_id),
                    None
                )
                
                # If not found, query DynamoDB
                if not scheme_data:
                    response_item = table.get_item(
                        Key={
                            'PK': f'SCHEME#{scheme_id}',
                            'SK': 'METADATA'
                        }
                    )
                    scheme_data = response_item.get('Item')
                
                if scheme_data:
                    scheme_card = SchemeCard(
                        id=scheme_data.get('schemeId', scheme_id),
                        name=scheme_data.get('name', 'Unknown Scheme'),
                        description=scheme_data.get('description', 'No description available'),
                        eligibilitySummary=scheme_data.get('targetAudience', 'See eligibility details'),
                        applicationSteps=scheme_data.get('applicationSteps', ['Visit official website for details'])
                    )
                    schemes.append(scheme_card)
                    
            except Exception as e:
                logger.error(f"Failed to retrieve scheme {scheme_id}: {e}")
                continue
    
    return schemes


def store_message(
    table,
    session_id: str,
    content: str,
    language: str,
    role: str,
    scheme_ids: List[str] = None
):
    """
    Store message in DynamoDB with data sanitization and enhanced error handling.
    
    Args:
        table: DynamoDB table resource
        session_id: Session identifier
        content: Message content
        language: Language code
        role: Message role (user or assistant)
        scheme_ids: Optional list of scheme IDs referenced in message
    """
    timestamp = get_current_timestamp()
    
    # Sanitize message content to remove PII before storage
    sanitized_content = sanitize_message_content(content)
    
    # Log if PII was detected and sanitized
    if sanitized_content != content:
        logger.warning(f"PII detected and sanitized in {role} message for session {session_id}")
    
    item = {
        'PK': f'SESSION#{session_id}',
        'SK': f'MESSAGE#{timestamp}',
        'messageId': f'msg-{timestamp}',
        'role': role,
        'content': sanitized_content,  # Store sanitized content
        'timestamp': timestamp,
        'language': language,
        'schemes': scheme_ids or [],
        'ttl': get_ttl_timestamp(24)
    }
    
    try:
        table.put_item(Item=item)
        logger.info(f"Stored {role} message for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to store message: {e}", exc_info=True)


def update_session_metadata(table, session_id: str, language: str):
    """
    Update or create session metadata with enhanced error handling.
    
    Args:
        table: DynamoDB table resource
        session_id: Session identifier
        language: Language code
    """
    timestamp = get_current_timestamp()
    
    try:
        # Try to update existing session
        table.update_item(
            Key={
                'PK': f'SESSION#{session_id}',
                'SK': 'METADATA'
            },
            UpdateExpression='SET lastAccessedAt = :timestamp, messageCount = messageCount + :inc',
            ExpressionAttributeValues={
                ':timestamp': timestamp,
                ':inc': 1
            }
        )
        logger.info(f"Updated session metadata for {session_id}")
        
    except Exception:
        # Create new session if it doesn't exist
        item = {
            'PK': f'SESSION#{session_id}',
            'SK': 'METADATA',
            'sessionId': session_id,
            'createdAt': timestamp,
            'lastAccessedAt': timestamp,
            'language': language,
            'messageCount': 1,
            'ttl': get_ttl_timestamp(24)
        }
        
        try:
            table.put_item(Item=item)
            logger.info(f"Created new session metadata for {session_id}")
        except Exception as e:
            logger.error(f"Failed to create session metadata: {e}", exc_info=True)
