"""Settings endpoint — read-only view of configuration.

Per spec §13, secrets stay in `.env` and are never exposed or editable via the
UI; this endpoint only reports non-secret defaults and which provider is set.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("")
def get_settings_view(_: User = Depends(get_current_user)) -> dict:
    provider_key_set = {
        "anthropic": bool(settings.anthropic_api_key),
        "openai": bool(settings.openai_api_key),
        "gemini": bool(settings.gemini_api_key),
    }
    return {
        "company_name": settings.company_name,
        "user_full_name": settings.user_full_name,
        "email_signature": settings.email_signature,
        "default_markup_percent": settings.default_markup_percent,
        "default_currency": settings.default_currency,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_key_configured": provider_key_set.get(settings.llm_provider.lower(), False),
        "app_env": settings.app_env,
        "edit_hint": "Values are configured in the .env file; restart to apply changes.",
    }
