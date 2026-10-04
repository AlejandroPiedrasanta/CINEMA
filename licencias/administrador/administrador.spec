# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para Windows, macOS y Linux. Deja fuera las partes de Qt que el panel
# no usa (OpenGL por software, red de Qt, formatos de imagen, traducciones): ejecutable más pequeño.
#   pyinstaller administrador.spec                     → un solo archivo portátil (dist/…exe)
#   set RCS_MODO=carpeta & pyinstaller administrador.spec → carpeta para el instalador
import os
import sys

EXCLUIR = ("opengl32sw", "qdirect2d", "/imageformats/", "/iconengines/", "/tls/", "/translations/",
           "qt6network", "qtnetwork", "qt6svg", "qt6pdf", "qt6opengl", "qt6virtualkeyboard")
CARPETA = os.environ.get("RCS_MODO") == "carpeta"
NOMBRE = "Administrador de Licencias"
WINDOWS = sys.platform == "win32"


def sirve(entrada) -> bool:
    nombre = entrada[0].replace("\\", "/").lower()
    return not any(x in nombre for x in EXCLUIR)


a = Analysis(["administrador_licencias.py"], excludes=["PySide6.QtNetwork", "tkinter"])
a.binaries = [b for b in a.binaries if sirve(b)]
a.datas = [d for d in a.datas if sirve(d)]
pyz = PYZ(a.pure)
opciones = dict(name=NOMBRE, debug=False, strip=False, upx=False, console=False,
                icon="icono.ico" if WINDOWS else None, version="version_info.txt" if WINDOWS else None)
if CARPETA:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **opciones)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NOMBRE)
    destino = coll
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **opciones)
    destino = exe
if sys.platform == "darwin":
    app = BUNDLE(destino, name=f"{NOMBRE}.app", bundle_identifier="com.rcs.administrador",
                 icon=None)
