# Self-contained setup for JellyfinPoster.
# Installs Python if it isn't already present (per-user, no admin rights
# required), installs the project's dependencies, then runs the refresh.
# Invoked by Start.bat -- not meant to be run standalone by a user.

$ErrorActionPreference = 'Stop'
$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoDir

function Find-Python {
    $candidates = New-Object System.Collections.Generic.List[string]

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $candidates.Add($cmd.Source) }

    # Per-user install locations, in case PATH hasn't been refreshed yet
    # in this process (winget/python.org installers update the registry,
    # not the current shell's environment).
    Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        ForEach-Object { $candidates.Add($_.FullName) }

    foreach ($exe in $candidates) {
        if (-not $exe -or -not (Test-Path $exe)) { continue }
        try {
            $verOut = & $exe -c "import sys; print(sys.version_info[0], sys.version_info[1])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $verOut) {
                $parts = $verOut.Trim() -split '\s+'
                $major = [int]$parts[0]; $minor = [int]$parts[1]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                    return $exe
                }
            }
        } catch { }
    }
    return $null
}

function Install-PythonViaWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { return $false }
    Write-Host "Installing Python via winget (this can take a minute)..."
    try {
        & winget install --id Python.Python.3.12 -e --scope user --silent `
            --accept-package-agreements --accept-source-agreements | Out-Null
    } catch {
        return $false
    }
    return $true
}

function Install-PythonViaDirectDownload {
    Write-Host "Downloading Python installer from python.org..."
    $pyVersion = "3.12.7"
    $url = "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-amd64.exe"
    $installer = Join-Path $env:TEMP "python-$pyVersion-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
    Write-Host "Installing Python (per-user, no admin needed)..."
    Start-Process -FilePath $installer `
        -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0" `
        -Wait
    Remove-Item $installer -ErrorAction SilentlyContinue
}

Write-Host "JellyfinPoster"
Write-Host "=============="
Write-Host ""

$python = Find-Python
if (-not $python) {
    Write-Host "Python 3.10+ was not found. Setting it up automatically -- no action needed."
    Install-PythonViaWinget | Out-Null
    $python = Find-Python
    if (-not $python) {
        Install-PythonViaDirectDownload
        $python = Find-Python
    }
    if (-not $python) {
        Write-Host ""
        Write-Host "Could not install Python automatically."
        Write-Host "Install it manually from https://www.python.org/downloads/ and re-run Start.bat."
        exit 1
    }
    Write-Host "Python installed: $python"
} else {
    Write-Host "Found Python: $python"
}

Write-Host "Checking dependencies..."
& $python -m pip install --upgrade pip --quiet --disable-pip-version-check
& $python -m pip install -r (Join-Path $RepoDir "requirements.txt") --quiet --disable-pip-version-check

function Read-RequiredValue {
    param([string]$Prompt, [string]$Hint)
    Write-Host $Hint -ForegroundColor DarkGray
    do {
        $value = Read-Host $Prompt
    } while ([string]::IsNullOrWhiteSpace($value))
    return $value
}

if (-not (Test-Path (Join-Path $RepoDir ".env"))) {
    Write-Host ""
    Write-Host "No .env file found -- let's set it up."
    Write-Host ""

    $tmdbToken = Read-RequiredValue "TMDB_TOKEN" "  Find it at: https://www.themoviedb.org/settings/api (API Read Access Token, v4 auth)"
    Write-Host ""
    $jfUrl = Read-RequiredValue "JF_URL" "  Your Jellyfin server's base URL, e.g. http://192.168.1.10:8096"
    Write-Host ""
    $jfApiKey = Read-RequiredValue "JF_API_KEY" "  Find it at: Jellyfin Dashboard > Advanced > API Keys (click + to create one)"

    $envLines = @(
        "TMDB_TOKEN=$tmdbToken"
        "JF_URL=$jfUrl"
        "JF_API_KEY=$jfApiKey"
        "JF_MOVIES_LIBRARY_NAME=Movies"
        "JF_TV_LIBRARY_NAME=TV Shows"
        "TMDB_MIN_VOTE_COUNT=30"
    )
    Set-Content -Path (Join-Path $RepoDir ".env") -Value $envLines -Encoding utf8
    Write-Host ""
    Write-Host ".env created."
}

Write-Host ""
Write-Host "Setting up hourly scheduled task..."
$pythonw = $python -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }
& (Join-Path $RepoDir "scripts\register_scheduled_task.ps1") -PythonExe $pythonw

Write-Host ""
Write-Host "Refreshing Movies and TV Shows library artwork now..."
Write-Host ""

& $python (Join-Path $RepoDir "jellyfin_poster.py")
exit $LASTEXITCODE
