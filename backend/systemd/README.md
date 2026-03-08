# Systemd Service Configuration

This directory contains the systemd service file for running the Bharat Sahayak FastAPI application as a system service on EC2 instances.

## Service File: bharat-sahayak.service

The service file configures the FastAPI application to:
- Run automatically on system boot
- Restart automatically on failure
- Run with 4 Uvicorn workers for production workload
- Log to systemd journal for centralized logging
- Use proper working directory and environment variables

## Installation

### 1. Prerequisites

Ensure the application is installed in `/opt/bharat-sahayak/`:

```bash
sudo mkdir -p /opt/bharat-sahayak
sudo chown ubuntu:ubuntu /opt/bharat-sahayak
cd /opt/bharat-sahayak
git clone <repository-url> .
```

### 2. Create Python Virtual Environment

```bash
cd /opt/bharat-sahayak/backend
python3 -m venv /opt/bharat-sahayak/venv
source /opt/bharat-sahayak/venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp /opt/bharat-sahayak/backend/.env.example /opt/bharat-sahayak/backend/.env
nano /opt/bharat-sahayak/backend/.env
```

Set the following variables:
- `DYNAMODB_TABLE`: Your DynamoDB table name
- `S3_TEMP_BUCKET`: Your S3 bucket for temporary audio files
- `BEDROCK_MODEL_ID`: Amazon Bedrock model ID
- `AWS_REGION`: AWS region (e.g., ap-south-1)
- `LOG_LEVEL`: Logging level (INFO recommended for production)

### 4. Install Systemd Service

Copy the service file to systemd directory:

```bash
sudo cp /opt/bharat-sahayak/backend/systemd/bharat-sahayak.service /etc/systemd/system/
```

Reload systemd to recognize the new service:

```bash
sudo systemctl daemon-reload
```

### 5. Enable and Start Service

Enable the service to start on boot:

```bash
sudo systemctl enable bharat-sahayak
```

Start the service:

```bash
sudo systemctl start bharat-sahayak
```

## Service Management

### Check Service Status

```bash
sudo systemctl status bharat-sahayak
```

### View Logs

View real-time logs:

```bash
sudo journalctl -u bharat-sahayak -f
```

View recent logs:

```bash
sudo journalctl -u bharat-sahayak -n 100
```

View logs since a specific time:

```bash
sudo journalctl -u bharat-sahayak --since "1 hour ago"
```

### Restart Service

```bash
sudo systemctl restart bharat-sahayak
```

### Stop Service

```bash
sudo systemctl stop bharat-sahayak
```

### Reload Configuration

After modifying the service file:

```bash
sudo systemctl daemon-reload
sudo systemctl restart bharat-sahayak
```

## Service Configuration Details

### User and Group

The service runs as the `ubuntu` user and group. If using a different user:

1. Edit the service file:
   ```bash
   sudo nano /etc/systemd/system/bharat-sahayak.service
   ```

2. Change the `User` and `Group` directives

3. Reload and restart:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart bharat-sahayak
   ```

### Working Directory

The service runs from `/opt/bharat-sahayak/backend/src`. If your installation path is different, update the `WorkingDirectory` directive in the service file.

### Environment Variables

Environment variables are loaded from `/opt/bharat-sahayak/backend/.env`. Ensure this file exists and contains all required variables.

### Uvicorn Workers

The service is configured to run with 4 workers (`--workers 4`). Adjust this based on your EC2 instance size:

- **t3.medium (2 vCPUs)**: 2-4 workers
- **t3.large (2 vCPUs)**: 2-4 workers
- **t3.xlarge (4 vCPUs)**: 4-8 workers
- **t3.2xlarge (8 vCPUs)**: 8-16 workers

General rule: 2-4 workers per CPU core.

To change the number of workers, edit the `ExecStart` line in the service file.

### Restart Policy

The service is configured with:
- `Restart=always`: Automatically restart on any failure
- `RestartSec=5`: Wait 5 seconds before restarting
- `TimeoutStopSec=30`: Allow 30 seconds for graceful shutdown

### Logging

Logs are sent to systemd journal with identifier `bharat-sahayak`. This allows:
- Centralized log management
- Integration with CloudWatch Logs Agent
- Log rotation handled by systemd

## Health Checks

The application exposes a health check endpoint at `http://localhost:8000/health`.

Test the health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "service": "bharat-sahayak-api",
  "version": "1.0.0"
}
```

## Troubleshooting

### Service Fails to Start

1. Check service status:
   ```bash
   sudo systemctl status bharat-sahayak
   ```

2. View detailed logs:
   ```bash
   sudo journalctl -u bharat-sahayak -n 50
   ```

3. Common issues:
   - **Missing .env file**: Ensure `/opt/bharat-sahayak/backend/.env` exists
   - **Wrong permissions**: Ensure ubuntu user can read all files
   - **Missing dependencies**: Reinstall requirements.txt
   - **Port already in use**: Check if another service is using port 8000

### Permission Errors

Ensure the ubuntu user owns the application directory:

```bash
sudo chown -R ubuntu:ubuntu /opt/bharat-sahayak
```

### AWS Credentials

The service uses the EC2 instance IAM role for AWS credentials. Ensure the instance has:
- DynamoDB read/write permissions
- S3 read/write permissions for the temp bucket
- Bedrock invoke permissions
- Translate, Polly, and Transcribe permissions

### Port 8000 Already in Use

Find the process using port 8000:

```bash
sudo lsof -i :8000
```

Kill the process or change the port in the service file.

## Integration with Load Balancer

The service listens on `0.0.0.0:8000`, making it accessible from the load balancer.

Configure your Application Load Balancer:
- **Target Group**: EC2 instances on port 8000
- **Health Check Path**: `/health`
- **Health Check Interval**: 30 seconds
- **Healthy Threshold**: 2
- **Unhealthy Threshold**: 3
- **Timeout**: 5 seconds

## Monitoring

### CloudWatch Logs

To send logs to CloudWatch, install and configure the CloudWatch Logs Agent:

```bash
sudo yum install amazon-cloudwatch-agent
```

Configure the agent to collect systemd journal logs for `bharat-sahayak`.

### CloudWatch Metrics

The application logs structured JSON that can be parsed for metrics:
- Request count
- Response time (duration_ms)
- Error rate
- Status code distribution

Use CloudWatch Logs Insights to query and create metrics from these logs.

## Security Considerations

1. **Run as non-root user**: The service runs as `ubuntu`, not root
2. **Environment file permissions**: Ensure `.env` is not world-readable:
   ```bash
   chmod 600 /opt/bharat-sahayak/backend/.env
   ```
3. **IAM role**: Use EC2 instance IAM role instead of hardcoded credentials
4. **Security groups**: Restrict port 8000 to load balancer security group only
5. **CORS configuration**: Update `allow_origins` in production to specific domains

## Updating the Application

To deploy a new version:

1. Pull the latest code:
   ```bash
   cd /opt/bharat-sahayak
   git pull
   ```

2. Update dependencies if needed:
   ```bash
   source /opt/bharat-sahayak/venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. Restart the service:
   ```bash
   sudo systemctl restart bharat-sahayak
   ```

4. Verify the service is running:
   ```bash
   sudo systemctl status bharat-sahayak
   curl http://localhost:8000/health
   ```

## Zero-Downtime Deployment

For zero-downtime deployments with multiple instances:

1. Remove one instance from the load balancer target group
2. Update and restart the service on that instance
3. Verify health checks pass
4. Add the instance back to the target group
5. Repeat for remaining instances

Alternatively, use a blue-green deployment strategy with separate target groups.
