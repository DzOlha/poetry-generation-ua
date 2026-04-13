"""Text processing adapters."""
from src.infrastructure.text.levenshtein_similarity import LevenshteinSimilarity
from src.infrastructure.text.ukrainian_text_processor import UkrainianTextProcessor

__all__ = ["LevenshteinSimilarity", "UkrainianTextProcessor"]
