[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

Write-Host ''
Write-Host 'NextTest setup / first run' -ForegroundColor Cyan
Write-Host "Project folder: $root" -ForegroundColor DarkGray

if (-not (Test-Path -LiteralPath (Join-Path $root 'start_nexttest.cmd'))) {
    Write-Host 'start_nexttest.cmd was not found.' -ForegroundColor Red
    Write-Host 'Extract the zip first, then run setup_nexttest.cmd from the extracted folder.' -ForegroundColor Yellow
    exit 2
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host 'Python was not found. Install Python 3.13 and enable Add python.exe to PATH.' -ForegroundColor Red
    Write-Host 'Download: https://www.python.org/downloads/windows/' -ForegroundColor Yellow
    exit 3
}
$pyVersion = (& python --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($pyVersion)) {
    Write-Host 'Python was found but could not run. Reinstall Python 3.13 with Add python.exe to PATH.' -ForegroundColor Red
    exit 3
}
Write-Host "Python: $pyVersion" -ForegroundColor DarkGray

$importCheck = 'import fastapi, uvicorn, numpy, pandas, sklearn'
& python -c $importCheck 2>$null | Out-Null
$importReady = ($LASTEXITCODE -eq 0)
if (-not $importReady) {
    Write-Host 'Installing Python dependencies (first run may take a few minutes)...' -ForegroundColor DarkGray
    $webReq = Join-Path $root 'requirements-web.txt'
    $computeReq = Join-Path $root 'requirements-compute.txt'
    & python -m pip install -r $webReq
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Retrying Python web dependencies with --user...' -ForegroundColor Yellow
        & python -m pip install --user -r $webReq
    }
    if ($LASTEXITCODE -ne 0) { Write-Host 'Python web dependencies failed. See the pip message above.' -ForegroundColor Red; exit 4 }
    & python -m pip install -r $computeReq
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Retrying Python compute dependencies with --user...' -ForegroundColor Yellow
        & python -m pip install --user -r $computeReq
    }
    if ($LASTEXITCODE -ne 0) { Write-Host 'Python compute dependencies failed. See the pip message above.' -ForegroundColor Red; exit 5 }
}
else {
    Write-Host 'Python dependencies are ready.' -ForegroundColor DarkGray
}

$dist = Join-Path $root 'frontend\dist\index.html'
if (Test-Path -LiteralPath $dist) {
    Write-Host 'Prebuilt frontend found; skipping npm build.' -ForegroundColor DarkGray
}
else {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        Write-Host 'npm was not found. Install Node.js LTS and reopen PowerShell.' -ForegroundColor Red
        Write-Host 'Download: https://nodejs.org/' -ForegroundColor Yellow
        Write-Host 'Or use the ReadyToRun zip that contains frontend/dist.' -ForegroundColor Yellow
        exit 6
    }
    Write-Host 'Installing frontend dependencies and building...' -ForegroundColor DarkGray
    Push-Location (Join-Path $root 'frontend')
    try {
        if (Test-Path -LiteralPath (Join-Path $root 'frontend\package-lock.json')) { & npm ci } else { & npm install }
        if ($LASTEXITCODE -ne 0) { Write-Host 'npm install failed.' -ForegroundColor Red; exit 7 }
        & npm run build
        if ($LASTEXITCODE -ne 0) { Write-Host 'Frontend build failed.' -ForegroundColor Red; exit 8 }
    }
    finally { Pop-Location }
}

$launcher = Join-Path $root 'start_nexttest.cmd'
$launcherArgs = @()
if ($NoBrowser) { $launcherArgs += '--no-browser' }
function New-NextTestShortcut {
    param([string]$Folder, [string]$Name, [string]$Script, [string]$Description)
    if (-not (Test-Path -LiteralPath $Folder)) { return }
    try {
        $shell = New-Object -ComObject WScript.Shell
        $link = $shell.CreateShortcut((Join-Path $Folder ($Name + '.lnk')))
        $link.TargetPath = $env:ComSpec
        $link.Arguments = '/c ""' + $Script + '""'
        $link.WorkingDirectory = $root
        $link.WindowStyle = 1
        $link.Description = $Description
        $link.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
        $link.Save()
    }
    catch { Write-Host ("Shortcut could not be created: " + $Name) -ForegroundColor Yellow }
}

$desktop = [Environment]::GetFolderPath('Desktop')
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$normalLauncher = Join-Path $root 'start_nexttest.cmd'
$deepseekLauncher = Join-Path $root 'start_nexttest_with_llm.cmd'
$deepseekConfig = Join-Path $root 'configure_nexttest_llm.cmd'
foreach ($folder in @($desktop, $startMenu)) {
    New-NextTestShortcut -Folder $folder -Name 'NextTest' -Script $normalLauncher -Description 'Open NextTest'
    New-NextTestShortcut -Folder $folder -Name 'NextTest DeepSeek' -Script $deepseekLauncher -Description 'Open NextTest with DeepSeek'
    New-NextTestShortcut -Folder $folder -Name 'NextTest DeepSeek Config' -Script $deepseekConfig -Description 'Configure DeepSeek key'
}
Write-Host 'Desktop and Start Menu shortcuts created.' -ForegroundColor Green

Write-Host 'Starting NextTest...' -ForegroundColor Green
& $launcher @launcherArgs
exit $LASTEXITCODE
