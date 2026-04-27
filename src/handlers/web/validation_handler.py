"""Custom `RequestValidationError` handler that respects route family.

FastAPI's default 422 response is JSON for every endpoint. That's correct
for the `/poems`, `/evaluation`, `/system`, `/health`, `/detect` API
routes — clients expect machine-readable errors. But the same default
hits browser-style POST routes (`/generate`, `/validate-web`, `/detect`,
`/evaluate`) when an HTML5-validated form is bypassed (curl, DevTools,
script). The user then sees raw JSON instead of the friendly Ukrainian
`error.html` page that the `DomainError` path already serves.

This handler keeps both contracts: HTML-form POSTs render `error.html`
with a translated message; everything else falls through to FastAPI's
JSON 422.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from src.handlers.web.routes._shared import templates

# Paths that render HTML on success → render HTML on validation failure too.
# Listed explicitly to avoid catching `/poems/detect` (JSON) just because
# `/detect` (HTML) shares a substring.
_HTML_POST_PATHS: frozenset[str] = frozenset({
    "/generate", "/validate-web", "/detect", "/evaluate",
})

# Pydantic error.type → Ukrainian phrase. Only the codes our routes can
# actually emit are listed; unknown codes fall back to the raw msg.
_TYPE_TRANSLATIONS: dict[str, str] = {
    "missing": "це поле є обов'язковим",
    "string_too_short": "значення не може бути порожнім",
    "string_too_long": "довжина має бути не більше за {max_length} символів",
    "less_than_equal": "значення має бути не більше за {le}",
    "greater_than_equal": "значення має бути не менше за {ge}",
    "less_than": "значення має бути менше за {lt}",
    "greater_than": "значення має бути більше за {gt}",
    "int_parsing": "значення має бути цілим числом",
    "float_parsing": "значення має бути числом",
    "value_error": "значення не пройшло перевірку",
}

# Field name (last token of `loc`) → human-readable Ukrainian label.
_FIELD_LABELS: dict[str, str] = {
    "theme": "Тема",
    "feet": "Кількість стоп",
    "foot_count": "Кількість стоп",
    "stanzas": "Кількість строф",
    "stanza_count": "Кількість строф",
    "iterations": "Макс. ітерацій виправлення",
    "max_iterations": "Макс. ітерацій виправлення",
    "poem_text": "Текст вірша",
    "meter": "Метр",
    "scheme": "Схема рими",
    "scenario_id": "Сценарій",
    "config_label": "Конфіг",
}


def _field_label(loc: tuple[Any, ...] | list[Any]) -> str:
    # Take the last meaningful loc element (skip "body"/"query"/etc.).
    for token in reversed(loc):
        if isinstance(token, str) and token not in {"body", "query", "path"}:
            return _FIELD_LABELS.get(token, token)
    return "поле"


def _translate(error: dict[str, Any]) -> str:
    err_type = str(error.get("type", ""))
    ctx = error.get("ctx") or {}
    template = _TYPE_TRANSLATIONS.get(err_type)
    if template is None:
        # Unknown error type — surface FastAPI's English msg as-is so the
        # user still sees something specific instead of a blank fallback.
        return str(error.get("msg", "помилка валідації"))
    try:
        return template.format(**ctx)
    except (KeyError, IndexError):
        return template


def install_validation_handler(app: FastAPI) -> None:
    """Register the route-aware `RequestValidationError` handler."""

    @app.exception_handler(RequestValidationError)
    def _on_validation_error(
        request: Request, exc: RequestValidationError,
    ) -> Response:
        if request.url.path in _HTML_POST_PATHS:
            items = [
                {
                    "field": _field_label(e.get("loc", [])),
                    "message": _translate(e),
                }
                for e in exc.errors()
            ]
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={
                    "error": "Введені дані не пройшли перевірку.",
                    "validation_errors": items,
                },
                status_code=422,
            )
        # Everything else: fall through to FastAPI's standard JSON shape.
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors())},
        )
