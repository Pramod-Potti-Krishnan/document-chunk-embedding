# 🚀 Railway Deployment Guide - Document Processing Microservice

## 🎯 Overview

This guide will help you deploy the Document Processing Microservice to Railway platform. The service provides a complete document processing pipeline from upload to vector storage in Supabase.

### ✨ **What You Get After Deployment:**
- **FastAPI application** running on Railway
- **Complete document processing pipeline**: Upload → Text extraction → Chunking → Embedding → Vector storage
- **Production-ready monitoring** with comprehensive health checks
- **Structured JSON logging** for production debugging
- **Auto-scaling** based on demand
- **Secure authentication** with JWT tokens
- **CORS configuration** for frontend integration

---

## 📋 Prerequisites

### **Required Services:**
1. **Railway Account** - [Sign up at railway.app](https://railway.app)
2. **Supabase Project** with pgvector enabled - [Your database is already configured]
3. **OpenAI API Key** - [Get from OpenAI platform](https://platform.openai.com)
4. **GitHub Repository** - Fork or use this repository

### **Current Database Status:**
✅ **Your Supabase Database is Ready:**
- **12 chunks** with **1536D embeddings** already stored
- **Connection verified**: Database with pgvector extension enabled
- **Vector search working** with similarity scores

---

## 🚀 Quick Deployment (5 Minutes)

### **Step 1: Create Railway Project**
1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose this repository: `deckster-backend/deckster-w-content-strategist/apps/document-processing-microservice/backend`

### **Step 2: Configure Environment Variables**
In Railway Dashboard → **Variables** tab, add these **REQUIRED** variables:

```bash
# 🔐 CRITICAL VARIABLES (Must be set)
DATABASE_URL=your-supabase-database-url-here
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
SECRET_KEY=your-secure-secret-key-here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key-here

# 🌐 PRODUCTION SETTINGS
ENVIRONMENT=production
LOG_LEVEL=INFO
LOG_FORMAT=json

# 🔒 CORS (Update with your frontend domain)
CORS_ORIGINS=["https://your-frontend-domain.com","https://your-app.railway.app"]
```

### **Step 3: Deploy**
1. Railway will automatically detect the configuration files
2. Click **"Deploy"**
3. Wait 2-3 minutes for build and deployment
4. Get your deployment URL: `https://your-app.railway.app`

### **Step 4: Test Deployment**
```bash
# Test health endpoint
curl https://your-app.railway.app/api/health

# Expected response:
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "services": {
    "database": true,
    "embeddings": true,
    "vector_database": true,
    "filesystem": true
  }
}
```

---

## 🔧 Configuration Details

### **Environment Variables Reference**

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DATABASE_URL` | ✅ | Supabase PostgreSQL connection | `postgresql://...` |
| `OPENAI_API_KEY` | ✅ | OpenAI API key for embeddings | `sk-proj-...` |
| `SECRET_KEY` | ✅ | JWT secret key | `your-secure-key` |
| `SUPABASE_URL` | ✅ | Supabase project URL | `https://xyz.supabase.co` |
| `SUPABASE_ANON_KEY` | ✅ | Supabase anonymous key | `eyJ...` |
| `ENVIRONMENT` | 📝 | Environment type | `production` |
| `CORS_ORIGINS` | 📝 | Allowed frontend domains | `["https://app.com"]` |
| `LOG_LEVEL` | 📝 | Logging level | `INFO` |
| `LOG_FORMAT` | 📝 | Log output format | `json` |

### **Railway Auto-Detected Files:**
- `railway.toml` - Railway deployment configuration
- `nixpacks.toml` - Build optimization
- `Dockerfile` - Container build instructions
- `start.sh` - Production startup script
- `requirements.txt` - Python dependencies

---

## 🔗 API Endpoints (Production Ready)

Once deployed, your service will provide these endpoints:

### **📊 Health & Monitoring**
```bash
GET /api/health              # Comprehensive health check
GET /api/docs                # API documentation
GET /api/redoc               # Alternative API docs
```

### **📄 Document Processing**
```bash
POST /api/documents/upload    # Upload and process document
GET /api/documents/status/{id} # Get processing status
GET /api/documents/list       # List user documents
GET /api/documents/{id}/chunks # Get document chunks
DELETE /api/documents/{id}    # Delete document
```

### **Example Upload Request:**
```bash
curl -X POST "https://your-app.railway.app/api/documents/upload" \
  -H "Authorization: Bearer your-jwt-token" \
  -F "file=@document.pdf" \
  -F "user_id=user123" \
  -F "session_id=session456" \
  -F "project_id=project789"
```

---

## 🔍 Monitoring & Troubleshooting

### **Health Check Details**
The `/api/health` endpoint monitors:
- ✅ **Database connectivity** (Supabase PostgreSQL)
- ✅ **Vector database** (pgvector functionality)
- ✅ **OpenAI API** (embedding service)
- ✅ **File system** (temp storage access)
- ✅ **Memory usage** (system resources)
- ✅ **Background processing** (FastAPI tasks)

### **Production Logging**
All logs are structured JSON for easy parsing:
```json
{
  "timestamp": "2025-01-20T10:30:00Z",
  "level": "INFO",
  "logger": "main",
  "message": "Request completed",
  "request_id": "abc123",
  "method": "POST",
  "url": "/api/documents/upload",
  "status_code": 200,
  "process_time": 1.234,
  "environment": "production",
  "platform": "railway"
}
```

### **Common Issues & Solutions**

#### **❌ Database Connection Failed**
```bash
# Check DATABASE_URL format
DATABASE_URL=postgresql://user:password@host:port/database

# Verify Supabase connection
curl -X GET "https://your-project.supabase.co/rest/v1/" \
  -H "apikey: your-anon-key"
```

#### **❌ OpenAI API Errors**
```bash
# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer your-openai-key"

# Check usage limits at platform.openai.com
```

#### **❌ File Upload Fails**
- Check `TEMP_UPLOAD_DIR` permissions
- Verify file size under `MAX_UPLOAD_SIZE_MB`
- Ensure supported file types: PDF, DOCX, TXT, MD

### **Railway-Specific Monitoring**
```bash
# View logs
railway logs

# Check deployment status
railway status

# Connect to deployed service
railway connect
```

---

## 🔒 Security Features

### **Production Security:**
- ✅ **Non-root user** in Docker container
- ✅ **JWT authentication** with configurable expiration
- ✅ **Rate limiting** (5000 requests/hour, 500 uploads/hour)
- ✅ **Input validation** and sanitization
- ✅ **CORS protection** with environment-specific origins
- ✅ **File type validation** (PDF, DOCX, TXT, MD only)
- ✅ **Request ID tracing** for debugging

### **Environment Separation:**
- **Development**: Permissive CORS, detailed error messages
- **Production**: Restricted CORS, sanitized errors, JSON logging

---

## 🎯 Integration Examples

### **Frontend Integration (React/Next.js)**
```typescript
// Upload document
const uploadDocument = async (file: File, userId: string) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('user_id', userId);
  formData.append('session_id', sessionId);

  const response = await fetch('https://your-app.railway.app/api/documents/upload', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`
    },
    body: formData
  });

  return response.json();
};

// Check processing status
const checkStatus = async (documentId: string) => {
  const response = await fetch(`https://your-app.railway.app/api/documents/status/${documentId}`, {
    headers: {
      'Authorization': `Bearer ${jwtToken}`
    }
  });

  return response.json();
};
```

### **Backend Integration (Python)**
```python
import requests

# Upload document
def upload_document(file_path: str, user_id: str, token: str):
    with open(file_path, 'rb') as f:
        response = requests.post(
            'https://your-app.railway.app/api/documents/upload',
            headers={'Authorization': f'Bearer {token}'},
            files={'file': f},
            data={
                'user_id': user_id,
                'session_id': 'your-session-id',
                'project_id': 'your-project-id'
            }
        )
    return response.json()
```

---

## 📈 Performance & Scaling

### **Railway Auto-Scaling:**
- **CPU-based scaling** from 1-10 instances
- **Memory optimization** with 512MB-2GB per instance
- **Connection pooling** optimized for Railway
- **Background task processing** with FastAPI

### **Database Performance:**
- **Connection pool size**: 10-20 connections (production)
- **Vector similarity search** with pgvector optimization
- **Batch embedding generation** (100 chunks at a time)
- **Chunking optimization** (1000-1500 chars with 200 overlap)

### **Expected Performance:**
- **Document upload**: < 2 seconds
- **Text extraction**: 1-5 seconds (depending on size)
- **Embedding generation**: 2-10 seconds (100 chunks/batch)
- **Vector storage**: < 1 second
- **Total processing time**: 5-30 seconds (typical document)

---

## 🛠️ Maintenance & Updates

### **Monitoring Dashboard**
Check these URLs regularly:
- `https://your-app.railway.app/api/health` - Service health
- `https://your-app.railway.app/api/docs` - API documentation
- Railway Dashboard - Logs and metrics

### **Database Monitoring**
```sql
-- Check vector storage status
SELECT COUNT(*) as total_chunks,
       COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embeddings
FROM document_chunks;

-- Check recent processing
SELECT filename, status, created_at
FROM documents
ORDER BY created_at DESC
LIMIT 10;
```

### **Updating the Service**
1. Push changes to your GitHub repository
2. Railway will automatically redeploy
3. Monitor deployment logs in Railway dashboard
4. Verify health check after deployment

---

## 🎉 Success Checklist

After deployment, verify these are working:

- [ ] ✅ **Health check returns "healthy"**
- [ ] ✅ **Document upload endpoint accepts files**
- [ ] ✅ **Processing status updates in real-time**
- [ ] ✅ **Chunks are stored in Supabase**
- [ ] ✅ **Embeddings are generated and searchable**
- [ ] ✅ **Logs are structured JSON**
- [ ] ✅ **API documentation is accessible**
- [ ] ✅ **CORS allows your frontend domain**
- [ ] ✅ **Rate limiting is active**
- [ ] ✅ **Error handling returns proper status codes**

---

## 🆘 Support & Resources

### **Documentation:**
- [Railway Documentation](https://docs.railway.app)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Supabase pgvector Guide](https://supabase.com/docs/guides/database/extensions/pgvector)

### **Your Configured Resources:**
- **Database**: Supabase with 12 chunks ready for search
- **Embeddings**: OpenAI text-embedding-3-small (1536D)
- **Processing Pipeline**: Tested and working locally
- **API**: Full CRUD operations for documents and chunks

### **Quick Test After Deployment:**
```bash
# Test the full pipeline
curl -X POST "https://your-app.railway.app/api/documents/upload" \
  -H "Authorization: Bearer test-token" \
  -F "file=@test_document.pdf" \
  -F "user_id=test-user" \
  -F "session_id=test-session"
```

**🎯 Your document processing microservice is now production-ready on Railway!**