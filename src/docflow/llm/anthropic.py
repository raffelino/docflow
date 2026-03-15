"""Anthropic Claude LLM provider."""

from __future__ import annotations

import structlog

from docflow.llm.base import DocumentClassification, build_prompt, parse_classification_response

logger = structlog.get_logger(__name__)


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022") -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        try:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError as e:
            raise ImportError("anthropic package not installed. Run: uv add anthropic") from e
        self.model = model

    async def classify_document(self, ocr_text: str) -> DocumentClassification:
        prompt = build_prompt(ocr_text)
        logger.info("Calling Anthropic Claude", model=self.model, text_chars=len(ocr_text))

        message = await self._client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        logger.debug("Anthropic response", raw=raw[:200])
        result = parse_classification_response(raw)
        logger.info(
            "Classification done",
            doc_type=result.doc_type,
            confidence=result.confidence,
            filename=result.suggested_filename,
        )
        return result
