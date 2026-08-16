$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Install requirements.txt first."
}

& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed." }

& $python -m PyInstaller --noconfirm --clean voice-writing-robot.spec
if ($LASTEXITCODE -ne 0) { throw "Executable build failed." }

$exe = Get-ChildItem -LiteralPath (Join-Path $projectRoot "dist") -Filter "*.exe" -Recurse | Select-Object -First 1
if ($null -eq $exe) { throw "Build finished, but no executable was found." }
Write-Host "Build complete: $($exe.FullName)" -ForegroundColor Green
