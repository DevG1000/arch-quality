@echo off
rem ============================================================
rem ci_gate_geometry_consistency.bat - geometry-consistency SKILL CI gate
rem
rem Script-based gate (no .github/workflows). Chains tests:
rem   1. unit/integration/e2e/mutation tests
rem   2. external regression (3 project baselines: occt/salome-geom/freecad)
rem   3. three-way consistency check (consistency_check.py)
rem   4. k-fold cross-validation\nrem   5. Agent Harness (LLM cost, optional via RUN_HARNESS=1)
rem
rem Any failure => exit code 1 (block merge).
rem ============================================================
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "%~dp0\.."

echo ============================================================
echo [1/5] unit/integration/e2e/mutation tests
echo ============================================================
python -m pytest tests\test_geometry_consistency.py tests\test_geometry_integration.py tests\mutation\test_geometry_mutation.py tests\test_harness_gcs.py -p no:randomly -q
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [2/5] external regression (3 project baselines)
echo ============================================================
python -m pytest tests\regression\test_geometry_regression.py -p no:randomly -q
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [3/5] three-way consistency check
echo ============================================================
python scripts\consistency_check.py --engine geometry_consistency
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [4/5] k-fold cross-validation
echo ============================================================
python scripts\cross_validate_geometry_consistency.py
if errorlevel 1 goto :FAIL

rem Agent Harness optional (LLM cost). Enable: set RUN_HARNESS=1
if "%RUN_HARNESS%"=="1" (
    echo.
    echo ============================================================
    echo [5/5] Agent Harness validation
    echo ============================================================
    python scripts\run_agent_harness.py --timeout 600
    if errorlevel 1 goto :FAIL
) else (
    echo.
    echo [5/5] Agent Harness skipped (set RUN_HARNESS=1 to enable, LLM cost)
)

echo.
echo ============================================================
echo GATE PASSED: geometry-consistency SKILL all tests PASS
echo ============================================================
exit /b 0

:FAIL
echo.
echo ============================================================
echo GATE FAILED: test failure detected, merge blocked
echo ============================================================
exit /b 1
