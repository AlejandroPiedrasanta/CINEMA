"""Dibuja las imágenes del instalador (banners y el icono) con el mismo estilo del Administrador.

    pip install pyside6 pillow
    python crear_imagenes.py

Crea en imagenes/: bienvenida.bmp (banner lateral de las páginas de bienvenida y final),
cabecera.bmp (banner de la parte de arriba), icono.ico y icono.png. También copia el icono
a ../administrador/icono.ico para el ejecutable.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "administrador"))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

VERSION = "4.0"
SALIDA = AQUI / "imagenes"


def _fondo(p: QPainter, w: int, h: int, luces):
    grad = QLinearGradient(0, 0, w * 0.4, h)
    grad.setColorAt(0, QColor("#1d1840"))
    grad.setColorAt(1, QColor("#0b1222"))
    p.fillRect(0, 0, w, h, grad)
    for x, y, r, color, alfa in luces:
        radial = QRadialGradient(QPointF(w * x, h * y), max(w, h) * r)
        c1, c2 = QColor(color), QColor(color)
        c1.setAlpha(alfa)
        c2.setAlpha(0)
        radial.setColorAt(0, c1)
        radial.setColorAt(1, c2)
        p.fillRect(0, 0, w, h, radial)
    # líneas diagonales muy suaves
    p.setPen(QColor(255, 255, 255, 10))
    for i in range(-h, w, 26):
        p.drawLine(i, 0, i + h, h)


def _texto(p: QPainter, rect: QRectF, texto: str, puntos: float, color: str, negrita=False,
           alineacion=Qt.AlignmentFlag.AlignCenter):
    f = QFont()
    f.setFamilies(["Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"])
    f.setPixelSize(int(puntos))
    f.setBold(negrita)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(rect, alineacion, texto)


def bienvenida(w: int = 328, h: int = 628) -> QImage:
    """Banner vertical de la izquierda (164x314 en pantalla normal; se dibuja al doble para pantallas HD)."""
    from interfaz import icono_app
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    _fondo(p, w, h, [(0.15, 0.22, 0.55, "#7c5cff", 120), (0.95, 0.55, 0.5, "#4f8cff", 90),
                     (0.25, 0.95, 0.45, "#f472b6", 70)])
    # halo detrás del logo
    halo = QRadialGradient(QPointF(w / 2, 200), 120)
    c = QColor("#7c5cff")
    c.setAlpha(110)
    halo.setColorAt(0, c)
    c.setAlpha(0)
    halo.setColorAt(1, c)
    p.fillRect(0, 0, w, h, halo)
    logo = icono_app().pixmap(256, 256)
    p.drawPixmap(QRectF(w / 2 - 68, 132, 136, 136), logo, QRectF(logo.rect()))
    _texto(p, QRectF(0, 300, w, 40), "Administrador", 34, "#ffffff", True)
    _texto(p, QRectF(0, 340, w, 40), "de Licencias", 34, "#ffffff", True)
    _texto(p, QRectF(0, 398, w, 26), "LEMON SQUEEZY · HOTMART · GUMROAD", 15, "#aab2c8", True)
    # puntos de colores de las plataformas
    for i, color in enumerate(("#facc15", "#f97316", "#ff90e8")):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(w / 2 - 24 + i * 24, 444), 6, 6)
    # versión
    p.setBrush(QColor(255, 255, 255, 22))
    p.drawRoundedRect(QRectF(w / 2 - 52, h - 92, 104, 36), 18, 18)
    _texto(p, QRectF(w / 2 - 52, h - 92, 104, 36), f"versión {VERSION}", 16, "#e8ebf3", True)
    p.end()
    return img


def cabecera(w: int = 300, h: int = 114) -> QImage:
    """Banner de la esquina superior derecha (150x57 en pantalla normal)."""
    from interfaz import icono_app
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    _fondo(p, w, h, [(0.85, 0.3, 0.9, "#7c5cff", 120), (0.1, 1.0, 0.7, "#4f8cff", 80)])
    logo = icono_app().pixmap(256, 256)
    p.drawPixmap(QRectF(w - 96, (h - 72) / 2, 72, 72), logo, QRectF(logo.rect()))
    _texto(p, QRectF(18, 24, w - 120, 34), "Administrador", 24, "#ffffff", True,
           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    _texto(p, QRectF(18, 56, w - 120, 34), "de Licencias", 24, "#c9cfe0", True,
           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
    from interfaz import icono_app
    SALIDA.mkdir(exist_ok=True)
    guardar_bmp(bienvenida(), SALIDA / "bienvenida.bmp")
    guardar_bmp(cabecera(), SALIDA / "cabecera.bmp")
    icono_app().pixmap(256, 256).save(str(SALIDA / "icono.png"))
    Image.open(SALIDA / "icono.png").save(SALIDA / "icono.ico",
                                          sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    shutil.copy(SALIDA / "icono.ico", AQUI.parent / "administrador" / "icono.ico")
    print("Imágenes creadas en", SALIDA)


if __name__ == "__main__":
    main()
