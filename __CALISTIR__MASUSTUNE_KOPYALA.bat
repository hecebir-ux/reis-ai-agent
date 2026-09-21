@echo off
chcp 65001 >nul
title REIS AI -> Masaustune Tasi

REM Kesin calisan PowerShell scriptini cagirir
REM Gerekirse Yonetici izni ister

cd /d "%~dp0"

echo.
echo =====================================================
echo   REIS AI Agent  -  MASAUSTUNE TASI (GARANTI)
echo =====================================================
echo.
echo Bu islem 1-3 dakika surecektir.
echo.
echo Devam edilsin mi?  (E/H)
choice /c EH /n /m "Secim: "
if errorlevel 2 goto :NO
if errorlevel 1 goto :YES
goto :END

:YES
echo.
echo PowerShell ile kopyalama basladi...
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0MASUSTUNE_KOPYALA_PS.ps1" -Auto
set E=%ERRORLEVEL%
echo.
if "%E%"=="0" (
    echo ISLEM BASARILI - Masaustune bakiniz.
) else (
    echo.
    echo OTOMATIK BASARISIZ. Lutfen MANUEL YONTEM KULLANIN:
    echo.
    echo 1. Su an bulundugunuz klasorde bulunan "REIS_AI_AGENT" ust klasorunu secin
    echo    (Bir ust klasore cikmaniz gerekebilir - bu klasorun adi zaten REIS_AI_AGENT)
    echo.
    echo 2. Sag tik ^> Kopyala
    echo.
    echo 3. Masaustunde bos alana sag tik ^> Yapistir
    echo.
    echo 4. Kopyalama bitince Masaustundeki REIS_AI_AGENT klasorunden
    echo    setup.bat ^> sonra start.bat dosyalarina cift tikla.
    echo.
)
pause
goto :END

:NO
echo Islem iptal edildi.
pause

:END
