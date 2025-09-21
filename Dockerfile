# Railway-optimized multi-stage build for Document Processing Microservice
FROM python:3.11-slim as builder

WORKDIR /app

# Set build environment variables
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Runtime stage - Railway optimized
FROM python:3.11-slim

WORKDIR /app

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH \
    ENVIRONMENT=production

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    poppler-utils \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /root/.local

# Create non-root user for security (Railway best practice)
RUN useradd --create-home --shell /bin/bash app

# Create necessary directories with proper permissions
RUN mkdir -p /tmp/document_uploads && \
    chown -R app:app /tmp/document_uploads && \
    chmod 755 /tmp/document_uploads

# Copy application code
COPY --chown=app:app . .

# Make start script executable
RUN chmod +x start.sh

# Switch to non-root user
USER app

# Expose port (Railway automatically sets $PORT)
EXPOSE 8000

# Health check optimized for Railway
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:${PORT:-8000}/api/health || exit 1

# Use Railway-optimized startup script
CMD ["bash", "start.sh"]