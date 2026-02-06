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
        
        if settings.llm_provider.upper() == "VERCEL":
            if not settings.vercel_ai_gateway_token:
                raise ValueError("Vercel AI Gateway token is required when provider is VERCEL")
                
            _llm_client = AsyncOpenAI(
                api_key=settings.vercel_ai_gateway_token.get_secret_value(),
                base_url=settings.vercel_ai_gateway_url
            )
            logger.info("LLM client initialized with Vercel AI Gateway")
        else:
            # Default to direct OpenAI
            api_key = None
            if settings.openai_api_key:
                api_key = settings.openai_api_key.get_secret_value()
            else:
                import os
                api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                logger.warning("No OpenAI API key found. LLM calls may fail.")
            
            _llm_client = AsyncOpenAI(
                api_key=api_key or "dummy_key_for_build"
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
    """
    Simple chat completion helper.
    Ensures robust handling of json_mode across different model providers.
    """
    client = get_llm_client()
    
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    
    if json_mode:
        # Some models or gateways fail with response_format
        # We'll try with it first, but fallback if it errors
        try:
            kwargs["response_format"] = {"type": "json_object"}
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.warning("LLM call with response_format failed, falling back to prompt-only JSON", error=str(e))
            # Remove response_format and try again
            if "response_format" in kwargs:
                del kwargs["response_format"]
            
            # Ensure the last message asks for JSON
            if messages and messages[-1]["role"] != "system":
                messages[-1]["content"] += "\n\nResponde únicamente en formato JSON válido."
            
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
    
    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content
