"""Unit tests for the LLM module (mocked HTTP/API calls)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docflow.llm.base import (
    DocumentClassification,
    build_prompt,
    parse_classification_response,
)


@pytest.mark.unit
class TestParseClassificationResponse:
    def test_clean_json(self):
        raw = json.dumps({
            "doc_type": "Rechnung",
            "tags": ["Vodafone", "2026-03"],
            "suggested_filename": "2026-03_Vodafone_Rechnung.pdf",
            "confidence": 0.95,
        })
        result = parse_classification_response(raw)
        assert result.doc_type == "Rechnung"
        assert "Vodafone" in result.tags
        assert result.suggested_filename == "2026-03_Vodafone_Rechnung.pdf"
        assert result.confidence == 0.95

    def test_markdown_fenced_json(self):
        raw = '```json\n{"doc_type":"Brief","tags":[],"suggested_filename":"brief.pdf","confidence":0.7}\n```'
        result = parse_classification_response(raw)
        assert result.doc_type == "Brief"
        assert result.confidence == 0.7

    def test_missing_fields_use_defaults(self):
        raw = '{"doc_type": "Sonstiges"}'
        result = parse_classification_response(raw)
        assert result.doc_type == "Sonstiges"
        assert result.tags == []
        assert result.suggested_filename == "document.pdf"
        assert result.confidence == 0.5

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            parse_classification_response("not json at all")


@pytest.mark.unit
class TestBuildPrompt:
    def test_ocr_text_in_prompt(self):
        prompt = build_prompt("Test invoice text")
        assert "Test invoice text" in prompt

    def test_prompt_requests_json(self):
        prompt = build_prompt("anything")
        assert "JSON" in prompt
        assert "doc_type" in prompt


@pytest.mark.unit
class TestAnthropicProvider:
    @pytest.mark.asyncio
    async def test_classify_document(self):
        from docflow.llm.anthropic import AnthropicProvider

        fake_response = json.dumps({
            "doc_type": "Kontoauszug",
            "tags": ["DKB", "2026-02"],
            "suggested_filename": "2026-02_DKB_Kontoauszug.pdf",
            "confidence": 0.88,
        })

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=fake_response)]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        # anthropic is imported lazily inside __init__, so mock at sys.modules level
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.AsyncAnthropic.return_value = mock_client
        with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
            provider = AnthropicProvider(api_key="test-key")

        provider._client = mock_client
        result = await provider.classify_document("Kontoauszug DKB Dezember 2026")

        assert result.doc_type == "Kontoauszug"
        assert "DKB" in result.tags

    def test_raises_without_api_key(self):
        from docflow.llm.anthropic import AnthropicProvider
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            AnthropicProvider(api_key="")


@pytest.mark.unit
class TestOllamaProvider:
    @pytest.mark.asyncio
    async def test_classify_document(self):
        import httpx
        from docflow.llm.ollama import OllamaProvider

        fake_response = {
            "response": json.dumps({
                "doc_type": "Vertrag",
                "tags": ["Mietvertrag"],
                "suggested_filename": "2026-01_Mietvertrag.pdf",
                "confidence": 0.80,
            })
        }

        mock_response = MagicMock()
        mock_response.json.return_value = fake_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")

        with patch("docflow.llm.ollama.httpx.AsyncClient", return_value=mock_client):
            result = await provider.classify_document("Mietvertrag Wohnung Berlin")

        assert result.doc_type == "Vertrag"


@pytest.mark.unit
class TestOpenRouterProvider:
    @pytest.mark.asyncio
    async def test_classify_document(self):
        from docflow.llm.openrouter import OpenRouterProvider

        fake_response = {
            "choices": [
                {"message": {"content": json.dumps({
                    "doc_type": "Rechnung",
                    "tags": ["Telekom"],
                    "suggested_filename": "2026-03_Telekom_Rechnung.pdf",
                    "confidence": 0.91,
                })}}
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = fake_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = OpenRouterProvider(api_key="or-test-key")

        with patch("docflow.llm.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await provider.classify_document("Rechnung Telekom")

        assert result.doc_type == "Rechnung"

    def test_raises_without_api_key(self):
        from docflow.llm.openrouter import OpenRouterProvider
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            OpenRouterProvider(api_key="")
