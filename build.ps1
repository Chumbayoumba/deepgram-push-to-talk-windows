$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pythonPath = Join-Path $root ".venv\Scripts\python.exe"
$pyInstallerPath = Join-Path $root ".venv\Scripts\pyinstaller.exe"
$buildPath = Join-Path $root "build"
$distPath = Join-Path $root "dist"
$distExePath = Join-Path $distPath "deepgram-stt.exe"
$envPath = Join-Path $root ".env"
$distEnvPath = Join-Path $distPath ".env"

function Remove-PathWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [switch]$Directory
    )

    for ($attempt = 1; $attempt -le 10; $attempt++) {
        if (-not (Test-Path $Path)) {
            return
        }

        try {
            if ($Directory) {
                Remove-Item $Path -Recurse -Force
            }
            else {
                Remove-Item $Path -Force
            }
            return
        }
        catch {
            if ($attempt -eq 10) {
                throw
            }
            Start-Sleep -Seconds 1
        }
    }
}

if (-not (Test-Path $pythonPath)) {
    throw "Virtual environment not found. Run .\install.ps1 first."
}

& $pythonPath -m pip install -e .[build]

if (-not (Test-Path $distPath)) {
    New-Item -ItemType Directory -Path $distPath | Out-Null
}

$runningAppProcesses = Get-CimInstance Win32_Process |
    Where-Object { $_.ExecutablePath -eq $distExePath } |
    Select-Object -ExpandProperty ProcessId

foreach ($processId in $runningAppProcesses) {
    Stop-Process -Id $processId -Force
}

if ($runningAppProcesses) {
    Start-Sleep -Seconds 1
}

Remove-PathWithRetry -Path $distExePath
Remove-PathWithRetry -Path $distEnvPath
Remove-PathWithRetry -Path $buildPath -Directory

& $pyInstallerPath --noconfirm --clean --onefile --name deepgram-stt --specpath $buildPath --collect-submodules pynput --collect-submodules sounddevice --collect-binaries sounddevice --collect-data sounddevice app_bootstrap.py

if (Test-Path $envPath) {
    Copy-Item $envPath $distEnvPath -Force
}

Write-Host "Build complete: $($distPath)\deepgram-stt.exe"
