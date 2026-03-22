"""
LLM client integration for the Clinic AI Assistant.
Connects to Qwen3.5 Plus via Alibaba DashScope API.
"""
import os
import time
import logging
import requests
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


class LLMClient:
    """Client for cloud LLM API (Qwen3.5 Plus via DashScope)."""

    def __init__(self, model: Optional[str] = None):
        t0 = time.time()
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "qwen3.5-plus")
        # Use the DashScope API endpoint from environment or default
        # The base URL should point to the API root (e.g., https://coding-intl.dashscope.aliyuncs.com)
        # and we'll append the full path to it
        base_url = os.getenv(
            "LLM_API_URL",
            "https://coding-intl.dashscope.aliyuncs.com"
        ).rstrip("/")
        self.api_url = f"{base_url}/apps/anthropic/v1/messages"

        # Initialize local embedding model (all-MiniLM-L6-v2)
        self._init_embedding_model()
        t1 = time.time()
        logger.info(f"[TIMING] LLMClient initialization: {t1-t0:.3f}s")

    def _init_embedding_model(self):
        """Initialize sentence-transformers for embeddings."""
        t0 = time.time()
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.has_embeddings = True
            t1 = time.time()
            logger.info(f"[TIMING] SentenceTransformer model loading: {t1-t0:.3f}s")
        except ImportError:
            logger.warning("sentence-transformers not installed. Local embeddings not available.")
            self.has_embeddings = False

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 512
    ) -> str:
        """Generate response from LLM using Claude-compatible API."""
        t0 = time.time()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": self.model,
            "system": system_prompt,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=120  # Increased timeout for slow API responses
            )
            response.raise_for_status()
            result = response.json()

            # Extract text from response content blocks
            for block in result.get('content', []):
                if block.get('type') == 'text':
                    t1 = time.time()
                    logger.info(f"[TIMING] LLM API call: {t1-t0:.3f}s")
                    return block['text']

            return "No text content in response"

        except requests.exceptions.Timeout:
            return "Error: Request timed out"
        except Exception as e:
            return f"Error generating response: {str(e)}"

    def embed(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using all-MiniLM-L6-v2."""
        if not self.has_embeddings:
            return None
        t0 = time.time()
        result = self.embedding_model.encode(text).tolist()
        t1 = time.time()
        logger.info(f"[TIMING] Single embed: {t1-t0:.3f}s")
        return result

    def generate_with_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 512
    ):
        """
        Generate response with streaming support.
        Note: DashScope API may not support streaming in the same way.
        This is a placeholder for future implementation.
        """
        # For now, fall back to non-streaming generation
        # Streaming support would require checking DashScope API capabilities
        response = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        yield response


# Singleton instance
llm_client = LLMClient()


if __name__ == "__main__":
    # Test LLM client
    import sys

    if len(sys.argv) > 1:
        test_prompt = sys.argv[1]
        result = llm_client.generate(
            system_prompt="You are an ultra-fast, direct assistant.",
            user_prompt=test_prompt
        )
        print(result)
