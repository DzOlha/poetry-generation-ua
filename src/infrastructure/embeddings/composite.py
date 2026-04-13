"""`CompositeEmbedder` — runtime fallback between a primary and secondary embedder.

The production wiring uses `LaBSEEmbedder` as primary and
`OfflineDeterministicEmbedder` as fallback. If the primary raises an
`EmbedderError` (model missing, network down, OOM), the composite switches
to the fallback for this call and every subsequent one — the user's audit
asked for a single runtime fallback chain instead of an
`offline_embedder: bool` config flag that forces the choice statically.
"""
from __future__ import annotations

from src.domain.errors import EmbedderError
from src.domain.ports import IEmbedder, ILogger


class CompositeEmbedder(IEmbedder):
    """Tries `primary`, falls back to `fallback` on `EmbedderError`.

    Once the primary has failed, the composite stays on the fallback for
    the rest of its lifetime so retries never re-load the broken model.
    The user can always construct a fresh composite if transient issues
    (e.g. a flaky download) warrant another attempt.
    """

    def __init__(
        self,
        primary: IEmbedder,
        fallback: IEmbedder,
        logger: ILogger,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._logger: ILogger = logger
        self._using_fallback: bool = False

    def encode(self, text: str) -> list[float]:
        if self._using_fallback:
            return self._fallback.encode(text)
        try:
            return self._primary.encode(text)
        except EmbedderError as exc:
            self._logger.warning(
                "primary embedder failed; switching to fallback",
                error=str(exc),
            )
            self._using_fallback = True
            return self._fallback.encode(text)
