import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect('postgresql://neondb_owner:npg_fIvBAb13GOzn@ep-misty-lab-ad2lnqxa-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')
    
    # Check patients table columns
    print('=== patients table ===')
    rows = await conn.fetch("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'patients' ORDER BY ordinal_position")
    for r in rows: print(f"  {r['column_name']} ({r['data_type']}, nullable={r['is_nullable']})")
    
    # Check patient_users table columns
    print('\n=== patient_users table ===')
    rows = await conn.fetch("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'patient_users' ORDER BY ordinal_position")
    for r in rows: print(f"  {r['column_name']} ({r['data_type']}, nullable={r['is_nullable']})")
    
    # Check a sample patient
    print('\n=== sample patient (first 3) ===')
    rows = await conn.fetch("SELECT id, name, email, user_id FROM patients LIMIT 3")
    for r in rows: print(f"  id={r['id']}, name={r['name']}, email={r['email']}, user_id={r['user_id']}")
    
    # Check journal_entries table
    print('\n=== journal_entries table ===')
    rows = await conn.fetch("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'journal_entries' ORDER BY ordinal_position")
    for r in rows: print(f"  {r['column_name']} ({r['data_type']}, nullable={r['is_nullable']})")
    
    await conn.close()
asyncio.run(check())
