"""Unit tests for PreloadResourcesRunner."""
from __future__ import annotations

from unittest.mock import MagicMock

from src.domain.ports import ILogger, IStressDictionary
from src.infrastructure.logging import NullLogger
from src.runners.preload_resources_runner import (
    PreloadResourcesRunner,
    PreloadResourcesRunnerConfig,
)


class TestPreloadResourcesRunner:
    def test_run_returns_zero_on_success(self) -> None:
        logger = NullLogger()
        stress_dict = MagicMock(spec=IStressDictionary)
        stress_dict.get_stress_index.return_value = 1
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(include_stanza=False, include_labse=False),
            logger=logger,
            stress_dictionary=stress_dict,
        )
        assert runner.run() == 0

    def test_stanza_preload_skipped_when_disabled(self) -> None:
        logger = MagicMock(spec=ILogger)
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(include_stanza=False, include_labse=False),
            logger=logger,
        )
        runner.run()
        # Should only log "All resources ready", not stanza/labse messages
        calls = [call.args[0] for call in logger.info.call_args_list]
        assert "All resources ready" in calls
        assert "Downloading Stanza UA model" not in calls

    def test_labse_preload_skipped_when_disabled(self) -> None:
        logger = MagicMock(spec=ILogger)
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(include_stanza=False, include_labse=False),
            logger=logger,
        )
        runner.run()
        calls = [call.args[0] for call in logger.info.call_args_list]
        assert "Downloading LaBSE model" not in calls

    def test_stress_dict_injected_is_used(self) -> None:
        logger = MagicMock(spec=ILogger)
        logger.info = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        stress_dict = MagicMock(spec=IStressDictionary)
        stress_dict.get_stress_index.return_value = 2
        runner = PreloadResourcesRunner(
            config=PreloadResourcesRunnerConfig(include_stanza=True, include_labse=False),
            logger=logger,
            stress_dictionary=stress_dict,
        )
        # Mock stanza model as already cached
        runner._stanza_model_ready = lambda: True  # type: ignore[method-assign]
        runner.run()
        stress_dict.get_stress_index.assert_called_once_with("весна")
