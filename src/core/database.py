from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from supabase import create_client, Client
from contextlib import contextmanager
import asyncpg
from typing import AsyncGenerator, Generator
from src.config.settings import settings
from src.models.database import Base
import logging

logger = logging.getLogger(__name__)

# SQLAlchemy setup
engine = create_engine(
    settings.database_url,
    poolclass=NullPool,  # Let Supabase handle connection pooling
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Supabase client
supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_key  # Use service key for RLS bypass when needed
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db_pool():
    """
    Create async database pool for high-performance operations.
    """
    return await asyncpg.create_pool(
        settings.database_url,
        min_size=10,
        max_size=20,
        command_timeout=60,
        server_settings={
            'jit': 'off',
            'search_path': 'public',
        }
    )


def create_tables():
    """
    Create all database tables.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def init_pgvector():
    """
    Initialize pgvector extension and create vector indexes.
    """
    try:
        with engine.begin() as conn:
            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        with engine.begin() as conn:
            # Create ivfflat index for faster similarity search
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunk_embedding_ivfflat
                ON document_chunks
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """))

        logger.info("pgvector extension and indexes initialized")
    except Exception as e:
        logger.error(f"Error initializing pgvector: {e}")
        # Don't raise - continue if pgvector fails


def init_rls_policies():
    """
    Initialize Row Level Security policies for Supabase.
    """
    policies = [
        # Enable RLS on tables
        "ALTER TABLE profiles ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE documents ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY",

        # Profiles policies
        """
        CREATE POLICY profiles_user_policy ON profiles
        FOR ALL USING (user_id = auth.uid()::text)
        """,

        # User sessions policies
        """
        CREATE POLICY user_sessions_policy ON user_sessions
        FOR ALL USING (user_id = auth.uid()::text)
        """,

        # Documents policies
        """
        CREATE POLICY documents_user_policy ON documents
        FOR ALL USING (user_id = auth.uid()::text)
        """,

        # Document chunks policies
        """
        CREATE POLICY chunks_user_policy ON document_chunks
        FOR ALL USING (user_id = auth.uid()::text)
        """,

        # Processing jobs policies
        """
        CREATE POLICY jobs_user_policy ON processing_jobs
        FOR ALL USING (user_id = auth.uid()::text)
        """,
    ]

    with engine.connect() as conn:
        for policy in policies:
            try:
                conn.execute(text(policy))
                conn.commit()
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"RLS policy error (may be okay if exists): {e}")


def init_database():
    """
    Initialize database with all required setup.
    """
    create_tables()
    init_pgvector()
    init_rls_policies()
    logger.info("Database initialization complete")


# Vector similarity search function
async def vector_similarity_search(
    embedding: list,
    user_id: str,
    session_id: str = None,
    project_id: str = None,
    limit: int = 10,
    threshold: float = 0.7
):
    """
    Perform vector similarity search using pgvector.
    """
    query = """
        SELECT
            id,
            document_id,
            chunk_index,
            text_content,
            1 - (embedding <=> $1::vector) as similarity
        FROM document_chunks
        WHERE user_id = $2
    """

    params = [embedding, user_id]
    param_count = 2

    if session_id:
        param_count += 1
        query += f" AND session_id = ${param_count}"
        params.append(session_id)

    if project_id:
        param_count += 1
        query += f" AND project_id = ${param_count}"
        params.append(project_id)

    query += f"""
        AND 1 - (embedding <=> $1::vector) > ${param_count + 1}
        ORDER BY embedding <=> $1::vector
        LIMIT ${param_count + 2}
    """

    params.extend([threshold, limit])

    pool = await get_async_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]