from pydantic_settings import BaseSettings
from typing import List, Optional
import os
import sys


class Settings(BaseSettings):
    # Application
    app_name: str = "document-processing-microservice"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = False

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    database_url: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # OpenAI API
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"  # For any text generation if needed
    openai_embedding_model: str = "text-embedding-3-small"
    openai_base_url: str = "https://api.openai.com"

    # Background Processing
    job_polling_interval: int = 5  # seconds, for optional database job queue

    # File Upload
    max_upload_size_mb: int = 50
    allowed_file_types: List[str] = ["pdf", "docx", "txt", "md"]
    temp_upload_dir: str = "/tmp/document_uploads"

    # Chunking
    chunk_size_min: int = 1000
    chunk_size_max: int = 1500
    chunk_overlap: int = 200
    max_chunks_per_document: int = 1000

    # Embedding
    embedding_batch_size: int = 100
    embedding_max_retries: int = 3
    embedding_retry_delay: int = 1
    embedding_dimension: int = 1536

    # Rate Limiting
    rate_limit_requests_per_hour: int = 1000
    rate_limit_upload_per_hour: int = 100

    # Monitoring
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    log_level: str = "INFO"
    log_format: str = "json"

    # Security
    file_scan_enabled: bool = True
    virus_scan_enabled: bool = False
    input_sanitization: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_railway(self) -> bool:
        """Check if running on Railway platform."""
        return "RAILWAY_ENVIRONMENT" in os.environ

    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return os.getenv('TESTING_MODE', 'false').lower() == 'true'

    @property
    def database_pool_size(self) -> int:
        """Get database connection pool size based on environment."""
        if self.is_production:
            return 20
        elif self.is_railway:
            return 10
        else:
            return 5

    @property
    def database_max_overflow(self) -> int:
        """Get database connection overflow based on environment."""
        if self.is_production:
            return 40
        elif self.is_railway:
            return 20
        else:
            return 10

    @property
    def temp_dir(self) -> str:
        """Get appropriate temp directory for the environment."""
        if self.is_railway or self.is_production:
            return "/tmp/document_uploads"
        else:
            return self.temp_upload_dir

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins based on environment."""
        if self.is_production:
            # Parse CORS_ORIGINS from environment if it's a string
            cors_env = os.getenv('CORS_ORIGINS', '[]')
            if isinstance(cors_env, str):
                try:
                    import json
                    return json.loads(cors_env)
                except:
                    return ["https://*.railway.app"]
            return self.cors_origins
        else:
            # Development - allow localhost
            return [
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
                "file://",
                "null"
            ]


settings = Settings()