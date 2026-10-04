"""Cinema Productions · ventanas sin marco con botones dibujados (minimizar, maximizar y cerrar).

Piezas que comparten el Administrador de Licencias y las ventanas de cinema_licencias:
  - BarraTitulo: barra propia que mueve la ventana (doble clic = maximizar) con BotonVentana dibujados.
  - instalar_agarraderas(): bordes para cambiar el tamaño de una ventana sin marco.
  - DialogoSinMarco: diálogo con esquinas redondeadas, sombra y animación al abrir y cerrar.
  - Mensaje / preguntar() / informar() / pedir_texto(): reemplazos de QMessageBox y QInputDialog.
  - Notificacion: aviso flotante en la esquina de la pantalla.
  - icono_cinema() y logo_cinema(): la marca Cinema Productions.

Los colores salen de PALETA (el Administrador la cambia según el tema elegido).

Creado por Cinema Productions.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QEvent, QObject, QParallelAnimationGroup, QPoint, QPointF,
                            QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QGuiApplication, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

__author__ = "Cinema Productions"

MARCA = "Cinema Productions"
RECURSOS = Path(__file__).resolve().with_name("recursos")

PALETA_OSCURA = {
    "fondo": "#0b0b0d", "panel": "#141417", "panel2": "#1c1c21", "borde": "#26262c", "borde2": "#34343c",
    "texto": "#ececf1", "suave": "#a1a1aa", "tenue": "#6b6b76", "titulo": "#ffffff",
    "acento": "#e50914", "acento2": "#ff5a36", "sobre_acento": "#ffffff", "oro": "#f5c518",
    "ok": "#22c55e", "aviso": "#f59e0b", "error": "#ef4444", "info": "#38bdf8", "sombra": "#000000",
}
PALETA_CLARA = {
    "fondo": "#f6f6f8", "panel": "#ffffff", "panel2": "#f1f1f4", "borde": "#e2e2e8", "borde2": "#cfcfd8",
    "texto": "#18181b", "suave": "#52525b", "tenue": "#8a8a96", "titulo": "#09090b",
    "acento": "#d10812", "acento2": "#f04a26", "sobre_acento": "#ffffff", "oro": "#b98900",
    "ok": "#15803d", "aviso": "#b45309", "error": "#dc2626", "info": "#0369a1", "sombra": "#1e1e28",
}
PALETA = dict(PALETA_OSCURA)
ANIM = {"factor": 1.0}          # 0 = sin animaciones; 1 = normal; 1.4 = más suaves

ESPACIO = 4                     # cuadrícula de 4 px
ALTO_BARRA = 36
RADIO = 12
CERRAR_ROJO = "#e81123"


def fijar_paleta(colores: dict) -> None:
    PALETA.update(colores)


def dur(ms: int) -> int:
    """Duración de una animación según la velocidad elegida (0 = desactivadas)."""
    return int(ms * ANIM["factor"]) if ANIM["factor"] > 0 else 0


def mezclar(a: str | QColor, b: str | QColor, t: float) -> QColor:
    a, b = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t), int(a.alpha() + (b.alpha() - a.alpha()) * t))


def tinte(color: str, alfa: float = 0.14) -> str:
    """rgba() para QSS (Qt lee los #RRGGBBAA al revés)."""
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {int(alfa * 255)})"


# ============================================================ marca

def icono_cinema(tam: int = 256) -> QPixmap:
    """Icono de la marca: carrete de cine rojo que forma la cabeza de una llave dorada."""
    pm = QPixmap(tam, tam)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(tam / 64, tam / 64)                 # se dibuja en una cuadrícula de 64x64
    fondo = QLinearGradient(0, 0, 64, 64)
    fondo.setColorAt(0, QColor("#23232a"))
    fondo.setColorAt(1, QColor("#07070a"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fondo)
    p.drawRoundedRect(QRectF(0, 0, 64, 64), 14, 14)
    brillo = QRadialGradient(QPointF(22, 32), 34)
    rojo = QColor("#e50914")
    rojo.setAlpha(95)
    brillo.setColorAt(0, rojo)
    rojo.setAlpha(0)
    brillo.setColorAt(1, rojo)
    p.setBrush(brillo)
    p.drawRoundedRect(QRectF(0, 0, 64, 64), 14, 14)
    oro = QLinearGradient(30, 26, 58, 42)
    oro.setColorAt(0, QColor("#ffe066"))
    oro.setColorAt(1, QColor("#d99a00"))
    p.setBrush(oro)
    p.drawRoundedRect(QRectF(30, 28.5, 27, 7), 2.5, 2.5)        # vástago
    p.drawRoundedRect(QRectF(47, 33, 5.5, 10.5), 1.6, 1.6)      # dientes
    p.drawRoundedRect(QRectF(39.5, 33, 4.5, 7), 1.6, 1.6)
    carrete = QLinearGradient(9, 19, 35, 45)
    carrete.setColorAt(0, QColor("#ff4040"))
    carrete.setColorAt(1, QColor("#a8050d"))
    p.setBrush(carrete)
    p.drawEllipse(QPointF(22, 32), 13.5, 13.5)
    p.setBrush(QColor("#0b0b0d"))
    for i in range(5):
        ang = math.radians(-90 + i * 72)
        p.drawEllipse(QPointF(22 + 7 * math.cos(ang), 32 + 7 * math.sin(ang)), 3.1, 3.1)
    p.drawEllipse(QPointF(22, 32), 1.7, 1.7)
    p.end()
    return pm


def icono_app() -> QIcon:
    icono = QIcon()
    for tam in (16, 24, 32, 48, 64, 128, 256):
        icono.addPixmap(icono_cinema(tam))
    return icono


def logo_cinema(alto: int = 20, color: str | None = None) -> QPixmap:
    """Logotipo 'CINEMA PRODUCTIONS' (blanco) escalado a 'alto' píxeles; con color lo vuelve a teñir."""
    original = QPixmap(str(RECURSOS / "cinema_productions.png"))
    if original.isNull():
        return QPixmap()
    pantalla = QGuiApplication.primaryScreen()
    dpr = pantalla.devicePixelRatio() if pantalla else 1.0
    pm = original.scaledToHeight(max(1, int(alto * dpr)), Qt.TransformationMode.SmoothTransformation)
    if color:
        p = QPainter(pm)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(pm.rect(), QColor(color))
        p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


# ============================================================ botones de la ventana

class BotonVentana(QAbstractButton):
    """Botón de la barra de título dibujado a mano: min, max, cerrar u ojo (modo privado)."""

    TIPOS = {"min": "Minimizar", "max": "Maximizar", "cerrar": "Cerrar", "ojo": "Ocultar nombres y correos",
             "tema": "Cambiar tema"}

    def __init__(self, tipo: str, parent=None):
        super().__init__(parent)
        self.tipo = tipo
        self.maximizada = False
        self.radio_esquina = 0.0
        self.setCheckable(tipo == "ojo")
        self.setFixedSize(46 if tipo in ("min", "max", "cerrar") else 40, ALTO_BARRA)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(self.TIPOS.get(tipo, ""))
        self.setAccessibleName(self.TIPOS.get(tipo, tipo))
        self._h = 0.0
        self._anim = QVariantAnimation(self, duration=150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._fijar)

    def _fijar(self, v):
        self._h = float(v)
        self.update()

    def _hacia(self, destino: float):
        self._anim.stop()
        if not dur(1):
            self._fijar(destino)
            return
        self._anim.setDuration(dur(150))
        self._anim.setStartValue(self._h)
        self._anim.setEndValue(destino)
        self._anim.start()

    def enterEvent(self, e):
        self._hacia(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hacia(0.0)
        super().leaveEvent(e)

    def sizeHint(self) -> QSize:
        return self.size()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        presion = 0.25 if self.isDown() else 0.0
        if self.tipo == "cerrar":
            fondo = QColor(CERRAR_ROJO)
            fondo.setAlpha(int(255 * min(1.0, self._h)))
            if self.isDown():
                fondo = fondo.darker(118)
        else:
            fondo = QColor(PALETA["texto"])
            fondo.setAlpha(int(255 * (0.08 * self._h + presion * 0.1)))
        camino = QPainterPath()
        if self.radio_esquina and self.tipo == "cerrar":
            rr = self.radio_esquina
            camino.moveTo(r.left(), r.top())
            camino.lineTo(r.right() - rr, r.top())
            camino.arcTo(QRectF(r.right() - 2 * rr, r.top(), 2 * rr, 2 * rr), 90, -90)
            camino.lineTo(r.right(), r.bottom())
            camino.lineTo(r.left(), r.bottom())
            camino.closeSubpath()
        else:
            camino.addRect(r)
        p.fillPath(camino, fondo)
        activo = self.isChecked() and self.tipo == "ojo"
        base = PALETA["acento"] if activo else PALETA["suave"]
        color = mezclar(base, "#ffffff" if self.tipo == "cerrar" else PALETA["texto"], self._h)
        if not self.isEnabled():
            color = QColor(PALETA["tenue"])
        pen = QPen(color, 1.1)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = round(r.center().x()) + 0.5, round(r.center().y()) + 0.5
        if self.tipo == "min":
            p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
        elif self.tipo == "max":
            if self.maximizada:     # "restaurar": dos ventanas superpuestas
                p.drawRect(QRectF(cx - 5, cy - 3, 8, 8))
                atras = QPainterPath(QPointF(cx - 3, cy - 3))
                atras.lineTo(cx - 3, cy - 5)
                atras.lineTo(cx + 5, cy - 5)
                atras.lineTo(cx + 5, cy + 3)
                atras.lineTo(cx + 3, cy + 3)
                p.drawPath(atras)
            else:
                p.drawRect(QRectF(cx - 5, cy - 5, 10, 10))
        elif self.tipo == "cerrar":
            p.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))
            p.drawLine(QPointF(cx + 5, cy - 5), QPointF(cx - 5, cy + 5))
        elif self.tipo == "ojo":
            ojo = QPainterPath(QPointF(cx - 8, cy))
            ojo.quadTo(QPointF(cx, cy - 8.5), QPointF(cx + 8, cy))
            ojo.quadTo(QPointF(cx, cy + 8.5), QPointF(cx - 8, cy))
            p.drawPath(ojo)
            p.drawEllipse(QPointF(cx, cy), 2.6, 2.6)
            if activo:
                p.drawLine(QPointF(cx - 7, cy + 7), QPointF(cx + 7, cy - 7))
        elif self.tipo == "tema":
            p.drawEllipse(QPointF(cx, cy), 6.5, 6.5)
            mitad = QPainterPath()
            mitad.moveTo(cx, cy - 6.5)
            mitad.arcTo(QRectF(cx - 6.5, cy - 6.5, 13, 13), 90, -180)
            mitad.closeSubpath()
            p.fillPath(mitad, color)


class BarraTitulo(QWidget):
    """Barra de título propia: arrastrar mueve la ventana, doble clic la maximiza."""

    def __init__(self, ventana: QWidget, titulo: str = "", icono: QIcon | None = None,
                 botones=("min", "max", "cerrar"), alto: int = ALTO_BARRA):
        super().__init__(ventana, objectName="barraTitulo")
        self.ventana = ventana
        self.setFixedHeight(alto)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3 * ESPACIO, 0, 0, 0)
        lay.setSpacing(2 * ESPACIO)
        self.icono = QLabel()
        self.icono.setFixedSize(18, 18)
        self.icono.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icono = icono if icono is not None else ventana.windowIcon()
        if icono and not icono.isNull():
            self.icono.setPixmap(icono.pixmap(18, 18))
        self.titulo = QLabel(titulo or ventana.windowTitle(), objectName="barraTituloTexto")
        self.titulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self.icono)
        lay.addWidget(self.titulo)
        lay.addStretch(1)
        self.extras = QHBoxLayout()
        self.extras.setSpacing(0)
        lay.addLayout(self.extras)
        self.botones: dict[str, BotonVentana] = {}
        for tipo in botones:
            b = BotonVentana(tipo, self)
            self.botones[tipo] = b
            lay.addWidget(b)
        if "min" in self.botones:
            self.botones["min"].clicked.connect(self.minimizar)
        if "max" in self.botones:
            self.botones["max"].clicked.connect(self.alternar_maximizar)
        if "cerrar" in self.botones:
            # en los diálogos, reject() cierra con su animación; close() es para las ventanas normales
            self.botones["cerrar"].clicked.connect(
                lambda: self.ventana.reject() if isinstance(self.ventana, QDialog) else self.ventana.close())
        ventana.installEventFilter(self)
        ventana.windowTitleChanged.connect(self.titulo.setText)

    def agregar(self, widget: QWidget):
        """Botón o control extra a la izquierda de minimizar."""
        self.extras.addWidget(widget)

    def esquina(self, radio: float):
        if "cerrar" in self.botones:
            self.botones["cerrar"].radio_esquina = radio
            self.botones["cerrar"].update()

    def minimizar(self):
        objetivo = self.ventana
        # un diálogo modal minimizado se perdería: se minimiza toda la aplicación (su ventana dueña)
        if isinstance(objetivo, QDialog) and objetivo.parentWidget() is not None:
            objetivo = objetivo.parentWidget().window()
        objetivo.showMinimized()

    def alternar_maximizar(self):
        if "max" not in self.botones:
            return
        if self.ventana.isMaximized():
            self.ventana.showNormal()
        else:
            self.ventana.showMaximized()

    def eventFilter(self, obj, ev):
        if obj is self.ventana and ev.type() == QEvent.Type.WindowStateChange and "max" in self.botones:
            b = self.botones["max"]
            b.maximizada = self.ventana.isMaximized()
            b.setToolTip("Restaurar" if b.maximizada else "Maximizar")
            b.update()
        return False

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            ventana = self.window().windowHandle()
            if ventana is not None:
                ventana.startSystemMove()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.alternar_maximizar()
            e.accept()


# ============================================================ cambiar el tamaño

class _Agarradera(QWidget):
    def __init__(self, ventana: QWidget, bordes, cursor):
        super().__init__(ventana)
        self.bordes = bordes
        self.setCursor(cursor)

    def paintEvent(self, _):
        # casi invisible pero no del todo: en ventanas translúcidas un píxel 100 % transparente no recibe clics
        QPainter(self).fillRect(self.rect(), QColor(0, 0, 0, 1))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self.window().isMaximized():
            ventana = self.window().windowHandle()
            if ventana is not None:
                ventana.startSystemResize(self.bordes)
            e.accept()


class _Agarraderas(QObject):
    def __init__(self, ventana: QWidget, grosor: int, margen: int):
        super().__init__(ventana)
        self.ventana, self.grosor, self.margen = ventana, grosor, margen
        E, C = Qt.Edge, Qt.CursorShape
        self.piezas = {
            "izq": _Agarradera(ventana, E.LeftEdge, C.SizeHorCursor),
            "der": _Agarradera(ventana, E.RightEdge, C.SizeHorCursor),
            "arr": _Agarradera(ventana, E.TopEdge, C.SizeVerCursor),
            "aba": _Agarradera(ventana, E.BottomEdge, C.SizeVerCursor),
            "ai": _Agarradera(ventana, E.TopEdge | E.LeftEdge, C.SizeFDiagCursor),
            "ad": _Agarradera(ventana, E.TopEdge | E.RightEdge, C.SizeBDiagCursor),
            "bi": _Agarradera(ventana, E.BottomEdge | E.LeftEdge, C.SizeBDiagCursor),
            "bd": _Agarradera(ventana, E.BottomEdge | E.RightEdge, C.SizeFDiagCursor),
        }
        ventana.installEventFilter(self)
        self.reubicar()

    def reubicar(self):
        w, h, g, m = self.ventana.width(), self.ventana.height(), self.grosor, self.margen
        esquina = g * 2
        geo = {
            "izq": QRect(m, m + esquina, g, h - 2 * (m + esquina)),
            "der": QRect(w - m - g, m + esquina, g, h - 2 * (m + esquina)),
            "arr": QRect(m + esquina, m, w - 2 * (m + esquina), g),
            "aba": QRect(m + esquina, h - m - g, w - 2 * (m + esquina), g),
            "ai": QRect(m, m, esquina, esquina), "ad": QRect(w - m - esquina, m, esquina, esquina),
            "bi": QRect(m, h - m - esquina, esquina, esquina), "bd": QRect(w - m - esquina, h - m - esquina, esquina,
                                                                          esquina),
        }
        visibles = not self.ventana.isMaximized() and not self.ventana.isFullScreen()
        for clave, pieza in self.piezas.items():
            pieza.setGeometry(geo[clave])
            pieza.setVisible(visibles)
            pieza.raise_()

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.Resize, QEvent.Type.WindowStateChange, QEvent.Type.Show,
                         QEvent.Type.ChildAdded):
            QTimer.singleShot(0, self.reubicar)
        return False


def instalar_agarraderas(ventana: QWidget, grosor: int = 6, margen: int = 0) -> _Agarraderas:
    """Bordes invisibles para cambiar el tamaño de una ventana sin marco (con el sistema)."""
    return _Agarraderas(ventana, grosor, margen)


def esquinas_redondeadas_windows(ventana: QWidget) -> None:
    """En Windows 11 pide al sistema esquinas redondeadas también para la ventana sin marco."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        preferencia = ctypes.c_int(2)            # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(ventana.winId()), 33, ctypes.byref(preferencia),
                                                   ctypes.sizeof(preferencia))
    except Exception:  # noqa: BLE001
        pass


def banderas_sin_marco(dialogo: bool = False):
    base = Qt.WindowType.Dialog if dialogo else Qt.WindowType.Window
    return (base | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint)


# ============================================================ diálogo sin marco

class DialogoSinMarco(QDialog):
    """Diálogo con barra propia, esquinas redondeadas y sombra. El contenido va en self.cuerpo."""

    def __init__(self, parent=None, titulo: str = "", ancho: int = 0, redimensionable: bool = True,
                 botones=("min", "max", "cerrar"), icono: QIcon | None = None, margen_sombra: int = 16):
        super().__init__(parent)
        self.setObjectName("dialogoSinMarco")
        self.setWindowFlags(banderas_sin_marco(dialogo=True))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(titulo)
        if icono is not None:
            self.setWindowIcon(icono)
        self._margen = margen_sombra
        self._cerrando = False
        self._animado = False
        self.exterior = QVBoxLayout(self)
        self.exterior.setContentsMargins(*([margen_sombra] * 4))
        self.tarjeta = QFrame(self, objectName="dialogoTarjeta")
        self.tarjeta.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._sombra = QGraphicsDropShadowEffect(self.tarjeta, blurRadius=28, offset=QPoint(0, 8),
                                                 color=self._color_sombra())
        self.tarjeta.setGraphicsEffect(self._sombra)
        self.exterior.addWidget(self.tarjeta)
        t = QVBoxLayout(self.tarjeta)
        t.setContentsMargins(1, 1, 1, 1)
        t.setSpacing(0)
        self.barra = BarraTitulo(self, titulo, icono, botones)
        self.barra.esquina(RADIO - 1)
        t.addWidget(self.barra)
        self.contenido = QWidget(objectName="dialogoContenido")
        t.addWidget(self.contenido, 1)
        self.cuerpo = QVBoxLayout(self.contenido)
        self.cuerpo.setContentsMargins(6 * ESPACIO, 2 * ESPACIO, 6 * ESPACIO, 5 * ESPACIO)
        self.cuerpo.setSpacing(3 * ESPACIO)
        if ancho:
            # ancho mínimo con un espaciador: un setMinimumWidth() anularía el mínimo que pide el contenido
            # y los botones quedarían recortados
            self.exterior.setSpacing(0)
            self.exterior.addSpacerItem(QSpacerItem(ancho, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
        self._agarraderas = instalar_agarraderas(self, 6, margen_sombra) if redimensionable else None

    @staticmethod
    def _color_sombra() -> QColor:
        c = QColor(PALETA.get("sombra", "#000000"))
        c.setAlpha(150 if QColor(PALETA["fondo"]).lightness() < 128 else 60)
        return c

    def changeEvent(self, e):
        if e.type() == QEvent.Type.WindowStateChange:
            maxi = self.isMaximized()
            self.exterior.setContentsMargins(*([0 if maxi else self._margen] * 4))
            self.tarjeta.setProperty("maximizada", maxi)
            self.tarjeta.style().unpolish(self.tarjeta)
            self.tarjeta.style().polish(self.tarjeta)
            self._sombra.setEnabled(not maxi)
            self.barra.esquina(0 if maxi else RADIO - 1)
        super().changeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        if self._animado or not dur(1):
            return
        self._animado = True
        final = self.pos()
        self.setWindowOpacity(0.0)
        grupo = QParallelAnimationGroup(self)
        opacidad = QPropertyAnimation(self, b"windowOpacity")
        opacidad.setStartValue(0.0)
        opacidad.setEndValue(1.0)
        mover = QPropertyAnimation(self, b"pos")
        mover.setStartValue(final + QPoint(0, 14))
        mover.setEndValue(final)
        for a in (opacidad, mover):
            a.setDuration(dur(240))
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            grupo.addAnimation(a)
        grupo.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)

    def closeEvent(self, e):
        # Cierre pedido por el sistema o al salir del programa: sin animación. Si el diálogo "esperara" a la
        # animación, Qt entendería que rechazó cerrarse y cancelaría la salida de la aplicación.
        self._sin_animacion = True
        try:
            super().closeEvent(e)
        finally:
            self._sin_animacion = False

    def done(self, resultado):
        if getattr(self, "_sin_animacion", False) or not dur(1) or not self.isVisible():
            self._cerrando = False
            super().done(resultado)
            return
        if self._cerrando:
            return
        self._cerrando = True
        salida = QPropertyAnimation(self, b"windowOpacity", self)
        salida.setDuration(dur(140))
        salida.setStartValue(self.windowOpacity())
        salida.setEndValue(0.0)

        def fin():
            if not self._cerrando:      # ya se cerró de otra forma mientras se animaba
                return
            QDialog.done(self, resultado)
            self._cerrando = False
            self._animado = False
            self.setWindowOpacity(1.0)

        salida.finished.connect(fin)
        salida.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


# ============================================================ mensajes

class IconoEstado(QWidget):
    """Círculo de color con un símbolo (?, !, i, ✓, ✕) que aparece con un pequeño rebote."""

    SIMBOLOS = {"pregunta": ("?", "info"), "peligro": ("!", "error"), "aviso": ("!", "aviso"),
                "info": ("i", "info"), "ok": ("✓", "ok"), "error": ("✕", "error")}

    def __init__(self, tipo: str = "info", tam: int = 48, latir: bool = False):
        super().__init__()
        self.setFixedSize(tam, tam)
        self.simbolo, clave = self.SIMBOLOS.get(tipo, self.SIMBOLOS["info"])
        self.color = QColor(PALETA[clave])
        self._p = 0.0 if dur(1) else 1.0
        self._pulso = 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=dur(520))
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.valueChanged.connect(self._fijar)
        self._latido = None
        if latir and dur(1):
            self._latido = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1600)
            self._latido.setLoopCount(-1)
            self._latido.valueChanged.connect(self._pulsar)

    def _fijar(self, v):
        self._p = float(v)
        self.update()

    def _pulsar(self, v):
        self._pulso = float(v)
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if dur(1) and self._p == 0.0:
            QTimer.singleShot(60, self._anim.start)
        if self._latido:
            self._latido.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        radio = self.width() / 2 - 2
        if self._latido:
            onda = QColor(self.color)
            onda.setAlpha(int(70 * (1 - self._pulso)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(onda)
            r = radio * (0.7 + 0.3 * self._pulso)
            p.drawEllipse(c, r, r)
        escala = max(0.0, self._p)
        fondo = QColor(self.color)
        fondo.setAlpha(46)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fondo)
        p.drawEllipse(c, radio * 0.86 * escala, radio * 0.86 * escala)
        p.setPen(QPen(self.color, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, radio * 0.86 * escala, radio * 0.86 * escala)
        if escala > 0.3:
            f = self.font()
            f.setPixelSize(max(8, int(radio * 0.95 * min(1.0, escala))))
            f.setBold(True)
            p.setFont(f)
            p.setPen(self.color)
            p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self.simbolo)


def boton_dialogo(texto: str, estilo: str = "secundario") -> QPushButton:
    b = QPushButton(texto, objectName=estilo)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setAutoDefault(False)
    b.setMinimumHeight(9 * ESPACIO)
    return b


class Mensaje(DialogoSinMarco):
    """Ventana de mensaje con icono, texto y botones (reemplaza a QMessageBox)."""

    def __init__(self, parent, titulo: str, texto: str, tipo: str = "info",
                 botones=(("Entendido", "primario", True),), detalle: str = ""):
        super().__init__(parent, titulo, ancho=440, redimensionable=False)
        self.respuesta = None
        icono = IconoEstado(tipo, 52)
        textos = QVBoxLayout()
        textos.setSpacing(ESPACIO)
        cab = QLabel(titulo, objectName="mensajeTitulo")
        cab.setWordWrap(True)
        cuerpo = QLabel(texto, objectName="mensajeTexto")
        cuerpo.setWordWrap(True)
        cuerpo.setTextFormat(Qt.TextFormat.RichText)
        cuerpo.setOpenExternalLinks(True)
        cuerpo.setMinimumWidth(300)
        textos.addWidget(cab)
        textos.addWidget(cuerpo)
        if detalle:
            d = QLabel(detalle, objectName="mensajeDetalle")
            d.setWordWrap(True)
            textos.addWidget(d)
        arriba = QHBoxLayout()
        arriba.setSpacing(4 * ESPACIO)
        arriba.addWidget(icono, 0, Qt.AlignmentFlag.AlignTop)
        arriba.addLayout(textos, 1)
        self.cuerpo.addLayout(arriba)
        self.cuerpo.addSpacing(2 * ESPACIO)
        fila = QHBoxLayout()
        fila.addStretch(1)
        self.campo: QLineEdit | None = None
        for i, (texto_b, estilo, valor) in enumerate(botones):
            b = boton_dialogo(texto_b, estilo)
            b.clicked.connect(lambda _=False, v=valor: self._elegir(v))
            if i == len(botones) - 1:
                b.setDefault(True)
            fila.addWidget(b)
        self.fila_botones = fila
        self.cuerpo.addLayout(fila)

    def _elegir(self, valor):
        self.respuesta = valor
        self.accept()


def preguntar(parent, titulo: str, texto: str, si: str = "Sí, continuar", no: str = "Cancelar",
              peligro: bool = True) -> bool:
    m = Mensaje(parent, titulo, texto, "peligro" if peligro else "pregunta",
                ((no, "secundario", False), (si, "peligro" if peligro else "primario", True)))
    m.exec()
    return m.respuesta is True


def informar(parent, titulo: str, texto: str, tipo: str = "info", boton: str = "Entendido") -> None:
    Mensaje(parent, titulo, texto, tipo, ((boton, "primario", True),)).exec()


def pedir_texto(parent, titulo: str, etiqueta: str, texto: str = "", marcador: str = "") -> str | None:
    m = Mensaje(parent, titulo, etiqueta, "pregunta", (("Cancelar", "secundario", False), ("Aceptar", "primario", True)))
    campo = QLineEdit(texto, placeholderText=marcador)
    campo.returnPressed.connect(lambda: m._elegir(True))
    m.cuerpo.insertWidget(m.cuerpo.count() - 1, campo)
    QTimer.singleShot(0, campo.setFocus)
    m.exec()
    return campo.text().strip() if m.respuesta is True else None


# ============================================================ notificación flotante

class Notificacion(QWidget):
    """Aviso que aparece en la esquina inferior derecha de la pantalla y se va solo."""

    _activas: list["Notificacion"] = []
    cerrada = Signal()

    def __init__(self, titulo: str, texto: str = "", tipo: str = "info", segundos: float = 6):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(12, 12, 12, 12)
        caja = QFrame(objectName="notificacion")
        caja.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        caja.setGraphicsEffect(QGraphicsDropShadowEffect(caja, blurRadius=24, offset=QPoint(0, 6),
                                                         color=DialogoSinMarco._color_sombra()))
        exterior.addWidget(caja)
        lay = QHBoxLayout(caja)
        lay.setContentsMargins(4 * ESPACIO, 3 * ESPACIO, 4 * ESPACIO, 3 * ESPACIO)
        lay.setSpacing(3 * ESPACIO)
        lay.addWidget(IconoEstado(tipo, 34), 0, Qt.AlignmentFlag.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        t = QLabel(titulo, objectName="mensajeTitulo")
        t.setWordWrap(True)
        textos.addWidget(t)
        if texto:
            d = QLabel(texto, objectName="mensajeTexto")
            d.setWordWrap(True)
            textos.addWidget(d)
        lay.addLayout(textos, 1)
        self.setFixedWidth(380)
        self.adjustSize()
        self._segundos = segundos

    def mostrar(self):
        pantalla = QGuiApplication.primaryScreen()
        zona = pantalla.availableGeometry() if pantalla else QRect(0, 0, 1280, 800)
        y = zona.bottom() - 8
        for n in Notificacion._activas:
            y -= n.height()
        destino = QPoint(zona.right() - self.width() - 8, y - self.height())
        Notificacion._activas.append(self)
        self.move(destino + QPoint(0, 30 if dur(1) else 0))
        self.setWindowOpacity(0.0 if dur(1) else 1.0)
        self.show()
        if dur(1):
            grupo = QParallelAnimationGroup(self)
            for prop, ini, fin in ((b"pos", destino + QPoint(0, 30), destino), (b"windowOpacity", 0.0, 1.0)):
                a = QPropertyAnimation(self, prop)
                a.setStartValue(ini)
                a.setEndValue(fin)
                a.setDuration(dur(320))
                a.setEasingCurve(QEasingCurve.Type.OutBack if prop == b"pos" else QEasingCurve.Type.OutCubic)
                grupo.addAnimation(a)
            grupo.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)
        QTimer.singleShot(int(self._segundos * 1000), self._salir)
        return self

    def mousePressEvent(self, e):
        self._salir()

    def _salir(self):
        if self not in Notificacion._activas:
            return
        Notificacion._activas.remove(self)
        if not dur(1):
            self.close()
            return
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(dur(260))
        a.setEndValue(0.0)
        a.finished.connect(self.close)
        a.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def closeEvent(self, e):
        self.cerrada.emit()
        super().closeEvent(e)


def notificar(titulo: str, texto: str = "", tipo: str = "info", segundos: float = 6) -> Notificacion:
    return Notificacion(titulo, texto, tipo, segundos).mostrar()


# ============================================================ estilos

def qss_ventanas(P: dict | None = None) -> str:
    """Estilos de la barra de título, los diálogos sin marco y los mensajes."""
    P = P or PALETA
    return f"""
QDialog#dialogoSinMarco {{ background: transparent; }}
QWidget#barraTitulo {{ background: transparent; }}
QLabel#barraTituloTexto {{ color: {P['suave']}; font-size: 12px; font-weight: 600; background: transparent; }}
QFrame#dialogoTarjeta {{ background: {P['panel']}; border: 1px solid {P['borde2']}; border-radius: {RADIO}px; }}
QFrame#dialogoTarjeta[maximizada="true"] {{ border-radius: 0px; border: none; }}
QWidget#dialogoContenido {{ background: transparent; }}
QLabel#mensajeTitulo {{ color: {P['titulo']}; font-size: 16px; font-weight: 700; background: transparent; }}
QLabel#mensajeTexto {{ color: {P['suave']}; font-size: 13px; background: transparent; }}
QLabel#mensajeDetalle {{ color: {P['tenue']}; font-size: 12px; background: transparent; }}
QFrame#notificacion {{ background: {P['panel2']}; border: 1px solid {P['borde2']}; border-radius: {RADIO}px; }}
"""


def qss_dialogos(P: dict | None = None) -> str:
    """Estilo completo para las ventanas de cinema_licencias dentro de cualquier programa."""
    P = P or PALETA
    return qss_ventanas(P) + f"""
QWidget {{ color: {P['texto']}; font-size: 13px; }}
QLabel {{ background: transparent; }}
QLabel#titulo {{ font-size: 22px; font-weight: 800; color: {P['titulo']}; }}
QLabel#sub {{ color: {P['suave']}; }}
QLabel#paso {{ color: {P['texto']}; font-weight: 600; }}
QLabel#tenue {{ color: {P['tenue']}; font-size: 11px; }}
QLabel#msg {{ color: {P['suave']}; min-height: 18px; }}
QLabel#msg[error="true"] {{ color: {P['error']}; }}
QLabel#msg[ok="true"] {{ color: {P['ok']}; }}
QLabel#dato {{ color: {P['titulo']}; font-weight: 600; }}
QLabel#datoTitulo {{ color: {P['tenue']}; font-size: 11px; font-weight: 700; }}
QFrame#banda {{ background: {tinte(P['error'], 0.12)}; border: 1px solid {tinte(P['error'], 0.35)};
               border-radius: 10px; }}
QFrame#banda[tipo="ok"] {{ background: {tinte(P['ok'], 0.12)}; border-color: {tinte(P['ok'], 0.35)}; }}
QFrame#banda[tipo="aviso"] {{ background: {tinte(P['aviso'], 0.12)}; border-color: {tinte(P['aviso'], 0.35)}; }}
QFrame#separador {{ background: {P['borde']}; min-height: 1px; max-height: 1px; }}
QLineEdit {{ background: {P['fondo']}; color: {P['titulo']}; border: 1px solid {P['borde2']}; border-radius: 10px;
            padding: 10px 12px; selection-background-color: {P['acento']}; }}
QLineEdit:focus {{ border: 1px solid {P['acento']}; }}
QLineEdit[error="true"] {{ border: 1px solid {P['error']}; }}
QPushButton {{ border-radius: 10px; padding: 8px 18px; font-weight: 600; }}
QPushButton#primario {{ color: {P['sobre_acento']}; border: none;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {P['acento']}, stop:1 {P['acento2']}); }}
QPushButton#primario:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {QColor(P['acento']).lighter(115).name()},
    stop:1 {QColor(P['acento2']).lighter(115).name()}); }}
QPushButton#primario:pressed {{ background: {P['acento']}; }}
QPushButton#primario:disabled {{ background: {P['panel2']}; color: {P['tenue']}; }}
QPushButton#secundario {{ background: {P['panel2']}; color: {P['texto']}; border: 1px solid {P['borde2']}; }}
QPushButton#secundario:hover {{ border-color: {P['suave']}; }}
QPushButton#secundario:pressed {{ background: {P['borde']}; }}
QPushButton#secundario:disabled {{ color: {P['tenue']}; border-color: {P['borde']}; }}
QPushButton#peligro {{ background: {tinte(P['error'], 0.14)}; color: {P['error']}; border: 1px solid {tinte(P['error'], 0.4)}; }}
QPushButton#peligro:hover {{ background: {tinte(P['error'], 0.24)}; }}
QPushButton#comprar {{ background: {P['panel2']}; color: {P['titulo']}; border: 1px solid {P['borde2']}; padding: 10px; }}
QPushButton#comprar:hover {{ border-color: {P['acento']}; color: {P['titulo']}; }}
QPushButton#enlace {{ background: transparent; border: none; color: {P['info']}; padding: 6px 4px; }}
QPushButton#enlace:hover {{ text-decoration: underline; }}
QPushButton#whatsapp {{ background: transparent; color: #25d366; border: 1px solid {tinte('#25d366', 0.4)}; }}
QPushButton#whatsapp:hover {{ background: {tinte('#25d366', 0.12)}; }}
QToolTip {{ background: {P['panel2']}; color: {P['texto']}; border: 1px solid {P['borde2']}; padding: 6px 8px; }}
"""
