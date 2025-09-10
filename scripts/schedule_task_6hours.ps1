param(
  [int]$StartHour = 0
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $scriptDir
$venvPy = Join-Path $project ".venv/Scripts/python.exe"

if (-Not (Test-Path $venvPy)) {
  Write-Error "Python venv not found at $venvPy. Run scripts/setup.ps1 first."
  exit 1
}

# Determine start hour from .env if not provided
if ($StartHour -lt 0) {
  $envFile = Join-Path $project ".env"
  if (-Not (Test-Path $envFile)) { $envFile = Join-Path $project "env.example" }
  if (Test-Path $envFile) {
    $lines = Get-Content $envFile | Where-Object { $_ -match '^SCHEDULE_HOUR=' }
    if ($lines) { $h = ($lines[0] -split '=',2)[1]; [int]::TryParse($h, [ref]$StartHour) | Out-Null }
  }
}
if ($StartHour -lt 0) { $StartHour = 0 }

$taskName = "PodcastTranscript6Hours"
$arguments = "-m src.main"
$action = New-ScheduledTaskAction -Execute $venvPy -Argument $arguments -WorkingDirectory $project

# Create trigger that runs every 6 hours starting from the specified hour
$startTime = [datetime]::Today.AddHours($StartHour)
$trigger = New-ScheduledTaskTrigger -Once -At $startTime -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 365)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable

# Remove existing task if it exists
try { 
  if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { 
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false | Out-Null 
  } 
} catch {}

# Register the new task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Fetch podcast transcripts and generate LinkedIn drafts every 6 hours" | Out-Null

Write-Host "Scheduled task '$taskName' registered to run every 6 hours starting at $StartHour:00."
Write-Host "The task will run at: $StartHour:00, $($StartHour + 6):00, $($StartHour + 12):00, and $($StartHour + 18):00 daily."
Write-Host ""
Write-Host "To view the task: Get-ScheduledTask -TaskName '$taskName'"
Write-Host "To remove the task: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
