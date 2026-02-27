from __future__ import annotations

from dataclasses import dataclass

from src.generation.llm import LLMClient, MockLLMClient, llm_from_env, merge_regenerated_poem
from src.meter.stress import StressDict
from src.meter.validator import check_meter_poem, meter_feedback
from src.retrieval.corpus import CorpusPoem, corpus_from_env
from src.retrieval.retriever import SemanticRetriever, build_rag_prompt
from src.rhyme.validator import check_rhyme, rhyme_feedback
from src.utils.text import split_nonempty_lines


@dataclass(frozen=True)
class PipelineReport:
    meter_ok: bool
    rhyme_ok: bool
    meter_accuracy: float
    rhyme_accuracy: float
    feedback: list[str]
    iterations: int


def check_poem(poem_text: str, meter: str, foot_count: int, rhyme_scheme: str, stress_dict: StressDict) -> PipelineReport:
    meter_results = check_meter_poem(poem_text, meter=meter, foot_count=foot_count, stress_dict=stress_dict)
    rhyme_results = check_rhyme(poem_text, scheme=rhyme_scheme, stress_dict=stress_dict)

    feedback: list[str] = []
    for i, res in enumerate(meter_results):
        if not res.ok:
            feedback.append(meter_feedback(i, meter, res))

    for pair in rhyme_results.pairs:
        if not pair.rhyme_ok:
            feedback.append(rhyme_feedback(pair, rhyme_scheme))

    meter_ok = all(r.ok for r in meter_results) if meter_results else True
    rhyme_ok = rhyme_results.is_valid

    meter_accuracy = (sum(1 for r in meter_results if r.ok) / len(meter_results)) if meter_results else 1.0
    rhyme_accuracy = (sum(1 for p in rhyme_results.pairs if p.rhyme_ok) / len(rhyme_results.pairs)) if rhyme_results.pairs else 1.0

    return PipelineReport(
        meter_ok=meter_ok,
        rhyme_ok=rhyme_ok,
        meter_accuracy=meter_accuracy,
        rhyme_accuracy=rhyme_accuracy,
        feedback=feedback,
        iterations=0,
    )


def run_full_pipeline(
    theme: str,
    meter: str,
    rhyme_scheme: str,
    foot_count: int,
    stanza_count: int = 1,
    lines_per_stanza: int = 4,
    corpus: list[CorpusPoem] | None = None,
    retriever: SemanticRetriever | None = None,
    llm: LLMClient | None = None,
    stress_dict: StressDict | None = None,
    max_iterations: int = 1,
    top_k: int = 5,
) -> tuple[str, PipelineReport]:
    corpus = corpus or corpus_from_env()
    retriever = retriever or SemanticRetriever()
    llm = llm or llm_from_env() or MockLLMClient()

    stress_dict = stress_dict or StressDict(on_ambiguity="first")

    retrieved = retriever.retrieve(theme, corpus, top_k=top_k)
    prompt = build_rag_prompt(
        theme=theme,
        meter=meter,
        rhyme_scheme=rhyme_scheme,
        retrieved=retrieved,
        stanza_count=stanza_count,
        lines_per_stanza=lines_per_stanza,
    )

    poem = llm.generate(prompt).text

    report = check_poem(poem, meter=meter, foot_count=foot_count, rhyme_scheme=rhyme_scheme, stress_dict=stress_dict)
    for it in range(max_iterations):
        if report.meter_ok and report.rhyme_ok:
            report = PipelineReport(
                meter_ok=report.meter_ok,
                rhyme_ok=report.rhyme_ok,
                meter_accuracy=report.meter_accuracy,
                rhyme_accuracy=report.rhyme_accuracy,
                feedback=report.feedback,
                iterations=it,
            )
            break
        prev_poem = poem
        poem = llm.regenerate_lines(poem, report.feedback).text
        poem = merge_regenerated_poem(prev_poem, poem, report.feedback)
        report = check_poem(poem, meter=meter, foot_count=foot_count, rhyme_scheme=rhyme_scheme, stress_dict=stress_dict)
    else:
        report = PipelineReport(
            meter_ok=report.meter_ok,
            rhyme_ok=report.rhyme_ok,
            meter_accuracy=report.meter_accuracy,
            rhyme_accuracy=report.rhyme_accuracy,
            feedback=report.feedback,
            iterations=max_iterations,
        )

    _ = split_nonempty_lines(poem)
    return poem, report
