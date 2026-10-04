"""Cinema Productions · dibuja las imágenes del instalador (banners e icono) con la marca.

    pip install pyside6 pillow
    python crear_imagenes.py

Crea en imagenes/: bienvenida.bmp (banner lateral de las páginas de bienvenida y final),
cabecera.bmp (banner de la parte de arriba), icono.ico y icono.png. También copia el icono
a ../administrador/icono.ico para el ejecutable.

Creado por Cinema Productions.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(AQUI.parent / "programa"), str(AQUI.parent / "administrador")]

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

__author__ = "Cinema Productions"

VERSION = "5.0"
SALIDA = AQUI / "imagenes"
PLATAFORMAS = (("#facc15", "Lemon Squeezy"), ("#f97316", "Hotmart"), ("#ff90e8", "Gumroad"), ("#3b82f6", "Polar"))


def _fondo(p: QPainter, w: int, h: int, luces, perforaciones: bool = True):
    grad = QLinearGradient(0, 0, w * 0.4, h)
    grad.setColorAt(0, QColor("#1c0a0e"))
    grad.setColorAt(1, QColor("#07070a"))
    p.fillRect(0, 0, w, h, grad)
    for x, y, r, color, alfa in luces:
        radial = QRadialGradient(QPointF(w * x, h * y), max(w, h) * r)
        c1, c2 = QColor(color), QColor(color)
        c1.setAlpha(alfa)
        c2.setAlpha(0)
        radial.setColorAt(0, c1)
        radial.setColorAt(1, c2)
        p.fillRect(0, 0, w, h, radial)
    if perforaciones:      # bordes de película de cine
        p.setPen(Qt.PenStyle.NoPen)
        tira = max(14, w // 16)
        for x in (0, w - tira):
            p.fillRect(QRectF(x, 0, tira, h), QColor(0, 0, 0, 150))
            alto = tira * 0.55
            for y in range(int(tira * 0.4), h, int(tira * 1.15)):
                p.setBrush(QColor(255, 255, 255, 34))
                p.drawRoundedRect(QRectF(x + tira * 0.25, y, tira * 0.5, alto), 2, 2)


def _texto(p: QPainter, rect: QRectF, texto: str, puntos: float, color: str, negrita=False,
           alineacion=Qt.AlignmentFlag.AlignCenter):
    f = QFont()
    f.setFamilies(["Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"])
    f.setPixelSize(int(puntos))
    f.setBold(negrita)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(rect, alineacion, texto)


def _logo(p: QPainter, centro_x: float, y: float, alto: int, color: str = "#ffffff", izquierda: float | None = None):
    from cinema_licencias.ventanas import logo_cinema
    pm = logo_cinema(alto, color)
    if pm.isNull():
        return
    ancho = pm.width() / pm.devicePixelRatio()
    x = izquierda if izquierda is not None else centro_x - ancho / 2
    p.drawPixmap(QRectF(x, y, ancho, alto), pm, QRectF(pm.rect()))


def bienvenida(w: int = 328, h: int = 628) -> QImage:
    """Banner vertical de la izquierda (164x314 en pantalla normal; se dibuja al doble para pantallas HD)."""
    from cinema_licencias.ventanas import icono_cinema
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    _fondo(p, w, h, [(0.5, 0.25, 0.6, "#e50914", 120), (0.9, 0.85, 0.55, "#f5c518", 45),
                     (0.1, 0.9, 0.5, "#e50914", 50)])
    logo = icono_cinema(512)
    p.drawPixmap(QRectF(w / 2 - 72, 112, 144, 144), logo, QRectF(logo.rect()))
    _texto(p, QRectF(0, 286, w, 40), "Administrador", 33, "#ffffff", True)
    _texto(p, QRectF(0, 324, w, 40), "de Licencias", 33, "#ffffff", True)
    _logo(p, w / 2, 382, 17)
    _texto(p, QRectF(0, 426, w, 24), "LEMON SQUEEZY · HOTMART", 13, "#a1a1aa", True)
    _texto(p, QRectF(0, 446, w, 24), "GUMROAD · POLAR", 13, "#a1a1aa", True)
    p.setPen(Qt.PenStyle.NoPen)
    for i, (color, _) in enumerate(PLATAFORMAS):
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(w / 2 - 36 + i * 24, 488), 6, 6)
    p.setBrush(QColor(255, 255, 255, 22))
    p.drawRoundedRect(QRectF(w / 2 - 56, h - 92, 112, 36), 18, 18)
    _texto(p, QRectF(w / 2 - 56, h - 92, 112, 36), f"versión {VERSION}", 16, "#f5f5f7", True)
    p.end()
    return img


def cabecera(w: int = 300, h: int = 114) -> QImage:
    """Banner de la esquina superior derecha (150x57 en pantalla normal)."""
    from cinema_licencias.ventanas import icono_cinema
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    _fondo(p, w, h, [(0.85, 0.4, 0.9, "#e50914", 110), (0.1, 1.0, 0.7, "#f5c518", 30)], perforaciones=False)
    logo = icono_cinema(256)
    p.drawPixmap(QRectF(w - 92, (h - 70) / 2, 70, 70), logo, QRectF(logo.rect()))
    _texto(p, QRectF(18, 18, w - 116, 32), "Administrador", 23, "#ffffff", True,
           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    _texto(p, QRectF(18, 46, w - 116, 32), "de Licencias", 23, "#d4d4d8", True,
           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    _logo(p, 0, 84, 10, "#a1a1aa", izquierda=19)
    p.end()
    return img


def guardar_bmp(img: QImage, destino: Path):
    png = destino.with_suffix(".tmp.png")
    img.save(str(png))
    Image.open(png).convert("RGB").save(destino, "BMP")
    png.unlink()


def main():
    global _APP
    _APP = QApplication.instance() or QApplication([])   # Qt necesita una aplicación para dibujar
    from cinema_licencias.ventanas import icono_cinema
    SALIDA.mkdir(exist_ok=True)
    guardar_bmp(bienvenida(), SALIDA / "bienvenida.bmp")
    guardar_bmp(cabecera(), SALIDA / "cabecera.bmp")
    icono_cinema(256).save(str(SALIDA / "icono.png"))
    Image.open(SALIDA / "icono.png").save(SALIDA / "icono.ico",
                                          sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    shutil.copy(SALIDA / "icono.ico", AQUI.parent / "administrador" / "icono.ico")
    print("Imágenes creadas en", SALIDA, "— Cinema Productions")


if __name__ == "__main__":
    main()
