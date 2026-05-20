import asyncio, asyncpg

DATABASE_URL = "postgresql://neondb_owner:npg_fIvBAb13GOzn@ep-misty-lab-ad2lnqxa-pooler.c-2.us-east-1.aws.neon.tech/neondb"

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    )
    print("=== TABLES IN NEON DB ===")
    for r in rows:
        cnt = await conn.fetchval(f'SELECT COUNT(*) FROM "{r["table_name"]}"')
        print(f"  {r['table_name']:25s} -> {cnt} rows")
    
    # Check pgvector extension
    ext = await conn.fetchval("SELECT installed_version FROM pg_available_extensions WHERE name = 'vector'")
    print(f"\npgvector extension: {ext or 'NOT INSTALLED'}")

    await conn.close()

asyncio.run(main())
