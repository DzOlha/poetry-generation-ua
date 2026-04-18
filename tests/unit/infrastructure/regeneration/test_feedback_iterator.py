"""Tests for ValidatingFeedbackIterator — the regenerate → merge → re-validate loop."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.evaluation import ABLATION_CONFIGS
from src.domain.feedback import LineFeedback, PairFeedback
from src.domain.models import (
    GenerationRequest,
    LineMeterResult,
    MeterResult,
    MeterSpec,
    PoemStructure,
    RhymeResult,
    RhymeScheme,
)
from src.domain.pipeline_context import PipelineState
from src.domain.ports import (
    IFeedbackCycle,
    IIterationStopPolicy,
    ILLMProvider,
    IRegenerationMerger,
)
from src.domain.ports.pipeline import FeedbackCycleOutcome
from src.infrastructure.logging import NullLogger
from src.infrastructure.regeneration.feedback_iterator import ValidatingFeedbackIterator
from src.infrastructure.tracing import PipelineTracer

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

@dataclass
class _ScriptedLLM(ILLMProvider):
    """Returns scripted outputs; records inputs for assertions."""

    regen_responses: list[str] = field(default_factory=list)
    generate_response: str = ""
    regen_calls: list[tuple[str, list[str]]] = field(default_factory=list)
    generate_calls: list[str] = field(default_factory=list)

    def generate(self, prompt: str) -> str:
        self.generate_calls.append(prompt)
        return self.generate_response

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        self.regen_calls.append((poem, list(feedback)))
        if self.regen_responses:
            return self.regen_responses.pop(0)
        return poem


@dataclass
class _RecordingMerger(IRegenerationMerger):
    """Remembers every merge call; by default returns regenerated as-is."""

    calls: list[tuple[str, str]] = field(default_factory=list)
    force_return: str | None = None

    def merge(self, original, regenerated, meter_feedback, rhyme_feedback):
        self.calls.append((original, regenerated))
        return self.force_return if self.force_return is not None else regenerated


@dataclass
class _FakeCycle(IFeedbackCycle):
    outcomes: list[FeedbackCycleOutcome] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def run(self, poem_text, meter, rhyme):
        self.calls.append(poem_text)
        if self.outcomes:
            return self.outcomes.pop(0)
        # default: clean result
        return FeedbackCycleOutcome(
            meter=_meter_result(1.0), rhyme=_rhyme_result(1.0),
            feedback_messages=(),
        )


@dataclass
class _NeverStop(IIterationStopPolicy):
    def should_stop(self, iteration, max_iterations, meter_result,
                    rhyme_result, history):
        return iteration > max_iterations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _meter_result(acc: float, violations: tuple[LineFeedback, ...] = ()) -> MeterResult:
    line = LineMeterResult(
        ok=acc >= 1.0,
        expected_stresses=(2, 4, 6, 8),
        actual_stresses=(2, 4, 6, 8),
        error_positions=(),
        total_syllables=8,
    )
    return MeterResult(
        ok=acc >= 1.0, accuracy=acc,
        feedback=violations, line_results=(line,),
    )


def _rhyme_result(acc: float, pairs: tuple[PairFeedback, ...] = ()) -> RhymeResult:
    return RhymeResult(ok=acc >= 1.0, accuracy=acc, feedback=pairs)


def _line_fb(idx: int) -> LineFeedback:
    return LineFeedback(
        line_idx=idx, meter_name="ямб", foot_count=4,
        expected_stresses=(2, 4, 6, 8), actual_stresses=(1,),
        total_syllables=8,
    )


def _make_state(
    *, poem: str, max_iterations: int = 2, expected_lines: int = 4,
    meter_acc: float = 0.5, rhyme_acc: float = 1.0,
    meter_feedback: tuple[LineFeedback, ...] = (),
) -> PipelineState:
    config = next(c for c in ABLATION_CONFIGS if c.label == "B")
    tracer = PipelineTracer(scenario_id="N01", config_label="B")
    request = GenerationRequest(
        theme="x",
        meter=MeterSpec(name="ямб", foot_count=4),
        rhyme=RhymeScheme(pattern="ABAB"),
        structure=PoemStructure(stanza_count=1, lines_per_stanza=expected_lines),
        max_iterations=max_iterations,
        top_k=3,
        metric_examples_top_k=2,
    )
    state = PipelineState(request=request, config=config, tracer=tracer)
    state.poem = poem
    state.prompt = "some prompt"
    state.last_meter_result = _meter_result(meter_acc, meter_feedback)
    state.last_rhyme_result = _rhyme_result(rhyme_acc)
    return state


def _make_iterator(
    llm: _ScriptedLLM,
    merger: _RecordingMerger | None = None,
    cycle: _FakeCycle | None = None,
) -> ValidatingFeedbackIterator:
    return ValidatingFeedbackIterator(
        llm=llm,
        feedback_cycle=cycle or _FakeCycle(),
        regeneration_merger=merger or _RecordingMerger(),
        stop_policy=_NeverStop(),
        logger=NullLogger(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSanitizationOfRegeneratedOutput:
    def test_scansion_lines_stripped_before_merger(self):
        poem = "рядок номер один\nрядок номер два\nрядок номер три\nрядок номер чотири\n"
        llm = _ScriptedLLM(regen_responses=[
            "чистий перший рядок вірша\nІ-ДУТЬ у СЛАВ-ний БІЙ\n1 2 3 4\nчистий другий рядок вірша\n"
        ])
        merger = _RecordingMerger()
        state = _make_state(
            poem=poem, max_iterations=1,
            meter_acc=0.5, meter_feedback=(_line_fb(1),),
        )
        _make_iterator(llm, merger).iterate(state)

        # Merger should have been called with sanitized regenerated text only.
        assert merger.calls, "merger should be invoked"
        _, regenerated_seen = merger.calls[0]
        assert "І-ДУТЬ" not in regenerated_seen
        assert "1 2 3 4" not in regenerated_seen
        assert "чистий перший" in regenerated_seen
        assert "чистий другий" in regenerated_seen

    def test_all_scansion_keeps_previous_poem(self):
        # If every line of regen output is stripped, sanitized is empty and
        # the iterator must keep prev_poem rather than feed empty to merger.
        poem = "рядок номер один\nрядок номер два\nрядок номер три\nрядок номер чотири\n"
        llm = _ScriptedLLM(regen_responses=[
            "І-ДУТЬ у СЛАВ-ний БІЙ те-ПЕР но-ВІ пол-КИ.\n1 2 3 4 5 6\n"
        ])
        merger = _RecordingMerger(force_return="MERGER-WAS-CALLED")
        state = _make_state(
            poem=poem, max_iterations=1,
            meter_acc=0.5, meter_feedback=(_line_fb(1),),
        )
        _make_iterator(llm, merger).iterate(state)

        assert merger.calls == [], "merger must not run on empty sanitized output"
        # prev_poem preserved verbatim
        assert state.poem == poem


class TestFullRegenPathOnLineCountMismatch:
    def test_uses_generate_not_regenerate_when_line_count_mismatches(self):
        # state.poem has 2 lines but structure expects 4 → full regen path.
        poem = "перший рядок недобудованого вірша\nдругий рядок недобудованого вірша\n"
        llm = _ScriptedLLM(
            generate_response=(
                "Вулиці втомлено світяться знов,\n"
                "Темрява випила залишки мов.\n"
                "Натовпом сунуть чужі містяни,\n"
                "Холодом дихають сірі стіни.\n"
            ),
        )
        state = _make_state(
            poem=poem, expected_lines=4, max_iterations=1,
            meter_acc=0.5, meter_feedback=(_line_fb(0),),
        )
        _make_iterator(llm).iterate(state)

        assert len(llm.generate_calls) == 1
        assert llm.regen_calls == []
        assert "Вулиці втомлено" in state.poem
        assert "Холодом дихають" in state.poem

    def test_full_regen_also_sanitized(self):
        poem = "лише перший короткий рядок\nі другий короткий рядок\n"  # 2 != 4 → full regen
        raw = (
            "Вулиці втомлено світяться знов,\n"
            "Темрява випила залишки мов.\n"
            "І-ДУТЬ у СЛАВ-ний БІЙ те-ПЕР но-ВІ пол-КИ.\n"
            "Натовпом сунуть чужі містяни,\n"
            "Холодом дихають сірі стіни.\n"
        )
        llm = _ScriptedLLM(generate_response=raw)
        state = _make_state(
            poem=poem, expected_lines=4, max_iterations=1,
            meter_acc=0.5, meter_feedback=(_line_fb(0),),
        )
        _make_iterator(llm).iterate(state)
        assert "І-ДУТЬ" not in state.poem
        assert "Вулиці втомлено" in state.poem

    def test_full_regen_returns_only_cot_keeps_previous_poem(self):
        # Full-regen branch: LLM leaks only chain-of-thought / scansion, so
        # Poem.from_text sanitises the entire output to an empty string. The
        # iterator must NOT fall back to the raw LLM reply — that would
        # contaminate state.poem with garbage like "КОЖЕН проХОЖИЙ (Ko-zhen
        # pro-cho-zhyj — stress on CHO. / u u / u)". Keep prev_poem instead.
        poem = "лише\nдва\n"  # 2 != expected 4 → full regen
        raw = (
            "КОЖЕН проХОЖИЙ — неМОВ опеЧАТка. "
            "(Ko-zhen pro-cho-zhyj - stress on CHO. / u u / u)\n"
            "1 2 3 4 5 6 7 8 9\n"
            "Wait, let me think about this again.\n"
        )
        llm = _ScriptedLLM(generate_response=raw)
        state = _make_state(
            poem=poem, expected_lines=4, max_iterations=1,
            meter_acc=0.5, meter_feedback=(_line_fb(0),),
        )
        _make_iterator(llm).iterate(state)
        assert state.poem == poem
        assert "КОЖЕН" not in state.poem
        assert "Ko-zhen" not in state.poem
        assert "Wait" not in state.poem


class TestEarlyExit:
    def test_no_iterations_when_validation_was_skipped(self):
        state = _make_state(poem="x\ny\nz\nq\n")
        state.last_meter_result = None  # simulate skipped validation
        state.last_rhyme_result = None
        llm = _ScriptedLLM()
        _make_iterator(llm).iterate(state)
        assert llm.regen_calls == []
        assert llm.generate_calls == []
