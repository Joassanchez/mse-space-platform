"""LLM chat endpoint — test the AI provider directly."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from argplant.shared.llm import get_llm_client
from argplant.shared.config import settings

logger = logging.getLogger("argplant.chat")

router = APIRouter(tags=["ai"])


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    system: str | None = None


class ChatResponse(BaseModel):
    response: str
    provider: str
    model: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a prompt to the configured LLM and return the response.

    Uses the provider and model configured via LLM_PROVIDER / LLM_MODEL env vars.
    Requires a valid API key (GEMINI_API_KEY for gemini provider).
    """
    if not settings.GEMINI_API_KEY and settings.LLM_PROVIDER == "gemini":
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY not configured. Set it in .env to use the LLM.",
        )

    try:
        client = get_llm_client()
        result = await client.generate(request.prompt, request.system)
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM dependency missing: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("LLM call failed")
        raise HTTPException(
            status_code=502,
            detail=f"LLM request failed: {exc}",
        ) from exc

    return ChatResponse(
        response=result,
        provider=settings.LLM_PROVIDER,
        model=settings.LLM_MODEL,
    )
