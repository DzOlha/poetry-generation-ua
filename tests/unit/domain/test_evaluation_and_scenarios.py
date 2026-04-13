"""Domain-layer branch coverage audit — fills gaps in existing domain tests.

The original test files cover MeterSpec, RhymeScheme, Poem, ValidationResult,
enums and error hierarchy. This module adds explicit coverage for:

  - `AblationConfig.is_enabled`
  - `EvaluationSummary.to_dict` rounding + shape
  - `StageRecord.to_dict` optional-field inclusion
  - `IterationRecord.to_dict`
  - `PipelineTrace.to_dict` with and without error
  - `StageTimer` context manager measurement
  - `ScenarioRegistry` lookup + duplicate rejection
  - `GenerationResult.poem_object` lazy conversion
  - `ValidationRequest` bundling
"""
from __future__ import annotations

import time

import pytest

from src.domain.errors import UnsupportedConfigError
from src.domain.evaluation import (
    AblationConfig,
    EvaluationSummary,
    IterationRecord,
    PipelineTrace,
    StageRecord,
)
from src.domain.models import (
    GenerationResult,
    MeterResult,
    MeterSpec,
    PoemStructure,
    RhymeResult,
    RhymeScheme,
    ValidationRequest,
    ValidationResult,
)
from src.domain.scenarios import EvaluationScenario, ScenarioRegistry
from src.domain.values import ScenarioCategory
from src.infrastructure.serialization import (
    evaluation_summary_to_dict,
    iteration_record_to_dict,
    pipeline_trace_to_dict,
    stage_record_to_dict,
)
from src.infrastructure.tracing.stage_timer import StageTimer

# ---------------------------------------------------------------------------
# AblationConfig
# ---------------------------------------------------------------------------

class TestAblationConfig:
    def test_is_enabled_for_stage_in_set(self) -> None:
        cfg = AblationConfig(
            label="X", enabled_stages=frozenset({"retrieval", "validation"}),
        )
        assert cfg.is_enabled("retrieval") is True
        assert cfg.is_enabled("validation") is True

    def test_is_enabled_false_for_unlisted_stage(self) -> None:
        cfg = AblationConfig(label="X", enabled_stages=frozenset({"retrieval"}))
        assert cfg.is_enabled("feedback_loop") is False

    def test_frozen_is_hashable(self) -> None:
        cfg = AblationConfig(label="X", enabled_stages=frozenset({"a"}))
        assert hash(cfg) is not None


# ---------------------------------------------------------------------------
# EvaluationSummary
# ---------------------------------------------------------------------------

class TestEvaluationSummary:
    def test_to_dict_rounds_floats_to_4_places(self) -> None:
        s = EvaluationSummary(
            scenario_id="N01",
            scenario_name="test",
            config_label="A",
            meter="ямб",
            foot_count=4,
            rhyme_scheme="ABAB",
            meter_accuracy=0.123456789,
            rhyme_accuracy=0.987654321,
            num_iterations=2,
            num_lines=4,
            duration_sec=1.23456789,
        )
        d = evaluation_summary_to_dict(s)
        assert d["meter_accuracy"] == 0.1235
        assert d["rhyme_accuracy"] == 0.9877
        assert d["duration_sec"] == 1.2346
        assert d["iterations"] == 2
        assert d["error"] is None

    def test_to_dict_includes_error(self) -> None:
        s = EvaluationSummary(
            scenario_id="N01", scenario_name="t", config_label="A",
            meter="ямб", foot_count=4, rhyme_scheme="ABAB",
            meter_accuracy=0.0, rhyme_accuracy=0.0,
            num_iterations=0, num_lines=0, duration_sec=0.0,
            error="boom",
        )
        assert evaluation_summary_to_dict(s)["error"] == "boom"


# ---------------------------------------------------------------------------
# StageRecord
# ---------------------------------------------------------------------------

class TestStageRecord:
    def test_to_dict_minimal(self) -> None:
        rec = StageRecord(name="x", input_summary="in", output_summary="out")
        d = stage_record_to_dict(rec)
        assert d["stage"] == "x"
        assert d["input"] == "in"
        assert d["output"] == "out"
        assert "input_data" not in d  # None -> omitted
        assert "output_data" not in d
        assert "error" not in d

    def test_to_dict_with_data(self) -> None:
        rec = StageRecord(
            name="x", input_data={"a": 1}, output_data={"b": 2}, error="e",
        )
        d = stage_record_to_dict(rec)
        assert d["input_data"] == {"a": 1}
        assert d["output_data"] == {"b": 2}
        assert d["error"] == "e"


# ---------------------------------------------------------------------------
# IterationRecord
# ---------------------------------------------------------------------------

class TestIterationRecord:
    def test_to_dict_rounds_accuracies(self) -> None:
        it = IterationRecord(
            iteration=1,
            poem_text="poem",
            meter_accuracy=0.3333333,
            rhyme_accuracy=0.6666666,
            feedback=("msg",),
            duration_sec=1.111111,
        )
        d = iteration_record_to_dict(it)
        assert d["meter_accuracy"] == 0.3333
        assert d["rhyme_accuracy"] == 0.6667
        assert d["duration_sec"] == 1.1111
        assert d["feedback"] == ("msg",)


# ---------------------------------------------------------------------------
# PipelineTrace
# ---------------------------------------------------------------------------

class TestPipelineTrace:
    def test_to_dict_without_error_omits_key(self) -> None:
        t = PipelineTrace(
            scenario_id="N01", config_label="A",
            final_poem="...", total_duration_sec=1.0,
        )
        d = pipeline_trace_to_dict(t)
        assert "error" not in d
        assert d["scenario_id"] == "N01"
        assert d["final_poem"] == "..."
        assert d["total_duration_sec"] == 1.0

    def test_to_dict_with_error_includes_key(self) -> None:
        t = PipelineTrace(scenario_id="N01", config_label="A", error="boom")
        assert pipeline_trace_to_dict(t)["error"] == "boom"

    def test_final_metrics_floats_are_rounded(self) -> None:
        t = PipelineTrace(
            scenario_id="N01", config_label="A",
            final_metrics={"meter_accuracy": 0.123456, "count": 5},
        )
        d = pipeline_trace_to_dict(t)
        assert d["final_metrics"]["meter_accuracy"] == 0.1235
        assert d["final_metrics"]["count"] == 5  # ints unchanged


# ---------------------------------------------------------------------------
# StageTimer
# ---------------------------------------------------------------------------

class TestStageTimer:
    def test_measures_elapsed_seconds(self) -> None:
        with StageTimer() as timer:
            time.sleep(0.01)
        assert timer.elapsed >= 0.01
        # Sanity ceiling — test infrastructure should never stall this long.
        assert timer.elapsed < 1.0


# ---------------------------------------------------------------------------
# ScenarioRegistry
# ---------------------------------------------------------------------------

class TestScenarioRegistry:
    def _scen(self, sid: str, cat: ScenarioCategory = ScenarioCategory.NORMAL) -> EvaluationScenario:
        return EvaluationScenario(
            id=sid, name=f"n{sid}", category=cat, theme="тест",
            meter="ямб", foot_count=4, rhyme_scheme="ABAB",
        )

    def test_by_id_returns_known_scenario(self) -> None:
        reg = ScenarioRegistry([self._scen("X01"), self._scen("X02")])
        scenario = reg.by_id("X01")
        assert scenario is not None
        assert scenario.id == "X01"

    def test_by_id_returns_none_for_unknown(self) -> None:
        reg = ScenarioRegistry([self._scen("X01")])
        assert reg.by_id("ZZZ") is None

    def test_by_category_filters(self) -> None:
        reg = ScenarioRegistry(
            [
                self._scen("N01", ScenarioCategory.NORMAL),
                self._scen("E01", ScenarioCategory.EDGE),
                self._scen("N02", ScenarioCategory.NORMAL),
            ]
        )
        normal = reg.by_category(ScenarioCategory.NORMAL)
        assert [s.id for s in normal] == ["N01", "N02"]

    def test_duplicate_ids_rejected_at_construction(self) -> None:
        with pytest.raises(UnsupportedConfigError):
            ScenarioRegistry([self._scen("X01"), self._scen("X01")])

    def test_len_and_iter(self) -> None:
        scenarios = [self._scen(f"X{i:02}") for i in range(3)]
        reg = ScenarioRegistry(scenarios)
        assert len(reg) == 3
        assert list(reg) == scenarios


# ---------------------------------------------------------------------------
# EvaluationScenario.build_request
# ---------------------------------------------------------------------------

class TestScenarioBuildRequest:
    def test_uses_defaults_when_no_override(self) -> None:
        scen = EvaluationScenario(
            id="N01", name="t", category=ScenarioCategory.NORMAL,
            theme="тема", meter="ямб", foot_count=4, rhyme_scheme="ABAB",
            stanza_count=2, lines_per_stanza=4,
        )
        req = scen.build_request()
        assert req.theme == "тема"
        assert req.meter == MeterSpec(name="ямб", foot_count=4)
        assert req.rhyme == RhymeScheme(pattern="ABAB")
        assert req.structure == PoemStructure(2, 4)

    def test_accepts_stanza_override(self) -> None:
        scen = EvaluationScenario(
            id="N01", name="t", category=ScenarioCategory.NORMAL,
            theme="тема", meter="ямб", foot_count=4, rhyme_scheme="ABAB",
        )
        req = scen.build_request(stanza_count=3, lines_per_stanza=6)
        assert req.structure.stanza_count == 3
        assert req.structure.lines_per_stanza == 6

    def test_raises_for_unsupported_meter(self) -> None:
        scen = EvaluationScenario(
            id="C04", name="bad", category=ScenarioCategory.CORNER,
            theme="x", meter="гекзаметр", foot_count=4, rhyme_scheme="ABAB",
        )
        with pytest.raises(UnsupportedConfigError):
            scen.build_request()

    def test_total_lines_property(self) -> None:
        scen = EvaluationScenario(
            id="N01", name="t", category=ScenarioCategory.NORMAL,
            theme="x", meter="ямб", foot_count=4, rhyme_scheme="ABAB",
            stanza_count=3, lines_per_stanza=4,
        )
        assert scen.total_lines == 12


# ---------------------------------------------------------------------------
# GenerationResult.poem_object
# ---------------------------------------------------------------------------

class TestGenerationResultPoemObject:
    def test_lazy_conversion_to_poem(self) -> None:
        validation = ValidationResult(
            meter=MeterResult(ok=True, accuracy=1.0),
            rhyme=RhymeResult(ok=True, accuracy=1.0),
        )
        result = GenerationResult(poem="рядок 1\nрядок 2\n", validation=validation)
        poem = result.poem_object
        assert poem.line_count == 2
        assert poem.lines == ("рядок 1", "рядок 2")


# ---------------------------------------------------------------------------
# ValidationRequest
# ---------------------------------------------------------------------------

class TestValidationRequest:
    def test_bundles_text_and_specs(self) -> None:
        req = ValidationRequest(
            poem_text="рядок 1\nрядок 2",
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        )
        assert req.poem_text.startswith("рядок")
        assert req.meter.name == "ямб"
        assert req.rhyme.pattern == "ABAB"

    def test_frozen(self) -> None:
        req = ValidationRequest(
            poem_text="x",
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        )
        with pytest.raises((AttributeError, TypeError)):
            req.poem_text = "y"  # type: ignore[misc]
