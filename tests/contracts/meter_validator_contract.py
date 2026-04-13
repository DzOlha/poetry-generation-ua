"""Contract every `IMeterValidator` implementation must satisfy.

Concrete test modules subclass `IMeterValidatorContract` and provide a
``validator`` pytest fixture that returns the implementation under test.
"""
from __future__ import annotations

from src.domain.models import MeterResult, MeterSpec
from src.domain.ports import IMeterValidator


class IMeterValidatorContract:
    """Every IMeterValidator must satisfy these behavioural guarantees.

    Subclasses must define a ``validator`` pytest fixture that returns
    the concrete ``IMeterValidator`` to test.
    """

    @staticmethod
    def _iamb_4ft() -> MeterSpec:
        return MeterSpec(name="ямб", foot_count=4)

    def test_validate_returns_meter_result(self, validator: IMeterValidator) -> None:
        result = validator.validate("Весна прийшла у ліс зелений", self._iamb_4ft())
        assert isinstance(result, MeterResult)

    def test_validate_returns_accuracy_in_range(self, validator: IMeterValidator) -> None:
        result = validator.validate(
            "Весна прийшла у ліс зелений,\nДе тінь і світло гомонить.\n",
            self._iamb_4ft(),
        )
        assert 0.0 <= result.accuracy <= 1.0

    def test_validate_empty_poem_returns_result(self, validator: IMeterValidator) -> None:
        result = validator.validate("", self._iamb_4ft())
        assert isinstance(result, MeterResult)

    def test_validate_single_line(self, validator: IMeterValidator) -> None:
        result = validator.validate("Весна прийшла у ліс зелений", self._iamb_4ft())
        assert isinstance(result, MeterResult)
        assert isinstance(result.accuracy, float)
