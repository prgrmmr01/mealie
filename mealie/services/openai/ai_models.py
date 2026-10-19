from __future__ import annotations

import httpx
from pydantic import BaseModel

from mealie.core.root_logger import get_logger

logger = get_logger("services.ai_models")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_OPENAI_COMPAT_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class ModelItem(BaseModel):
    id: str
    name: str
    description: str | None = None


async def fetch_gemini_models(api_key: str, timeout: int = 15) -> list[ModelItem]:
    """Queries the Google Gemini API for available models supporting content generation."""
    url = f"{GEMINI_API_URL}/models?key={api_key}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    models: list[ModelItem] = []
    raw_models = data.get("models", [])
    for item in raw_models:
        methods = item.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            full_name = item.get("name", "")  # e.g. "models/gemini-2.5-flash"
            model_id = full_name.removeprefix("models/")
            display_name = item.get("displayName", model_id)
            desc = item.get("description", "")
            models.append(ModelItem(id=model_id, name=display_name, description=desc))

    priority_order = [
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    def sort_key(m: ModelItem) -> int:
        for i, prefix in enumerate(priority_order):
            if m.id.startswith(prefix):
                return i
        return 999

    models.sort(key=lambda m: (sort_key(m), m.name))
    return models


async def fetch_openai_models(api_key: str, base_url: str | None = None, timeout: int = 15) -> list[ModelItem]:
    """Queries an OpenAI or OpenAI-compatible endpoint for available models."""
    base = (base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

    models: list[ModelItem] = []
    for item in data.get("data", []):
        model_id = item.get("id", "")
        if model_id:
            models.append(ModelItem(id=model_id, name=model_id))

    models.sort(key=lambda m: m.name)
    return models
