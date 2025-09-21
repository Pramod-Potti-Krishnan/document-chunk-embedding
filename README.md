# 📄 Document Processing Microservice

A production-ready FastAPI microservice for document processing with vector embeddings, designed for Railway deployment.

## 🚀 Features

- **Document Processing Pipeline**: Upload → Text extraction → Chunking → Embedding generation → Vector storage
- **Supported Formats**: PDF, DOCX, TXT, MD
- **Vector Storage**: Supabase PostgreSQL with pgvector extension
- **Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
- **Authentication**: JWT-based with configurable expiration
- **Production Ready**: Health checks, structured logging, error handling, rate limiting

## 📋 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension
- OpenAI API key
- Supabase account (optional)

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/Pramod-Potti-Krishnan/document-chunk-embedding.git
cd document-chunk-embedding
```

2. **Set up virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.production.example .env
# Edit .env with your credentials
```

5. **Run the application**
```bash
python -m uvicorn src.main:app --reload --port 8000
```

6. **Access the API**
- API Documentation: http://localhost:8000/api/docs
- Health Check: http://localhost:8000/api/health
- Test Interface: http://localhost:8000/test (development only)

## 🚂 Railway Deployment

### Quick Deploy

1. **Fork this repository**

2. **Create Railway project**
   - Go to [Railway](https://railway.app)
   - Create new project from GitHub repo

3. **Set environment variables** (see `.env.production.example`)
   - DATABASE_URL
   - OPENAI_API_KEY
   - SECRET_KEY
   - SUPABASE_URL
   - SUPABASE_ANON_KEY

4. **Deploy**
   - Railway will auto-detect configuration
   - Deployment takes 2-3 minutes

See [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) for detailed instructions.

## 📚 API Endpoints

### Document Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/documents/upload` | POST | Upload and process document |
| `/api/documents/status/{id}` | GET | Get processing status |
| `/api/documents/list` | GET | List user documents |
| `/api/documents/{id}/metadata` | GET | Get document metadata |
| `/api/documents/{id}/chunks` | GET | Get document chunks |
| `/api/documents/{id}` | DELETE | Delete document |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check with service status |
| `/api/docs` | GET | API documentation (Swagger) |
| `/api/redoc` | GET | API documentation (ReDoc) |

## 🔧 Configuration

### Environment Variables

See `.env.production.example` for all configuration options.

Key settings:
- `ENVIRONMENT`: development/production
- `MAX_UPLOAD_SIZE_MB`: Maximum file size (default: 50)
- `CHUNK_SIZE_MAX`: Maximum chunk size (default: 1500)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 200)
- `RATE_LIMIT_REQUESTS_PER_HOUR`: API rate limit (default: 5000)

### Database Schema

The service uses three main tables:
- `documents`: Document metadata
- `document_chunks`: Text chunks with embeddings
- `processing_jobs`: Background job tracking

## 🧪 Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=src tests/

# Run specific test
pytest tests/integration/test_api_documents.py
```

## 📦 Project Structure

```
document-chunk-embedding/
├── src/
│   ├── main.py              # FastAPI application
│   ├── config/
│   │   └── settings.py       # Configuration management
│   ├── core/
│   │   ├── auth.py          # Authentication
│   │   └── database.py      # Database connection
│   ├── models/
│   │   ├── database.py      # SQLAlchemy models
│   │   └── schemas.py       # Pydantic schemas
│   └── services/
│       ├── async_processor.py    # Document processing
│       ├── document_processor.py # Text extraction
│       ├── text_chunker.py      # Text chunking
│       └── embeddings_service.py # Embedding generation
├── tests/                    # Test suite
├── railway.toml             # Railway configuration
├── Dockerfile               # Container definition
├── requirements.txt         # Python dependencies
└── start.sh                # Production startup script
```

## 🔍 Monitoring

### Health Check Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "services": {
    "database": true,
    "embeddings": true,
    "vector_database": true,
    "filesystem": true,
    "memory_available": true,
    "disk_available": true
  },
  "uptime_seconds": 3600
}
```

### Structured Logging

Production logs are in JSON format for easy parsing:

```json
{
  "timestamp": "2025-01-20T10:30:00Z",
  "level": "INFO",
  "message": "Request completed",
  "request_id": "abc123",
  "method": "POST",
  "url": "/api/documents/upload",
  "status_code": 200,
  "process_time": 1.234
}
```

## 🔒 Security

- JWT authentication with configurable expiration
- Rate limiting (5000 requests/hour default)
- Input validation and sanitization
- File type restrictions
- Non-root Docker user
- Environment-based CORS configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For issues and questions:
- Open an issue on [GitHub](https://github.com/Pramod-Potti-Krishnan/document-chunk-embedding/issues)
- Check [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) for deployment help
- Review [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) for troubleshooting

## 🚀 Quick Links

- [Railway Deployment Guide](RAILWAY_DEPLOYMENT.md)
- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md)
- [Environment Template](.env.production.example)
- [API Documentation](http://localhost:8000/api/docs)