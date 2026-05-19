import asyncio
import asyncpg
import os
from dotenv import load_dotenv
load_dotenv(override=True)

async def test():
    url = os.getenv("DATABASE_URL")
    print(f"Connecting to DB...")
    conn = await asyncpg.connect(url, timeout=10)
    print("Connected!")
    await conn.close()

asyncio.run(test())
