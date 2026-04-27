# ADR-001: Hexagonal Architecture with Domain Ports

## Status
Accepted

## Context
The poetry generation system combines neural models, LLM APIs, rule-based linguistic analysis, and file-based data stores. Each component evolves independently and must be testable in isolation.

## Decision
Adopt hexagonal (ports-and-adapters) architecture:
- **Domain layer** (`src/domain/`) contains value objects, entities, error hierarchy, and abstract port interfaces. It has zero dependencies on infrastructure.
- **Infrastructure layer** (`src/infrastructure/`) implements all ports with concrete adapters.
- **Services layer** (`src/services/`) contains thin use-case facades (`PoetryService`, `EvaluationService`).
- **Handlers layer** (`src/handlers/`) converts between transport formats (HTTP, CLI) and domain objects.
- **Runners layer** (`src/runners/`) implements `IRunner` for script-level orchestration.
- **Composition root** (`src/composition_root.py`) is the single place where concrete classes are wired together.

## Consequences
- All port interfaces live in `src/domain/ports/` as ABCs. Domain models (including `LineFeedback`, `PairFeedback`, `CorpusEntry`, `MetricCorpusEntry`) live in `src/domain/models/`.
- Infrastructure modules never import from services or handlers.
- Tests can substitute any port with a fake/mock without touching infrastructure code.
- The composition root (`Container` in `src/composition_root.py`) is now a thin façade composing six focused sub-containers (primitives, validation, generation, metrics, evaluation, detection) — each living in its own module under `src/infrastructure/composition/`. It is the only place that imports both domain ports and infrastructure classes.
- The same discipline extends to time and sleep: services depend on `IClock` / `IDelayer` (`src/domain/ports/clock.py`); concrete `SystemClock` / `SystemDelayer` adapters wrapping `time.perf_counter` / `time.sleep` live in `src/infrastructure/clock/`. `EvaluationService` and `BatchEvaluationService` never call `time.*` directly — tests inject fakes.
