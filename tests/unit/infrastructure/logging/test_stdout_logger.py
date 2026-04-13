"""Tests for the ILogger adapters."""
from __future__ import annotations

import io

from src.infrastructure.logging import CollectingLogger, NullLogger, StdOutLogger


class TestNullLogger:
    def test_all_methods_are_noops(self):
        logger = NullLogger()
        logger.info("hello", key="value")
        logger.warning("hello")
        logger.error("hello")


class TestCollectingLogger:
    def test_records_info(self):
        logger = CollectingLogger()
        logger.info("msg", k=1)
        assert logger.records == [("info", "msg", {"k": 1})]

    def test_records_all_levels(self):
        logger = CollectingLogger()
        logger.info("a")
        logger.warning("b")
        logger.error("c")
        assert [r[0] for r in logger.records] == ["info", "warning", "error"]


class TestStdOutLogger:
    def test_info_writes_to_stream(self):
        stream = io.StringIO()
        logger = StdOutLogger(stream=stream)
        logger.info("hello", color="red")
        output = stream.getvalue()
        assert "info" in output
        assert "hello" in output
        assert "color='red'" in output

    def test_min_level_filters_info(self):
        stream = io.StringIO()
        logger = StdOutLogger(stream=stream, min_level="warning")
        logger.info("hidden")
        logger.warning("shown")
        output = stream.getvalue()
        assert "hidden" not in output
        assert "shown" in output
