
import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

async def check_pdi_tables():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in .env")
        return

    supabase: Client = create_client(url, key)
    
    tables = ["pdi_documents", "pdi_entities", "pdi_entity_relations"]
    
    for table in tables:
        try:
            print(f"Checking table: {table}...")
            result = supabase.table(table).select("*").limit(1).execute()
            print(f"  OK: Table {table} exists. Data count: {len(result.data)}")
        except Exception as e:
            print(f"  ERROR: Table {table} failed or does not exist: {str(e)}")
            
    # Check RPC
    try:
        print("Checking RPC: match_pdi_entities...")
        # Mock embedding (1536 zeros)
        mock_embedding = [0.0] * 1536
        result = supabase.rpc("match_pdi_entities", {
            "query_embedding": mock_embedding,
            "match_threshold": 0.5,
            "match_count": 1
        }).execute()
        print(f"  OK: RPC match_pdi_entities exists. Result type: {type(result.data)}")
    except Exception as e:
        print(f"  ERROR: RPC match_pdi_entities failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(check_pdi_tables())
