"""Ollama (local) LLM provider."""

from __future__ import annotations

import httpx
import structlog

from docflow.llm.base import DocumentClassification, build_prompt, parse_classification_response

logger = structlog.get_logger(__name__)


class OllamaProvider:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def classify_document(self, ocr_text: str) -> DocumentClassification:
        prompt = build_prompt(ocr_text)
        logger.info("Calling Ollama", model=self.model, text_chars=len(ocr_text))

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()

        raw = data.get("response", "")
        logger.debug("Ollama response", raw=raw[:200])
        result = parse_classification_response(raw)
        logger.info(
            "Classification done",
            doc_type=result.doc_type,
            confidence=result.confidence,
            filename=result.suggested_filename,
        )
        return result
