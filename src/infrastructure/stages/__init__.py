"""Pipeline stages — IPipelineStage implementations for the evaluation pipeline.

Each stage is a small class that reads/writes PipelineState and records
exactly one StageRecord (success or error). Adding a new stage is a
one-file change; ablation variants differ only in which stages they run.
"""
from src.infrastructure.stages.feedback_stage import FeedbackLoopStage
from src.infrastructure.stages.final_metrics_stage import FinalMetricsStage
from src.infrastructure.stages.generation_stage import GenerationStage
from src.infrastructure.stages.metric_examples_stage import MetricExamplesStage
from src.infrastructure.stages.prompt_stage import PromptStage
from src.infrastructure.stages.retrieval_stage import RetrievalStage
from src.infrastructure.stages.stage_record_builder import DefaultStageRecordBuilder
from src.infrastructure.stages.validation_stage import ValidationStage

__all__ = [
    "DefaultStageRecordBuilder",
    "FeedbackLoopStage",
    "FinalMetricsStage",
    "GenerationStage",
    "MetricExamplesStage",
    "PromptStage",
    "RetrievalStage",
    "ValidationStage",
]
