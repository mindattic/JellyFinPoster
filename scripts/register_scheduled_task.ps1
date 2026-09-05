<#
Registers a Windows Scheduled Task that runs jellyfin_poster.py once per hour.
Run this from an elevated or normal PowerShell prompt on the machine that
will perform the refresh:

    .\scripts\register_scheduled_task.ps1

The task runs as the current user, only when logged on, with no console
window popping up (pythonw.exe). If the PC is asleep or off at a scheduled
run, it catches up as soon as the PC is next available (StartWhenAvailable).
#>
param(
    [string]$TaskName = "JellyfinPosterRefresh",
    [string]$StartTime = "00:00",
    [string]$PythonExe = "pythonw"
)

$ProjectDir = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $ProjectDir "jellyfin_poster.py"

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Once -At $StartTime -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "Refreshes Jellyfin Movies/TV Shows library artwork from trending TMDB titles" -Force

Write-Host "Registered scheduled task '$TaskName' to run every hour, starting at $StartTime (catches up on wake/login if missed)."
