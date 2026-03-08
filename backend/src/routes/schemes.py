"""Schemes route handler for FastAPI."""

import os
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.utils import (
    get_dynamodb_table,
    get_current_timestamp,
    validate_language_code,
    logger
)

# Create router
router = APIRouter()

# Module-level cache with 5-minute TTL
_scheme_cache: Dict[str, Any] = {}
_cache_timestamp: float = 0
CACHE_TTL_SECONDS = 300  # 5 minutes


def is_cache_valid() -> bool:
    """Check if the cache is still valid (within TTL)."""
    global _cache_timestamp
    current_time = time.time()
    return (current_time - _cache_timestamp) < CACHE_TTL_SECONDS


def get_cached_schemes() -> Optional[List[Dict[str, Any]]]:
    """Get schemes from cache if valid."""
    if is_cache_valid() and 'all_schemes' in _scheme_cache:
        logger.info("Returning schemes from cache")
        return _scheme_cache['all_schemes']
    return None


def set_cached_schemes(schemes: List[Dict[str, Any]]):
    """Store schemes in cache with current timestamp."""
    global _cache_timestamp, _scheme_cache
    _scheme_cache['all_schemes'] = schemes
    _cache_timestamp = time.time()
    logger.info(f"Cached {len(schemes)} schemes")


def get_cached_scheme(scheme_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific scheme from cache if valid."""
    if is_cache_valid() and scheme_id in _scheme_cache:
        logger.info(f"Returning scheme {scheme_id} from cache")
        return _scheme_cache[scheme_id]
    return None


def set_cached_scheme(scheme_id: str, scheme: Dict[str, Any]):
    """Store a specific scheme in cache."""
    global _cache_timestamp, _scheme_cache
    _scheme_cache[scheme_id] = scheme
    if _cache_timestamp == 0:
        _cache_timestamp = time.time()
    logger.info(f"Cached scheme {scheme_id}")


@router.get("/schemes", status_code=status.HTTP_200_OK)
async def list_schemes(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    language: str = Query('en', description="Language for translations")
):
    """
    List all schemes with optional filtering and pagination.
    
    Query parameters:
    - category: Filter by category (uses GSI)
    - limit: Number of results (default: 50, max: 100)
    - offset: Pagination offset (default: 0)
    - language: Language for translations (default: en)
    
    Features:
    - Memory caching with 5-minute TTL
    - Efficient pagination using DynamoDB pagination tokens
    - Category filtering using GSI
    """
    # Validate language code
    try:
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
    
    table = get_dynamodb_table()
    
    try:
        # Check cache first for non-filtered requests
        if not category:
            cached_schemes = get_cached_schemes()
            if cached_schemes:
                # Apply pagination to cached results
                paginated_schemes = cached_schemes[offset:offset + limit]
                schemes_with_translations = [
                    apply_translations(scheme, language) for scheme in paginated_schemes
                ]
                
                response_body = {
                    'schemes': schemes_with_translations,
                    'total': len(cached_schemes),
                    'limit': limit,
                    'offset': offset
                }
                
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=response_body,
                    headers={'Cache-Control': 'public, max-age=3600'}  # 1 hour cache
                )
        
        # Fetch from DynamoDB
        if category:
            # Query by category using GSI
            response = table.query(
                IndexName='CategoryIndex',
                KeyConditionExpression='category = :category',
                ExpressionAttributeValues={
                    ':category': category
                }
            )
            items = response.get('Items', [])
            
            # Handle pagination manually for GSI queries
            total = len(items)
            items = items[offset:offset + limit]
            
        else:
            # Scan all schemes - fetch all for caching
            items = []
            scan_kwargs = {
                'FilterExpression': 'begins_with(PK, :prefix) AND SK = :sk',
                'ExpressionAttributeValues': {
                    ':prefix': 'SCHEME#',
                    ':sk': 'METADATA'
                }
            }
            
            # Paginate through all results for caching
            while True:
                response = table.scan(**scan_kwargs)
                items.extend(response.get('Items', []))
                
                # Check if there are more items
                last_key = response.get('LastEvaluatedKey')
                if not last_key:
                    break
                scan_kwargs['ExclusiveStartKey'] = last_key
            
            # Cache all schemes
            formatted_all = [format_scheme_summary(item) for item in items]
            set_cached_schemes(formatted_all)
            
            # Apply pagination
            total = len(items)
            items = items[offset:offset + limit]
        
        # Format schemes for response
        schemes = []
        for item in items:
            scheme = format_scheme_summary(item)
            scheme = apply_translations(scheme, language)
            schemes.append(scheme)
        
        response_body = {
            'schemes': schemes,
            'total': total,
            'limit': limit,
            'offset': offset
        }
        
        # Add cache-control header: 1 hour for scheme list
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_body,
            headers={'Cache-Control': 'public, max-age=3600'}
        )
        
    except Exception as e:
        logger.error(f"Failed to list schemes: {e}", exc_info=True)
        error_body = {
            'error': 'InternalError',
            'message': 'Failed to retrieve schemes',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body
        )


@router.get("/schemes/{schemeId}", status_code=status.HTTP_200_OK)
async def get_scheme_details(
    request: Request,
    schemeId: str,
    language: str = Query('en', description="Language for translations")
):
    """
    Get detailed information about a specific scheme.
    
    Query parameters:
    - language: Language for translations (default: en)
    
    Features:
    - Memory caching with 5-minute TTL
    - Translation support for scheme names and descriptions
    """
    # Validate language code
    try:
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
    
    # Get correlation ID from request state (set by middleware)
    correlation_id = getattr(request.state, 'correlation_id', None)
    
    table = get_dynamodb_table()
    
    try:
        # Check cache first
        cached_scheme = get_cached_scheme(schemeId)
        if cached_scheme:
            scheme_with_translation = apply_translations(cached_scheme, language)
            # Add cache-control header: 24 hours for scheme details
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=scheme_with_translation,
                headers={'Cache-Control': 'public, max-age=86400'}
            )
        
        # Fetch from DynamoDB
        response = table.get_item(
            Key={
                'PK': f'SCHEME#{schemeId}',
                'SK': 'METADATA'
            }
        )
        
        item = response.get('Item')
        
        if not item:
            error_body = {
                'error': 'SchemeNotFound',
                'message': f"Scheme with ID '{schemeId}' does not exist",
                'requestId': correlation_id,
                'timestamp': get_current_timestamp()
            }
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_body
            )
        
        # Format scheme details
        scheme_details = format_scheme_details(item)
        
        # Cache the scheme
        set_cached_scheme(schemeId, scheme_details)
        
        # Apply translations
        scheme_with_translation = apply_translations(scheme_details, language)
        
        # Add cache-control header: 24 hours for scheme details
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=scheme_with_translation,
            headers={'Cache-Control': 'public, max-age=86400'}
        )
        
    except Exception as e:
        logger.error(f"Failed to get scheme details: {e}", exc_info=True)
        error_body = {
            'error': 'InternalError',
            'message': 'Failed to retrieve scheme details',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body
        )


def format_scheme_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format scheme item for list response."""
    return {
        'id': item.get('schemeId', ''),
        'name': item.get('name', ''),
        'nameTranslations': item.get('nameTranslations', {}),
        'description': item.get('description', ''),
        'descriptionTranslations': item.get('descriptionTranslations', {}),
        'category': item.get('category', ''),
        'targetAudience': item.get('targetAudience', '')
    }


def format_scheme_details(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format scheme item for detailed response."""
    return {
        'id': item.get('schemeId', ''),
        'name': item.get('name', ''),
        'nameTranslations': item.get('nameTranslations', {}),
        'description': item.get('description', ''),
        'descriptionTranslations': item.get('descriptionTranslations', {}),
        'category': item.get('category', ''),
        'eligibilityRules': format_eligibility_rules(item.get('eligibilityRules', [])),
        'benefits': item.get('benefits', ''),
        'applicationSteps': item.get('applicationSteps', []),
        'documents': item.get('documents', []),
        'officialWebsite': item.get('officialWebsite', ''),
        'lastUpdated': item.get('lastUpdated', 0)
    }


def apply_translations(scheme: Dict[str, Any], language: str) -> Dict[str, Any]:
    """
    Apply language translations to scheme data.
    
    If a translation exists for the requested language, it replaces the default
    English name/description. Otherwise, the English version is used.
    
    Args:
        scheme: Scheme dictionary with nameTranslations and descriptionTranslations
        language: Target language code (e.g., 'hi', 'ta', 'en')
    
    Returns:
        Scheme dictionary with translated name and description
    """
    result = scheme.copy()
    
    # Apply name translation if available
    name_translations = scheme.get('nameTranslations', {})
    if language != 'en' and language in name_translations:
        result['name'] = name_translations[language]
        logger.debug(f"Applied name translation for language: {language}")
    
    # Apply description translation if available
    desc_translations = scheme.get('descriptionTranslations', {})
    if language != 'en' and language in desc_translations:
        result['description'] = desc_translations[language]
        logger.debug(f"Applied description translation for language: {language}")
    
    # Remove translation dictionaries from response to keep it clean
    result.pop('nameTranslations', None)
    result.pop('descriptionTranslations', None)
    
    return result


def format_eligibility_rules(rules: List[Dict]) -> List[Dict]:
    """Format eligibility rules for public API response."""
    formatted_rules = []
    
    for rule in rules:
        formatted_rules.append({
            'criterion': rule.get('criterion', ''),
            'requirement': rule.get('requirement', '')
        })
    
    return formatted_rules
