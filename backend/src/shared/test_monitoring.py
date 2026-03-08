"""Unit tests for monitoring and logging functionality."""

import json
import logging
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch, call
from io import StringIO

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import utils


class TestJSONFormatter:
    """Test JSON log formatter."""
    
    def test_basic_log_format(self):
        """Test that logs are formatted as valid JSON with required fields."""
        # Create a log record
        logger = logging.getLogger('test_logger')
        formatter = utils.JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        # Format the record
        formatted = formatter.format(record)
        
        # Parse as JSON
        log_data = json.loads(formatted)
        
        # Verify required fields
        assert 'timestamp' in log_data
        assert 'level' in log_data
        assert 'message' in log_data
        assert 'logger' in log_data
        assert 'function' in log_data
        assert 'line' in log_data
        
        # Verify values
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'Test message'
        assert log_data['logger'] == 'test_logger'
        assert log_data['function'] == 'test_function'
        assert log_data['line'] == 42
        
        # Verify timestamp format (ISO 8601 with Z suffix)
        assert log_data['timestamp'].endswith('Z')
        datetime.fromisoformat(log_data['timestamp'].rstrip('Z'))
    
    def test_log_with_correlation_id(self):
        """Test that correlation ID is included in log output."""
        formatter = utils.JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        # Add correlation ID
        record.correlation_id = 'test-correlation-123'
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'correlationId' in log_data
        assert log_data['correlationId'] == 'test-correlation-123'
    
    def test_log_with_request_id(self):
        """Test that request ID is included in log output."""
        formatter = utils.JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        record.request_id = 'test-request-456'
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'requestId' in log_data
        assert log_data['requestId'] == 'test-request-456'
    
    def test_log_with_session_id(self):
        """Test that session ID is included in log output."""
        formatter = utils.JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        record.session_id = 'test-session-789'
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'sessionId' in log_data
        assert log_data['sessionId'] == 'test-session-789'
    
    def test_log_with_performance_metrics(self):
        """Test that performance metrics are included in log output."""
        formatter = utils.JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Performance metric',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        record.duration_ms = 123.45
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'durationMs' in log_data
        assert log_data['durationMs'] == 123.45
    
    def test_log_with_token_usage(self):
        """Test that token usage metrics are included in log output."""
        formatter = utils.JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Token usage',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        record.input_tokens = 100
        record.output_tokens = 50
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'inputTokens' in log_data
        assert 'outputTokens' in log_data
        assert log_data['inputTokens'] == 100
        assert log_data['outputTokens'] == 50
    
    def test_log_with_exception(self):
        """Test that exceptions are formatted in log output."""
        formatter = utils.JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.ERROR,
            pathname='test.py',
            lineno=42,
            msg='Error occurred',
            args=(),
            exc_info=exc_info,
            func='test_function'
        )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'exception' in log_data
        assert 'ValueError: Test error' in log_data['exception']
        assert 'Traceback' in log_data['exception']
    
    def test_log_with_extra_data(self):
        """Test that extra data is included in log output."""
        formatter = utils.JSONFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        record.extra_data = {
            'customField1': 'value1',
            'customField2': 123,
            'customField3': True
        }
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'customField1' in log_data
        assert 'customField2' in log_data
        assert 'customField3' in log_data
        assert log_data['customField1'] == 'value1'
        assert log_data['customField2'] == 123
        assert log_data['customField3'] is True
    
    def test_log_excludes_pii(self):
        """Test that logs do not contain PII in message content."""
        formatter = utils.JSONFormatter()
        
        # Simulate a log message that should not contain raw PII
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='User request processed',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        # Add sanitized metadata (no actual PII)
        record.extra_data = {
            'operation': 'chat_request',
            'messageLength': 150,
            'language': 'hi'
        }
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # Verify no PII fields are present
        assert 'email' not in log_data
        assert 'phone' not in log_data
        assert 'name' not in log_data
        assert 'address' not in log_data
        assert 'aadhaar' not in log_data
        
        # Verify only metadata is present
        assert log_data['operation'] == 'chat_request'
        assert log_data['messageLength'] == 150
        assert log_data['language'] == 'hi'


class TestLogWithContext:
    """Test structured logging with context."""
    
    @patch('shared.utils.logger')
    def test_log_with_correlation_id(self, mock_logger):
        """Test logging with correlation ID."""
        utils.log_with_context(
            'INFO',
            'Test message',
            correlation_id='test-correlation-123'
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        assert call_args[0][0] == 'Test message'
        assert 'correlation_id' in call_args[1]['extra']
        assert call_args[1]['extra']['correlation_id'] == 'test-correlation-123'
    
    @patch('shared.utils.logger')
    def test_log_with_request_id(self, mock_logger):
        """Test logging with request ID."""
        utils.log_with_context(
            'INFO',
            'Test message',
            request_id='test-request-456'
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        assert 'request_id' in call_args[1]['extra']
        assert call_args[1]['extra']['request_id'] == 'test-request-456'
    
    @patch('shared.utils.logger')
    def test_log_with_session_id(self, mock_logger):
        """Test logging with session ID."""
        utils.log_with_context(
            'INFO',
            'Test message',
            session_id='test-session-789'
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        assert 'session_id' in call_args[1]['extra']
        assert call_args[1]['extra']['session_id'] == 'test-session-789'
    
    @patch('shared.utils.logger')
    def test_log_with_duration(self, mock_logger):
        """Test logging with duration metric."""
        utils.log_with_context(
            'INFO',
            'Operation completed',
            duration_ms=123.45
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        assert 'duration_ms' in call_args[1]['extra']
        assert call_args[1]['extra']['duration_ms'] == 123.45
    
    @patch('shared.utils.logger')
    def test_log_with_extra_data(self, mock_logger):
        """Test logging with extra structured data."""
        extra_data = {
            'operation': 'test_operation',
            'status': 'success'
        }
        
        utils.log_with_context(
            'INFO',
            'Test message',
            extra_data=extra_data
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        assert 'extra_data' in call_args[1]['extra']
        assert call_args[1]['extra']['extra_data'] == extra_data


class TestPerformanceMetrics:
    """Test performance metric logging."""
    
    @patch('shared.utils.log_with_context')
    def test_log_performance_metric(self, mock_log):
        """Test that performance metrics are logged correctly."""
        utils.log_performance_metric(
            operation='test_operation',
            duration_ms=123.45,
            correlation_id='test-correlation-123'
        )
        
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        
        assert call_args[0][0] == 'INFO'
        assert 'test_operation' in call_args[0][1]
        assert '123.45ms' in call_args[0][1]
        assert call_args[1]['correlation_id'] == 'test-correlation-123'
        
        extra_data = call_args[1]['extra_data']
        assert extra_data['metricType'] == 'performance'
        assert extra_data['operation'] == 'test_operation'
        assert extra_data['durationMs'] == 123.45
    
    @patch('shared.utils.log_with_context')
    def test_log_performance_metric_with_metadata(self, mock_log):
        """Test performance metrics with additional metadata."""
        metadata = {
            'endpoint': '/chat',
            'statusCode': 200
        }
        
        utils.log_performance_metric(
            operation='api_request',
            duration_ms=250.0,
            metadata=metadata
        )
        
        mock_log.assert_called_once()
        extra_data = mock_log.call_args[1]['extra_data']
        
        assert extra_data['endpoint'] == '/chat'
        assert extra_data['statusCode'] == 200


class TestTokenUsageMetrics:
    """Test token usage metric logging."""
    
    @patch('shared.utils.logger')
    def test_log_token_usage(self, mock_logger):
        """Test that token usage is logged correctly."""
        utils.log_token_usage(
            operation='bedrock_invoke',
            input_tokens=100,
            output_tokens=50,
            correlation_id='test-correlation-123',
            model_id='anthropic.claude-3-sonnet'
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        # Verify message content
        message = call_args[0][0]
        assert 'bedrock_invoke' in message
        assert 'Input: 100' in message
        assert 'Output: 50' in message
        assert 'Total: 150' in message
        
        # Verify extra data
        extra = call_args[1]['extra']
        assert extra['correlation_id'] == 'test-correlation-123'
        assert extra['input_tokens'] == 100
        assert extra['output_tokens'] == 50
        
        extra_data = extra['extra_data']
        assert extra_data['metricType'] == 'tokenUsage'
        assert extra_data['operation'] == 'bedrock_invoke'
        assert extra_data['inputTokens'] == 100
        assert extra_data['outputTokens'] == 50
        assert extra_data['totalTokens'] == 150
        assert extra_data['modelId'] == 'anthropic.claude-3-sonnet'
    
    @patch('shared.utils.logger')
    def test_log_token_usage_without_model_id(self, mock_logger):
        """Test token usage logging without model ID."""
        utils.log_token_usage(
            operation='bedrock_invoke',
            input_tokens=100,
            output_tokens=50
        )
        
        mock_logger.info.assert_called_once()
        extra_data = mock_logger.info.call_args[1]['extra']['extra_data']
        
        # Model ID should not be present
        assert 'modelId' not in extra_data


class TestAPICallMetrics:
    """Test API call metric logging."""
    
    @patch('shared.utils.log_with_context')
    def test_log_successful_api_call(self, mock_log):
        """Test logging successful API calls."""
        utils.log_api_call(
            service='bedrock',
            operation='InvokeModel',
            duration_ms=500.0,
            correlation_id='test-correlation-123',
            success=True
        )
        
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        
        assert call_args[0][0] == 'INFO'
        assert 'bedrock.InvokeModel' in call_args[0][1]
        assert 'Success' in call_args[0][1]
        assert '500.00ms' in call_args[0][1]
        
        extra_data = call_args[1]['extra_data']
        assert extra_data['metricType'] == 'apiCall'
        assert extra_data['service'] == 'bedrock'
        assert extra_data['operation'] == 'InvokeModel'
        assert extra_data['durationMs'] == 500.0
        assert extra_data['success'] is True
        assert 'error' not in extra_data
    
    @patch('shared.utils.log_with_context')
    def test_log_failed_api_call(self, mock_log):
        """Test logging failed API calls."""
        utils.log_api_call(
            service='translate',
            operation='TranslateText',
            duration_ms=100.0,
            correlation_id='test-correlation-123',
            success=False,
            error='ServiceUnavailable'
        )
        
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        
        assert call_args[0][0] == 'ERROR'
        assert 'translate.TranslateText' in call_args[0][1]
        assert 'Failed' in call_args[0][1]
        
        extra_data = call_args[1]['extra_data']
        assert extra_data['success'] is False
        assert extra_data['error'] == 'ServiceUnavailable'


class TestCorrelationID:
    """Test correlation ID generation."""
    
    def test_get_correlation_id_format(self):
        """Test that correlation ID is a valid UUID."""
        correlation_id = utils.get_correlation_id()
        
        # Should be a valid UUID string
        assert isinstance(correlation_id, str)
        assert len(correlation_id) == 36
        assert correlation_id.count('-') == 4
        
        # Should be parseable as UUID
        import uuid
        uuid.UUID(correlation_id)
    
    def test_get_correlation_id_uniqueness(self):
        """Test that correlation IDs are unique."""
        id1 = utils.get_correlation_id()
        id2 = utils.get_correlation_id()
        id3 = utils.get_correlation_id()
        
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3


class TestHandleExceptionsDecorator:
    """Test exception handling decorator with logging."""
    
    @pytest.mark.skip(reason="handle_exceptions decorator removed during FastAPI migration - now using FastAPI exception handlers")
    def test_decorator_adds_correlation_id(self):
        """Test that decorator adds correlation ID to event."""
        @utils.handle_exceptions
        def test_handler(event, context):
            assert 'correlationId' in event
            assert len(event['correlationId']) == 36
            return utils.create_response(200, {'message': 'success'})
        
        event = {
            'httpMethod': 'GET',
            'path': '/test',
            'requestContext': {
                'requestId': 'test-request-id',
                'identity': {'sourceIp': '127.0.0.1'}
            }
        }
        
        response = test_handler(event, None)
        assert response['statusCode'] == 200
    
    @pytest.mark.skip(reason="handle_exceptions decorator removed during FastAPI migration - now using FastAPI exception handlers")
    @patch('shared.utils.log_with_context')
    def test_decorator_logs_request_start(self, mock_log):
        """Test that decorator logs request start."""
        @utils.handle_exceptions
        def test_handler(event, context):
            return utils.create_response(200, {'message': 'success'})
        
        event = {
            'httpMethod': 'POST',
            'path': '/chat',
            'requestContext': {
                'requestId': 'test-request-id',
                'identity': {'sourceIp': '127.0.0.1'}
            }
        }
        
        test_handler(event, None)
        
        # Should have at least 2 calls: start and completion
        assert mock_log.call_count >= 2
        
        # Check first call (request start)
        first_call = mock_log.call_args_list[0]
        assert first_call[0][0] == 'INFO'
        assert 'Request started' in first_call[0][1]
        assert 'POST' in first_call[0][1]
        assert '/chat' in first_call[0][1]
    
    @pytest.mark.skip(reason="handle_exceptions decorator removed during FastAPI migration - now using FastAPI exception handlers")
    @patch('shared.utils.log_with_context')
    def test_decorator_logs_request_completion(self, mock_log):
        """Test that decorator logs request completion with duration."""
        @utils.handle_exceptions
        def test_handler(event, context):
            import time
            time.sleep(0.001)  # Small delay to ensure measurable duration
            return utils.create_response(200, {'message': 'success'})
        
        event = {
            'httpMethod': 'GET',
            'path': '/schemes',
            'requestContext': {
                'requestId': 'test-request-id',
                'identity': {'sourceIp': '127.0.0.1'}
            }
        }
        
        test_handler(event, None)
        
        # Check last call (request completion)
        last_call = mock_log.call_args_list[-1]
        assert last_call[0][0] == 'INFO'
        assert 'Request completed successfully' in last_call[0][1]
        
        # Should include duration
        assert 'duration_ms' in last_call[1]
        assert last_call[1]['duration_ms'] >= 0  # Duration should be non-negative
    
    @pytest.mark.skip(reason="handle_exceptions decorator removed during FastAPI migration - now using FastAPI exception handlers")
    @patch('shared.utils.log_with_context')
    def test_decorator_logs_errors(self, mock_log):
        """Test that decorator logs errors with stack traces."""
        @utils.handle_exceptions
        def test_handler(event, context):
            raise ValueError("Test error")
        
        event = {
            'httpMethod': 'POST',
            'path': '/test',
            'requestContext': {
                'requestId': 'test-request-id',
                'identity': {'sourceIp': '127.0.0.1'}
            }
        }
        
        response = test_handler(event, None)
        
        # Should return error response
        assert response['statusCode'] == 400
        
        # Should log the error
        error_calls = [call for call in mock_log.call_args_list if call[0][0] == 'WARNING']
        assert len(error_calls) > 0
        assert 'Validation error' in error_calls[0][0][1]


class TestMetricEmission:
    """Test that metrics are emitted correctly for CloudWatch."""
    
    @patch('shared.utils.logger')
    def test_performance_metric_emission(self, mock_logger):
        """Test that performance metrics are emitted in correct format."""
        utils.log_performance_metric(
            operation='api_request',
            duration_ms=123.45,
            correlation_id='test-123'
        )
        
        # Verify logger was called
        mock_logger.info.assert_called_once()
        
        # Get the extra data
        extra = mock_logger.info.call_args[1]['extra']
        extra_data = extra['extra_data']
        
        # Verify metric structure for CloudWatch parsing
        assert extra_data['metricType'] == 'performance'
        assert extra_data['operation'] == 'api_request'
        assert extra_data['durationMs'] == 123.45
        
        # Verify correlation ID for tracing
        assert extra['correlation_id'] == 'test-123'
    
    @patch('shared.utils.logger')
    def test_token_usage_metric_emission(self, mock_logger):
        """Test that token usage metrics are emitted in correct format."""
        utils.log_token_usage(
            operation='bedrock_invoke',
            input_tokens=100,
            output_tokens=50,
            model_id='claude-3'
        )
        
        mock_logger.info.assert_called_once()
        
        extra = mock_logger.info.call_args[1]['extra']
        extra_data = extra['extra_data']
        
        # Verify metric structure
        assert extra_data['metricType'] == 'tokenUsage'
        assert extra_data['inputTokens'] == 100
        assert extra_data['outputTokens'] == 50
        assert extra_data['totalTokens'] == 150
        assert extra_data['modelId'] == 'claude-3'
    
    @patch('shared.utils.log_with_context')
    def test_api_call_metric_emission(self, mock_log):
        """Test that API call metrics are emitted in correct format."""
        utils.log_api_call(
            service='dynamodb',
            operation='PutItem',
            duration_ms=25.5,
            success=True
        )
        
        mock_log.assert_called_once()
        extra_data = mock_log.call_args[1]['extra_data']
        
        # Verify metric structure
        assert extra_data['metricType'] == 'apiCall'
        assert extra_data['service'] == 'dynamodb'
        assert extra_data['operation'] == 'PutItem'
        assert extra_data['durationMs'] == 25.5
        assert extra_data['success'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
