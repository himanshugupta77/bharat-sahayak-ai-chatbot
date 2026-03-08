"""Session route handler for FastAPI."""

import logging
import os
import sys
from typing import Optional

from fastapi import APIRouter, Header, status
from fastapi.responses import JSONResponse

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.utils import get_current_timestamp, logger
from shared.session_manager import (
    get_session_info,
    delete_session_data,
    update_session_access_time
)

# Create router
router = APIRouter()


@router.get("/session/info", status_code=status.HTTP_200_OK)
async def get_session_information(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """
    Get session information including expiration status.
    
    Args:
        x_session_id: Session ID from X-Session-Id header
    
    Returns:
        Session information with expiration details
    """
    # Validate session ID is provided
    if not x_session_id:
        error_body = {
            'error': 'MissingSessionId',
            'message': 'Session ID is required in X-Session-Id header',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
    
    try:
        session_info = get_session_info(x_session_id)
        
        # Update access time if session exists and not expired
        if session_info['exists'] and not session_info['expired']:
            update_session_access_time(x_session_id)
        
        response_body = {
            'sessionId': x_session_id,
            'exists': session_info['exists'],
            'expired': session_info['expired'],
            'timeRemainingSeconds': session_info['timeRemaining'],
            'showExpirationWarning': session_info['showWarning'],
            'messageCount': session_info.get('messageCount', 0)
        }
        
        # Add timestamps if session exists
        if session_info['exists']:
            response_body['createdAt'] = session_info.get('createdAt')
            response_body['lastAccessedAt'] = session_info.get('lastAccessedAt')
        
        logger.info(
            f"Retrieved session info for {x_session_id}: "
            f"expired={session_info['expired']}, "
            f"remaining={session_info['timeRemaining']}s"
        )
        
        return response_body
        
    except Exception as e:
        logger.error(f"Error getting session info: {e}", exc_info=True)
        error_body = {
            'error': 'InternalError',
            'message': 'Failed to retrieve session information',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body
        )


@router.delete("/session", status_code=status.HTTP_200_OK)
async def delete_session(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """
    Delete all session data immediately.
    
    Args:
        x_session_id: Session ID from X-Session-Id header
    
    Returns:
        Confirmation of session deletion
    """
    # Validate session ID is provided
    if not x_session_id:
        error_body = {
            'error': 'MissingSessionId',
            'message': 'Session ID is required in X-Session-Id header',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
    
    try:
        success = delete_session_data(x_session_id)
        
        if success:
            logger.info(f"Successfully deleted session {x_session_id}")
            return {
                'message': 'Session data deleted successfully',
                'sessionId': x_session_id
            }
        else:
            error_body = {
                'error': 'DeletionFailed',
                'message': 'Failed to delete session data',
                'timestamp': get_current_timestamp()
            }
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_body
            )
            
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        error_body = {
            'error': 'InternalError',
            'message': 'Failed to delete session data',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body
        )
