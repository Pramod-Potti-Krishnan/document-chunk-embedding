-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create profiles table
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    full_name VARCHAR(255),
    organization VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    storage_quota_mb INTEGER DEFAULT 5000,
    storage_used_mb FLOAT DEFAULT 0.0,
    documents_quota INTEGER DEFAULT 10000,
    documents_count INTEGER DEFAULT 0,
    api_calls_quota INTEGER DEFAULT 100000,
    api_calls_count INTEGER DEFAULT 0,
    preferences JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE
);

-- Create user_sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    project_id VARCHAR(255) DEFAULT '-',
    session_name VARCHAR(255),
    session_type VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id, session_id, project_id)
);

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    project_id VARCHAR(255) DEFAULT '-',
    user_session_id UUID REFERENCES user_sessions(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    file_hash VARCHAR(64),
    mime_type VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    processing_error TEXT,
    processing_attempts INTEGER DEFAULT 0,
    total_pages INTEGER,
    total_chunks INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    language VARCHAR(10),
    storage_path VARCHAR(500),
    storage_url VARCHAR(1000),
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create document_chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    project_id VARCHAR(255) DEFAULT '-',
    chunk_index INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    chunk_size INTEGER NOT NULL,
    token_count INTEGER,
    page_number INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    overlap_start INTEGER,
    overlap_end INTEGER,
    embedding vector(1536),
    embedding_model VARCHAR(100),
    embedding_created_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- Create processing_jobs table
CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    celery_task_id VARCHAR(255) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    priority INTEGER DEFAULT 5,
    progress_percentage INTEGER DEFAULT 0,
    progress_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    processing_time_seconds FLOAT,
    error_message TEXT,
    error_details JSONB,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create processing_stats table
CREATE TABLE IF NOT EXISTS processing_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    date TIMESTAMP WITH TIME ZONE NOT NULL,
    documents_processed INTEGER DEFAULT 0,
    documents_failed INTEGER DEFAULT 0,
    total_chunks_created INTEGER DEFAULT 0,
    total_embeddings_created INTEGER DEFAULT 0,
    total_bytes_processed INTEGER DEFAULT 0,
    avg_processing_time_seconds FLOAT,
    max_processing_time_seconds FLOAT,
    min_processing_time_seconds FLOAT,
    api_calls_count INTEGER DEFAULT 0,
    embedding_api_calls INTEGER DEFAULT 0,
    estimated_cost_usd FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- Create indexes for better performance
CREATE INDEX idx_profiles_user_id ON profiles(user_id);
CREATE INDEX idx_user_sessions_hierarchy ON user_sessions(user_id, session_id, project_id);
CREATE INDEX idx_documents_hierarchy ON documents(user_id, session_id, project_id);
CREATE INDEX idx_documents_status ON documents(status, created_at);
CREATE INDEX idx_document_chunks_hierarchy ON document_chunks(user_id, session_id, project_id);
CREATE INDEX idx_document_chunks_document ON document_chunks(document_id, chunk_index);
CREATE INDEX idx_processing_jobs_status ON processing_jobs(status, created_at);
CREATE INDEX idx_processing_jobs_user ON processing_jobs(user_id, status);
CREATE INDEX idx_processing_jobs_celery ON processing_jobs(celery_task_id);
CREATE INDEX idx_processing_stats_user_date ON processing_stats(user_id, date);

-- Create vector similarity search index
CREATE INDEX idx_chunk_embedding_ivfflat ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Enable Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_stats ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (for Supabase Auth integration)
-- Note: These assume auth.uid() returns the user_id
CREATE POLICY "Users can view own profile" ON profiles
    FOR ALL USING (user_id = auth.uid()::text);

CREATE POLICY "Users can manage own sessions" ON user_sessions
    FOR ALL USING (user_id = auth.uid()::text);

CREATE POLICY "Users can manage own documents" ON documents
    FOR ALL USING (user_id = auth.uid()::text);

CREATE POLICY "Users can view own chunks" ON document_chunks
    FOR ALL USING (user_id = auth.uid()::text);

CREATE POLICY "Users can view own jobs" ON processing_jobs
    FOR ALL USING (user_id = auth.uid()::text);

CREATE POLICY "Users can view own stats" ON processing_stats
    FOR ALL USING (user_id = auth.uid()::text);

-- Create update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_sessions_updated_at BEFORE UPDATE ON user_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_jobs_updated_at BEFORE UPDATE ON processing_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_stats_updated_at BEFORE UPDATE ON processing_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();