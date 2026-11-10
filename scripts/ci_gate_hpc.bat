@echo off
rem ============================================================
rem ci_gate_hpc.bat - HPC/GPU SKILL CI gate
rem   1. unit tests
rem   2. three-way consistency
rem   3. regression (W4 baseline; skip if absent)
rem   4. cross-validation (B3.7, 9-fold LOOCV)
rem   5. Agent Harness (optional: RUN_HARNESS=1)
rem Any failure => exit 1.
rem ============================================================
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "%~dp0\.."

echo ============================================================
echo [1/5] unit tests
echo ============================================================
python -m pytest tests\test_hpc_architecture.py -p no:randomly -q
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [2/5] three-way consistency
echo ============================================================
python scripts\consistency_check.py --engine hpc
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [3/5] regression (W4 baseline)
echo ============================================================
if exist tests\regression\test_hpc_regression.py (
  python -m pytest tests\regression\test_hpc_regression.py -p no:randomly -q
  if errorlevel 1 goto :FAIL
) else (
  echo [SKIP] tests\regression\test_hpc_regression.py not available yet ^(W4^)
)

echo.
echo ============================================================
echo [4/5] cross-validation (B3.7, 9-fold LOOCV)
echo ============================================================
python scripts\cross_validate_hpc.py
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo [5/5] agent harness (optional)
echo ============================================================
if "%RUN_HARNESS%"=="1" (
  python scripts\run_agent_harness.py --case case-7-hpc-good
  if errorlevel 1 goto :FAIL
) else (
  echo [SKIP] set RUN_HARNESS=1 to run case-7-hpc-good
)

echo.
echo GATE PASS
exit /b 0

:FAIL
echo.
echo GATE FAIL
exit /b 1
