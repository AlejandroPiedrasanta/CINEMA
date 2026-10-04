# -*- mode: python ; coding: utf-8 -*-
# Igual que CONSTRUIR_EXE.bat, pero sin las partes de Qt que el panel no usa (exe más pequeño).
EXCLUIR = ("opengl32sw.dll", "qdirect2d.dll", "\\imageformats\\", "\\iconengines\\", "\\tls\\",
           "\\translations\\", "Qt6Network", "QtNetwork", "Qt6Svg", "Qt6Pdf", "Qt6OpenGL")

a = Analysis(["administrador_licencias.py"], excludes=["PySide6.QtNetwork", "tkinter"])
a.binaries = [b for b in a.binaries if not any(x.lower() in b[0].lower() for x in EXCLUIR)]
a.datas = [d for d in a.datas if not any(x.lower() in d[0].lower() for x in EXCLUIR)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Administrador de Licencias",
          debug=False, strip=False, upx=False, console=False, icon="icono.ico")
