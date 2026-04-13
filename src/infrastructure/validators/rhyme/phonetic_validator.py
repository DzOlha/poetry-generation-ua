"""Phonetic rhyme validator for Ukrainian poetry.

Validates rhyme pairs by delegating phonetic analysis to `IRhymePairAnalyzer`
and line shaping to `ILineSplitter` / `ITokenizer`. The validator itself only
orchestrates the scheme → pair loop and aggregates the result; it no longer
owns stress resolution, transcription, or string similarity.
"""
from __future__ import annotations

from src.domain.feedback import PairFeedback
from src.domain.models import RhymePairResult, RhymeResult, RhymeScheme
from src.domain.ports import (
    ILineSplitter,
    IRhymePairAnalyzer,
    IRhymeSchemeExtractor,
    IRhymeValidator,
    ITokenizer,
)
from src.domain.value_objects import ClausulaType, RhymePrecision


class PhoneticRhymeValidator(IRhymeValidator):
    """Validates rhyme by comparing phonetic endings of line-final words."""

    def __init__(
        self,
        line_splitter: ILineSplitter,
        tokenizer: ITokenizer,
        scheme_extractor: IRhymeSchemeExtractor,
        pair_analyzer: IRhymePairAnalyzer,
        threshold: float = 0.7,
    ) -> None:
        self._lines = line_splitter
        self._tokenizer = tokenizer
        self._scheme = scheme_extractor
        self._pairs_analyzer = pair_analyzer
        self._threshold = threshold

    def validate(self, poem_text: str, scheme: RhymeScheme) -> RhymeResult:
        lines = self._lines.split_lines(poem_text)
        pairs = self._scheme.extract_pairs(scheme.pattern, len(lines))

        pair_results: list[RhymePairResult] = []
        for a_idx, b_idx in pairs:
            w_a = self._last_word(lines[a_idx])
            w_b = self._last_word(lines[b_idx])
            if not w_a or not w_b:
                pair_results.append(RhymePairResult(
                    line_a_idx=a_idx,
                    line_b_idx=b_idx,
                    word_a=w_a,
                    word_b=w_b,
                    rhyme_part_a="",
                    rhyme_part_b="",
                    score=0.0,
                    ok=False,
                    clausula_a=ClausulaType.UNKNOWN,
                    clausula_b=ClausulaType.UNKNOWN,
                    precision=RhymePrecision.NONE,
                ))
                continue
            analysis = self._pairs_analyzer.analyze(w_a, w_b)
            pair_results.append(RhymePairResult(
                line_a_idx=a_idx,
                line_b_idx=b_idx,
                word_a=w_a,
                word_b=w_b,
                rhyme_part_a=analysis.rhyme_part_a,
                rhyme_part_b=analysis.rhyme_part_b,
                score=analysis.score,
                ok=analysis.score >= self._threshold,
                clausula_a=analysis.clausula_a,
                clausula_b=analysis.clausula_b,
                precision=analysis.precision,
            ))

        ok = all(p.ok for p in pair_results)
        accuracy = (
            sum(1 for p in pair_results if p.ok) / len(pair_results)
            if pair_results else 1.0
        )
        feedback: tuple[PairFeedback, ...] = tuple(
            PairFeedback(
                line_a_idx=p.line_a_idx,
                line_b_idx=p.line_b_idx,
                scheme_pattern=scheme.pattern,
                word_a=p.word_a,
                word_b=p.word_b,
                rhyme_part_a=p.rhyme_part_a,
                rhyme_part_b=p.rhyme_part_b,
                score=p.score,
                clausula_a=p.clausula_a,
                clausula_b=p.clausula_b,
                precision=p.precision,
            )
            for p in pair_results if not p.ok
        )
        return RhymeResult(
            ok=ok,
            accuracy=accuracy,
            feedback=feedback,
            pair_results=tuple(pair_results),
        )

    def _last_word(self, line: str) -> str:
        words = self._tokenizer.extract_words(line)
        return words[-1] if words else ""
