#!/bin/bash

# Bharat Sahayak FastAPI Application Deployment Script
# This script handles the complete setup and startup of the FastAPI application on EC2 instances

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
APP_DIR="/opt/bharat-sahayak"
BACKEND_DIR="${APP_DIR}/backend"
VENV_DIR="${APP_DIR}/venv"
ENV_FILE="${BACKEND_DIR}/.env"
REQUIREMENTS_FILE="${BACKEND_DIR}/requirements.txt"
SERVICE_NAME="bharat-sahayak"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    log_error "This script should not be run as root. Please run as the application user (e.g., ubuntu)."
    exit 1
fi

log_info "Starting Bharat Sahayak deployment..."

# Step 1: Check if application directory exists
if [ ! -d "$APP_DIR" ]; then
    log_error "Application directory $APP_DIR does not exist."
    log_info "Please ensure the application code is deployed to $APP_DIR"
    exit 1
fi

cd "$APP_DIR"

# Step 2: Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    log_info "Virtual environment already exists at $VENV_DIR"
fi

# Step 3: Activate virtual environment
log_info "Activating virtual environment..."
source "${VENV_DIR}/bin/activate"

# Step 4: Upgrade pip
log_info "Upgrading pip..."
pip install --upgrade pip

# Step 5: Install dependencies from requirements.txt
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    log_error "Requirements file not found at $REQUIREMENTS_FILE"
    exit 1
fi

log_info "Installing dependencies from requirements.txt..."
pip install -r "$REQUIREMENTS_FILE"

# Step 6: Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    log_warn ".env file not found at $ENV_FILE"
    
    # Check if .env.example exists
    if [ -f "${BACKEND_DIR}/.env.example" ]; then
        log_info "Copying .env.example to .env..."
        cp "${BACKEND_DIR}/.env.example" "$ENV_FILE"
        log_warn "Please edit $ENV_FILE with your actual configuration values"
    else
        log_error "Neither .env nor .env.example found. Cannot proceed."
        exit 1
    fi
fi

# Step 7: Load and validate environment variables
log_info "Loading environment variables from $ENV_FILE..."
set -a  # Automatically export all variables
source "$ENV_FILE"
set +a

# Validate required environment variables
REQUIRED_VARS=("DYNAMODB_TABLE" "S3_TEMP_BUCKET" "BEDROCK_MODEL_ID" "AWS_REGION")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    log_error "Missing required environment variables: ${MISSING_VARS[*]}"
    log_info "Please set these variables in $ENV_FILE"
    exit 1
fi

log_info "Environment variables validated successfully"
log_info "  DYNAMODB_TABLE: $DYNAMODB_TABLE"
log_info "  S3_TEMP_BUCKET: $S3_TEMP_BUCKET"
log_info "  BEDROCK_MODEL_ID: $BEDROCK_MODEL_ID"
log_info "  AWS_REGION: $AWS_REGION"
log_info "  LOG_LEVEL: ${LOG_LEVEL:-INFO}"

# Step 8: Check AWS credentials
log_info "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured or invalid"
    log_info "Please configure AWS credentials using one of:"
    log_info "  - IAM role attached to EC2 instance (recommended)"
    log_info "  - AWS CLI: aws configure"
    log_info "  - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    exit 1
fi

log_info "AWS credentials validated successfully"

# Step 9: Test DynamoDB table access
log_info "Testing DynamoDB table access..."
if ! aws dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$AWS_REGION" &> /dev/null; then
    log_error "Cannot access DynamoDB table: $DYNAMODB_TABLE"
    log_info "Please ensure:"
    log_info "  - The table exists in region $AWS_REGION"
    log_info "  - IAM permissions allow dynamodb:DescribeTable"
    exit 1
fi

log_info "DynamoDB table access verified"

# Step 10: Test S3 bucket access
log_info "Testing S3 bucket access..."
if ! aws s3 ls "s3://$S3_TEMP_BUCKET" --region "$AWS_REGION" &> /dev/null; then
    log_error "Cannot access S3 bucket: $S3_TEMP_BUCKET"
    log_info "Please ensure:"
    log_info "  - The bucket exists in region $AWS_REGION"
    log_info "  - IAM permissions allow s3:ListBucket"
    exit 1
fi

log_info "S3 bucket access verified"

# Step 11: Start the application with uvicorn
log_info "Starting Bharat Sahayak FastAPI application..."
log_info "Application will be available at http://0.0.0.0:8000"
log_info "Press Ctrl+C to stop the application"

cd "${BACKEND_DIR}/src"

# Start uvicorn with configuration from systemd service
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level "${LOG_LEVEL:-info}"
