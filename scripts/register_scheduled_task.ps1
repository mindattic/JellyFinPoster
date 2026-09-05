<#
Registers a Windows Scheduled Task that runs jellyfin_poster.py once daily.
Run this from an elevated or normal PowerShell prompt on the machine that
will perform the refresh:

    .\scripts\register_scheduled_task.ps1

The task runs as the current user, only when logged on, with no console
window popping up (pythonw.exe). If the PC is asleep or off at the
scheduled time, it catches up as soon as the PC is next available
(StartWhenAvailable).
#>
param(
    [string]$TaskName = "JellyfinPosterRefresh",
    [string]$Time = "00:00",
    [string]$PythonExe = "pythonw"
)

$ProjectDir = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $ProjectDir "jellyfin_poster.py"

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "Refreshes Jellyfin Movies/TV Shows library artwork from trending TMDB titles" -Force

Write-Host "Registered scheduled task '$TaskName' to run daily at $Time (catches up on wake/login if missed)."
