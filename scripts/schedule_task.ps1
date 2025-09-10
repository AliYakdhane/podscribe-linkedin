param(
  [int]$Hour = -1
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $scriptDir
$venvPy = Join-Path $project ".venv/Scripts/python.exe"

if (-Not (Test-Path $venvPy)) {
  Write-Error "Python venv not found at $venvPy. Run scripts/setup.ps1 first."
  exit 1
}

# Determine hour
if ($Hour -lt 0) {
  $envFile = Join-Path $project ".env"
  if (-Not (Test-Path $envFile)) { $envFile = Join-Path $project "env.example" }
  if (Test-Path $envFile) {
    $lines = Get-Content $envFile | Where-Object { $_ -match '^SCHEDULE_HOUR=' }
    if ($lines) { $h = ($lines[0] -split '=',2)[1]; [int]::TryParse($h, [ref]$Hour) | Out-Null }
  }
}
if ($Hour -lt 0) { $Hour = 8 }

$taskName = "PodcastTranscriptDaily"
$arguments = "-m src.main"
$action = New-ScheduledTaskAction -Execute $venvPy -Argument $arguments -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($Hour).TimeOfDay)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

try { if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false | Out-Null } } catch {}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Fetch podcast transcripts and generate LinkedIn drafts daily" | Out-Null

Write-Host "Scheduled task '$taskName' registered to run daily at $Hour:00."
