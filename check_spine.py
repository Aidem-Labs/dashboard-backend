import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect('postgresql://neondb_owner:npg_fIvBAb13GOzn@ep-misty-lab-ad2lnqxa-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')
    rows = await conn.fetch('SELECT * FROM spine_log ORDER BY created_at DESC')
    print(f'Total entries: {len(rows)}')
    for r in rows:
        print(f"  ID: {str(r['id'])[:8]}... Trigger: {r['trigger_type']} | Created: {r['created_at']}")
        print(f"  Original: {(r['original_output'] or 'N/A')[:100]}")
        print(f"  Replacement: {(r['replacement_output'] or 'N/A')[:100]}")
        print()
    await conn.close()
asyncio.run(check())
