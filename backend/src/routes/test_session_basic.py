"""Basic unit tests for session route handlers."""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestSessionRoutes(unittest.TestCase):
    """Test session route handlers."""
    
    @patch('routes.session.get_session_info')
    @patch('routes.session.update_session_access_time')
    def test_get_session_info_success(self, mock_update, mock_get_info):
        """Test successful session info retrieval."""
        # Mock session info
        mock_get_info.return_value = {
            'exists': True,
            'expired': False,
            'timeRemaining': 3600,
            'showWarning': False,
            'messageCount': 5,
            'createdAt': 1234567890,
            'lastAccessedAt': 1234567900
        }
        
        # Make request
        response = client.get(
            "/session/info",
            headers={"X-Session-Id": "test-session-123"}
        )
        
        # Verify response
        assert response.status_code == 200
        body = response.json()
        assert body['sessionId'] == 'test-session-123'
        assert body['exists'] is True
        assert body['expired'] is False
        assert body['timeRemainingSeconds'] == 3600
        assert body['showExpirationWarning'] is False
        assert body['messageCount'] == 5
        assert 'createdAt' in body
        assert 'lastAccessedAt' in body
        
        # Verify session access time was updated
        mock_update.assert_called_once_with('test-session-123')
    
    def test_get_session_info_missing_header(self):
        """Test session info request without X-Session-Id header."""
        response = client.get("/session/info")
        
        assert response.status_code == 400
        body = response.json()
        assert body['error'] == 'MissingSessionId'
        assert 'Session ID is required' in body['message']
    
    @patch('routes.session.get_session_info')
    def test_get_session_info_expired_session(self, mock_get_info):
        """Test session info for expired session."""
        # Mock expired session
        mock_get_info.return_value = {
            'exists': True,
            'expired': True,
            'timeRemaining': 0,
            'showWarning': True,
            'messageCount': 10,
            'createdAt': 1234567890,
            'lastAccessedAt': 1234567900
        }
        
        response = client.get(
            "/session/info",
            headers={"X-Session-Id": "expired-session"}
        )
        
        assert response.status_code == 200
        body = response.json()
        assert body['expired'] is True
        assert body['timeRemainingSeconds'] == 0
    
    @patch('routes.session.get_session_info')
    def test_get_session_info_nonexistent_session(self, mock_get_info):
        """Test session info for non-existent session."""
        # Mock non-existent session
        mock_get_info.return_value = {
            'exists': False,
            'expired': False,
            'timeRemaining': 0,
            'showWarning': False
        }
        
        response = client.get(
            "/session/info",
            headers={"X-Session-Id": "nonexistent-session"}
        )
        
        assert response.status_code == 200
        body = response.json()
        assert body['exists'] is False
        assert 'createdAt' not in body
        assert 'lastAccessedAt' not in body
    
    @patch('routes.session.delete_session_data')
    def test_delete_session_success(self, mock_delete):
        """Test successful session deletion."""
        mock_delete.return_value = True
        
        response = client.delete(
            "/session",
            headers={"X-Session-Id": "test-session-123"}
        )
        
        assert response.status_code == 200
        body = response.json()
        assert body['message'] == 'Session data deleted successfully'
        assert body['sessionId'] == 'test-session-123'
        
        mock_delete.assert_called_once_with('test-session-123')
    
    def test_delete_session_missing_header(self):
        """Test session deletion without X-Session-Id header."""
        response = client.delete("/session")
        
        assert response.status_code == 400
        body = response.json()
        assert body['error'] == 'MissingSessionId'
        assert 'Session ID is required' in body['message']
    
    @patch('routes.session.delete_session_data')
    def test_delete_session_failure(self, mock_delete):
        """Test session deletion failure."""
        mock_delete.return_value = False
        
        response = client.delete(
            "/session",
            headers={"X-Session-Id": "test-session-123"}
        )
        
        assert response.status_code == 500
        body = response.json()
        assert body['error'] == 'DeletionFailed'
    
    @patch('routes.session.get_session_info')
    def test_get_session_info_with_expiration_warning(self, mock_get_info):
        """Test session info when expiration warning should be shown."""
        # Mock session with warning (< 5 minutes remaining)
        mock_get_info.return_value = {
            'exists': True,
            'expired': False,
            'timeRemaining': 240,  # 4 minutes
            'showWarning': True,
            'messageCount': 8,
            'createdAt': 1234567890,
            'lastAccessedAt': 1234567900
        }
        
        response = client.get(
            "/session/info",
            headers={"X-Session-Id": "warning-session"}
        )
        
        assert response.status_code == 200
        body = response.json()
        assert body['showExpirationWarning'] is True
        assert body['timeRemainingSeconds'] == 240


if __name__ == '__main__':
    unittest.main()
