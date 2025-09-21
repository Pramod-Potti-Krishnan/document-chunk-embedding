# Document Processing Microservice - API Integration Guide

## 🚀 Production API
**Base URL:** `https://document-chunk-embedding-production.up.railway.app:8080`
**Environment:** Production
**API Version:** v1

## 📋 Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
- [Frontend Integration Examples](#frontend-integration-examples)
- [Error Handling](#error-handling)
- [Workflows & Use Cases](#workflows--use-cases)
- [Response Schemas](#response-schemas)
- [Performance & Security](#performance--security)
- [Quick Start Guide](#quick-start-guide)

## Overview

This Document Processing Microservice provides a complete pipeline for processing documents into searchable vector embeddings. Perfect for building AI-powered document search, Q&A systems, and content analysis applications.

### 🎯 Key Features
- **Document Upload & Processing**: PDF, DOCX, TXT, MD support
- **Intelligent Text Chunking**: 512-token chunks with overlap
- **Vector Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
- **Vector Storage**: Supabase PostgreSQL with pgvector
- **Real-time Processing**: Background jobs with status tracking
- **Production Ready**: JWT auth, rate limiting, comprehensive error handling

### 🔄 Processing Pipeline
```
Upload Document → Text Extraction → Smart Chunking → Generate Embeddings → Store in Vector DB
```

### 📊 Supported Document Types
| Format | Extension | Max Size |
|--------|-----------|----------|
| PDF | `.pdf` | 10MB |
| Word Document | `.docx` | 10MB |
| Text File | `.txt` | 10MB |
| Markdown | `.md` | 10MB |

## Authentication

All API endpoints (except `/api/health`) require JWT authentication.

### 🔑 JWT Token Format
```javascript
// Request Header
{
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}

// Token Payload
{
  "sub": "user_123",           // User ID
  "username": "john.doe",      // Username
  "exp": 1735689600,          // Expiration timestamp
  "iat": 1735603200           // Issued at timestamp
}
```

### 🔧 Frontend Auth Setup
```typescript
// API client configuration
const API_BASE = 'https://document-chunk-embedding-production.up.railway.app:8080';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
    'Content-Type': 'application/json'
  }
});
```

## API Endpoints

### 1. Health Check
**`GET /api/health`** - *No authentication required*

Monitor service status and dependencies.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "services": {
    "database": true,
    "openai": true,
    "supabase": true,
    "storage": true
  },
  "metrics": {
    "database_time": "2024-01-10T12:00:00Z",
    "memory_usage_percent": 45.2,
    "disk_usage_percent": 62.8
  },
  "uptime_seconds": 3600.5,
  "timestamp": "2024-01-10T13:00:00Z"
}
```

### 2. Upload Document
**`POST /api/documents/upload`** - *Requires authentication*

Upload and process a document.

**Request (FormData):**
```javascript
const formData = new FormData();
formData.append('file', fileObject);        // Required: File input
formData.append('user_id', 'user_123');     // Required: User identifier
formData.append('session_id', 'session_456'); // Required: Session ID
formData.append('project_id', 'project_789'); // Optional: Project grouping
formData.append('metadata', JSON.stringify({ // Optional: Custom metadata
  category: 'research',
  tags: ['AI', 'ML'],
  source: 'upload'
}));
formData.append('tags', JSON.stringify(['important', 'review'])); // Optional: Tags array
```

**cURL Example:**
```bash
curl -X POST "https://document-chunk-embedding-production.up.railway.app:8080/api/documents/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf" \
  -F "user_id=user_123" \
  -F "session_id=session_456"
```

**Response:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Document uploaded successfully and processing started",
  "processing_job_id": "660e8400-e29b-41d4-a716-446655440001",
  "estimated_processing_time": 45
}
```

### 3. Get Document Status
**`GET /api/documents/status/{document_id}`** - *Requires authentication*

Check document processing status.

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "session_id": "session_456",
  "project_id": "project_789",
  "filename": "research_paper.pdf",
  "file_type": "pdf",
  "status": "processing",           // pending | processing | completed | failed
  "progress_percentage": 75,
  "processing_started_at": "2024-01-10T10:30:05Z",
  "processing_completed_at": null,
  "processing_error": null,
  "created_at": "2024-01-10T10:30:00Z",
  "updated_at": "2024-01-10T10:31:15Z"
}
```

### 4. List Documents
**`GET /api/documents/list`** - *Requires authentication*

Retrieve user's documents with filtering and pagination.

**Query Parameters:**
- `user_id` (required): User identifier
- `session_id` (optional): Filter by session
- `project_id` (optional): Filter by project
- `status` (optional): `pending | processing | completed | failed`
- `limit` (optional): 1-100, default 50
- `offset` (optional): Pagination offset, default 0
- `order_by` (optional): `created_at | updated_at | filename`, default `created_at`
- `order_desc` (optional): `true | false`, default `true`

**Example Request:**
```javascript
const response = await fetch(
  `${API_BASE}/api/documents/list?user_id=user_123&status=completed&limit=20`,
  {
    headers: { 'Authorization': `Bearer ${token}` }
  }
);
```

**Response:**
```json
{
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "user_123",
      "session_id": "session_456",
      "project_id": "project_789",
      "filename": "research_paper.pdf",
      "file_type": "pdf",
      "file_size_bytes": 2048576,
      "status": "completed",
      "total_pages": 15,
      "total_chunks": 28,
      "total_tokens": 14336,
      "metadata": {
        "category": "research",
        "extraction_method": "pdfplumber",
        "language": "en"
      },
      "tags": ["important", "review"],
      "created_at": "2024-01-10T10:30:00Z",
      "processing_completed_at": "2024-01-10T10:31:30Z"
    }
  ],
  "total": 45,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

### 5. Get Document Metadata
**`GET /api/documents/{document_id}/metadata`** - *Requires authentication*

Get detailed document information.

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "session_id": "session_456",
  "project_id": "project_789",
  "filename": "research_paper.pdf",
  "file_type": "pdf",
  "file_size_bytes": 2048576,
  "status": "completed",
  "total_pages": 15,
  "total_chunks": 28,
  "total_tokens": 14336,
  "storage_url": "https://storage.supabase.com/...",
  "metadata": {
    "category": "research",
    "extraction_method": "pdfplumber",
    "language": "en",
    "processing_duration": 85.2
  },
  "tags": ["important", "review"],
  "created_at": "2024-01-10T10:30:00Z",
  "processing_started_at": "2024-01-10T10:30:05Z",
  "processing_completed_at": "2024-01-10T10:31:30Z"
}
```

### 6. Get Document Chunks
**`GET /api/documents/{document_id}/chunks`** - *Requires authentication*

Retrieve text chunks and embeddings for semantic search.

**Query Parameters:**
- `limit` (optional): 1-100, default 50
- `offset` (optional): Pagination offset, default 0
- `include_embeddings` (optional): `true | false`, default `false`

**Response:**
```json
{
  "chunks": [
    {
      "id": "chunk_001",
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "chunk_index": 0,
      "text_content": "This research explores the applications of artificial intelligence in modern healthcare systems...",
      "chunk_size": 512,
      "token_count": 125,
      "page_number": 1,
      "start_char": 0,
      "end_char": 512,
      "embedding": [0.1234, -0.5678, 0.9012, ...], // 1536 dimensions when requested
      "metadata": {
        "section": "introduction",
        "has_table": false,
        "confidence": 0.95
      },
      "created_at": "2024-01-10T10:31:00Z"
    }
  ],
  "total": 28,
  "limit": 50,
  "offset": 0,
  "has_more": false
}
```

### 7. Delete Document
**`DELETE /api/documents/{document_id}`** - *Requires authentication*

Delete document and all associated chunks and embeddings.

**Response:**
```json
{
  "success": true,
  "message": "Document deleted successfully",
  "deleted_chunks": 28
}
```

## Frontend Integration Examples

### React/TypeScript Complete Implementation

#### 1. API Client Class
```typescript
// utils/DocumentAPIClient.ts
import axios, { AxiosInstance, AxiosError } from 'axios';

interface UploadResponse {
  document_id: string;
  status: string;
  message: string;
  processing_job_id?: string;
  estimated_processing_time?: number;
}

interface DocumentResponse {
  id: string;
  user_id: string;
  filename: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress_percentage: number;
  total_chunks: number;
  processing_error?: string;
  created_at: string;
  processing_completed_at?: string;
}

interface ChunkResponse {
  id: string;
  document_id: string;
  chunk_index: number;
  text_content: string;
  token_count: number;
  embedding?: number[];
  metadata: Record<string, any>;
}

class DocumentAPIClient {
  private client: AxiosInstance;
  private retryAttempts = 3;

  constructor(token: string) {
    this.client = axios.create({
      baseURL: 'https://document-chunk-embedding-production.up.railway.app:8080',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      timeout: 30000
    });

    // Request interceptor for logging
    this.client.interceptors.request.use((config) => {
      config.headers['X-Request-ID'] = this.generateRequestId();
      console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
      return config;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => this.handleError(error)
    );
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private async handleError(error: AxiosError): Promise<never> {
    if (error.response?.status === 429) {
      const retryAfter = parseInt(error.response.headers['retry-after'] || '60');
      console.warn(`Rate limited. Retrying after ${retryAfter} seconds...`);
      await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
      // Retry the original request
      return this.client.request(error.config!);
    }

    if (error.response?.status === 401) {
      // Handle token expiration
      console.error('Authentication failed. Token may be expired.');
      // Trigger token refresh in your app
    }

    return Promise.reject(error);
  }

  // Upload document with progress tracking
  async uploadDocument(
    file: File,
    userId: string,
    sessionId: string,
    projectId?: string,
    metadata?: Record<string, any>
  ): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);
    formData.append('session_id', sessionId);

    if (projectId) {
      formData.append('project_id', projectId);
    }

    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    const response = await this.client.post('/api/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });

    return response.data;
  }

  // Get document status
  async getDocumentStatus(documentId: string): Promise<DocumentResponse> {
    const response = await this.client.get(`/api/documents/status/${documentId}`);
    return response.data;
  }

  // Poll for processing completion
  async waitForProcessing(
    documentId: string,
    onProgress?: (progress: number, status: string) => void,
    pollInterval: number = 2000,
    maxAttempts: number = 150 // 5 minutes max
  ): Promise<DocumentResponse> {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const doc = await this.getDocumentStatus(documentId);

      // Call progress callback
      if (onProgress) {
        onProgress(doc.progress_percentage, doc.status);
      }

      if (doc.status === 'completed') {
        return doc;
      }

      if (doc.status === 'failed') {
        throw new Error(`Processing failed: ${doc.processing_error || 'Unknown error'}`);
      }

      // Wait before next poll
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }

    throw new Error('Processing timeout - document may still be processing');
  }

  // Get document chunks for search
  async getDocumentChunks(
    documentId: string,
    includeEmbeddings: boolean = false,
    limit: number = 50,
    offset: number = 0
  ): Promise<{ chunks: ChunkResponse[]; total: number; has_more: boolean }> {
    const response = await this.client.get(
      `/api/documents/${documentId}/chunks`,
      {
        params: {
          include_embeddings: includeEmbeddings,
          limit,
          offset
        }
      }
    );
    return response.data;
  }

  // List user documents
  async listDocuments(
    userId: string,
    filters?: {
      sessionId?: string;
      projectId?: string;
      status?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<{ documents: DocumentResponse[]; total: number; has_more: boolean }> {
    const params = {
      user_id: userId,
      ...filters
    };

    const response = await this.client.get('/api/documents/list', { params });
    return response.data;
  }

  // Delete document
  async deleteDocument(documentId: string): Promise<{ success: boolean; message: string }> {
    const response = await this.client.delete(`/api/documents/${documentId}`);
    return response.data;
  }

  // Health check
  async healthCheck() {
    const response = await this.client.get('/api/health');
    return response.data;
  }
}

export default DocumentAPIClient;
```

#### 2. React Hook for Document Upload
```typescript
// hooks/useDocumentUpload.ts
import { useState, useCallback } from 'react';
import DocumentAPIClient from '../utils/DocumentAPIClient';

interface UploadState {
  isUploading: boolean;
  progress: number;
  status: string;
  documentId?: string;
  error?: string;
}

export const useDocumentUpload = (apiClient: DocumentAPIClient) => {
  const [uploadState, setUploadState] = useState<UploadState>({
    isUploading: false,
    progress: 0,
    status: 'idle'
  });

  const uploadDocument = useCallback(async (
    file: File,
    userId: string,
    sessionId: string,
    options?: {
      projectId?: string;
      metadata?: Record<string, any>;
    }
  ) => {
    try {
      setUploadState({
        isUploading: true,
        progress: 0,
        status: 'uploading'
      });

      // Upload document
      const uploadResponse = await apiClient.uploadDocument(
        file,
        userId,
        sessionId,
        options?.projectId,
        options?.metadata
      );

      setUploadState(prev => ({
        ...prev,
        documentId: uploadResponse.document_id,
        status: 'processing'
      }));

      // Wait for processing with progress updates
      const finalDoc = await apiClient.waitForProcessing(
        uploadResponse.document_id,
        (progress, status) => {
          setUploadState(prev => ({
            ...prev,
            progress,
            status
          }));
        }
      );

      setUploadState(prev => ({
        ...prev,
        isUploading: false,
        progress: 100,
        status: 'completed'
      }));

      return finalDoc;

    } catch (error) {
      setUploadState(prev => ({
        ...prev,
        isUploading: false,
        error: error instanceof Error ? error.message : 'Upload failed'
      }));
      throw error;
    }
  }, [apiClient]);

  const resetUpload = useCallback(() => {
    setUploadState({
      isUploading: false,
      progress: 0,
      status: 'idle'
    });
  }, []);

  return {
    uploadState,
    uploadDocument,
    resetUpload
  };
};
```

#### 3. Document Upload Component
```tsx
// components/DocumentUploader.tsx
import React, { useState } from 'react';
import { useDocumentUpload } from '../hooks/useDocumentUpload';
import DocumentAPIClient from '../utils/DocumentAPIClient';

interface DocumentUploaderProps {
  userId: string;
  sessionId: string;
  projectId?: string;
  onUploadComplete?: (documentId: string) => void;
}

const DocumentUploader: React.FC<DocumentUploaderProps> = ({
  userId,
  sessionId,
  projectId,
  onUploadComplete
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // Get JWT token from your auth system
  const token = localStorage.getItem('jwt_token') || '';
  const apiClient = new DocumentAPIClient(token);

  const { uploadState, uploadDocument, resetUpload } = useDocumentUpload(apiClient);

  const handleFileSelect = (selectedFile: File) => {
    // Validate file
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'text/markdown'];

    if (selectedFile.size > maxSize) {
      alert('File size must be less than 10MB');
      return;
    }

    if (!allowedTypes.includes(selectedFile.type)) {
      alert('Supported formats: PDF, DOCX, TXT, MD');
      return;
    }

    setFile(selectedFile);
    resetUpload();
  };

  const handleUpload = async () => {
    if (!file) return;

    try {
      const result = await uploadDocument(
        file,
        userId,
        sessionId,
        {
          projectId,
          metadata: {
            uploadedAt: new Date().toISOString(),
            originalName: file.name,
            fileSize: file.size
          }
        }
      );

      console.log('Upload completed:', result);
      onUploadComplete?.(result.id);

    } catch (error) {
      console.error('Upload failed:', error);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="document-uploader">
      {/* File Drop Zone */}
      <div
        className={`drop-zone ${dragActive ? 'active' : ''} ${uploadState.isUploading ? 'disabled' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".pdf,.docx,.txt,.md"
          onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
          disabled={uploadState.isUploading}
          style={{ display: 'none' }}
          id="file-input"
        />

        <label htmlFor="file-input" className="file-input-label">
          {file ? (
            <div>
              <p><strong>Selected:</strong> {file.name}</p>
              <p><strong>Size:</strong> {(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          ) : (
            <div>
              <p>📄 Drop a document here or click to select</p>
              <p><small>Supports: PDF, DOCX, TXT, MD (max 10MB)</small></p>
            </div>
          )}
        </label>
      </div>

      {/* Upload Button */}
      {file && !uploadState.isUploading && uploadState.status !== 'completed' && (
        <button
          onClick={handleUpload}
          className="upload-button"
        >
          Upload & Process Document
        </button>
      )}

      {/* Progress Display */}
      {uploadState.isUploading && (
        <div className="upload-progress">
          <div className="progress-info">
            <span>Status: {uploadState.status}</span>
            <span>{uploadState.progress}%</span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${uploadState.progress}%` }}
            />
          </div>
          {uploadState.status === 'processing' && (
            <p><small>⚡ Extracting text, chunking, and generating embeddings...</small></p>
          )}
        </div>
      )}

      {/* Success State */}
      {uploadState.status === 'completed' && (
        <div className="upload-success">
          <p>✅ Document processed successfully!</p>
          <p><small>Document ID: {uploadState.documentId}</small></p>
          <button onClick={() => { setFile(null); resetUpload(); }}>
            Upload Another Document
          </button>
        </div>
      )}

      {/* Error State */}
      {uploadState.error && (
        <div className="upload-error">
          <p>❌ Upload failed: {uploadState.error}</p>
          <button onClick={() => { resetUpload(); }}>
            Try Again
          </button>
        </div>
      )}
    </div>
  );
};

export default DocumentUploader;
```

### Vue.js Integration Example

```vue
<!-- components/DocumentUploader.vue -->
<template>
  <div class="document-uploader">
    <div
      class="drop-zone"
      :class="{ active: dragActive, disabled: loading }"
      @dragenter.prevent="dragActive = true"
      @dragover.prevent
      @dragleave.prevent="dragActive = false"
      @drop.prevent="handleDrop"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".pdf,.docx,.txt,.md"
        @change="handleFileSelect"
        style="display: none"
      />

      <div @click="$refs.fileInput.click()">
        <p v-if="!selectedFile">📄 Drop document or click to select</p>
        <p v-else><strong>{{ selectedFile.name }}</strong></p>
      </div>
    </div>

    <button
      v-if="selectedFile && !loading"
      @click="uploadDocument"
      class="upload-btn"
    >
      Upload & Process
    </button>

    <div v-if="loading" class="progress">
      <p>{{ status }} - {{ progress }}%</p>
      <div class="progress-bar">
        <div :style="{ width: progress + '%' }" class="progress-fill"></div>
      </div>
    </div>

    <div v-if="error" class="error">
      <p>Error: {{ error }}</p>
      <button @click="resetUpload">Try Again</button>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue';

export default {
  name: 'DocumentUploader',
  props: {
    userId: { type: String, required: true },
    sessionId: { type: String, required: true },
    projectId: { type: String, default: null }
  },
  emits: ['upload-complete'],
  setup(props, { emit }) {
    const selectedFile = ref(null);
    const dragActive = ref(false);
    const loading = ref(false);
    const progress = ref(0);
    const status = ref('');
    const error = ref('');

    const API_BASE = 'https://document-chunk-embedding-production.up.railway.app:8080';
    const token = localStorage.getItem('jwt_token');

    const handleFileSelect = (event) => {
      const file = event.target.files[0];
      if (file) {
        selectedFile.value = file;
        error.value = '';
      }
    };

    const handleDrop = (event) => {
      dragActive.value = false;
      const file = event.dataTransfer.files[0];
      if (file) {
        selectedFile.value = file;
        error.value = '';
      }
    };

    const uploadDocument = async () => {
      if (!selectedFile.value) return;

      loading.value = true;
      progress.value = 0;
      status.value = 'Uploading...';
      error.value = '';

      try {
        // Upload document
        const formData = new FormData();
        formData.append('file', selectedFile.value);
        formData.append('user_id', props.userId);
        formData.append('session_id', props.sessionId);
        if (props.projectId) {
          formData.append('project_id', props.projectId);
        }

        const uploadResponse = await fetch(`${API_BASE}/api/documents/upload`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData
        });

        if (!uploadResponse.ok) {
          throw new Error(`Upload failed: ${uploadResponse.statusText}`);
        }

        const uploadData = await uploadResponse.json();
        const documentId = uploadData.document_id;

        // Poll for completion
        status.value = 'Processing...';
        await pollForCompletion(documentId);

        emit('upload-complete', documentId);

      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const pollForCompletion = async (documentId) => {
      const maxAttempts = 150; // 5 minutes

      for (let i = 0; i < maxAttempts; i++) {
        try {
          const response = await fetch(`${API_BASE}/api/documents/status/${documentId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });

          const doc = await response.json();
          progress.value = doc.progress_percentage || 0;

          if (doc.status === 'completed') {
            progress.value = 100;
            status.value = 'Completed!';
            return;
          } else if (doc.status === 'failed') {
            throw new Error(doc.processing_error || 'Processing failed');
          }

          await new Promise(resolve => setTimeout(resolve, 2000));
        } catch (err) {
          throw new Error(`Status check failed: ${err.message}`);
        }
      }

      throw new Error('Processing timeout');
    };

    const resetUpload = () => {
      selectedFile.value = null;
      loading.value = false;
      progress.value = 0;
      status.value = '';
      error.value = '';
    };

    return {
      selectedFile,
      dragActive,
      loading,
      progress,
      status,
      error,
      handleFileSelect,
      handleDrop,
      uploadDocument,
      resetUpload
    };
  }
};
</script>
```

## Error Handling

### 🚨 Error Response Format
All API errors follow this consistent structure:

```json
{
  "error": "validation_error",
  "error_code": "DOC_001",
  "message": "File size exceeds maximum limit of 10MB",
  "details": {
    "max_size_mb": 10,
    "file_size_mb": 15.2,
    "field": "file"
  },
  "correlation_id": "req_1704888000_abc123xyz"
}
```

### 📋 Error Codes Reference

| Code | Description | Resolution |
|------|-------------|------------|
| `AUTH_001` | Invalid or expired JWT token | Refresh authentication token |
| `AUTH_002` | Missing authorization header | Include `Authorization: Bearer <token>` |
| `DOC_001` | File size exceeds 10MB limit | Reduce file size or split document |
| `DOC_002` | Unsupported file type | Use PDF, DOCX, TXT, or MD files |
| `DOC_003` | Document not found | Verify document ID exists and user has access |
| `DOC_004` | Document processing failed | Check file format, retry with different file |
| `PROC_001` | Processing job failed | Retry upload or contact support |
| `RATE_001` | Rate limit exceeded (100 req/min) | Wait for `retry-after` period |
| `VAL_001` | Request validation failed | Check required fields and formats |
| `DB_001` | Database connection error | Retry after brief delay |
| `SYS_001` | Internal server error | Retry or contact support |

### 🔧 Error Handling Implementation

```typescript
// Error handling utility
class APIError extends Error {
  constructor(
    public errorCode: string,
    public details: any,
    public correlationId?: string
  ) {
    super();
  }
}

// Enhanced error handler
const handleAPIError = (error: AxiosError) => {
  if (error.response?.data) {
    const errorData = error.response.data;

    switch (errorData.error_code) {
      case 'AUTH_001':
        // Handle token expiration
        localStorage.removeItem('jwt_token');
        window.location.href = '/login';
        break;

      case 'DOC_001':
        alert(`File too large: ${errorData.details?.file_size_mb}MB. Maximum: ${errorData.details?.max_size_mb}MB`);
        break;

      case 'DOC_002':
        alert('Unsupported file type. Please use PDF, DOCX, TXT, or MD files.');
        break;

      case 'RATE_001':
        const retryAfter = error.response.headers['retry-after'] || 60;
        console.log(`Rate limited. Retry after ${retryAfter} seconds`);
        // Implement exponential backoff
        break;

      default:
        console.error(`API Error ${errorData.error_code}: ${errorData.message}`);
        if (errorData.correlation_id) {
          console.error(`Correlation ID: ${errorData.correlation_id}`);
        }
    }

    throw new APIError(errorData.error_code, errorData.details, errorData.correlation_id);
  }

  throw error;
};

// Retry with exponential backoff
const retryWithBackoff = async (fn: () => Promise<any>, maxRetries = 3) => {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (error.response?.status === 429) {
        const delay = Math.pow(2, attempt) * 1000; // 1s, 2s, 4s
        await new Promise(resolve => setTimeout(resolve, delay));
      } else {
        throw error;
      }
    }
  }
  throw new Error('Max retries exceeded');
};
```

## Workflows & Use Cases

### 🔄 Complete Document Processing Flow

```mermaid
graph TD
    A[Select Document] --> B[Validate File]
    B --> C[Upload to API]
    C --> D[Extract Text]
    D --> E[Create Chunks]
    E --> F[Generate Embeddings]
    F --> G[Store in Vector DB]
    G --> H[Mark Complete]
    H --> I[Ready for Search]

    B -->|Invalid| J[Show Error]
    C -->|Failed| J
    D -->|Failed| J
    E -->|Failed| J
    F -->|Failed| J
    G -->|Failed| J
```

### 🔍 Semantic Search Implementation

Once documents are processed, implement semantic search:

```typescript
// Semantic search implementation
class SemanticSearch {
  constructor(private apiClient: DocumentAPIClient) {}

  async searchAcrossDocuments(
    query: string,
    userId: string,
    options?: {
      documentIds?: string[];
      topK?: number;
      threshold?: number;
    }
  ): Promise<SearchResult[]> {
    const { documentIds, topK = 10, threshold = 0.7 } = options || {};

    // 1. Get all completed documents
    const docsResponse = await this.apiClient.listDocuments(userId, {
      status: 'completed'
    });

    const targetDocs = documentIds
      ? docsResponse.documents.filter(doc => documentIds.includes(doc.id))
      : docsResponse.documents;

    // 2. Collect all chunks with embeddings
    const allChunks: ChunkWithDoc[] = [];
    for (const doc of targetDocs) {
      const chunksResponse = await this.apiClient.getDocumentChunks(
        doc.id,
        true, // include embeddings
        100   // get all chunks
      );

      const chunksWithDoc = chunksResponse.chunks.map(chunk => ({
        ...chunk,
        document: doc
      }));

      allChunks.push(...chunksWithDoc);
    }

    // 3. Generate query embedding (requires OpenAI API)
    const queryEmbedding = await this.generateQueryEmbedding(query);

    // 4. Calculate similarities
    const results = allChunks.map(chunk => ({
      chunk,
      similarity: this.cosineSimilarity(queryEmbedding, chunk.embedding!),
      document: chunk.document
    }));

    // 5. Filter and sort
    return results
      .filter(result => result.similarity >= threshold)
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, topK);
  }

  private async generateQueryEmbedding(query: string): Promise<number[]> {
    // You'll need to implement this with OpenAI API
    // This is a simplified version - use your actual OpenAI integration
    const response = await fetch('https://api.openai.com/v1/embeddings', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'text-embedding-3-small',
        input: query
      })
    });

    const data = await response.json();
    return data.data[0].embedding;
  }

  private cosineSimilarity(a: number[], b: number[]): number {
    const dotProduct = a.reduce((sum, val, i) => sum + val * b[i], 0);
    const magnitudeA = Math.sqrt(a.reduce((sum, val) => sum + val * val, 0));
    const magnitudeB = Math.sqrt(b.reduce((sum, val) => sum + val * val, 0));
    return dotProduct / (magnitudeA * magnitudeB);
  }
}

// Usage example
const searchEngine = new SemanticSearch(apiClient);

const results = await searchEngine.searchAcrossDocuments(
  "artificial intelligence in healthcare",
  "user_123",
  { topK: 5, threshold: 0.75 }
);

console.log('Search results:', results);
```

### 📊 Batch Document Processing

```typescript
// Batch upload utility
const batchUploadDocuments = async (
  files: File[],
  userId: string,
  sessionId: string,
  onProgress?: (completed: number, total: number) => void
) => {
  const results = [];

  for (let i = 0; i < files.length; i++) {
    try {
      const result = await apiClient.uploadDocument(files[i], userId, sessionId);

      // Wait for processing to complete
      const finalDoc = await apiClient.waitForProcessing(result.document_id);

      results.push({ success: true, document: finalDoc, file: files[i].name });

      if (onProgress) {
        onProgress(i + 1, files.length);
      }

    } catch (error) {
      results.push({
        success: false,
        error: error.message,
        file: files[i].name
      });
    }
  }

  return results;
};
```

## Response Schemas

### TypeScript Type Definitions

```typescript
// Complete type definitions for the API
export interface UploadResponse {
  document_id: string;
  status: 'pending' | 'processing';
  message: string;
  processing_job_id?: string;
  estimated_processing_time?: number;
}

export interface DocumentStatus {
  id: string;
  user_id: string;
  session_id: string;
  project_id: string;
  filename: string;
  file_type: 'pdf' | 'docx' | 'txt' | 'md';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress_percentage: number;
  processing_started_at?: string;
  processing_completed_at?: string;
  processing_error?: string;
  created_at: string;
  updated_at?: string;
}

export interface DocumentResponse {
  id: string;
  user_id: string;
  session_id: string;
  project_id: string;
  filename: string;
  file_type: 'pdf' | 'docx' | 'txt' | 'md';
  file_size_bytes: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_pages?: number;
  total_chunks: number;
  total_tokens: number;
  storage_url?: string;
  metadata: Record<string, any>;
  tags: string[];
  created_at: string;
  updated_at?: string;
  processing_started_at?: string;
  processing_completed_at?: string;
}

export interface ChunkResponse {
  id: string;
  document_id: string;
  chunk_index: number;
  text_content: string;
  chunk_size: number;
  token_count?: number;
  page_number?: number;
  start_char: number;
  end_char: number;
  embedding?: number[]; // 1536 dimensions
  metadata: Record<string, any>;
  created_at: string;
}

export interface DocumentListResponse {
  documents: DocumentResponse[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface ChunkListResponse {
  chunks: ChunkResponse[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface DeleteResponse {
  success: boolean;
  message: string;
  deleted_chunks: number;
}

export interface ErrorResponse {
  error: string;
  error_code: string;
  message: string;
  details?: Record<string, any>;
  correlation_id?: string;
}

export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  version: string;
  environment: string;
  services: {
    database: boolean;
    openai: boolean;
    supabase: boolean;
    storage: boolean;
  };
  metrics: {
    database_time?: string;
    memory_usage_percent: number;
    disk_usage_percent: number;
  };
  uptime_seconds: number;
  timestamp: string;
}
```

## Performance & Security

### ⚡ Rate Limiting
- **Default**: 100 requests per minute per IP
- **Authenticated**: 200 requests per minute per user
- **Upload Endpoint**: 10 uploads per minute per user

### 🔒 Security Best Practices

```typescript
// Secure API client setup
class SecureAPIClient {
  private token: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.token = this.getSecureToken();
    this.refreshToken = this.getSecureRefreshToken();
  }

  // Store tokens securely
  private getSecureToken(): string | null {
    // Use httpOnly cookies in production, localStorage for demo
    return localStorage.getItem('jwt_token');
  }

  private async refreshAuthToken(): Promise<void> {
    if (!this.refreshToken) throw new Error('No refresh token available');

    // Implement token refresh logic
    const response = await fetch('/auth/refresh', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${this.refreshToken}` }
    });

    if (response.ok) {
      const data = await response.json();
      this.token = data.access_token;
      this.storeTokenSecurely(data.access_token);
    }
  }

  private storeTokenSecurely(token: string): void {
    // In production, use httpOnly cookies
    localStorage.setItem('jwt_token', token);
  }

  // Input validation
  private validateFile(file: File): void {
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
      'text/markdown'
    ];

    if (file.size > maxSize) {
      throw new Error(`File size (${(file.size / 1024 / 1024).toFixed(2)}MB) exceeds maximum of 10MB`);
    }

    if (!allowedTypes.includes(file.type)) {
      throw new Error('Unsupported file type. Use PDF, DOCX, TXT, or MD files.');
    }
  }

  // Sanitize metadata
  private sanitizeMetadata(metadata: any): any {
    // Remove potentially dangerous fields
    const sanitized = { ...metadata };
    delete sanitized.__proto__;
    delete sanitized.constructor;

    // Ensure values are safe
    Object.keys(sanitized).forEach(key => {
      if (typeof sanitized[key] === 'string') {
        sanitized[key] = sanitized[key].replace(/<script[^>]*>.*?<\/script>/gi, '');
      }
    });

    return sanitized;
  }
}
```

### 🚀 Performance Optimization

```typescript
// Optimized batch operations
class OptimizedAPIClient extends DocumentAPIClient {
  private cache = new Map();
  private requestQueue: Array<() => Promise<any>> = [];
  private isProcessingQueue = false;

  // Cache document metadata
  async getDocumentMetadataWithCache(documentId: string): Promise<DocumentResponse> {
    const cacheKey = `doc_meta_${documentId}`;

    if (this.cache.has(cacheKey)) {
      const cached = this.cache.get(cacheKey);
      if (Date.now() - cached.timestamp < 60000) { // 1 minute cache
        return cached.data;
      }
    }

    const data = await this.getDocumentMetadata(documentId);
    this.cache.set(cacheKey, { data, timestamp: Date.now() });
    return data;
  }

  // Debounced search
  private searchDebounceMap = new Map();

  async debouncedSearch(
    query: string,
    userId: string,
    delay: number = 300
  ): Promise<any> {
    const key = `${query}_${userId}`;

    if (this.searchDebounceMap.has(key)) {
      clearTimeout(this.searchDebounceMap.get(key));
    }

    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(async () => {
        try {
          // Implement actual search logic here
          const results = await this.searchDocuments(query, userId);
          resolve(results);
        } catch (error) {
          reject(error);
        } finally {
          this.searchDebounceMap.delete(key);
        }
      }, delay);

      this.searchDebounceMap.set(key, timeoutId);
    });
  }

  // Connection pooling simulation
  private connectionPool: Array<any> = [];

  private async getConnection() {
    // Reuse existing connections when possible
    if (this.connectionPool.length > 0) {
      return this.connectionPool.pop();
    }

    // Create new connection
    return this.createNewConnection();
  }

  private createNewConnection() {
    // Implementation would depend on your HTTP client
    return axios.create({
      baseURL: this.client.defaults.baseURL,
      headers: this.client.defaults.headers,
      timeout: 30000
    });
  }
}
```

## Quick Start Guide

### 🚀 5-Minute Integration

1. **Get Your JWT Token**
```javascript
// Replace with your authentication method
const token = 'your_jwt_token_here';
```

2. **Create API Client**
```javascript
import DocumentAPIClient from './utils/DocumentAPIClient';
const apiClient = new DocumentAPIClient(token);
```

3. **Upload and Process Document**
```javascript
const fileInput = document.getElementById('file-input');
const file = fileInput.files[0];

// Upload
const uploadResponse = await apiClient.uploadDocument(
  file,
  'user_123',
  'session_456'
);

// Wait for processing
const finalDoc = await apiClient.waitForProcessing(
  uploadResponse.document_id,
  (progress, status) => console.log(`${status}: ${progress}%`)
);

console.log('Document processed:', finalDoc);
```

4. **Get Chunks for Search**
```javascript
const chunks = await apiClient.getDocumentChunks(
  finalDoc.id,
  true // include embeddings
);

console.log(`Retrieved ${chunks.total} chunks for semantic search`);
```

### 🧪 Test Your Integration

```javascript
// Health check
const health = await apiClient.healthCheck();
console.log('API Status:', health.status);

// Test upload with small file
const testFile = new File(['Hello world'], 'test.txt', { type: 'text/plain' });
const result = await apiClient.uploadDocument(testFile, 'test_user', 'test_session');
console.log('Test upload successful:', result);
```

### 📱 Mobile Considerations

```javascript
// Mobile-optimized upload with compression
const compressImageIfNeeded = (file) => {
  if (file.size > 5 * 1024 * 1024) { // 5MB
    console.warn('Large file detected. Consider client-side compression.');
  }
  return file;
};

// Progressive upload for slow connections
const uploadWithProgress = async (file) => {
  const compressedFile = compressImageIfNeeded(file);

  return apiClient.uploadDocument(
    compressedFile,
    userId,
    sessionId,
    { timeout: 60000 } // Extended timeout for mobile
  );
};
```

## Support & Resources

### 📚 Additional Resources
- **Interactive API Docs**: https://document-chunk-embedding-production.up.railway.app:8080/docs
- **OpenAPI Schema**: https://document-chunk-embedding-production.up.railway.app:8080/openapi.json
- **Health Monitor**: https://document-chunk-embedding-production.up.railway.app:8080/api/health

### 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Check JWT token validity and format |
| 413 File Too Large | Ensure file is under 10MB |
| 429 Rate Limited | Implement exponential backoff retry |
| Processing stuck at 0% | Check file format compatibility |
| No chunks returned | Verify document status is 'completed' |
| CORS errors | Ensure your domain is whitelisted |

### 💡 Best Practices Checklist

- [ ] ✅ Implement proper error handling for all API calls
- [ ] ✅ Use exponential backoff for rate limit handling
- [ ] ✅ Cache document metadata to reduce API calls
- [ ] ✅ Validate files client-side before upload
- [ ] ✅ Show progress indicators for long operations
- [ ] ✅ Handle network interruptions gracefully
- [ ] ✅ Sanitize user input before sending to API
- [ ] ✅ Use HTTPS for all API communications
- [ ] ✅ Store JWT tokens securely (httpOnly cookies preferred)
- [ ] ✅ Implement token refresh mechanism
- [ ] ✅ Add request correlation IDs for debugging
- [ ] ✅ Monitor API health in production

### 🆘 Getting Help

**API Issues:**
- Check the health endpoint first
- Include correlation ID from error responses
- Monitor browser network tab for request details

**Integration Questions:**
- Review the code examples in this documentation
- Test with simple cases first (small text files)
- Verify authentication setup

**Production Deployment:**
- Monitor rate limits and adjust client behavior
- Implement proper logging and error tracking
- Set up health monitoring and alerts

---

*API Documentation v1.0.0*
*Last Updated: January 2025*
*Production API: https://document-chunk-embedding-production.up.railway.app:8080*