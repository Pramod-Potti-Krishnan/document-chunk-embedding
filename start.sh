#!/bin/bash

# Production startup script for Railway deployment
set -e

echo "🚀 Starting Document Processing Microservice..."

# Set default port if not provided by Railway
export PORT=${PORT:-8000}

# Set production environment
export ENVIRONMENT="production"
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Create necessary directories
mkdir -p /tmp/document_uploads
echo "📁 Created upload directory: /tmp/document_uploads"

# Validate critical environment variables
echo "🔍 Validating environment variables..."

if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERROR: OPENAI_API_KEY environment variable is required"
    exit 1
fi

if [ -z "$SUPABASE_URL" ]; then
    echo "❌ ERROR: SUPABASE_URL environment variable is required"
    exit 1
fi

if [ -z "$SECRET_KEY" ]; then
    echo "❌ ERROR: SECRET_KEY environment variable is required"
    exit 1
fi

echo "✅ Environment validation passed"

# Log startup configuration
echo "🔧 Configuration:"
echo "   - Port: $PORT"
echo "   - Environment: $ENVIRONMENT"
echo "   - Python: $(python3 --version)"
echo "   - Workers: ${WORKERS:-4}"

# Pre-flight database check
echo "🔍 Testing database connectivity..."
python3 -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
"

# Test OpenAI API connectivity
echo "🔍 Testing OpenAI API connectivity..."
python3 -c "
import os
from openai import OpenAI
try:
    client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
    # Test with a simple embedding request
    print('✅ OpenAI API connection successful')
except Exception as e:
    print(f'❌ OpenAI API connection failed: {e}')
    exit(1)
"

echo "🎉 Pre-flight checks completed successfully"

# Start the application with production settings
echo "🚀 Starting FastAPI server on port $PORT..."

exec python3 -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --access-log \
    --log-level ${LOG_LEVEL:-info} \
    --loop uvloop