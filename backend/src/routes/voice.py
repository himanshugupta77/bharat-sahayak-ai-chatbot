"""Voice route handlers for FastAPI."""

import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.models import (
    TextToSpeechRequest,
    TextToSpeechResponse,
    VoiceToTextRequest,
    VoiceToTextResponse
)
from shared.utils import (
    get_polly_client,
    get_s3_client,
    get_transcribe_client,
    retry_with_backoff,
    sanitize_input,
    validate_language_code,
    validate_audio_format,
    get_current_timestamp,
    logger
)

# Create router
router = APIRouter()

# Voice mapping for supported languages
# Using Amazon Polly neural voices for Indian languages
# Note: Polly has limited native support for Indian languages beyond Hindi
# For languages without native voices, we use Indian English (Kajal) which provides
# better pronunciation of Indian names and terms compared to standard English voices
VOICE_MAP = {
    'en': 'Kajal',      # Indian English, female, neural
    'hi': 'Aditi',      # Hindi, female, standard (neural not available)
    'mr': 'Kajal',      # Marathi (using Indian English voice)
    'ta': 'Kajal',      # Tamil (using Indian English voice)
    'te': 'Kajal',      # Telugu (using Indian English voice)
    'bn': 'Kajal',      # Bengali (using Indian English voice)
    'gu': 'Kajal',      # Gujarati (using Indian English voice)
    'kn': 'Kajal',      # Kannada (using Indian English voice)
    'ml': 'Kajal',      # Malayalam (using Indian English voice)
    'pa': 'Kajal',      # Punjabi (using Indian English voice)
    'or': 'Kajal'       # Odia (using Indian English voice)
}

# Engine selection per voice
# Kajal supports neural engine, Aditi only supports standard
VOICE_ENGINE = {
    'Kajal': 'neural',
    'Aditi': 'standard'
}


@router.post("/voice/text-to-speech", status_code=status.HTTP_200_OK)
async def text_to_speech(
    request: Request,
    tts_request: TextToSpeechRequest
):
    """
    Generate speech audio using Amazon Polly.
    
    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 9.7
    
    Args:
        request: FastAPI Request object
        tts_request: Validated TextToSpeechRequest from request body
    
    Returns:
        TextToSpeechResponse with audio data
    """
    # Get correlation ID from request state (set by middleware)
    correlation_id = getattr(request.state, 'correlation_id', None)
    
    # Sanitize and validate inputs
    try:
        text = sanitize_input(tts_request.text, max_length=3000)
        language = validate_language_code(tts_request.language)
        low_bandwidth = tts_request.lowBandwidth
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
    
    # Log request
    logger.info(
        f"Text-to-speech request: language={language}, "
        f"text_length={len(text)}, lowBandwidth={low_bandwidth}",
        extra={'correlation_id': correlation_id}
    )
    
    # Select voice for language
    voice_id = VOICE_MAP.get(language, 'Kajal')
    engine = VOICE_ENGINE.get(voice_id, 'neural')
    
    # Determine output format based on bandwidth mode
    # Note: Polly supports mp3, ogg_vorbis, and pcm
    # For low bandwidth, we use ogg_vorbis which provides better compression than mp3
    if low_bandwidth:
        output_format = 'ogg_vorbis'  # Better compression for low bandwidth
    else:
        output_format = 'mp3'  # Standard format
    
    try:
        # Synthesize speech
        audio_data, duration = synthesize_speech(
            text,
            voice_id,
            engine,
            output_format,
            correlation_id
        )
        
        # Encode to base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        # Log response
        logger.info(
            f"Speech synthesized: {len(audio_data)} bytes, {duration:.2f}s, format={output_format}",
            extra={'correlation_id': correlation_id}
        )
        
        # Create response
        # Note: We return 'opus' in the format field for low bandwidth mode
        # even though we're using ogg_vorbis, as they're compatible
        response_format = 'opus' if low_bandwidth else 'mp3'
        response = TextToSpeechResponse(
            audioData=audio_base64,
            format=response_format,
            duration=duration,
            sizeBytes=len(audio_data)
        )
        
        return response.model_dump()
        
    except Exception as e:
        logger.error(
            f"Text-to-speech failed: {e}",
            exc_info=True,
            extra={'correlation_id': correlation_id}
        )
        error_body = {
            'error': 'SynthesisError',
            'message': 'Failed to generate speech audio. Please try again.',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body
        )


@router.post("/voice/speech-to-text", status_code=status.HTTP_200_OK)
async def speech_to_text(
    request: Request,
    stt_request: VoiceToTextRequest
):
    """
    Transcribe audio to text using Amazon Transcribe.
    
    Args:
        request: FastAPI Request object
        stt_request: Validated VoiceToTextRequest from request body
    
    Returns:
        VoiceToTextResponse with transcript
    """
    # Get correlation ID from request state (set by middleware)
    correlation_id = getattr(request.state, 'correlation_id', None)
    
    # Validate audio format
    try:
        audio_format = validate_audio_format(stt_request.format)
    except ValueError as e:
        error_body = {
            'error': 'ValidationError',
            'message': str(e),
            'field': 'format',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
    
    # Validate audio data is present
    if not stt_request.audioData:
        error_body = {
            'error': 'ValidationError',
            'message': 'audioData field is required',
            'field': 'audioData',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
    
    # Decode base64 audio data
    try:
        audio_bytes = base64.b64decode(stt_request.audioData)
    except Exception as e:
        logger.error(
            f"Failed to decode audio data: {e}",
            extra={'correlation_id': correlation_id}
        )
        error_body = {
            'error': 'InvalidAudioData',
            'message': 'Audio data must be valid base64-encoded string',
            'field': 'audioData',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
    
    # Check audio size (max 10MB)
    if len(audio_bytes) > 10 * 1024 * 1024:
        error_body = {
            'error': 'PayloadTooLarge',
            'message': 'Audio file exceeds maximum size of 10MB',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content=error_body
        )
    
    # Log request
    logger.info(
        f"Speech-to-text request: format={audio_format}, size={len(audio_bytes)} bytes",
        extra={'correlation_id': correlation_id}
    )
    
    # Upload to S3 temporary bucket
    s3_key = None
    
    try:
        s3_key = upload_to_s3(audio_bytes, audio_format, correlation_id)
        
        # Start transcription job
        job_name = start_transcription_job(s3_key, audio_format, correlation_id)
        
        # Wait for completion
        transcript, language, confidence = wait_for_transcription(job_name, correlation_id)
        
        # Create response
        response = VoiceToTextResponse(
            transcript=transcript,
            detectedLanguage=language,
            confidence=confidence
        )
        
        return response.model_dump()
    
    except ValueError as e:
        # Handle audio quality errors
        error_msg = str(e)
        if "Audio quality is too low" in error_msg or "No speech detected" in error_msg:
            error_body = {
                'error': 'AudioQualityError',
                'message': error_msg,
                'timestamp': get_current_timestamp()
            }
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_body
            )
        
        # Other validation errors
        logger.error(
            f"Speech-to-text validation error: {e}",
            extra={'correlation_id': correlation_id}
        )
        error_body = {
            'error': 'TranscriptionError',
            'message': str(e),
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body
        )
        
    except TimeoutError as e:
        logger.error(
            f"Transcription timeout: {e}",
            extra={'correlation_id': correlation_id}
        )
        error_body = {
            'error': 'TranscriptionTimeout',
            'message': str(e),
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body
        )
        
    except Exception as e:
        logger.error(
            f"Speech-to-text failed: {e}",
            exc_info=True,
            extra={'correlation_id': correlation_id}
        )
        error_body = {
            'error': 'TranscriptionError',
            'message': 'Failed to transcribe audio. Please try again.',
            'timestamp': get_current_timestamp()
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body
        )
        
    finally:
        # Clean up S3 object
        if s3_key:
            delete_from_s3(s3_key, correlation_id)


def synthesize_speech(
    text: str,
    voice_id: str,
    engine: str,
    output_format: str,
    correlation_id: Optional[str] = None
) -> tuple:
    """
    Synthesize speech using Amazon Polly.
    
    Args:
        text: Text to synthesize
        voice_id: Polly voice ID
        engine: Polly engine ('neural' or 'standard')
        output_format: Output audio format ('mp3' or 'ogg_vorbis')
        correlation_id: Correlation ID for request tracing
    
    Returns:
        Tuple of (audio_bytes, duration_seconds)
    """
    polly_client = get_polly_client()
    
    # Prepare synthesis parameters
    synthesis_params = {
        'Text': text,
        'OutputFormat': output_format,
        'VoiceId': voice_id,
        'Engine': engine
    }
    
    def _synthesize():
        response = polly_client.synthesize_speech(**synthesis_params)
        
        # Read audio stream
        audio_stream = response['AudioStream']
        audio_data = audio_stream.read()
        
        # Calculate duration more accurately
        # Polly returns RequestCharacters which we can use for estimation
        # Average speaking rate: ~150 words per minute = 2.5 words per second
        # Average word length: ~5 characters
        # So roughly: characters / (2.5 * 5) = characters / 12.5 seconds per character
        char_count = len(text)
        duration = char_count / 12.5  # More accurate than word-based calculation
        
        # Minimum duration of 0.5 seconds for very short text
        duration = max(duration, 0.5)
        
        return audio_data, duration
    
    try:
        audio_data, duration = retry_with_backoff(_synthesize, max_retries=3)
        
        # Log compression ratio for low bandwidth mode
        if output_format == 'ogg_vorbis':
            # OGG Vorbis typically achieves 40-60% size reduction compared to MP3
            logger.info(
                f"Low bandwidth mode: using OGG Vorbis format for compression",
                extra={'correlation_id': correlation_id}
            )
        
        logger.info(
            f"Synthesized speech: {len(audio_data)} bytes, ~{duration:.1f}s, "
            f"voice={voice_id}, engine={engine}, format={output_format}",
            extra={'correlation_id': correlation_id}
        )
        return audio_data, duration
        
    except Exception as e:
        logger.error(
            f"Speech synthesis failed: {e}",
            extra={'correlation_id': correlation_id}
        )
        raise


def upload_to_s3(
    audio_bytes: bytes,
    format: str,
    correlation_id: Optional[str] = None
) -> str:
    """
    Upload audio to S3 temporary bucket with 1-hour expiration.
    
    Args:
        audio_bytes: Audio data bytes
        format: Audio format (webm, mp3, wav)
        correlation_id: Correlation ID for request tracing
    
    Returns:
        S3 key of uploaded file
    """
    s3_client = get_s3_client()
    bucket_name = os.environ.get('S3_TEMP_BUCKET')
    
    if not bucket_name:
        raise ValueError("S3_TEMP_BUCKET environment variable not set")
    
    # Generate unique key
    file_extension = format
    s3_key = f'audio/{uuid.uuid4()}.{file_extension}'
    
    # Calculate expiration time (1 hour from now)
    expiration = datetime.utcnow() + timedelta(hours=1)
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=audio_bytes,
            ContentType=f'audio/{format}',
            Expires=expiration,
            Metadata={
                'ttl': str(int(expiration.timestamp()))
            }
        )
        
        logger.info(
            f"Uploaded audio to s3://{bucket_name}/{s3_key} with 1-hour TTL",
            extra={'correlation_id': correlation_id}
        )
        return s3_key
        
    except Exception as e:
        logger.error(
            f"Failed to upload to S3: {e}",
            extra={'correlation_id': correlation_id}
        )
        raise


def start_transcription_job(
    s3_key: str,
    format: str,
    correlation_id: Optional[str] = None
) -> str:
    """
    Start Amazon Transcribe job.
    
    Args:
        s3_key: S3 key of audio file
        format: Audio format (webm, mp3, wav)
        correlation_id: Correlation ID for request tracing
    
    Returns:
        Transcription job name
    """
    transcribe_client = get_transcribe_client()
    bucket_name = os.environ.get('S3_TEMP_BUCKET')
    
    job_name = f'transcribe-{uuid.uuid4()}'
    
    # Map format to Transcribe media format
    media_format_map = {
        'webm': 'webm',
        'mp3': 'mp3',
        'wav': 'wav'
    }
    
    media_format = media_format_map.get(format, 'mp3')
    
    try:
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={
                'MediaFileUri': f's3://{bucket_name}/{s3_key}'
            },
            MediaFormat=media_format,
            IdentifyLanguage=True,
            LanguageOptions=[
                'en-IN', 'hi-IN', 'mr-IN', 'ta-IN', 'te-IN',
                'bn-IN', 'gu-IN', 'kn-IN', 'ml-IN', 'pa-IN', 'or-IN'
            ]
        )
        
        logger.info(
            f"Started transcription job: {job_name}",
            extra={'correlation_id': correlation_id}
        )
        return job_name
        
    except Exception as e:
        logger.error(
            f"Failed to start transcription job: {e}",
            extra={'correlation_id': correlation_id}
        )
        raise


def wait_for_transcription(
    job_name: str,
    correlation_id: Optional[str] = None,
    max_wait: int = 30
) -> tuple:
    """
    Wait for transcription job to complete.
    
    Args:
        job_name: Transcription job name
        correlation_id: Correlation ID for request tracing
        max_wait: Maximum wait time in seconds
    
    Returns:
        Tuple of (transcript, language, confidence)
    """
    transcribe_client = get_transcribe_client()
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            status = response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                # Get transcript
                transcript_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                transcript_data = get_transcript_from_uri(transcript_uri, correlation_id)
                
                # Extract transcript text
                transcripts = transcript_data['results'].get('transcripts', [])
                if not transcripts or not transcripts[0].get('transcript'):
                    logger.warning(
                        "Empty transcript received",
                        extra={'correlation_id': correlation_id}
                    )
                    raise ValueError(
                        "No speech detected in audio. Please speak clearly and try again."
                    )
                
                transcript = transcripts[0]['transcript']
                
                # Get detected language
                language_code = response['TranscriptionJob'].get('LanguageCode', 'en-IN')
                language = language_code.split('-')[0]  # Extract language code (e.g., 'en' from 'en-IN')
                
                # Get confidence (average of all items)
                items = transcript_data['results'].get('items', [])
                confidences = [
                    float(item.get('alternatives', [{}])[0].get('confidence', 0))
                    for item in items
                    if 'alternatives' in item
                ]
                confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                # Check if confidence is too low (audio quality issue)
                if confidence < 0.5:
                    logger.warning(
                        f"Low confidence transcription: {confidence}",
                        extra={'correlation_id': correlation_id}
                    )
                    raise ValueError(
                        f"Audio quality is too low for transcription (confidence: {confidence:.2f}). "
                        "Please speak clearly and try again."
                    )
                
                logger.info(
                    f"Transcription completed: {transcript[:50]}... (confidence: {confidence:.2f})",
                    extra={'correlation_id': correlation_id}
                )
                return transcript, language, confidence
                
            elif status == 'FAILED':
                failure_reason = response['TranscriptionJob'].get('FailureReason', 'Unknown')
                logger.error(
                    f"Transcription failed: {failure_reason}",
                    extra={'correlation_id': correlation_id}
                )
                raise ValueError(f"Transcription failed: {failure_reason}")
            
            # Wait before polling again
            time.sleep(1)
            
        except Exception as e:
            logger.error(
                f"Error checking transcription status: {e}",
                extra={'correlation_id': correlation_id}
            )
            raise
    
    # Timeout
    logger.error(
        f"Transcription timeout after {max_wait}s",
        extra={'correlation_id': correlation_id}
    )
    raise TimeoutError(f"Transcription did not complete within {max_wait} seconds")


def get_transcript_from_uri(
    uri: str,
    correlation_id: Optional[str] = None
) -> dict:
    """
    Fetch transcript JSON from URI.
    
    Args:
        uri: Transcript file URI
        correlation_id: Correlation ID for request tracing
    
    Returns:
        Transcript data dictionary
    """
    import urllib.request
    
    try:
        with urllib.request.urlopen(uri) as response:
            return json.loads(response.read())
    except Exception as e:
        logger.error(
            f"Failed to fetch transcript: {e}",
            extra={'correlation_id': correlation_id}
        )
        raise


def delete_from_s3(
    s3_key: str,
    correlation_id: Optional[str] = None
):
    """
    Delete audio file from S3.
    
    Args:
        s3_key: S3 key of audio file
        correlation_id: Correlation ID for request tracing
    """
    s3_client = get_s3_client()
    bucket_name = os.environ.get('S3_TEMP_BUCKET')
    
    try:
        s3_client.delete_object(
            Bucket=bucket_name,
            Key=s3_key
        )
        logger.info(
            f"Deleted s3://{bucket_name}/{s3_key}",
            extra={'correlation_id': correlation_id}
        )
    except Exception as e:
        logger.warning(
            f"Failed to delete S3 object: {e}",
            extra={'correlation_id': correlation_id}
        )
