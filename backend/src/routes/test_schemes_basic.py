"""Basic tests for schemes route handlers."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app

client = TestClient(app)


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table for testing."""
    with patch('routes.schemes.get_dynamodb_table') as mock:
        table = Mock()
        mock.return_value = table
        yield table


def test_list_schemes_success(mock_dynamodb_table):
    """Test GET /schemes returns list with pagination."""
    # Mock DynamoDB scan response
    mock_dynamodb_table.scan.return_value = {
        'Items': [
            {
                'PK': 'SCHEME#pm-kisan',
                'SK': 'METADATA',
                'schemeId': 'pm-kisan',
                'name': 'PM-KISAN',
                'nameTranslations': {'hi': 'पीएम-किसान'},
                'description': 'Income support for farmers',
                'descriptionTranslations': {'hi': 'किसानों के लिए आय सहायता'},
                'category': 'agriculture',
                'targetAudience': 'Small and marginal farmers'
            },
            {
                'PK': 'SCHEME#ayushman-bharat',
                'SK': 'METADATA',
                'schemeId': 'ayushman-bharat',
                'name': 'Ayushman Bharat',
                'nameTranslations': {'hi': 'आयुष्मान भारत'},
                'description': 'Health insurance scheme',
                'descriptionTranslations': {'hi': 'स्वास्थ्य बीमा योजना'},
                'category': 'health',
                'targetAudience': 'Poor and vulnerable families'
            }
        ]
    }
    
    response = client.get("/schemes?limit=10&offset=0")
    
    assert response.status_code == 200
    data = response.json()
    assert 'schemes' in data
    assert 'total' in data
    assert 'limit' in data
    assert 'offset' in data
    assert len(data['schemes']) == 2
    assert data['total'] == 2
    assert data['limit'] == 10
    assert data['offset'] == 0


def test_list_schemes_with_category_filter(mock_dynamodb_table):
    """Test GET /schemes with category filter."""
    # Mock DynamoDB query response
    mock_dynamodb_table.query.return_value = {
        'Items': [
            {
                'PK': 'SCHEME#pm-kisan',
                'SK': 'METADATA',
                'schemeId': 'pm-kisan',
                'name': 'PM-KISAN',
                'nameTranslations': {},
                'description': 'Income support for farmers',
                'descriptionTranslations': {},
                'category': 'agriculture',
                'targetAudience': 'Small and marginal farmers'
            }
        ]
    }
    
    response = client.get("/schemes?category=agriculture")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data['schemes']) == 1
    assert data['schemes'][0]['category'] == 'agriculture'


def test_list_schemes_with_language(mock_dynamodb_table):
    """Test GET /schemes with language parameter applies translations."""
    # Mock DynamoDB scan response
    mock_dynamodb_table.scan.return_value = {
        'Items': [
            {
                'PK': 'SCHEME#pm-kisan',
                'SK': 'METADATA',
                'schemeId': 'pm-kisan',
                'name': 'PM-KISAN',
                'nameTranslations': {'hi': 'पीएम-किसान'},
                'description': 'Income support for farmers',
                'descriptionTranslations': {'hi': 'किसानों के लिए आय सहायता'},
                'category': 'agriculture',
                'targetAudience': 'Small and marginal farmers'
            }
        ]
    }
    
    response = client.get("/schemes?language=hi")
    
    assert response.status_code == 200
    data = response.json()
    assert data['schemes'][0]['name'] == 'पीएम-किसान'
    assert data['schemes'][0]['description'] == 'किसानों के लिए आय सहायता'
    # Translation dictionaries should be removed
    assert 'nameTranslations' not in data['schemes'][0]
    assert 'descriptionTranslations' not in data['schemes'][0]


def test_get_scheme_details_success(mock_dynamodb_table):
    """Test GET /schemes/{schemeId} returns scheme details."""
    # Mock DynamoDB get_item response
    mock_dynamodb_table.get_item.return_value = {
        'Item': {
            'PK': 'SCHEME#pm-kisan',
            'SK': 'METADATA',
            'schemeId': 'pm-kisan',
            'name': 'PM-KISAN',
            'nameTranslations': {'hi': 'पीएम-किसान'},
            'description': 'Income support for farmers',
            'descriptionTranslations': {'hi': 'किसानों के लिए आय सहायता'},
            'category': 'agriculture',
            'eligibilityRules': [
                {'criterion': 'landOwnership', 'requirement': 'Must own agricultural land'}
            ],
            'benefits': 'Rs. 6000 per year',
            'applicationSteps': ['Visit PM-KISAN portal', 'Register with Aadhaar'],
            'documents': ['Aadhaar card', 'Land ownership documents'],
            'officialWebsite': 'https://pmkisan.gov.in',
            'lastUpdated': 1234567890
        }
    }
    
    response = client.get("/schemes/pm-kisan")
    
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == 'pm-kisan'
    assert data['name'] == 'PM-KISAN'
    assert data['category'] == 'agriculture'
    assert 'eligibilityRules' in data
    assert 'benefits' in data
    assert 'applicationSteps' in data
    assert 'documents' in data
    assert 'officialWebsite' in data


def test_get_scheme_details_not_found(mock_dynamodb_table):
    """Test GET /schemes/{schemeId} with non-existent ID returns 404."""
    # Mock DynamoDB get_item response with no item
    mock_dynamodb_table.get_item.return_value = {}
    
    response = client.get("/schemes/non-existent-scheme")
    
    assert response.status_code == 404
    data = response.json()
    assert data['error'] == 'SchemeNotFound'
    assert 'non-existent-scheme' in data['message']


def test_get_scheme_details_with_language(mock_dynamodb_table):
    """Test GET /schemes/{schemeId} with language parameter applies translations."""
    # Mock DynamoDB get_item response
    mock_dynamodb_table.get_item.return_value = {
        'Item': {
            'PK': 'SCHEME#pm-kisan',
            'SK': 'METADATA',
            'schemeId': 'pm-kisan',
            'name': 'PM-KISAN',
            'nameTranslations': {'hi': 'पीएम-किसान'},
            'description': 'Income support for farmers',
            'descriptionTranslations': {'hi': 'किसानों के लिए आय सहायता'},
            'category': 'agriculture',
            'eligibilityRules': [],
            'benefits': 'Rs. 6000 per year',
            'applicationSteps': [],
            'documents': [],
            'officialWebsite': 'https://pmkisan.gov.in',
            'lastUpdated': 1234567890
        }
    }
    
    response = client.get("/schemes/pm-kisan?language=hi")
    
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == 'पीएम-किसान'
    assert data['description'] == 'किसानों के लिए आय सहायता'


def test_list_schemes_invalid_language(mock_dynamodb_table):
    """Test GET /schemes with invalid language code returns 400."""
    response = client.get("/schemes?language=invalid")
    
    assert response.status_code == 400
    data = response.json()
    assert data['error'] == 'ValidationError'


def test_list_schemes_cache_control_header(mock_dynamodb_table):
    """Test GET /schemes includes Cache-Control header."""
    mock_dynamodb_table.scan.return_value = {
        'Items': []
    }
    
    response = client.get("/schemes")
    
    assert response.status_code == 200
    assert 'cache-control' in response.headers
    assert 'max-age=3600' in response.headers['cache-control']


def test_get_scheme_details_cache_control_header(mock_dynamodb_table):
    """Test GET /schemes/{schemeId} includes Cache-Control header."""
    mock_dynamodb_table.get_item.return_value = {
        'Item': {
            'PK': 'SCHEME#pm-kisan',
            'SK': 'METADATA',
            'schemeId': 'pm-kisan',
            'name': 'PM-KISAN',
            'nameTranslations': {},
            'description': 'Income support',
            'descriptionTranslations': {},
            'category': 'agriculture',
            'eligibilityRules': [],
            'benefits': 'Rs. 6000',
            'applicationSteps': [],
            'documents': [],
            'officialWebsite': 'https://pmkisan.gov.in',
            'lastUpdated': 1234567890
        }
    }
    
    response = client.get("/schemes/pm-kisan")
    
    assert response.status_code == 200
    assert 'cache-control' in response.headers
    assert 'max-age=86400' in response.headers['cache-control']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
