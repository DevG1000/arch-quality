@echo off
rem ============================================================
rem arch-quality.bat — 架构质量评估启动器 (Windows)
rem
rem 用法: arch-quality.bat [项目根目录] [选项...]
rem ============================================================
setlocal

rem 切换控制台到 UTF-8 代码页 (65001)
chcp 65001 >nul 2>&1

rem 强制 Python I/O 用 UTF-8
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONLEGACYWINDOWSSTDIO=0"

rem 调用主入口
python -m arch_quality %*

endlocal