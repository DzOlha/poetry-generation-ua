"""Web UI router — aggregates sub-routers for each use-case domain.

Split into focused route modules under ``routes/``:

  - ``routes/index.py``            — landing page
  - ``routes/generation.py``        — poem generation and validation
  - ``routes/evaluation.py``        — evaluation scenario management
  - ``routes/detection.py``         — meter/rhyme auto-detection
  - ``routes/ablation_report.py``   — pre-computed ablation-analysis dashboard
"""
from __future__ import annotations

from fastapi import APIRouter

from src.handlers.web.routes.ablation_report import router as ablation_report_router
from src.handlers.web.routes.detection import router as detection_router
from src.handlers.web.routes.evaluation import router as evaluation_router
from src.handlers.web.routes.generation import router as generation_router
from src.handlers.web.routes.index import router as index_router

router = APIRouter(tags=["web"])
router.include_router(index_router)
router.include_router(generation_router)
router.include_router(evaluation_router)
router.include_router(detection_router)
router.include_router(ablation_report_router)
