$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pythonPath = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    python -m venv .venv
}

& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install -e .[dev]

Write-Host "Installation complete."
