@echo off
REM ============================================================================
REM  PussStage - first-run setup and guarded build on the PC.
REM  Edit the two paths below, then run from a Developer Command Prompt.
REM
REM  Written on macOS and NOT yet run on Windows - expect to fix a path.
REM ============================================================================

set "UE_ROOT=C:\Program Files\Epic Games\UE_5.8"
set "PROJECT=%~dp0.."

echo.
echo === 1. Editor must be closed =================================
REM This is the guard the macOS side never had. Building with the editor open
REM produced hot-reload libraries three separate times, and the test run then
REM passed against stale binaries - a false green.
tasklist /FI "IMAGENAME eq UnrealEditor.exe" 2>NUL | find /I "UnrealEditor.exe" >NUL
if not errorlevel 1 (
    echo   FAIL: UnrealEditor.exe is running. Close it before building.
    exit /b 1
)
echo   OK: no editor running.

echo.
echo === 2. Engine ================================================
if not exist "%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" (
    echo   FAIL: Unreal Engine 5.8 not found at %UE_ROOT%
    echo   Edit UE_ROOT at the top of this script.
    exit /b 1
)
echo   OK: %UE_ROOT%

echo.
echo === 3. Python with numpy =====================================
REM The analyzer imports numpy. The engine's bundled Python 3.11 does NOT ship
REM it, which is why this looks for a system interpreter.
set "PYEXE="
py -c "import numpy" >NUL 2>&1 && set "PYEXE=py"
if not defined PYEXE python -c "import numpy" >NUL 2>&1 && set "PYEXE=python"
if not defined PYEXE (
    echo   FAIL: no Python with numpy on PATH.
    echo   Fix:  py -m pip install numpy
    echo   Or set INFINITYSTAGE_PYTHON to a specific interpreter.
    exit /b 1
)
for /f "delims=" %%v in ('%PYEXE% -c "import numpy;print(numpy.__version__)"') do set "NPV=%%v"
echo   OK: %PYEXE%, numpy %NPV%

echo.
echo === 4. Build =================================================
call "%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" PussStageEditor Win64 Development -Project="%PROJECT%\PussStage.uproject" -waitmutex
if errorlevel 1 (
    echo   FAIL: build failed.
    exit /b 1
)
echo   OK: build succeeded.

echo.
echo === 5. Prove the new code is in the binary ====================
REM A symbol check is not enough - an anonymous-namespace function can inline
REM away and export nothing. UE's TEXT() literals are UTF-16, so search for one.
set "DLL=%PROJECT%\Plugins\InfinityStage\Binaries\Win64\UnrealEditor-InfinityStageEditor.dll"
if not exist "%DLL%" (
    echo   FAIL: %DLL% not found.
    exit /b 1
)
%PYEXE% -c "import sys;d=open(sys.argv[1],'rb').read();n=d.count('INFINITYSTAGE_PYTHON'.encode('utf-16-le'));print('   marker occurrences:',n);sys.exit(0 if n else 1)" "%DLL%"
if errorlevel 1 (
    echo   FAIL: marker absent - you are about to test STALE binaries.
    exit /b 1
)
echo   OK: new code is linked.

echo.
echo === 6. Environment variables to set ==========================
echo   PUSS_PROJECT_ROOT   = %PROJECT%
echo   PUSS_DRIVE_ROOT     = ^<shared drive^>\Projects\2026. SHS 3 Evenings
echo   PUSS_SOUND_ROOT     = %%PUSS_DRIVE_ROOT%%\Sound
echo   INFINITYSTAGE_PYTHON= only if py.exe / python.exe are not found
echo.
echo   setx PUSS_PROJECT_ROOT "%PROJECT%"
echo.
echo Bootstrap complete. Next: open the project, run the automation suite,
echo and record the pass count (M.5). The Mac figure does not carry over.
