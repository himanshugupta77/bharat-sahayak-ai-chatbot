"""Basic unit tests for voice route handlers."""

import base64
import json
import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app

client = TestClient(app)


class TestTextToSpeech:
    """Test cases for POST /voice/text-to-speech endpoint."""
    
    @patch('routes.voice.synthesize_speech')
    def test_text_to_speech_success(self, mock_synthesize):
        """Test successful text-to-speech conversion."""
        # Mock synthesize_speech to return audio data
        mock_audio = b'fake_audio_data'
        mock_synthesize.return_value = (mock_audio, 2.5)
        
        request_data = {
            'text': 'Hello, this is a test.',
            'language': 'en',
            'lowBandwidth': False
        }
        
        response = client.post('/voice/text-to-speech', json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert 'audioData' in data
        assert 'format' in data
        assert 'duration' in data
        assert 'sizeBytes' in data
        assert data['format'] == 'mp3'
        assert data['duration'] == 2.5
    
    @patch('routes.voice.synthesize_speech')
    def test_text_to_speech_low_bandwidth(self, mock_synthesize):
        """Test text-to-speech with low bandwidth mode."""
        mock_audio = b'fake_audio_data'
        mock_synthesize.return_value = (mock_audio, 2.5)
        
        request_data = {
            'text': 'Hello, this is a test.',
            'language': 'en',
            'lowBandwidth': True
        }
        
        response = client.post('/voice/text-to-speech', json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Low bandwidth mode should return opus format
        assert data['format'] == 'opus'
    
    @patch('routes.voice.synthesize_speech')
    def test_text_to_speech_hindi(self, mock_synthesize):
        """Test text-to-speech with Hindi language."""
        mock_audio = b'fake_audio_data'
        mock_synthesize.return_value = (mock_audio, 2.5)
        
        request_data = {
            'text': 'नमस्ते, यह एक परीक्षण है।',
            'language': 'hi',
            'lowBandwidth': False
        }
        
        response = client.post('/voice/text-to-speech', json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify correct voice was selected (Aditi for Hindi)
        mock_synthesize.assert_called_once()
        call_args = mock_synthesize.call_args[0]
        assert call_args[1] == 'Aditi'  # voice_id
        assert call_args[2] == 'standard'  # engine
    
    def test_text_to_speech_empty_text(self):
        """Test text-to-speech with empty text returns 400."""
        request_data = {
            'text': '',
            'language': 'en',
            'lowBandwidth': False
        }
        
        response = client.post('/voice/text-to-speech', json=request_data)
        
        # Pydantic validation should fail for empty text
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_text_to_speech_text_too_long(self):
        """Test text-to-speech with text exceeding max length."""
        request_data = {
            'text': 'a' * 3001,  # Exceeds 3000 character limit
            'language': 'en',
            'lowBandwidth': False
        }
        
        response = client.post('/voice/text-to-speech', json=request_data)
        
        # Pydantic validation should fail
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_text_to_speech_invalid_language(self):
        """Test text-to-speech with invalid language code."""
        request_data = {
            'text': 'Hello, this is a test.',
            'language': 'invalid',
            'lowBandwidth': False
        }
        
        response = client.post('/voice/text-to-speech', json=request_data)
        
        # Pydantic validation happens first (422), then route validation (400)
        # Invalid language is caught by Pydantic model validation
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    @patch('routes.voice.synthesize_speech')
    def test_text_to_speech_synthesis_error(self, mock_synthesize):
        """Test text-to-speech when synthesis fails."""
        mock_synthesize.side_effect = Exception('Polly service error')
        
        request_data = {
            'text': 'Hello, this is a test.',
            'language': 'en',
            'lowBandwidth': False
        }
        
        response = client.post('/voice/text-to-speech', json=request_data)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert data['error'] == 'SynthesisError'


class TestSpeechToText:
    """Test cases for POST /voice/speech-to-text endpoint."""
    
    @patch('routes.voice.upload_to_s3')
    @patch('routes.voice.start_transcription_job')
    @patch('routes.voice.wait_for_transcription')
    @patch('routes.voice.delete_from_s3')
    def test_speech_to_text_success(
        self,
        mock_delete,
        mock_wait,
        mock_start,
        mock_upload
    ):
        """Test successful speech-to-text conversion."""
        # Mock the transcription pipeline
        mock_upload.return_value = 'audio/test-key.mp3'
        mock_start.return_value = 'job-123'
        mock_wait.return_value = ('Hello, this is a test.', 'en', 0.95)
        
        # Create fake audio data
        fake_audio = b'fake_audio_data'
        audio_base64 = base64.b64encode(fake_audio).decode('utf-8')
        
        request_data = {
            'audioData': audio_base64,
            'format': 'mp3'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert 'transcript' in data
        assert 'detectedLanguage' in data
        assert 'confidence' in data
        assert data['transcript'] == 'Hello, this is a test.'
        assert data['detectedLanguage'] == 'en'
        assert data['confidence'] == 0.95
        
        # Verify cleanup was called (with correlation_id)
        assert mock_delete.call_count == 1
        call_args = mock_delete.call_args[0]
        assert call_args[0] == 'audio/test-key.mp3'
    
    @patch('routes.voice.upload_to_s3')
    @patch('routes.voice.start_transcription_job')
    @patch('routes.voice.wait_for_transcription')
    @patch('routes.voice.delete_from_s3')
    def test_speech_to_text_webm_format(
        self,
        mock_delete,
        mock_wait,
        mock_start,
        mock_upload
    ):
        """Test speech-to-text with webm format."""
        mock_upload.return_value = 'audio/test-key.webm'
        mock_start.return_value = 'job-123'
        mock_wait.return_value = ('Test transcript', 'en', 0.90)
        
        fake_audio = b'fake_audio_data'
        audio_base64 = base64.b64encode(fake_audio).decode('utf-8')
        
        request_data = {
            'audioData': audio_base64,
            'format': 'webm'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_speech_to_text_invalid_format(self):
        """Test speech-to-text with invalid audio format."""
        fake_audio = b'fake_audio_data'
        audio_base64 = base64.b64encode(fake_audio).decode('utf-8')
        
        request_data = {
            'audioData': audio_base64,
            'format': 'invalid'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        # Pydantic validation happens first (422), then route validation (400)
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    def test_speech_to_text_missing_audio_data(self):
        """Test speech-to-text with missing audio data."""
        request_data = {
            'audioData': '',
            'format': 'mp3'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['error'] == 'ValidationError'
        assert data['field'] == 'audioData'
    
    def test_speech_to_text_invalid_base64(self):
        """Test speech-to-text with invalid base64 data."""
        request_data = {
            'audioData': 'not-valid-base64!!!',
            'format': 'mp3'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['error'] == 'InvalidAudioData'
    
    def test_speech_to_text_file_too_large(self):
        """Test speech-to-text with file exceeding 10MB limit."""
        # Create audio data larger than 10MB
        large_audio = b'x' * (11 * 1024 * 1024)
        audio_base64 = base64.b64encode(large_audio).decode('utf-8')
        
        request_data = {
            'audioData': audio_base64,
            'format': 'mp3'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        data = response.json()
        assert data['error'] == 'PayloadTooLarge'
    
    @patch('routes.voice.upload_to_s3')
    @patch('routes.voice.start_transcription_job')
    @patch('routes.voice.wait_for_transcription')
    @patch('routes.voice.delete_from_s3')
    def test_speech_to_text_low_quality_audio(
        self,
        mock_delete,
        mock_wait,
        mock_start,
        mock_upload
    ):
        """Test speech-to-text with low quality audio."""
        mock_upload.return_value = 'audio/test-key.mp3'
        mock_start.return_value = 'job-123'
        mock_wait.side_effect = ValueError('Audio quality is too low for transcription')
        
        fake_audio = b'fake_audio_data'
        audio_base64 = base64.b64encode(fake_audio).decode('utf-8')
        
        request_data = {
            'audioData': audio_base64,
            'format': 'mp3'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['error'] == 'AudioQualityError'
        
        # Verify cleanup was still called
        mock_delete.assert_called_once()
    
    @patch('routes.voice.upload_to_s3')
    @patch('routes.voice.start_transcription_job')
    @patch('routes.voice.wait_for_transcription')
    @patch('routes.voice.delete_from_s3')
    def test_speech_to_text_no_speech_detected(
        self,
        mock_delete,
        mock_wait,
        mock_start,
        mock_upload
    ):
        """Test speech-to-text when no speech is detected."""
        mock_upload.return_value = 'audio/test-key.mp3'
        mock_start.return_value = 'job-123'
        mock_wait.side_effect = ValueError('No speech detected in audio')
        
        fake_audio = b'fake_audio_data'
        audio_base64 = base64.b64encode(fake_audio).decode('utf-8')
        
        request_data = {
            'audioData': audio_base64,
            'format': 'mp3'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['error'] == 'AudioQualityError'
    
    @patch('routes.voice.upload_to_s3')
    @patch('routes.voice.start_transcription_job')
    @patch('routes.voice.wait_for_transcription')
    @patch('routes.voice.delete_from_s3')
    def test_speech_to_text_timeout(
        self,
        mock_delete,
        mock_wait,
        mock_start,
        mock_upload
    ):
        """Test speech-to-text when transcription times out."""
        mock_upload.return_value = 'audio/test-key.mp3'
        mock_start.return_value = 'job-123'
        mock_wait.side_effect = TimeoutError('Transcription did not complete within 30 seconds')
        
        fake_audio = b'fake_audio_data'
        audio_base64 = base64.b64encode(fake_audio).decode('utf-8')
        
        request_data = {
            'audioData': audio_base64,
            'format': 'mp3'
        }
        
        response = client.post('/voice/speech-to-text', json=request_data)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert data['error'] == 'TranscriptionTimeout'
        
        # Verify cleanup was still called
        mock_delete.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
