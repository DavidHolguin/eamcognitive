import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.llm import chat_completion

async def test_robust_json():
    print("Testing robust JSON mode...")
    
    messages = [
        {"role": "system", "content": "Eres un asistente que solo responde en JSON."},
        {"role": "user", "content": "Genera un objeto JSON con el nombre 'EAM' y el año 2026."}
    ]
    
    try:
        print("1. Calling with json_mode=True (should attempt response_format first)...")
        response = await chat_completion(messages, json_mode=True)
        print(f"Response: {response}")
        
        # Test if it actually returns valid JSON
        import json
        json.loads(response)
        print("✅ JSON is valid.")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    if not os.getenv("VERCEL_AI_GATEWAY_TOKEN"):
        print("⚠️ VERCEL_AI_GATEWAY_TOKEN not found in environment. Test might fail if .env is missing or invalid.")
    
    asyncio.run(test_robust_json())
