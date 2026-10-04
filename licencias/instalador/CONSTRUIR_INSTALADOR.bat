@echo off
chcp 65001 >nul
title Construir instalador del Administrador de Licencias
cd /d "%~dp0"

set PY=py
where py >nul 2>nul || set PY=python
set NSIS=makensis
where makensis >nul 2>nul || set NSIS="%ProgramFiles(x86)%\NSIS\makensis.exe"

echo.
echo  [1/3] Instalando PySide6 y PyInstaller...
%PY% -m pip install --upgrade --quiet -r ..\requirements.txt
if errorlevel 1 goto error

echo  [2/3] Preparando el programa (tarda 1-2 minutos)...
cd ..\administrador
set RCS_MODO=carpeta
%PY% -m PyInstaller --noconfirm --clean administrador.spec
if errorlevel 1 goto error
cd ..\instalador

echo  [3/3] Creando el instalador...
%NSIS% /V2 instalador.nsi
if errorlevel 1 goto sin_nsis

echo.
echo  LISTO: "Instalar Administrador de Licencias 4.0.0.exe" en esta carpeta
explorer .
pause
exit /b 0

:sin_nsis
echo.
echo  No se pudo crear el instalador. Instala NSIS (gratis): https://nsis.sourceforge.io
echo  o en una terminal:  winget install NSIS.NSIS   y vuelve a intentarlo.
pause
exit /b 1

:error
echo.
echo  Hubo un error. Verifica que Python este instalado (python.org) y vuelve a intentarlo.
pause
exit /b 1
