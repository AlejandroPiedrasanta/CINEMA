@echo off
chcp 65001 >nul
title Construir Administrador de Licencias
cd /d "%~dp0"

set PY=py
where py >nul 2>nul || set PY=python

echo.
echo  [1/2] Instalando PySide6 y PyInstaller...
%PY% -m pip install --upgrade --quiet pyside6 pyinstaller
if errorlevel 1 goto error

echo  [2/2] Creando el .exe (tarda 1-2 minutos)...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "Administrador de Licencias" --icon icono.ico administrador_licencias.py
if errorlevel 1 goto error

echo.
echo  LISTO: dist\Administrador de Licencias.exe
explorer dist
pause
exit /b 0

:error
echo.
echo  Hubo un error. Verifica que Python este instalado (python.org) y vuelve a intentarlo.
pause
exit /b 1
