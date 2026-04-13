"""Tests for `ExponentialBackoffRetry`."""
from __future__ import annotations

import pytest

from src.domain.errors import DomainError, LLMError
from src.infrastructure.llm.decorators import ExponentialBackoffRetry


class TestExponentialBackoffRetry:
    def test_should_retry_true_for_llm_error_within_limit(self) -> None:
        policy = ExponentialBackoffRetry(max_attempts=3)
        assert policy.should_retry(attempt=1, exc=LLMError("boom")) is True
        assert policy.should_retry(attempt=2, exc=LLMError("boom")) is True

    def test_should_retry_false_after_max_attempts(self) -> None:
        policy = ExponentialBackoffRetry(max_attempts=3)
        assert policy.should_retry(attempt=3, exc=LLMError("boom")) is False

    def test_should_retry_false_for_non_llm_error(self) -> None:
        policy = ExponentialBackoffRetry(max_attempts=3)
        assert policy.should_retry(attempt=1, exc=DomainError("other")) is False

    def test_next_delay_doubles_then_caps(self) -> None:
        policy = ExponentialBackoffRetry(
            max_attempts=10,
            base_delay_sec=1.0,
            max_delay_sec=4.0,
            multiplier=2.0,
        )
        assert policy.next_delay_sec(1) == 1.0
        assert policy.next_delay_sec(2) == 2.0
        assert policy.next_delay_sec(3) == 4.0
        assert policy.next_delay_sec(4) == 4.0  # capped

    def test_construction_validates_inputs(self) -> None:
        with pytest.raises(ValueError):
            ExponentialBackoffRetry(max_attempts=0)
        with pytest.raises(ValueError):
            ExponentialBackoffRetry(base_delay_sec=-1.0)
        with pytest.raises(ValueError):
            ExponentialBackoffRetry(multiplier=0.0)
