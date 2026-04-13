"""Shared pytest fixtures.

Fixtures are organised into focused modules under ``tests/fixtures/``:

  fixtures.infrastructure — low-level adapters (stress, embedder, LLM mock, ...)
  fixtures.validators     — meter, rhyme, composite validators
  fixtures.services       — full PoetryService via composition root
  fixtures.domain         — domain requests, sample poems, constants

All fixtures are re-exported here via pytest_plugins so every test module
can use them without explicit imports.
"""

# pytest_plugins collects fixtures from these modules automatically.
pytest_plugins = [
    "tests.fixtures.infrastructure",
    "tests.fixtures.validators",
    "tests.fixtures.services",
    "tests.fixtures.domain",
]
