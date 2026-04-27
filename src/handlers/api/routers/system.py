"""System metadata routes — surfaces server-side state SPAs need.

The HTML form pages (`generate.html`, `evaluate.html`) inject `LLMInfo`
to disable the submit button and show a "Generation unavailable" banner
when the LLM stack is not ready. Without an API equivalent an SPA can
only discover the same condition by trying a generation and catching
the 503 — too late to gate the UI.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.config import LLMInfo
from src.handlers.api.dependencies import get_llm_info
from src.handlers.api.schemas import LLMInfoSchema

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/llm-info", response_model=LLMInfoSchema)
def get_llm_info_endpoint(
    llm_info: LLMInfo = Depends(get_llm_info),
) -> LLMInfoSchema:
    """Return the active LLM provider, model, and readiness flag.

    Mirrors the data the HTML `/generate` and `/evaluate` form pages put
    on `llm_info`. SPAs use this to render a "Generation unavailable"
    banner and disable the submit button when `ready=False`.
    """
    return LLMInfoSchema.from_domain(llm_info)
