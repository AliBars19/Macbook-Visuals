# ═══════════════════════════════════════════════════════════════
# Apollova Render Watcher — Task Scheduler Setup
# ═══════════════════════════════════════════════════════════════
# Run this ONCE as Administrator to register the watcher as a
# scheduled task that starts automatically when you log in.
#
# Usage (from PowerShell as Admin):
#   cd C:\Users\xx\Downloads\Apollova\Apollova
#   .\setup_task.ps1
#
# To remove later:
#   Unregister-ScheduledTask -TaskName "Apollova Render Watcher" -Confirm:$false
# ═══════════════════════════════════════════════════════════════

# ── Configuration (edit these if your paths differ) ───────────
$TaskName = "Apollova Render Watcher"
$PythonPath = "python"                                                    # Uses system Python
$ScriptPath = "$PSScriptRoot\render_watcher.py"                           # Same folder as this script
$WorkingDir = $PSScriptRoot                                               # Apollova root
$Description = "Monitors After Effects render folders and auto-uploads videos to the Apollova website"

# ── Validate ──────────────────────────────────────────────────
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: render_watcher.py not found at $ScriptPath" -ForegroundColor Red
    Write-Host "Make sure this script is in the same folder as render_watcher.py" -ForegroundColor Yellow
    exit 1
}

# Check if .env exists
$EnvPath = Join-Path $WorkingDir ".env"
if (-not (Test-Path $EnvPath)) {
    Write-Host "WARNING: No .env file found at $EnvPath" -ForegroundColor Yellow
    Write-Host "The watcher needs GATE_PASSWORD set in .env to work." -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y") { exit 0 }
}

# ── Remove existing task if present ───────────────────────────
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# ── Create the task ───────────────────────────────────────────
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -RestartCount 3 `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Don't require admin privileges to run
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description $Description `
    -Force

# ── Verify ────────────────────────────────────────────────────
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host ""
    Write-Host "SUCCESS: '$TaskName' registered!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Trigger:  Runs at login for $env:USERNAME" -ForegroundColor Cyan
    Write-Host "  Script:   $ScriptPath" -ForegroundColor Cyan
    Write-Host "  WorkDir:  $WorkingDir" -ForegroundColor Cyan
    Write-Host "  Restarts: Up to 3x if it crashes (every 5 min)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  Start now:    Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "  Stop:         Stop-ScheduledTask -TaskName '$TaskName'"
    Write-Host "  Check status: Get-ScheduledTask -TaskName '$TaskName' | Select State"
    Write-Host "  Remove:       Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
    Write-Host ""
} else {
    Write-Host "ERROR: Task registration failed" -ForegroundColor Red
    exit 1
}
