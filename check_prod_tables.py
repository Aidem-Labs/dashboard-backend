import asyncio, asyncpg

DB = "postgresql://neondb_owner:npg_fIvBAb13GOzn@ep-shiny-mud-adwijmjc-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

async def main():
    conn = await asyncpg.connect(DB)
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    )
    print("=== PRODUCTION BRANCH TABLES ===")
    for r in rows:
        cnt = await conn.fetchval(f'SELECT COUNT(*) FROM "{r["table_name"]}"')
        print(f"  {r['table_name']:25s} -> {cnt} rows")
    await conn.close()

asyncio.run(main())
