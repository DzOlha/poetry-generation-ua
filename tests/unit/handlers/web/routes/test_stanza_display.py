"""Unit tests for per-stanza display helpers in the detection route.

_plain_stanza is duplicated here because the route module depends on
FastAPI which is not available in unit-test context.
"""
from __future__ import annotations


def _plain_stanza(stanza_text: str) -> dict[str, object]:
    """Exact copy of src.handlers.web.routes.detection._plain_stanza."""
    lines = [ln for ln in stanza_text.splitlines() if ln.strip()]
    return {
        "line_displays": [
            {"blank": False, "text": ln.strip(), "segments": None}
            for ln in lines
        ],
        "meter_accuracy": None,
        "rhyme_accuracy": None,
        "lines_count": len(lines),
    }


class TestPlainStanza:
    def test_returns_all_required_keys(self) -> None:
        result = _plain_stanza("рядок один\nрядок два")
        assert "line_displays" in result
        assert "meter_accuracy" in result
        assert "rhyme_accuracy" in result
        assert "lines_count" in result

    def test_meter_accuracy_is_none(self) -> None:
        result = _plain_stanza("рядок")
        assert result["meter_accuracy"] is None

    def test_rhyme_accuracy_is_none(self) -> None:
        result = _plain_stanza("рядок")
        assert result["rhyme_accuracy"] is None

    def test_lines_count(self) -> None:
        result = _plain_stanza("a\nb\nc\nd")
        assert result["lines_count"] == 4

    def test_blank_lines_excluded(self) -> None:
        result = _plain_stanza("a\n\nb\n\nc")
        assert result["lines_count"] == 3

    def test_line_displays_have_text(self) -> None:
        result = _plain_stanza("рядок один\nрядок два")
        displays = result["line_displays"]
        assert isinstance(displays, list)
        assert len(displays) == 2
        assert displays[0]["text"] == "рядок один"
        assert displays[1]["text"] == "рядок два"

    def test_line_displays_no_segments(self) -> None:
        result = _plain_stanza("рядок")
        displays = result["line_displays"]
        assert isinstance(displays, list)
        assert displays[0]["segments"] is None
