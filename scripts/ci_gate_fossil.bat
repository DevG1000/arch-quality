@echo off
rem ============================================================
rem ci_gate_fossil.bat - 化石代码/技术债 CI gate
rem   1. unit tests
rem   2. three-way consistency
rem   3. regression (5 baselines)
rem   4. coverage matrix 108/108
rem   5. Agent Harness (optional: RUN_HARNESS=1)
rem ============================================================
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "%~dp0\.."

echo ============================================================
echo [1/5] unit tests
echo ============================================================
python -m pytest tests\test_fossil_code.py -p no:randomly -q
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [2/5] three-way consistency
echo ============================================================
python scripts\consistency_check.py --engine fossil
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [3/5] regression (5 baselines)
echo ============================================================
python -m pytest tests\regression\test_fossil_regression.py -p no:randomly -q
if errorlevel 1 goto :FAIL
if "%RUN_FOSSIL_REAL%"=="1" (
  python -m pytest tests\regression\test_fossil_real_regression.py -p no:randomly -q
  if errorlevel 1 goto :FAIL
) else (
  echo [SKIP] set RUN_FOSSIL_REAL=1 to run Code_Aster/BRL-CAD/OpenFOAM baselines
)

echo.
echo ============================================================
echo [4/5] coverage matrix 108/108
echo ============================================================
python scripts\gen_rule_coverage_matrix.py --check
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [5/5] agent harness (optional)
echo ============================================================
if "%RUN_HARNESS%"=="1" (
  python scripts\run_agent_harness.py --case case-10-fossil-good
  if errorlevel 1 goto :FAIL
  python scripts\run_agent_harness.py --case case-11-fossil-flawed
  if errorlevel 1 goto :FAIL
  python scripts\run_agent_harness.py --case case-12-fossil-non
  if errorlevel 1 goto :FAIL
) else (
  echo [SKIP] set RUN_HARNESS=1 to run case-10/11/12
)

echo.
echo GATE PASS
exit /b 0

:FAIL
echo.
echo GATE FAIL
exit /b 1
