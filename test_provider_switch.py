import os
import sys
import asyncio

# Mock environment before importing app modules
os.environ["LLM_PROVIDER"] = "OPENAI"
# Ensure we don't accidentally use Vercel URL
if "VERCEL_AI_GATEWAY_URL" in os.environ:
    del os.environ["VERCEL_AI_GATEWAY_URL"]

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.config import get_settings
from app.core.llm import get_llm_client

def test_config():
    settings = get_settings()
    print(f"Provider: {settings.llm_provider}")
    print(f"Vercel URL: {settings.vercel_ai_gateway_url}")
    
    client = get_llm_client()
    print(f"Client Base URL: {client.base_url}")
    
    # OpenAI default base url should be https://api.openai.com/v1/
    if "api.openai.com" in str(client.base_url):
        print("✅ Client is using OpenAI direct URL")
    else:
        print(f"❌ Client is NOT using OpenAI URL: {client.base_url}")

if __name__ == "__main__":
    test_config()
