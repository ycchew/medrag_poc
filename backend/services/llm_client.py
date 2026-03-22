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
        base_url = os.getenv(
            "LLM_API_URL", "https://coding-intl.dashscope.aliyuncs.com"
        ).rstrip("/")
        self.api_url = f"{base_url}/apps/anthropic/v1/messages"
        self.embedding_url = f"{base_url}/compatible-mode/v1/embeddings"

        # Check if API key is available
        self.has_embeddings = bool(self.api_key)
        if not self.has_embeddings:
            logger.warning("LLM_API_KEY not set. API features not available.")

        t1 = time.time()
        logger.info(f"[TIMING] LLMClient initialization: {t1 - t0:.3f}s")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> str:
        """Generate response from LLM using Claude-compatible API."""
        t0 = time.time()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.model,
            "system": system_prompt,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        try:
            response = requests.post(
                self.api_url, headers=headers, json=payload, timeout=120
            )
            response.raise_for_status()
            result = response.json()

            for block in result.get("content", []):
                if block.get("type") == "text":
                    t1 = time.time()
                    logger.info(f"[TIMING] LLM API call: {t1 - t0:.3f}s")
                    return block["text"]

            return "No text content in response"

        except requests.exceptions.Timeout:
            return "Error: Request timed out"
        except Exception as e:
            return f"Error generating response: {str(e)}"

    def embed(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using DashScope API."""
        if not self.has_embeddings:
            logger.error("Cannot generate embeddings: LLM_API_KEY not set")
            return None

        t0 = time.time()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "text-embedding-v3",
            "input": text,
            "dimensions": 384,
            "encoding_format": "float",
        }

        try:
            response = requests.post(
                self.embedding_url, headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            result = response.json()

            embedding = result.get("data", [{}])[0].get("embedding")
            t1 = time.time()
            logger.info(f"[TIMING] Embed API call: {t1 - t0:.3f}s")
            return embedding

        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def generate_with_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ):
        """Generate response with streaming support."""
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
            user_prompt=test_prompt,
        )
        print(result)
