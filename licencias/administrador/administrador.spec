# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para Windows, macOS y Linux. Deja fuera las partes de Qt que el panel
# no usa (OpenGL por software, red de Qt, formatos de imagen, traducciones): ejecutable más pequeño.
import sys

EXCLUIR = ("opengl32sw", "qdirect2d", "/imageformats/", "/iconengines/", "/tls/", "/translations/",
           "qt6network", "qtnetwork", "qt6svg", "qt6pdf", "qt6opengl", "qt6virtualkeyboard")


def sirve(entrada) -> bool:
    nombre = entrada[0].replace("\\", "/").lower()
    return not any(x in nombre for x in EXCLUIR)


a = Analysis(["administrador_licencias.py"], excludes=["PySide6.QtNetwork", "tkinter"])
a.binaries = [b for b in a.binaries if sirve(b)]
a.datas = [d for d in a.datas if sirve(d)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Administrador de Licencias",
          debug=False, strip=False, upx=False, console=False,
          icon="icono.ico" if sys.platform == "win32" else None)
if sys.platform == "darwin":
    app = BUNDLE(exe, name="Administrador de Licencias.app", bundle_identifier="com.rcs.administrador")
