"""Tests for MaxIterationsOrValidStopPolicy."""
from __future__ import annotations

from src.domain.models import MeterResult, RhymeResult
from src.infrastructure.regeneration import MaxIterationsOrValidStopPolicy

_PASS = MeterResult(ok=True, accuracy=1.0)
_PASS_RHYME = RhymeResult(ok=True, accuracy=1.0)
_FAIL = MeterResult(ok=False, accuracy=0.0)
_FAIL_RHYME = RhymeResult(ok=False, accuracy=0.0)


class TestMaxIterationsOrValidStopPolicy:
    def test_stops_when_max_exceeded(self):
        policy = MaxIterationsOrValidStopPolicy()
        assert policy.should_stop(4, 3, _FAIL, _FAIL_RHYME, ()) is True

    def test_stops_when_valid(self):
        policy = MaxIterationsOrValidStopPolicy()
        assert policy.should_stop(1, 5, _PASS, _PASS_RHYME, ()) is True

    def test_continues_when_still_failing(self):
        policy = MaxIterationsOrValidStopPolicy()
        assert policy.should_stop(1, 5, _FAIL, _FAIL_RHYME, ()) is False
