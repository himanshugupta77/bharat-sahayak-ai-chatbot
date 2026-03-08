"""
FastAPI application entry point for Bharat Sahayak API.

This module initializes the FastAPI application with middleware for CORS,
request logging, and error handling. It serves as the main entry point for
the migrated backend from AWS Lambda to EC2 deployment.
"""

import json
import logging
import os
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv not installed, rely on system environment variables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Bharat Sahayak API")
    logger.info("Server listening on host 0.0.0.0, port 8000")
    yield
    # Shutdown
    logger.info("Shutting down Bharat Sahayak API")


# Initialize FastAPI application
app = FastAPI(
    title="Bharat Sahayak API",
    description="Government welfare scheme discovery platform",
    version="1.0.0",
    lifespan=lifespan
)


# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on environment in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all incoming requests and responses with structured JSON format.
    
    Logs include:
    - Correlation ID for request tracking
    - Source IP address
    - HTTP method and path
    - Request duration
    - Response status code
    """
    # Generate correlation ID for request tracking
    correlation_id = str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    
    # Extract source IP
    source_ip = request.client.host if request.client else "unknown"
    
    # Log request start
    logger.info(json.dumps({
        "event": "request_start",
        "correlation_id": correlation_id,
        "method": request.method,
        "path": request.url.path,
        "source_ip": source_ip,
        "timestamp": time.time()
    }))
    
    # Process request
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Log request completion
    logger.info(json.dumps({
        "event": "request_complete",
        "correlation_id": correlation_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": round(duration * 1000, 2),
        "source_ip": source_ip,
        "timestamp": time.time()
    }))
    
    return response


# Global Error Handling Middleware
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch all unhandled exceptions and return standardized error responses.
    
    Logs errors with correlation ID and stack trace for debugging.
    Returns a generic error message to avoid exposing internal details.
    """
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    
    # Log error with stack trace
    logger.error(json.dumps({
        "event": "unhandled_exception",
        "correlation_id": correlation_id,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "path": request.url.path,
        "method": request.method,
        "stack_trace": traceback.format_exc(),
        "timestamp": time.time()
    }))
    
    # Return standardized error response
    error_body = {
        "error": "InternalServerError",
        "message": "An unexpected error occurred. Please try again later.",
        "requestId": correlation_id,
        "timestamp": int(time.time())
    }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body
    )


# Import route handlers
from routes.chat import router as chat_router
from routes.eligibility import router as eligibility_router
from routes.schemes import router as schemes_router
from routes.session import router as session_router
from routes.voice import router as voice_router

# Register route handlers
app.include_router(chat_router, tags=["chat"])
app.include_router(eligibility_router, tags=["eligibility"])
app.include_router(schemes_router, tags=["schemes"])
app.include_router(session_router, tags=["session"])
app.include_router(voice_router, tags=["voice"])


# Health Check Endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint for load balancer and monitoring.
    
    Returns:
        dict: Status information including service name and health status
    """
    return {
        "status": "healthy",
        "service": "bharat-sahayak-api",
        "version": "1.0.0"
    }


# Application entry point for uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
