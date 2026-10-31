@echo off
setlocal
chcp 65001 >nul
echo.
echo NextTest one-click installer
echo Downloading the ReadyToRun package and extracting to %LOCALAPPDATA%\NextTest
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
  "$zip=Join-Path $env:TEMP 'NextTest_V3_ReadyToRun.zip';" ^
  "Invoke-WebRequest -Uri 'https://github.com/yeto0620/NextTest/releases/download/v3.0.0/NextTest_V3_ReadyToRun.zip' -OutFile $zip -UseBasicParsing;" ^
  "$target=Join-Path $env:LOCALAPPDATA 'NextTest';" ^
  "New-Item -ItemType Directory -Force $target | Out-Null;" ^
  "Expand-Archive -LiteralPath $zip -DestinationPath $target -Force;" ^
  "Start-Process -FilePath (Join-Path $target 'setup_nexttest.cmd') -WorkingDirectory $target"

if errorlevel 1 (
  echo.
  echo Installer failed. Check the network connection and try again.
  pause
  exit /b 1
)
echo.
echo Installer finished. A setup window should be open.
pause
endlocal
