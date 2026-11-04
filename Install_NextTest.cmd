@echo off
setlocal
chcp 65001 >nul
echo.
echo NextTest one-click installer
echo Downloading the ReadyToRun package. No Node/npm is required.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "try {" ^
  "  [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
  "  $candidates=Get-ChildItem -LiteralPath $env:USERPROFILE -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'NextTest' -or $_.Name -like 'NextTest-*' } | Sort-Object LastWriteTime -Descending;" ^
  "  $target=if ($candidates) { $candidates[0].FullName } else { Join-Path $env:USERPROFILE 'NextTest' };" ^
  "  Write-Host ('Install/update destination: ' + $target) -ForegroundColor DarkGray;" ^
  "  $downloads=Join-Path $env:USERPROFILE 'Downloads';" ^
  "  New-Item -ItemType Directory -Force -Path $downloads | Out-Null;" ^
  "  $zip=Join-Path $downloads ('NextTest_' + [guid]::NewGuid().ToString('N') + '.zip');" ^
  "  Write-Host ('Download destination: ' + $zip) -ForegroundColor DarkGray;" ^
  "  Invoke-WebRequest -Uri 'https://github.com/yeto0620/NextTest/releases/download/v1.1.0/NextTest_V1.1_ReadyToRun.zip' -OutFile $zip -UseBasicParsing;" ^
  "  Unblock-File -LiteralPath $zip -ErrorAction SilentlyContinue;" ^
  "  if ((Get-Item -LiteralPath $zip).Length -lt 1000000) { throw 'Downloaded package is too small.' }" ^
  "  Write-Host ('Extract destination: ' + $target) -ForegroundColor DarkGray;" ^
  "  New-Item -ItemType Directory -Force -Path $target | Out-Null;" ^
  "  try { Expand-Archive -LiteralPath $zip -DestinationPath $target -Force } catch { $target=Join-Path $env:USERPROFILE ('NextTest-' + (Get-Date -Format 'yyyyMMdd-HHmmss')); New-Item -ItemType Directory -Force -Path $target | Out-Null; Expand-Archive -LiteralPath $zip -DestinationPath $target -Force }" ^
  "  $setup=Join-Path $target 'setup_nexttest.cmd';" ^
  "  if (-not (Test-Path -LiteralPath $setup)) { throw ('setup_nexttest.cmd not found in ' + $target) }" ^
  "  Write-Host ('Starting: ' + $setup) -ForegroundColor Green;" ^
  "  Start-Process -FilePath $env:ComSpec -ArgumentList '/c', ('"' + $setup + '"') -WorkingDirectory $target;" ^
  "  Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue;" ^
  "}" ^
  "catch {" ^
  "  Write-Host ('INSTALLER ERROR: ' + $_.Exception.Message) -ForegroundColor Red;" ^
  "  Write-Host ('Target folder: ' + $target) -ForegroundColor Yellow;" ^
  "  exit 1" ^
  "}"

if errorlevel 1 (
  echo.
  echo Installer failed. The error above shows the exact path and reason.
  echo If access is denied, run this file from Downloads, not from a protected folder.
  pause
  exit /b 1
)
echo.
echo Installer finished. A setup window should be open.
pause
endlocal
