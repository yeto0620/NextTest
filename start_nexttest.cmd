@echo off
setlocal EnableExtensions
rem 端口范围：8501–8510；--port 由 start_nexttest.py 校验
rem 透传 --doctor、--no-browser 和 --port；不启动第二套服务
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHON_EXE="
set "PYTHON_MODE=none"
set "IS_DOCTOR=0"
if /I "%~1"=="--doctor" set "IS_DOCTOR=1"

if defined NEXTEST_COMPUTE_PYTHON if exist "%NEXTEST_COMPUTE_PYTHON%" (
    set "PYTHON_EXE=%NEXTEST_COMPUTE_PYTHON%"
    set "PYTHON_MODE=direct"
)
if "%PYTHON_MODE%"=="none" if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    set "PYTHON_MODE=direct"
)
if "%PYTHON_MODE%"=="direct" goto run_direct

where py >nul 2>nul
if not errorlevel 1 (
    py -3.13 -c "import sys; sys.exit(0 if sys.version_info >= (3,13) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_MODE=py"
)
if "%PYTHON_MODE%"=="py" goto run_py

where python >nul 2>nul
if not errorlevel 1 set "PYTHON_MODE=python"
if "%PYTHON_MODE%"=="python" goto run_python

echo 未找到可用的 Python 3.13。
echo 请安装 Python 3.13，或将 NEXTEST_COMPUTE_PYTHON 指向 python.exe。
if "%IS_DOCTOR%"=="0" pause
exit /b 1

:run_direct
"%PYTHON_EXE%" "%~dp0scripts\start_nexttest.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:run_py
py -3.13 "%~dp0scripts\start_nexttest.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:run_python
python "%~dp0scripts\start_nexttest.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:finish
if not "%EXIT_CODE%"=="0" (
    echo.
    echo NextTest 未启动。请按上方中文提示修复环境后重试。
    if "%IS_DOCTOR%"=="0" pause
)
exit /b %EXIT_CODE%
