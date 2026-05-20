import asyncio, asyncpg

DB = "postgresql://neondb_owner:npg_fIvBAb13GOzn@ep-misty-lab-ad2lnqxa-pooler.c-2.us-east-1.aws.neon.tech/neondb"

async def main():
    conn = await asyncpg.connect(DB)
    rows = await conn.fetch("SELECT * FROM auth_users ORDER BY created_at DESC LIMIT 5")
    print("=== DEV BRANCH: auth_users (last 5) ===")
    for r in rows:
        print(f"  id={r['id']}  email={r['email']}  verified={r['is_verified']}  admin={r['is_admin']}  created={r['created_at']}")
    await conn.close()

asyncio.run(main())
