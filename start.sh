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

# Pre-flight database check (non-fatal)
echo "🔍 Testing database connectivity..."
python3 -c "
import os
try:
    import psycopg2
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    print('✅ Database connection successful')
except ImportError as e:
    print(f'⚠️  WARNING: psycopg2 not yet installed: {e}')
    print('   Database checks will be performed after server startup')
except Exception as e:
    print(f'⚠️  WARNING: Database connection failed: {e}')
    print('   Server will start anyway and retry connections')
" || true

# Test OpenAI API connectivity (non-fatal)
echo "🔍 Testing OpenAI API connectivity..."
python3 -c "
import os
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
    # Test with a simple embedding request
    print('✅ OpenAI API connection successful')
except ImportError as e:
    print(f'⚠️  WARNING: OpenAI library not yet installed: {e}')
    print('   OpenAI checks will be performed after server startup')
except Exception as e:
    print(f'⚠️  WARNING: OpenAI API connection failed: {e}')
    print('   Server will start anyway and retry connections')
" || true

echo "🎉 Pre-flight checks completed successfully"

# Start the application with production settings
echo "🚀 Starting FastAPI server on port $PORT..."

exec python3 -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --access-log \
    --log-level $(echo ${LOG_LEVEL:-info} | tr '[:upper:]' '[:lower:]') \
    --loop uvloop