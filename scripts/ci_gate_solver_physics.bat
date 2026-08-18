@echo off
rem ============================================================
rem ci_gate_solver_physics.bat - solver-physics SKILL CI gate
rem
rem Script-based gate (no .github/workflows). Chains tests:
rem   1. unit/sampling/integration/e2e/mutation tests
rem   2. external regression (9 project baselines)
rem   3. three-way consistency check
rem   4. k-fold cross-validation
rem   5. Agent Harness (LLM cost, optional via RUN_HARNESS=1)
rem
rem Any failure => exit code 1 (block merge).
rem ============================================================
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "%~dp0\.."

echo ============================================================
echo [1/5] unit/sampling/integration/e2e/mutation tests
echo ============================================================
python -m pytest tests\test_solver_physics.py tests\test_solver_physics_sampling.py tests\test_solver_physics_integration.py tests\test_solver_physics_e2e.py tests\mutation\test_solver_physics_mutation.py -p no:randomly -q
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [2/5] external regression (9 project baselines)
echo ============================================================
python -m pytest tests\regression\test_solver_physics_regression.py -p no:randomly -q
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [3/5] three-way consistency check
echo ============================================================
python scripts\consistency_check_solver_physics.py
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [4/5] k-fold cross-validation
echo ============================================================
python scripts\cross_validate_solver_physics.py
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
echo GATE PASSED: solver-physics SKILL all tests PASS
echo ============================================================
exit /b 0

:FAIL
echo.
echo ============================================================
echo GATE FAILED: test failure detected, merge blocked
echo ============================================================
exit /b 1
