param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectPython = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw '请先按 code/README.md 创建虚拟环境并安装依赖。'
}
& $projectPython (Join-Path $PSScriptRoot 'server.py') --port $Port --open-browser
