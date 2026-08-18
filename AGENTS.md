# AGENTS.md — arch-quality repo guide

## Install & Setup

```powershell
pip install -e .                  # dev install from repo root
python -m arch_quality --help     # entry if arch-quality not on PATH
```

## Entry Points (`pyproject.toml`)

| Command | Source module | Purpose |
|---------|--------------|---------|
| `arch-quality` | `arch_report.py:main` | Comprehensive report (CLI default) |
| `arch-quality-standard` | `arch_metrics_standard.py:main` | Standard 4-dimension metrics only |
| `arch-quality-multilang` | `arch_metrics_multilang.py:main` | Multilang 6-dim + MLR rules only |
| `arch-quality-template` | `arch_metrics_template.py:main` | Template metaprogramming only |
| via `-m` | `arch_metrics_numerical_accuracy.py:main` | Numerical accuracy (no CLI entry in pyproject) |

## Architecture

```
src/arch_quality/
  arch_core.py                  # FileIndex, DepGraph, GitHistory (shared)
  arch_metrics_standard.py      # StandardMetrics — 4 dims (30%+25%+20%+25%)
  arch_metrics_multilang.py     # MultilangMetrics — 6 dims + 12 MLR rules
  arch_metrics_template.py      # TemplateMetaprogrammingMetrics — 6 dims + 12 MLR
  arch_metrics_numerical_accuracy.py  # NumericalAccuracyMetrics — 6 dims + 12 NVR
  arch_report.py                # ComprehensiveReport — merges all above
  arch_report_generator.py      # Markdown report template (16 sections)
  arch_bindings_parser.py       # pybind11 binding extraction (C++ side)
  arch_python_ast.py            # pybind11 call extraction (Python side, AST)
  arch_multilang_matcher.py     # Builds cross-language edges
  skills/*.md                   # Weight definitions (parsed at runtime)
```

## Key Commands

```powershell
# Run all tests
python -m pytest tests/

# Run single test file
python -m pytest tests/test_numerical_accuracy.py

# Run single test class/method
python -m pytest tests/test_numerical_accuracy.py::TestNonNumericalProject

# Run regression tests (snapshot-based)
$env:ARCH_REGRESSION_UPDATE=1; python -m pytest tests/regression/test_regression.py

# Run comprehensive report against a project
python -m arch_quality D:\path\to\project --json --md

# With build dir (for SWIG bindings)
python -m arch_quality D:\path\to\project --build-dir D:\path\to\build
```

## Critical Conventions

- **Encoding**: All file I/O uses UTF-8 BOM. `read_text_smart()` auto-tries UTF-8-sig → UTF-8 → GBK → GB18030 → Latin-1. Always use these helpers from `arch_core.py`, not bare `open()`.
- **Weights**: All dimension weights are parsed from `skills/*.md` at runtime. Weights sum must be exactly 100% or error is raised. Never hardcode weights.
- **Multilang/Template/NumAcc enhancements**: Auto-detected (by file extensions/keywords). When 0/1/2/3 enhancements active, base structural weight adjusts: 100%/85%/70%/60%.
- **Report mode**: Default is `central` (`~/.config/opencode/arch-reports/`). Use `--report-mode local` for project-local storage.
- **Windows script**: `scripts\arch-quality.bat` sets `chcp 65001` + `PYTHONIOENCODING=utf-8`. Replicates this when running manually.
- **Skills in `.opencode/skills/`**: Contains `knowledge-base-management/`, `mms-testing/`, `numerical-accuracy/` — these are OpenCode skill definitions, separate from `src/arch_quality/skills/*.md`.

## Tests

- Framework: `unittest` (standard library). Run via `python -m pytest`.
- No `pytest.ini` or `conftest.py` — test discovery by convention.
- Regression tests use snapshot JSON files in `tests/regression/snapshots/`. Set `$env:ARCH_REGRESSION_UPDATE=1` to update baselines.
- Mutation tests in `tests/mutation/`.
- No CI workflows (no `.github/workflows/`).
- No type checker (`mypy`) or linter (`ruff`) config in the repo.

## Agent Harness

Validates the `architecture-quality` **agent behavior** (LLM orchestrating tools correctly), complementing pytest (which validates the Python tools' scoring). Uses opencode's own mechanisms — constraints (permissions), verification (assertors), correction (retry).

```powershell
# Run all harness cases
python scripts\run_agent_harness.py

# Single case
python scripts\run_agent_harness.py --case case-1-multiphysics --timeout 600 --verbose
```

- Location: `opencode-harness/` — `harness_runner.py`, `assertors/` (tool_usage / output_schema / score_sanity), `cases/` (3 JSON cases), `reports/`.
- **Single source of truth**: `opencode-harness/rules.json` shared by both Python assertors and the opencode plugin hook.
- **Inline plugin assert**: `.opencode/plugins/agent-assert.js` auto-asserts after eval commands run inside any opencode session (mode `log` by default; set `rules.json` `"assert_mode": "throw"` to block on failure).
- Runs `opencode run --agent architecture-quality --format json` — requires the agent registered as `mode: primary` (global `~/.config/opencode/opencode.jsonc`; project `opencode.json` is overridden by global).
- Costs LLM tokens (~1-5 min per case). Cases use synthetic projects in `tests/mutation/projects/`.

## Things to Keep in Mind

- `opencode.json` defines skill paths, the `architecture-quality` agent (`mode: primary`), and `plugin` (npm plugins only; local plugins auto-load from `.opencode/plugins/`). `opencode1.json` is legacy/unmerged.
- The solver/physics field modular architecture assessment (`docs/zh/求解器和物理场模块化架构模式识别评估/`) is **fully implemented** — `arch_metrics_solver_physics.py` (SolverPhysicsMetrics, 4 dims + 12 MPR), tests (97 unit/integration/e2e/mutation), 9 regression baselines, k-fold cross-validation, agent harness. B3.5 enhancements: OpenFOAM config-dict scan, preCICE multi-mode arch detection, FreeFEM src-subdir solver-unit fallback. C-stage deliverables: `scripts/ci_gate_solver_physics.bat` (CI gate), user prompt template (`...用户交互提示词模板.md`), report template (`...报告模板.md`).
- `package.json` in `.opencode/` is for OpenCode plugin dependency (`@opencode-ai/plugin@1.2.24`), not the project itself.
- **`.opencode/plugins/`**: Project-level OpenCode plugins (auto-loaded). `agent-assert.js` hooks `tool.execute.before/after` to auto-assert eval-command outputs at the framework level (independent of the external Python harness). Rules shared via `opencode-harness/rules.json`.
