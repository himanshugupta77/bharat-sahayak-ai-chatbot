"""Basic tests for eligibility FastAPI route."""

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Import the main app
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app

client = TestClient(app)


@patch('routes.eligibility.get_dynamodb_table')
@patch('routes.eligibility.get_scheme')
class TestEligibilityRoute:
    """Basic tests for eligibility route."""
    
    def test_eligibility_endpoint_exists(self, mock_get_scheme, mock_get_table):
        """Test that the eligibility endpoint is registered."""
        # Mock scheme data
        mock_scheme = {
            'schemeId': 'pm-kisan',
            'name': 'PM-KISAN',
            'benefits': '₹6000 per year',
            'applicationSteps': ['Visit portal', 'Register', 'Apply'],
            'documents': ['Aadhaar', 'Land records'],
            'category': 'agriculture',
            'eligibilityRules': [
                {
                    'criterion': 'Land Ownership',
                    'type': 'boolean',
                    'requirement': 'Must own land',
                    'evaluator': 'lambda u: u.get("ownsLand", False)'
                }
            ]
        }
        
        mock_get_scheme.return_value = mock_scheme
        mock_table = Mock()
        mock_table.query.return_value = {'Items': []}
        mock_get_table.return_value = mock_table
        
        # Make request
        response = client.post(
            "/eligibility",
            json={
                "schemeId": "pm-kisan",
                "userInfo": {
                    "ownsLand": True
                }
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "eligible" in data
        assert "explanation" in data
        assert "schemeDetails" in data
    
    def test_eligibility_eligible_user(self, mock_get_scheme, mock_get_table):
        """Test eligibility check for eligible user."""
        # Mock scheme data
        mock_scheme = {
            'schemeId': 'pm-kisan',
            'name': 'PM-KISAN',
            'benefits': '₹6000 per year',
            'applicationSteps': ['Visit portal', 'Register', 'Apply'],
            'documents': ['Aadhaar', 'Land records'],
            'category': 'agriculture',
            'eligibilityRules': [
                {
                    'criterion': 'Land Ownership',
                    'type': 'boolean',
                    'requirement': 'Must own land',
                    'evaluator': 'lambda u: u.get("ownsLand", False)'
                },
                {
                    'criterion': 'Land Size',
                    'type': 'numeric',
                    'requirement': 'Land ≤ 2 hectares',
                    'evaluator': 'lambda u: u.get("landSize", 0) <= 2'
                }
            ]
        }
        
        mock_get_scheme.return_value = mock_scheme
        mock_table = Mock()
        mock_table.query.return_value = {'Items': []}
        mock_get_table.return_value = mock_table
        
        # Make request
        response = client.post(
            "/eligibility",
            json={
                "schemeId": "pm-kisan",
                "userInfo": {
                    "ownsLand": True,
                    "landSize": 1.5
                }
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["eligible"] is True
        assert len(data["explanation"]["criteria"]) == 2
        assert data["schemeDetails"]["name"] == "PM-KISAN"
    
    def test_eligibility_not_eligible_user(self, mock_get_scheme, mock_get_table):
        """Test eligibility check for ineligible user."""
        # Mock scheme data
        mock_scheme = {
            'schemeId': 'pm-kisan',
            'name': 'PM-KISAN',
            'benefits': '₹6000 per year',
            'applicationSteps': ['Visit portal', 'Register', 'Apply'],
            'documents': ['Aadhaar', 'Land records'],
            'category': 'agriculture',
            'eligibilityRules': [
                {
                    'criterion': 'Land Ownership',
                    'type': 'boolean',
                    'requirement': 'Must own land',
                    'evaluator': 'lambda u: u.get("ownsLand", False)'
                }
            ]
        }
        
        mock_get_scheme.return_value = mock_scheme
        mock_table = Mock()
        mock_table.query.return_value = {
            'Items': [
                {
                    'schemeId': 'mgnrega',
                    'name': 'MGNREGA'
                }
            ]
        }
        mock_get_table.return_value = mock_table
        
        # Make request
        response = client.post(
            "/eligibility",
            json={
                "schemeId": "pm-kisan",
                "userInfo": {
                    "ownsLand": False
                }
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["eligible"] is False
        assert "not eligible" in data["explanation"]["summary"].lower()
    
    def test_scheme_not_found(self, mock_get_scheme, mock_get_table):
        """Test handling of non-existent scheme."""
        mock_get_scheme.return_value = None
        mock_get_table.return_value = Mock()
        
        # Make request
        response = client.post(
            "/eligibility",
            json={
                "schemeId": "invalid-scheme",
                "userInfo": {
                    "age": 30
                }
            }
        )
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "SchemeNotFound"
    
    def test_invalid_scheme_id_format(self, mock_get_scheme, mock_get_table):
        """Test validation of scheme ID format."""
        # Make request with invalid scheme ID
        response = client.post(
            "/eligibility",
            json={
                "schemeId": "INVALID_SCHEME!",
                "userInfo": {
                    "age": 30
                }
            }
        )
        
        # Verify response - should be 422 (validation error) or 400
        assert response.status_code in [400, 422]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
