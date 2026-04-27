"""Unit tests for ``PreloadResourcesRunner``.

The original tests asserted on ``MagicMock(spec=...)`` call counts —
"did I call this internal method with that argument?" — which couples
the test to the runner's implementation rather than its observable
behaviour. The audit asked for hand-written stubs and outcome-focused
assertions, so this version uses small ``ILogger`` / ``IStressDictionary``
stubs and verifies the visible side-effects (exit code, recorded log
lines, recorded queries).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.ports import ILogger, IStressDictionary
from src.runners.preload_resources_runner import (
    PreloadResourcesRunner,
    PreloadResourcesRunnerConfig,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

@dataclass
class _RecordingLogger(ILogger):
    """Captures every structured log line — assertions look at the record list."""

    records: list[tuple[str, str, dict[str, object]]] = field(default_factory=list)

    def info(self, message: str, **fields: object) -> None:
        self.records.append(("info", message, dict(fields)))

    def warning(self, message: str, **fields: object) -> None:
        self.records.append(("warning", message, dict(fields)))

    def error(self, message: str, **fields: object) -> None:
        self.records.append(("error", message, dict(fields)))

    def messages(self) -> list[str]:
        return [m for _, m, _ in self.records]


@dataclass
class _RecordingStressDictionary(IStressDictionary):
    """Hand-written stub — records every query and returns a fixed index."""

    return_value: int = 1
    queries: list[str] = field(default_factory=list)

    def get_stress_index(self, word: str) -> int | None:
        self.queries.append(word)
        return self.return_value


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------

class TestPreloadResourcesRunner:
    def test_run_returns_zero_on_success(self) -> None:
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(
                include_stanza=False, include_labse=False,
            ),
            logger=_RecordingLogger(),
            stress_dictionary=_RecordingStressDictionary(),
        )
        assert runner.run() == 0

    def test_emits_all_resources_ready_message(self) -> None:
        logger = _RecordingLogger()
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(
                include_stanza=False, include_labse=False,
            ),
            logger=logger,
        )
        runner.run()
        assert "All resources ready" in logger.messages()

    def test_stanza_phase_skipped_when_disabled(self) -> None:
        logger = _RecordingLogger()
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(
                include_stanza=False, include_labse=False,
            ),
            logger=logger,
        )
        runner.run()
        # No stanza-phase log lines appeared at all.
        assert "Downloading Stanza UA model" not in logger.messages()
        assert "Stanza model cached" not in logger.messages()

    def test_labse_phase_skipped_when_disabled(self) -> None:
        logger = _RecordingLogger()
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(
                include_stanza=False, include_labse=False,
            ),
            logger=logger,
        )
        runner.run()
        assert "Downloading LaBSE model" not in logger.messages()
        assert "LaBSE model cached" not in logger.messages()

    def test_injected_stress_dictionary_is_queried_when_stanza_phase_runs(self) -> None:
        logger = _RecordingLogger()
        stress_dict = _RecordingStressDictionary(return_value=2)
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(
                include_stanza=True, include_labse=False,
            ),
            logger=logger,
            stress_dictionary=stress_dict,
        )
        # Pretend the Stanza model is already cached so we skip the network call.
        runner._stanza_model_ready = lambda: True  # type: ignore[method-assign]
        runner.run()

        # Observable side-effects: the stress dictionary was queried with the
        # expected probe word, and the runner logged the OK record carrying
        # the index it received from the dictionary.
        assert stress_dict.queries == ["весна"]
        ok_records = [
            (msg, fields)
            for level, msg, fields in logger.records
            if level == "info" and msg == "Stress dictionary OK"
        ]
        assert ok_records == [("Stress dictionary OK", {"stress_index": 2})]

    def test_warns_when_no_stress_dictionary_injected(self) -> None:
        logger = _RecordingLogger()
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(
                include_stanza=True, include_labse=False,
            ),
            logger=logger,
            stress_dictionary=None,
        )
        runner._stanza_model_ready = lambda: True  # type: ignore[method-assign]
        runner.run()

        warnings = [msg for level, msg, _ in logger.records if level == "warning"]
        assert any("No stress dictionary injected" in m for m in warnings)
