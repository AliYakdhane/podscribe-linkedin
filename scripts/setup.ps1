param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $root
Write-Host "Project root: $project"

# Create venv
$venvPath = Join-Path $project ".venv"
if (-Not (Test-Path $venvPath)) {
  & $PythonExe -m venv $venvPath
}

$py = Join-Path $venvPath "Scripts/python.exe"

# Upgrade pip and install requirements
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $project "requirements.txt")

Write-Host "Setup complete. Activate: `"$venvPath\Scripts\Activate.ps1`""
