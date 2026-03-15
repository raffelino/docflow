"""OpenRouter LLM provider (OpenAI-compatible API)."""

from __future__ import annotations

import httpx
import structlog

from docflow.llm.base import DocumentClassification, build_prompt, parse_classification_response

logger = structlog.get_logger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3-haiku",
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for the OpenRouter provider")
        self.api_key = api_key
        self.model = model

    async def classify_document(self, ocr_text: str) -> DocumentClassification:
        prompt = build_prompt(ocr_text)
        logger.info("Calling OpenRouter", model=self.model, text_chars=len(ocr_text))

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/docflow",
            "X-Title": "DocFlow",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OPENROUTER_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        raw = data["choices"][0]["message"]["content"]
        logger.debug("OpenRouter response", raw=raw[:200])
        result = parse_classification_response(raw)
        logger.info(
            "Classification done",
            doc_type=result.doc_type,
            confidence=result.confidence,
            filename=result.suggested_filename,
        )
        return result
