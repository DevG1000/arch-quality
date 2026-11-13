@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
echo == docs gate (G0/G1/G3) ==
for %%D in (gcs) do (
  python scripts\doc_lint.py --dimension %%D
  if errorlevel 1 exit /b 1
)
if not "%~1"=="" (
  echo == PR state %~1 ==
  python scripts\pr_state.py status --pr-id %~1
  if errorlevel 1 exit /b 1
)
exit /b 0