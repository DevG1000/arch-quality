# 把 harness 中的 agent 定义安装到项目 .opencode/agents（该目录被 .gitignore 忽略）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "opencode-harness\agents"
$dst = Join-Path $root ".opencode\agents"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -LiteralPath (Join-Path $src "proposer.md") -Destination (Join-Path $dst "assessment-proposer.md") -Force
Copy-Item -LiteralPath (Join-Path $src "reviewer.md") -Destination (Join-Path $dst "assessment-reviewer.md") -Force
Write-Host "installed: $dst\assessment-proposer.md"
Write-Host "installed: $dst\assessment-reviewer.md"
