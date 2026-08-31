@echo off
REM ci_gate_roadmap.bat - H1 WP-5 CI gate (Windows, minimal robust)
REM Gates: unit / consistency / coverage / snapshot / perf
REM Usage: ci_gate_roadmap.bat [--quick] [--update] [--project ROOT]
REM Exit: 0=pass 1=block

set "PYTHONIOENCODING=utf-8"
set "PROJECT_ROOT="

:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--project" set "PROJECT_ROOT=%~2"
if /i "%~1"=="--update" set "ARCH_REGRESSION_UPDATE=1"
shift /1
goto parse
:parsed

echo === H1 WP-5 CI Gate ===

echo.
echo [1/5] Unit tests...
python -m pytest tests/ -k "not regression and not solver_physics_e2e and not kahan_summation" -q
if not %errorlevel%==0 (
    echo [FAIL] Unit tests
    exit /b 1
)

echo.
echo [2/5] Consistency check...
python scripts/consistency_check.py
if not %errorlevel%==0 (
    echo [FAIL] Consistency
    exit /b 1
)

echo.
echo [3/5] Coverage matrix...
python scripts/gen_rule_coverage_matrix.py --check
if not %errorlevel%==0 (
    echo [FAIL] Coverage
    exit /b 1
)

echo.
echo [4/5] Snapshot regression...
python -m pytest tests/regression/test_standard_regression.py::TestArchQuality -q
if not %errorlevel%==0 (
    echo [FAIL] Snapshot
    exit /b 1
)

echo.
echo [5/5] Perf baseline (informational)...
if not "%PROJECT_ROOT%"=="" (
    python scripts/benchmark_h1_baseline.py --project "%PROJECT_ROOT%" --runs 1 --tag gate
) else (
    echo [INFO] No --project, skip perf
)

echo.
echo [PASS] All gates passed
exit /b 0