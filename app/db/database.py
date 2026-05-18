import asyncpg
from app.config import DATABASE_URL
from app.utils.celebrity_profiles import seed_celebrity_profiles

_pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def init_db():
    """Create tables ONLY if they don't exist. Won't touch existing tables."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check which tables already exist
        existing = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        existing_names = {row["table_name"] for row in existing}

        # Only create tables that don't exist yet
        if "sessions" not in existing_names:
            await conn.execute("""
                CREATE TABLE sessions (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    user_id UUID,
                    onboarding_data JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX idx_sessions_created_at ON sessions(created_at);
                CREATE INDEX idx_sessions_user_id ON sessions(user_id);
            """)
            print("Created table: sessions")
        else:
            await conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id UUID;")
            await conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS onboarding_data JSONB DEFAULT '{}';")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);")

        if "persona_configs" not in existing_names:
            await conn.execute("""
                CREATE TABLE persona_configs (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
                    persona_name TEXT NOT NULL,
                    tweets JSONB,
                    persona_traits TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX idx_persona_configs_session_id ON persona_configs(session_id);
            """)
            print("Created table: persona_configs")

        if "messages" not in existing_names:
            await conn.execute("""
                CREATE TABLE messages (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX idx_messages_session_id ON messages(session_id);
            """)
            print("Created table: messages")

        if "celebrity_profiles" not in existing_names:
            await conn.execute("""
                CREATE TABLE celebrity_profiles (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    personality_traits TEXT,
                    speaking_style TEXT,
                    common_topics TEXT,
                    sample_tweets JSONB,
                    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX idx_celebrity_profiles_name ON celebrity_profiles(name);
            """)
            print("Created table: celebrity_profiles")


        if "learning_queue" not in existing_names:
            await conn.execute("""
                CREATE TABLE learning_queue (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    question TEXT NOT NULL,
                    ai_answer TEXT,
                    feedback TEXT,
                    suggested_answer TEXT,
                    suggested_answer_embedding vector(384),
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX idx_learning_queue_status ON learning_queue(status);
            """)
            print("Created table: learning_queue")

        # Ensure pgvector extension and document_chunks table exist
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        if "document_chunks" not in existing_names:
            await conn.execute("""
                CREATE TABLE document_chunks (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    session_id TEXT,
                    filename TEXT,
                    file_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    full_content TEXT,
                    embedding vector(384),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX idx_chunks_file_name ON document_chunks(file_name);
                CREATE INDEX idx_chunks_session_id ON document_chunks(session_id);
            """)
            print("Created table: document_chunks")
        else:
            # Migrate: add new columns if missing
            await conn.execute("""
                ALTER TABLE document_chunks
                    ADD COLUMN IF NOT EXISTS session_id TEXT,
                    ADD COLUMN IF NOT EXISTS filename TEXT,
                    ADD COLUMN IF NOT EXISTS full_content TEXT;
            """)
            await conn.execute("""
                UPDATE document_chunks SET filename = file_name WHERE filename IS NULL;
            """)
            # Backfill full_content: for each file, set full_content on the earliest chunk
            await conn.execute("""
                UPDATE document_chunks dc
                SET full_content = dc.content
                FROM (
                    SELECT DISTINCT ON (file_name) id
                    FROM document_chunks
                    ORDER BY file_name, created_at ASC
                ) first
                WHERE dc.id = first.id AND dc.full_content IS NULL;
            """)

        if "auth_users" not in existing_names:
            await conn.execute("""
                CREATE TABLE auth_users (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX idx_auth_users_email ON auth_users(email);
            """)
            print("Created table: auth_users")

        if "auth_otp_codes" not in existing_names:
            await conn.execute("""
                CREATE TABLE auth_otp_codes (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    email TEXT NOT NULL,
                    code TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX idx_auth_otp_email ON auth_otp_codes(email);
            """)
            print("Created table: auth_otp_codes")

        # Drop legacy documents table if it still exists
        await conn.execute("DROP TABLE IF EXISTS documents CASCADE;")

        print("Database check complete. Only created tables that didn't exist.")


        # Seed pre-stored celebrity profiles
        await seed_celebrity_profiles(pool)
