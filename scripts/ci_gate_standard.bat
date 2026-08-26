@echo off
REM ci_gate_standard.bat — 标准架构质量 CI 门禁（对齐指南 9.2 维度级口径）
REM
REM 门禁规则（指南 9.2）:
REM   1. 结构质量综合分 < 60 → 阻断合并 (BLOCK)
REM   2. 存在跨包循环依赖 (HIGH 问题) → 阻断合并 (BLOCK)
REM   3. 设计质量综合分 < 50 → 触发警告 (WARN)
REM
REM 用法:
REM   ci_gate_standard.bat <项目根目录> [--json]
REM
REM 退出码:
REM   0 = 通过
REM   1 = 阻断（结构<60 或 SAR-011/012 ERROR 或跨包循环）
REM   2 = 警告（设计<50，不阻断）

setlocal EnableDelayedExpansion
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"

set "PROJECT_ROOT=%~1"
if "%PROJECT_ROOT%"=="" set "PROJECT_ROOT=."
shift /1

echo === 标准架构质量 CI 门禁 ===
echo 项目: %PROJECT_ROOT%

REM 运行标准评估并捕获 JSON
set "REPORT=%~dp0..\docs\zh\架构质量标准\.ci_standard_report.json"
python -m arch_quality "%PROJECT_ROOT%" --json --report-mode local > "%REPORT%" 2>&1
if errorlevel 1 (
    echo [ERROR] 评估执行失败
    exit /b 1
)

REM 解析门禁判定（用 Python）
python -c "
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
data = json.load(open(r'%REPORT%', encoding='utf-8-sig'))
dims = data.get('dimensions', {})
structural = dims.get('structural', {}).get('score', 100)
design = dims.get('design', {}).get('score', 100)
violations = data.get('mlr_violations', [])
errors = [v for v in violations if v.get('output_level') == 'ERROR']
cycles = [v for v in violations if v.get('rule') in ('MLR-001','SAR-001') and v.get('severity')=='HIGH']

print(f'结构质量: {structural:.1f}')
print(f'设计质量: {design:.1f}')
print(f'ERROR 违规: {len(errors)}')
print(f'跨包循环: {len(cycles)}')

block = structural < 60 or len(errors) > 0 or len(cycles) > 0
warn = design < 50 and not block

if block:
    print('RESULT: BLOCK')
    sys.exit(1)
elif warn:
    print('RESULT: WARN')
    sys.exit(2)
else:
    print('RESULT: PASS')
    sys.exit(0)
"
set "GATE_CODE=%ERRORLEVEL%"

if "%GATE_CODE%"=="0" (
    echo.
    echo [PASS] 门禁通过
    exit /b 0
)
if "%GATE_CODE%"=="2" (
    echo.
    echo [WARN] 设计质量 < 50，建议关注（不阻断）
    exit /b 0
)
echo.
echo [BLOCK] 门禁阻断：结构质量 < 60 或存在 ERROR/跨包循环
exit /b 1