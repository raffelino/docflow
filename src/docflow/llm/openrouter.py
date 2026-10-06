"""OpenRouter LLM provider (OpenAI-compatible API)."""

from __future__ import annotations

import httpx
import structlog

from docflow.llm.base import DocumentClassification, build_prompt, parse_classification_response

logger = structlog.get_logger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Reasoning-Modelle (DeepSeek V4) denken standardmaessig vor der Antwort und
# zaehlen das gegen max_tokens: mit 512 Tokens kam bei Dokumenten gar kein
# content mehr zurueck ('NoneType' object is not subscriptable), bei kuerzeren
# ein abgeschnittenes JSON. Fuer die Klassifikation braucht es kein Nachdenken,
# also aus — das ist auch die billigste und schnellste Variante.
REASONING = {"enabled": False}
MAX_TOKENS = 1024


class OpenRouterProvider:
    def __init__(
        self,
        api_key: str,
        model: str = "deepseek/deepseek-v4.1-flash",
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
            "max_tokens": MAX_TOKENS,
            "reasoning": REASONING,
            # JSON-Modus: kein Prosa-Vorspann, keine Markdown-Zaeune
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(OPENROUTER_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        raw = choice["message"].get("content")
        if not raw:
            raise ValueError(
                f"OpenRouter lieferte keinen Inhalt (finish_reason="
                f"{choice.get('finish_reason')!r}, model={self.model})"
            )
        logger.debug("OpenRouter response", raw=raw[:200])
        result = parse_classification_response(raw)
        logger.info(
            "Classification done",
            doc_type=result.doc_type,
            confidence=result.confidence,
            filename=result.suggested_filename,
        )
        return result
