"""Logging adapters — ILogger implementations."""
from src.infrastructure.logging.stdout_logger import CollectingLogger, NullLogger, StdOutLogger

__all__ = ["StdOutLogger", "CollectingLogger", "NullLogger"]
