import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect('postgresql://neondb_owner:npg_fIvBAb13GOzn@ep-misty-lab-ad2lnqxa-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')
    rows = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
    for r in rows:
        print(r['table_name'])
    await conn.close()
asyncio.run(check())
