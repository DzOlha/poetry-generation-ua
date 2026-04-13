"""Pipeline orchestration infrastructure.

Holds the concrete SequentialPipeline and DefaultStageSkipPolicy that wire
stages together, and the DefaultStageFactory that builds the stage list from
a stage catalog. The mutable `PipelineState` aggregate lives in the domain
layer (`src.domain.pipeline_context`) because every field is a domain
concept — the audit flagged it as a layering leak when it lived here.
"""
from src.infrastructure.pipeline.poem_generation_pipeline import (
    DefaultPoemGenerationPipeline,
)
from src.infrastructure.pipeline.sequential_pipeline import SequentialPipeline
from src.infrastructure.pipeline.skip_policy import DefaultStageSkipPolicy
from src.infrastructure.pipeline.stage_factory import (
    DefaultStageFactory,
    StageRegistration,
)

__all__ = [
    "DefaultPoemGenerationPipeline",
    "DefaultStageFactory",
    "DefaultStageSkipPolicy",
    "SequentialPipeline",
    "StageRegistration",
]
