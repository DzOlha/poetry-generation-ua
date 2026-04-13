"""Meter/rhyme detection API route."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.handlers.api.dependencies import get_detection_service
from src.handlers.api.schemas import DetectionRequestSchema, DetectionResultSchema
from src.services.detection_service import DetectionService

router = APIRouter(prefix="/poems", tags=["poems"])


@router.post("/detect", response_model=DetectionResultSchema)
def detect_poem(
    request: DetectionRequestSchema,
    service: DetectionService = Depends(get_detection_service),
) -> DetectionResultSchema:
    """Auto-detect meter and rhyme scheme of a poem."""
    result = service.detect(request.poem_text, sample_lines=request.sample_lines)
    return DetectionResultSchema.from_domain(result)
