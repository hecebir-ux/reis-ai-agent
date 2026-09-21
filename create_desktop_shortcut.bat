@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "TARGET=%~dp0dist\REIS_AI\REIS_AI.exe"
if not exist "%TARGET%" (
    echo Once build_app.bat calistirin.
    pause
    exit /b 1
)

set "DESKTOP=%USERPROFILE%\Desktop"
set "LNK=%DESKTOP%\REIS AI.lnk"

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%LNK%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%~dp0dist\REIS_AI'; $s.Description = 'REIS AI Local Autonomous Agent'; $s.Save()"

echo Masaustu kisayolu olusturuldu: %LNK%
pause
