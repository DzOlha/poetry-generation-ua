"""Runner classes — encapsulate top-level program execution flows.

Each runner implements `IRunner`: a single `run()` returning a UNIX exit code.
Scripts and CLI entry points stay thin — they parse arguments, construct the
runner, and call `run()`. All orchestration logic is testable and replaceable.
"""
from src.runners.build_corpus_runner import BuildCorpusRunner, BuildCorpusRunnerConfig
from src.runners.build_embeddings_runner import (
    BuildEmbeddingsRunner,
    BuildEmbeddingsRunnerConfig,
)
from src.runners.evaluation_runner import EvaluationRunner, EvaluationRunnerConfig
from src.runners.generate_runner import GenerateRunner, GenerateRunnerConfig
from src.runners.preload_resources_runner import (
    PreloadResourcesRunner,
    PreloadResourcesRunnerConfig,
)
from src.runners.validate_runner import ValidateRunner, ValidateRunnerConfig

__all__ = [
    "BuildCorpusRunner",
    "BuildCorpusRunnerConfig",
    "BuildEmbeddingsRunner",
    "BuildEmbeddingsRunnerConfig",
    "EvaluationRunner",
    "EvaluationRunnerConfig",
    "GenerateRunner",
    "GenerateRunnerConfig",
    "PreloadResourcesRunner",
    "PreloadResourcesRunnerConfig",
    "ValidateRunner",
    "ValidateRunnerConfig",
]
