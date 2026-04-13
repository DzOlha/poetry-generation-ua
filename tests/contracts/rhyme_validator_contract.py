"""Contract every `IRhymeValidator` implementation must satisfy.

Concrete test modules subclass `IRhymeValidatorContract` and provide a
``validator`` pytest fixture that returns the implementation under test.
"""
from __future__ import annotations

from src.domain.models import RhymeResult, RhymeScheme
from src.domain.ports import IRhymeValidator


class IRhymeValidatorContract:
    """Every IRhymeValidator must satisfy these behavioural guarantees.

    Subclasses must define a ``validator`` pytest fixture that returns
    the concrete ``IRhymeValidator`` to test.
    """

    @staticmethod
    def _abab() -> RhymeScheme:
        return RhymeScheme(pattern="ABAB")

    def test_validate_returns_rhyme_result(self, validator: IRhymeValidator) -> None:
        poem = "ліс\nвіс\nріс\nніс\n"
        result = validator.validate(poem, self._abab())
        assert isinstance(result, RhymeResult)

    def test_validate_returns_accuracy_in_range(self, validator: IRhymeValidator) -> None:
        poem = "ліс\nвіс\nріс\nніс\n"
        result = validator.validate(poem, self._abab())
        assert 0.0 <= result.accuracy <= 1.0

    def test_validate_empty_poem_returns_result(self, validator: IRhymeValidator) -> None:
        result = validator.validate("", self._abab())
        assert isinstance(result, RhymeResult)

    def test_validate_single_line(self, validator: IRhymeValidator) -> None:
        result = validator.validate("одна лінійка", self._abab())
        assert isinstance(result, RhymeResult)
