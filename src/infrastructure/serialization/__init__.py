"""Serialization adapters — convert domain objects to dicts/JSON."""
from src.infrastructure.serialization.evaluation_serializer import (
    evaluation_summary_to_dict,
    iteration_record_to_dict,
    pipeline_trace_to_dict,
    stage_record_to_dict,
)

__all__ = [
    "evaluation_summary_to_dict",
    "stage_record_to_dict",
    "iteration_record_to_dict",
    "pipeline_trace_to_dict",
]
