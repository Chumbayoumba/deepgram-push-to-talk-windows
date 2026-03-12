$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pythonPath = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    throw "Virtual environment not found. Run .\install.ps1 first."
}

& $pythonPath -m deepgram_stt
