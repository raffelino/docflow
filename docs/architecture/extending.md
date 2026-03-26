# Erweiterbarkeit

DocFlow ist durch Protocol-basierte Abstraktion leicht erweiterbar.

## Neuen LLM-Provider hinzufuegen

1. Erstelle `src/docflow/llm/myprovider.py`:

```python
from docflow.llm.base import (
    DocumentClassification,
    build_prompt,
    parse_classification_response,
)

class MyProvider:
    async def classify_document(
        self, ocr_text: str
    ) -> DocumentClassification:
        prompt = build_prompt(ocr_text)
        # API-Aufruf hier...
        raw_response = await call_my_api(prompt)
        return parse_classification_response(raw_response)
```

2. Registriere in `llm/__init__.py`:

```python
def get_llm_provider(settings):
    if settings.llm_provider == "myprovider":
        return MyProvider(settings)
    # ...
```

3. Fuege den Provider-Namen in `config.py` zum `Literal`-Typ hinzu

4. Schreibe Tests in `tests/test_llm.py`

## Neues Storage-Backend hinzufuegen

1. Erstelle `src/docflow/storage/myprovider.py`:

```python
class MyStorage:
    @property
    def name(self) -> str:
        return "mystorage"

    async def save(
        self, local_path: Path, destination_path: str
    ) -> str:
        # Upload-Logik hier...
        return "mystorage://bucket/path"
```

2. Registriere in `storage/__init__.py`

3. Fuege den Backend-Namen in `config.py` hinzu

4. Schreibe Tests in `tests/e2e/test_e2e_storage.py`

## DocumentClassification

Die zentrale Datenklasse fuer LLM-Ergebnisse:

```python
@dataclass
class DocumentClassification:
    doc_type: str           # z.B. "Rechnung"
    tags: list[str]         # z.B. ["Vodafone", "Mobilfunk"]
    suggested_filename: str # z.B. "2026-03_Vodafone_Rechnung.pdf"
    confidence: float       # 0.0 - 1.0
```
