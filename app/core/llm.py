"""
LLM Client Utilities - Unified interface for LLM and embedding calls
Uses Vercel AI Gateway or direct OpenAI API
"""

from typing import Optional
import structlog
from openai import AsyncOpenAI

from app.config import get_settings

logger = structlog.get_logger(__name__)

_llm_client: Optional[AsyncOpenAI] = None


def get_llm_client() -> AsyncOpenAI:
    """Get or create the LLM client singleton."""
    global _llm_client
    
    if _llm_client is None:
        settings = get_settings()
        
        # Use Vercel AI Gateway if configured, otherwise direct OpenAI
        if settings.vercel_ai_gateway_url:
            _llm_client = AsyncOpenAI(
                api_key=settings.vercel_ai_gateway_token.get_secret_value(),
                base_url=settings.vercel_ai_gateway_url
            )
            logger.info("LLM client initialized with Vercel AI Gateway")
        else:
            # Fallback to direct OpenAI (would need OPENAI_API_KEY in env)
            import os
            _llm_client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY", "")
            )
            logger.info("LLM client initialized with direct OpenAI")
    
    return _llm_client


async def generate_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Generate embedding vector for text using OpenAI embeddings API."""
    client = get_llm_client()
    
    # Truncate text if too long (8191 tokens max for embedding models)
    max_chars = 30000  # Rough estimate, ~4 chars per token
    if len(text) > max_chars:
        text = text[:max_chars]
    
    try:
        response = await client.embeddings.create(
            model=model,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("Embedding generation failed", error=str(e), text_length=len(text))
        # Return zero vector as fallback (1536 dimensions for text-embedding-3-small)
        return [0.0] * 1536


async def chat_completion(
    messages: list[dict],
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    json_mode: bool = False
) -> str:
    """Simple chat completion helper."""
    client = get_llm_client()
    
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    
    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content
