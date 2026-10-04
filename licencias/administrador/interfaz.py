"""Cinema Productions · Administrador de Licencias — componentes animados de la interfaz (PySide6).

Todos los colores salen del tema activo (temas.C). Las animaciones respetan la velocidad elegida en
Ajustes (0 = desactivadas).

Creado por Cinema Productions.
"""
from __future__ import annotations

import hashlib
import math

from PySide6.QtCore import (QEasingCurve, QEvent, QEventLoop, QObject, QParallelAnimationGroup, QPoint, QPointF,
                            QPropertyAnimation, QRectF, QRunnable, QSequentialAnimationGroup, QSize, Qt, QThreadPool,
                            QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QFrame,
                               QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QSizePolicy, QStackedWidget, QStyle, QStyledItemDelegate, QTableWidget,
                               QTableWidgetItem, QToolTip, QVBoxLayout, QWidget)

from temas import (C, DENSIDADES, ESP_MD, ESP_SM, ESP_XS, LETRA, RADIO_LG, RADIO_XL, aplicar_tema,
                   construir_qss)
from cinema_licencias.ventanas import (ANIM, MARCA, BarraTitulo, BotonVentana, DialogoSinMarco, IconoEstado,
                                       banderas_sin_marco, dur, esquinas_redondeadas_windows, icono_app,
                                       icono_cinema, informar, instalar_agarraderas, logo_cinema, mezclar, notificar,
                                       pedir_texto, preguntar, tinte)

__author__ = "Cinema Productions"
__all__ = ["ANIM", "C", "MARCA", "BarraTitulo", "BotonVentana", "IconoEstado", "aplicar_tema", "banderas_sin_marco",
           "construir_qss", "esquinas_redondeadas_windows", "icono_app", "icono_cinema", "informar",
           "instalar_agarraderas", "logo_cinema", "mezclar", "notificar", "pedir_texto", "preguntar", "tinte"]

ANIMACIONES = {"activas": True}
PRIVACIDAD = {"activa": False, "nombres": True, "correos": True, "claves": True}


def _oculto(que: str) -> bool:
    """True si el modo privado está activo y en Ajustes se eligió ocultar «que» (nombres, correos o claves)."""
    return bool(PRIVACIDAD["activa"] and PRIVACIDAD.get(que))
TABLA = {"alto": DENSIDADES["normal"]}
ESTADO_TOKEN = {
    "Activa": "ok", "Sin activar": "info", "Bloqueada": "error", "Vencida": "aviso", "Revocada": "error",
    "Pagada": "ok", "Aprobada": "ok", "Completada": "ok", "Reembolsada": "error", "Contracargo": "error",
    "Reembolso parcial": "aviso", "Cancelada": "tenue", "Anulada": "tenue", "Borrador": "tenue",
    "Pendiente": "info", "Esperando pago": "info", "Fallida": "error", "En disputa": "aviso",
    "En línea": "ok", "Suspendida": "error", "Retirada": "error",
}
FUENTE_MONO = ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "monospace"]
ROL_DATO = Qt.ItemDataRole.UserRole
ROL_COLOR = Qt.ItemDataRole.UserRole + 1
ROL_ORDEN = Qt.ItemDataRole.UserRole + 2


def ms(duracion: int) -> int:
    """Duración de una animación (0 si el usuario las desactivó)."""
    return dur(duracion)


def fijar_animaciones(activas: bool, velocidad: float = 1.0):
    ANIMACIONES["activas"] = bool(activas)
    ANIM["factor"] = float(velocidad) if activas else 0.0


def color_estado(texto: str) -> str:
    return C.get(ESTADO_TOKEN.get(texto, "suave"), C["suave"])


def legible(color: str) -> str:
    """En temas claros, los colores muy claros (amarillo de Lemon Squeezy…) se oscurecen para leerse."""
    c = QColor(color)
    if not C.get("oscuro", True) and c.lightness() > 150:
        return c.darker(175).name()
    return color


# ============================================================ privacidad

def _velar(palabra: str) -> str:
    return (palabra[:1] + "•" * min(5, max(2, len(palabra) - 1))) if palabra else ""


def priv_nombre(nombre: str | None) -> str:
    """'Juan Pérez' → 'J••• P••••' cuando el modo privado está activo."""
    if nombre and "@" in str(nombre):
        return priv_correo(nombre)
    if not nombre or not _oculto("nombres"):
        return nombre or ""
    return " ".join(_velar(p) for p in str(nombre).split())


def priv_correo(correo: str | None) -> str:
    """'juan@gmail.com' → 'j•••@g••••.com' cuando el modo privado está activo."""
    if not correo or not _oculto("correos") or "@" not in str(correo):
        return correo or ""
    usuario, _, dominio = str(correo).partition("@")
    nombre, punto, final = dominio.rpartition(".")
    return f"{_velar(usuario)}@{_velar(nombre or dominio)}{punto}{final if nombre else ''}"


def priv_clave(clave: str | None) -> str:
    if not clave or not _oculto("claves"):
        return clave or ""
    return f"••••-••••-{str(clave)[-4:]}"


def priv_tel(tel: str | None) -> str:
    if not tel or not PRIVACIDAD["activa"]:
        return tel or ""
    return "•" * max(0, len(tel) - 3) + tel[-3:]


def priv_equipo(nombre: str | None) -> str:
    return priv_nombre(nombre) if nombre else ""


# ============================================================ pequeñas piezas

def estilo_pildora(etiqueta_: QLabel, texto: str, color: str):
    etiqueta_.setText(texto)
    etiqueta_.setStyleSheet(f"color:{legible(color)}; background:{tinte(color)}; border-radius:12px; "
                            "padding:2px 12px; font-weight:700;")


def pildora(texto: str = "", color: str | None = None) -> QLabel:
    """Etiqueta de estado redondeada (Activa, Conectado, Modo prueba…)."""
    l = QLabel()
    l.setFixedHeight(24)
    l.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    estilo_pildora(l, texto, color or C["suave"])
    return l


def insignia_icono(icono: str, color: str, tam: int = 52) -> QLabel:
    l = QLabel(icono)
    l.setAlignment(Qt.AlignmentFlag.AlignCenter)
    l.setFixedSize(tam, tam)
    l.setStyleSheet(f"font-size:{int(tam * 0.5)}px; background:{tinte(color, 0.16)}; border-radius:{tam // 3}px;")
    return l


class Avatar(QWidget):
    """Círculo con las iniciales de la persona y un color fijo según su nombre o correo."""

    PALETA = ("#e50914", "#7c5cff", "#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#8b5cf6", "#ef4444")

    def __init__(self, nombre: str = "", clave: str = "", tam: int = 40):
        super().__init__()
        self.setFixedSize(tam, tam)
        self.fijar(nombre, clave)

    def fijar(self, nombre: str, clave: str = ""):
        partes = [p for p in (nombre or "").replace("@", " ").split() if p]
        self.iniciales = "".join(p[0] for p in partes[:2]).upper() or "?"
        if _oculto("nombres"):
            self.iniciales = self.iniciales[:1]
        h = int(hashlib.md5((clave or nombre or "?").lower().encode()).hexdigest()[:6], 16)
        self.color = QColor(self.PALETA[h % len(self.PALETA)])
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, self.color.lighter(120))
        grad.setColorAt(1, self.color.darker(130))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(r)
        f = QFont(self.font())
        f.setPixelSize(int(self.height() * 0.38))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.iniciales)


# ============================================================ tareas en segundo plano

class _Senales(QObject):
    ok = Signal(object)
    error = Signal(str)


class Tarea(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args, self.senales = fn, args, _Senales()

    def run(self):
        try:
            self.senales.ok.emit(self.fn(*self.args))
        except Exception as e:  # noqa: BLE001
            self.senales.error.emit(str(e) or e.__class__.__name__)


_TAREAS: set[Tarea] = set()


def en_hilo(fn, *args, ok=None, error=None):
    """Ejecuta fn(*args) fuera de la interfaz; ok(resultado) o error(texto) vuelven a la interfaz."""
    t = Tarea(fn, *args)
    _TAREAS.add(t)

    def responder(callback, valor):
        _TAREAS.discard(t)
        try:
            if callback:
                callback(valor)
        except RuntimeError:   # la ventana se cerró mientras tanto
            pass

    t.senales.ok.connect(lambda r: responder(ok, r))
    t.senales.error.connect(lambda e: responder(error, e))
    QThreadPool.globalInstance().start(t)


# ============================================================ animaciones sueltas

def fundido(widget: QWidget, desde=0.0, hasta=1.0, duracion=260, al_terminar=None):
    if not ms(duracion):
        if al_terminar:
            al_terminar()
        return
    efecto = QGraphicsOpacityEffect(widget)
    efecto.setOpacity(desde)
    widget.setGraphicsEffect(efecto)
    anim = QPropertyAnimation(efecto, b"opacity", widget)
    anim.setDuration(ms(duracion))
    anim.setStartValue(desde)
    anim.setEndValue(hasta)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def fin():
        if hasta >= 1:
            try:
                widget.setGraphicsEffect(None)
            except RuntimeError:
                return
        if al_terminar:
            al_terminar()

    anim.finished.connect(fin)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def sacudir(widget: QWidget):
    """Sacudida horizontal (por ejemplo, cuando una clave o credencial es incorrecta)."""
    if not ms(1):
        return
    origen = widget.pos()
    grupo = QSequentialAnimationGroup(widget)
    for dx in (12, -10, 8, -6, 3, 0):
        a = QPropertyAnimation(widget, b"pos")
        a.setDuration(45)
        a.setEndValue(origen + QPoint(dx, 0))
        grupo.addAnimation(a)
    grupo.start(QSequentialAnimationGroup.DeletionPolicy.DeleteWhenStopped)


# ============================================================ componentes

class DialogoBase(DialogoSinMarco):
    """Diálogo del Administrador: sin marco, con barra propia, sombra y animación de entrada.
    El contenido se agrega a self.cuerpo."""

    def __init__(self, parent=None, titulo: str = "", ancho: int = 0, redimensionable: bool = True):
        super().__init__(parent, titulo, ancho=ancho, redimensionable=redimensionable, icono=icono_app())


class Pila(QStackedWidget):
    """Páginas que entran deslizándose (hacia la derecha o la izquierda) con un fundido."""

    def ir_a(self, indice: int):
        anterior = self.currentIndex()
        if indice == anterior:
            return
        self.setCurrentIndex(indice)
        nueva = self.currentWidget()
        if not ms(1):
            return
        final = nueva.pos()
        sentido = 1 if indice > anterior else -1
        efecto = QGraphicsOpacityEffect(nueva)
        nueva.setGraphicsEffect(efecto)
        opacidad = QPropertyAnimation(efecto, b"opacity")
        opacidad.setStartValue(0.0)
        opacidad.setEndValue(1.0)
        mover = QPropertyAnimation(nueva, b"pos")
        mover.setStartValue(final + QPoint(28 * sentido, 0))
        mover.setEndValue(final)
        grupo = QParallelAnimationGroup(self)
        for a in (opacidad, mover):
            a.setDuration(ms(300))
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            grupo.addAnimation(a)

        def fin():
            try:
                nueva.setGraphicsEffect(None)
                nueva.move(final)
            except RuntimeError:
                pass

        grupo.finished.connect(fin)
        grupo.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)


class ContadorAnimado(QLabel):
    """Número que sube (o baja) animado hasta su nuevo valor."""

    def __init__(self, formato=None, parent=None):
        super().__init__("0", parent)
        self.formato = formato or (lambda v: f"{round(v):,}")
        self._valor = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.setText(self.formato(float(v))))

    def fijar(self, valor: float):
        valor = float(valor)
        if valor == self._valor and self.text() not in ("", "0", "—"):
            return
        self._anim.stop()
        if not ms(1):
            self._valor = valor
            self.setText(self.formato(valor))
            return
        self._anim.setDuration(ms(900))
        self._anim.setStartValue(self._valor)
        self._anim.setEndValue(valor)
        self._valor = valor
        self._anim.start()


class Spinner(QWidget):
    """Indicador de carga giratorio."""

    def __init__(self, tam=18, parent=None):
        super().__init__(parent)
        self.setFixedSize(tam, tam)
        self._angulo = 0
        self._timer = QTimer(self, interval=16, timeout=self._girar)
        self.hide()

    def _girar(self):
        self._angulo = (self._angulo + 8) % 360
        self.update()

    def iniciar(self):
        self.show()
        self._timer.start()

    def detener(self):
        self._timer.stop()
        self.hide()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.setPen(QPen(QColor(C["borde2"]), 2.4))
        p.drawEllipse(r)
        p.setPen(QPen(QColor(C["acento"]), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(r, -self._angulo * 16, 100 * 16)


class _BarraTiempo(QWidget):
    """Línea fina que se vacía mientras el aviso está en pantalla."""

    def __init__(self, color: str, segundos: float):
        super().__init__()
        self.setFixedHeight(3)
        self.color = QColor(color)
        self._p = 1.0
        self._anim = QVariantAnimation(self, startValue=1.0, endValue=0.0, duration=int(segundos * 1000))
        self._anim.valueChanged.connect(self._fijar)
        self._anim.start()

    def _fijar(self, v):
        self._p = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        c = QColor(self.color)
        c.setAlpha(160)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(0, 0, self.width() * self._p, self.height()), 1.5, 1.5)


class Toast(QFrame):
    """Aviso flotante que entra desde abajo a la derecha y se va solo."""

    _activos: list["Toast"] = []

    def __init__(self, ventana: QWidget, titulo: str, texto: str, tipo: str, segundos: float):
        super().__init__(ventana, objectName="toast")
        iconos = {"ok": ("✓", C["ok"]), "error": ("!", C["error"]), "info": ("i", C["info"]),
                  "venta": ("$", C["ok"]), "aviso": ("!", C["aviso"])}
        icono, color = iconos.get(tipo, iconos["info"])
        marca = QLabel(icono)
        marca.setAlignment(Qt.AlignmentFlag.AlignCenter)
        marca.setFixedSize(30, 30)
        marca.setStyleSheet(f"background:{tinte(color, 0.2)}; color:{legible(color)}; border-radius:15px; "
                            "font-weight:800;")
        textos = QVBoxLayout()
        textos.setSpacing(1)
        t = QLabel(titulo, objectName="toastTitulo")
        t.setWordWrap(True)
        textos.addWidget(t)
        if texto:
            d = QLabel(texto, objectName="toastTexto")
            d.setWordWrap(True)
            textos.addWidget(d)
        fila_ = QHBoxLayout()
        fila_.setSpacing(12)
        fila_.addWidget(marca, 0, Qt.AlignmentFlag.AlignTop)
        fila_.addLayout(textos, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 18, 10)
        lay.setSpacing(8)
        lay.addLayout(fila_)
        if ms(1):
            lay.addWidget(_BarraTiempo(color, segundos))
        self.setFixedWidth(340)
        self.adjustSize()
        sombra = QColor(C["sombra"])
        sombra.setAlpha(150 if C.get("oscuro", True) else 55)
        self.setGraphicsEffect(QGraphicsDropShadowEffect(self, blurRadius=32, offset=QPoint(0, 8), color=sombra))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @classmethod
    def mostrar(cls, ventana: QWidget, titulo: str, texto: str = "", tipo: str = "info", segundos: float = 4.5):
        if ventana is None:
            return
        t = cls(ventana, titulo, texto, tipo, segundos)
        cls._activos.append(t)
        t.show()
        t.raise_()
        cls._recolocar(ventana, nuevo=t)
        QTimer.singleShot(int(segundos * 1000), t._salir)

    def mousePressEvent(self, e):
        self._salir()

    @classmethod
    def _recolocar(cls, ventana, nuevo=None):
        y = ventana.height() - 40
        for t in reversed(cls._activos):
            try:
                if t.parent() is not ventana:
                    continue
            except RuntimeError:
                continue
            y -= t.height()
            destino = QPoint(ventana.width() - t.width() - 24, y)
            if t is nuevo and ms(1):
                t.move(destino + QPoint(0, 24))
            anim = QPropertyAnimation(t, b"pos", t)
            anim.setDuration(ms(260))
            anim.setEndValue(destino)
            anim.setEasingCurve(QEasingCurve.Type.OutBack if t is nuevo else QEasingCurve.Type.OutCubic)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            y -= 10

    def _salir(self):
        if self not in Toast._activos:
            return
        try:
            ventana = self.parent()
        except RuntimeError:
            return

        def quitar():
            if self in Toast._activos:
                Toast._activos.remove(self)
            try:
                self.deleteLater()
                Toast._recolocar(ventana)
            except RuntimeError:
                pass

        if not ms(1):
            quitar()
            return
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(ms(220))
        anim.setEndValue(self.pos() + QPoint(40, 0))
        anim.finished.connect(quitar)
        self.setGraphicsEffect(None)
        fundido(self, 1.0, 0.0, 220)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class PanelDeslizante(QFrame):
    """Panel de detalle que se abre deslizándose desde la derecha."""

    def __init__(self, ancho=370, parent=None):
        super().__init__(parent, objectName="panelDetalle")
        self.ancho = ancho
        self.setMaximumWidth(0)
        self.setMinimumWidth(0)
        self._anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def abierto(self) -> bool:
        return self.maximumWidth() > 0

    def _ir(self, destino: int):
        self._anim.stop()
        if not ms(1):
            self.setMaximumWidth(destino)
            return
        self._anim.setDuration(ms(280))
        self._anim.setStartValue(self.maximumWidth())
        self._anim.setEndValue(destino)
        self._anim.start()

    def abrir(self):
        self._ir(self.ancho)

    def cerrar(self):
        self._ir(0)


class NavLateral(QWidget):
    """Menú lateral con secciones; un indicador se desliza hasta la opción elegida.
    Se puede plegar para mostrar solo los iconos."""

    cambiado = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent, objectName="nav")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(2)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.botones: list[QPushButton] = []
        self.iconos: list[str] = []
        self.textos: list[str] = []
        self.secciones: list[QLabel] = []
        self.valores: list[int] = []
        self.plegado = False
        self.indicador = QFrame(self, objectName="navIndicador")
        self.indicador.setFixedWidth(4)
        self.indicador.hide()
        self._anim = QPropertyAnimation(self.indicador, b"geometry", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def seccion(self, texto: str):
        l = QLabel(texto.upper(), objectName="seccionLateral")
        self.secciones.append(l)
        self.lay.addWidget(l)

    def agregar(self, icono: str, texto: str, atajo: str = "") -> int:
        b = QPushButton(objectName="navBoton")
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        indice = len(self.botones)
        self.grupo.addButton(b, indice)
        b.clicked.connect(lambda: self.seleccionar(indice, emitir=True))
        if atajo:
            b.setToolTip(f"{texto}  ({atajo})")
        self.botones.append(b)
        self.iconos.append(icono)
        self.textos.append(texto)
        self.valores.append(0)
        self.lay.addWidget(b)
        self._rotular(indice)
        return indice

    def _rotular(self, i: int):
        insignia = f"   ● {self.valores[i]}" if self.valores[i] else ""
        if self.plegado:
            self.botones[i].setText(f" {self.iconos[i]}" + (" •" if self.valores[i] else ""))
            self.botones[i].setToolTip(self.textos[i])
        else:
            self.botones[i].setText(f"  {self.iconos[i]}   {self.textos[i]}{insignia}")

    def insignia(self, indice: int, valor: int):
        self.valores[indice] = valor
        self._rotular(indice)

    def plegar(self, plegado: bool):
        self.plegado = plegado
        for l in self.secciones:
            l.setVisible(not plegado)
        for i in range(len(self.botones)):
            self._rotular(i)
        actual = self.grupo.checkedId()
        if actual >= 0:
            QTimer.singleShot(0, lambda: self._reajustar(actual))

    def seleccionar(self, indice: int, emitir=False):
        b = self.botones[indice]
        b.setChecked(True)
        destino = b.geometry().adjusted(0, 8, 0, -8)
        destino.setWidth(4)
        if not self.indicador.isVisible() or not ms(1):
            self.indicador.setGeometry(destino)
            self.indicador.show()
        else:
            self._anim.stop()
            self._anim.setDuration(ms(260))
            self._anim.setEndValue(destino)
            self._anim.start()
        self.indicador.raise_()
        if emitir:
            self.cambiado.emit(indice)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        actual = self.grupo.checkedId()
        if actual >= 0:
            QTimer.singleShot(0, lambda: self._reajustar(actual))

    def _reajustar(self, indice):
        g = self.botones[indice].geometry().adjusted(0, 8, 0, -8)
        g.setWidth(4)
        self.indicador.setGeometry(g)


class TarjetaKPI(QFrame):
    """Tarjeta con un número animado; se ilumina al pasar el ratón."""

    def __init__(self, titulo: str, color: str, formato=None, ayuda: str = ""):
        super().__init__(objectName="kpi")
        self.color = color
        self.valor = ContadorAnimado(formato)
        self.valor.setObjectName("kpiValor")
        self.valor.setStyleSheet(f"color:{legible(color)}")
        self.sub = QLabel(ayuda, objectName="kpiSub")
        self.sub.setWordWrap(True)
        cab = QLabel(titulo.upper(), objectName="kpiTitulo")
        cab.setWordWrap(True)
        barra = QFrame(objectName="kpiBarra")
        barra.setFixedHeight(3)
        barra.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {color}, stop:1 transparent);"
                            "border-radius:1px;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(ESP_XS)
        lay.addWidget(barra)
        lay.addSpacing(ESP_XS)
        lay.addWidget(cab)
        lay.addWidget(self.valor)
        lay.addWidget(self.sub)
        sombra = QColor(color).darker(150)
        if not C.get("oscuro", True):
            sombra.setAlpha(90)
        self._sombra = QGraphicsDropShadowEffect(self, blurRadius=0, offset=QPoint(0, 0), color=sombra)
        self.setGraphicsEffect(self._sombra)
        self._brillo = QVariantAnimation(self, duration=220)
        self._brillo.valueChanged.connect(self._fijar_brillo)

    def _fijar_brillo(self, v):
        # en reposo no hay sombra; al pasar el ratón crece y baja un poco
        self._sombra.setBlurRadius(float(v))
        self._sombra.setOffset(0, float(v) / 26 * 6)

    def _animar_brillo(self, hasta):
        self._brillo.stop()
        if not ms(1):
            self._fijar_brillo(hasta)
            return
        self._brillo.setStartValue(self._sombra.blurRadius())
        self._brillo.setEndValue(hasta)
        self._brillo.start()

    def enterEvent(self, e):
        self._animar_brillo(26.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animar_brillo(0.0)
        super().leaveEvent(e)


class GraficoBarras(QWidget):
    """Barras apiladas por serie que crecen al aparecer. Muestra el detalle al pasar el ratón."""

    def __init__(self, parent=None, unidad: str = "", sin_datos: str = "Sin ventas"):
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.setMouseTracking(True)
        self.unidad, self.sin_datos = unidad, sin_datos
        self.etiquetas: list[str] = []
        self.series: dict[str, list[float]] = {}
        self.colores: dict[str, str] = {}
        self.nombres: dict[str, str] = {}
        self._progreso = 1.0
        self._resaltada = -1
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._avanzar)

    def _avanzar(self, v):
        self._progreso = float(v)
        self.update()

    def fijar(self, etiquetas, series, colores, nombres):
        cambio = (etiquetas, series) != (self.etiquetas, self.series)
        self.etiquetas, self.series, self.colores, self.nombres = etiquetas, series, colores, nombres
        if cambio and ms(1):
            self._anim.stop()
            self._anim.setDuration(ms(1200))
            self._anim.start()
        else:
            self._progreso = 1.0
            self.update()

    def _totales(self):
        n = len(self.etiquetas)
        return [sum(s[i] for s in self.series.values()) for i in range(n)]

    def _geometria(self):
        izq, der, arriba, abajo = 38, 8, 10, 26
        ancho = max(1, self.width() - izq - der)
        alto = max(1, self.height() - arriba - abajo)
        return izq, arriba, ancho, alto

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        izq, arriba, ancho, alto = self._geometria()
        totales = self._totales()
        maximo = max(totales + [1])
        maximo = max(3, -(-maximo // 3) * 3)    # múltiplo de 3: las líneas guía caen en números enteros
        p.setFont(QFont(self.font().family(), 8))
        for i in range(4):
            y = arriba + alto - alto * i / 3
            p.setPen(QPen(QColor(C["borde"]), 1, Qt.PenStyle.DashLine if i else Qt.PenStyle.SolidLine))
            p.drawLine(int(izq), int(y), int(izq + ancho), int(y))
            p.setPen(QColor(C["tenue"]))
            p.drawText(QRectF(0, y - 8, izq - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{maximo * i / 3:g}")
        n = len(self.etiquetas)
        if not n:
            return
        paso = ancho / n
        barra = max(3.0, paso * 0.62)
        curva = QEasingCurve(QEasingCurve.Type.OutBack)
        resalte = QColor(C["texto"])
        resalte.setAlpha(12)
        for i, etiqueta_ in enumerate(self.etiquetas):
            # cada barra arranca un poco después que la anterior (efecto "ola")
            propio = min(1.0, max(0.0, self._progreso * 1.6 - i / max(1, n) * 0.6))
            crecimiento = curva.valueForProgress(propio)
            x = izq + i * paso + (paso - barra) / 2
            base = arriba + alto
            if i == self._resaltada:
                p.fillRect(QRectF(izq + i * paso, arriba, paso, alto), resalte)
            for clave, valores in self.series.items():
                h = alto * valores[i] / maximo * crecimiento
                if h <= 0:
                    continue
                color = QColor(self.colores.get(clave, C["acento"]))
                grad = QLinearGradient(0, base - h, 0, base)
                grad.setColorAt(0, color.lighter(120))
                grad.setColorAt(1, color)
                camino = QPainterPath()
                camino.addRoundedRect(QRectF(x, base - h, barra, h), min(4, barra / 2), min(4, barra / 2))
                p.fillPath(camino, grad)
                base -= h
            if n <= 10 or i % max(1, n // 6) == 0 or i == n - 1:
                p.setPen(QColor(C["tenue"]))
                p.drawText(QRectF(izq + i * paso - 20, arriba + alto + 6, paso + 40, 16),
                           Qt.AlignmentFlag.AlignHCenter, etiqueta_)

    def mouseMoveEvent(self, e):
        izq, _, ancho, _ = self._geometria()
        n = len(self.etiquetas)
        i = int((e.position().x() - izq) / (ancho / n)) if n else -1
        i = i if 0 <= i < n else -1
        if i != self._resaltada:
            self._resaltada = i
            self.update()
        if i >= 0:
            lineas = [f"<b>{self.etiquetas[i]}</b>"]
            for clave, valores in self.series.items():
                if valores[i]:
                    lineas.append(f"<span style='color:{self.colores.get(clave)}'>●</span> "
                                  f"{self.nombres.get(clave, clave)}: {valores[i]:g}{self.unidad}")
            if len(lineas) == 1:
                lineas.append(self.sin_datos)
            QToolTip.showText(e.globalPosition().toPoint(), "<br>".join(lineas), self)

    def leaveEvent(self, e):
        self._resaltada = -1
        self.update()
        super().leaveEvent(e)


class GraficoDona(QWidget):
    """Gráfico circular (dona) que se dibuja girando; el total va en el centro."""

    def __init__(self, tam: int = 150, texto_centro: str = "total"):
        super().__init__()
        self.setFixedSize(tam, tam)
        self.texto_centro = texto_centro
        self.partes: list[tuple[str, float, str]] = []
        self._p = 1.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._fijar)

    def _fijar(self, v):
        self._p = float(v)
        self.update()

    def fijar(self, partes: list[tuple[str, float, str]]):
        """partes = [(nombre, valor, color), …]"""
        cambio = partes != self.partes
        self.partes = partes
        tip = "<br>".join(f"<span style='color:{c}'>●</span> {n}: <b>{v:g}</b>" for n, v, c in partes if v)
        self.setToolTip(tip)
        if cambio and ms(1):
            self._anim.stop()
            self._anim.setDuration(ms(1000))
            self._anim.start()
        else:
            self._p = 1.0
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grosor = self.width() * 0.13
        r = QRectF(grosor / 2 + 2, grosor / 2 + 2, self.width() - grosor - 4, self.height() - grosor - 4)
        p.setPen(QPen(QColor(C["borde"]), grosor))
        p.drawEllipse(r)
        total = sum(v for _, v, _ in self.partes)
        inicio = 90.0
        if total:
            for _, valor, color in self.partes:
                arco = -360.0 * valor / total * self._p
                if valor:
                    p.setPen(QPen(QColor(color), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                    p.drawArc(r, int(inicio * 16), int(arco * 16))
                inicio += arco
        f = QFont(self.font())
        f.setPixelSize(int(self.height() * 0.2))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(C["titulo"]))
        p.drawText(QRectF(0, -8, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter,
                   f"{round(total * self._p):,}")
        f.setPixelSize(max(9, int(self.height() * 0.08)))
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(C["tenue"]))
        p.drawText(QRectF(0, self.height() * 0.16, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter,
                   self.texto_centro)


class DelegadoPildora(QStyledItemDelegate):
    """Dibuja las celdas de estado como 'píldoras' de color."""

    def paint(self, painter, opcion, indice):
        color = indice.data(ROL_COLOR)
        if not color:
            return super().paint(painter, opcion, indice)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if opcion.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(opcion.rect, QColor(C["seleccion"]))
        elif indice.row() % 2:
            painter.fillRect(opcion.rect, QColor(C["panel2"]))
        texto = str(indice.data(Qt.ItemDataRole.DisplayRole) or "")
        f = QFont(opcion.font)
        f.setPointSizeF(max(7.5, f.pointSizeF() - 1))
        f.setBold(True)
        painter.setFont(f)
        ancho = min(painter.fontMetrics().horizontalAdvance(texto) + 26, opcion.rect.width() - 12)
        alto = 22
        r = QRectF(opcion.rect.x() + 8, opcion.rect.center().y() - alto / 2 + 1, ancho, alto)
        base = QColor(color)
        fondo = QColor(base)
        fondo.setAlpha(38)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fondo)
        painter.drawRoundedRect(r, alto / 2, alto / 2)
        painter.setBrush(base)
        painter.drawEllipse(QRectF(r.x() + 9, r.center().y() - 3, 6, 6))
        painter.setPen(QColor(legible(color)).lighter(115 if C.get("oscuro", True) else 100))
        painter.drawText(r.adjusted(18, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         painter.fontMetrics().elidedText(texto, Qt.TextElideMode.ElideRight, int(r.width() - 24)))
        painter.restore()


class EstadoVacio(QWidget):
    """Mensaje amable cuando una lista está vacía, con un botón de acción opcional."""

    def __init__(self, icono: str, titulo: str, texto: str, boton_texto: str = ""):
        super().__init__(objectName="vacio")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(ESP_SM)
        self.icono = QLabel(icono, objectName="vacioIcono")
        self.icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titulo = QLabel(titulo, objectName="vacioTitulo")
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texto = QLabel(texto, objectName="vacioTexto")
        self.texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texto.setWordWrap(True)
        self.texto.setMaximumWidth(460)
        lay.addWidget(self.icono)
        lay.addWidget(self.titulo)
        lay.addWidget(self.texto, 0, Qt.AlignmentFlag.AlignHCenter)
        self.boton = boton(boton_texto, "primario") if boton_texto else None
        if self.boton:
            lay.addSpacing(ESP_SM)
            lay.addWidget(self.boton, 0, Qt.AlignmentFlag.AlignHCenter)

    def showEvent(self, e):
        super().showEvent(e)
        if ms(1):
            QTimer.singleShot(0, lambda: self.isVisible() and entrada_escalonada([self.icono, self.titulo, self.texto],
                                                                                 12, 60, 420))


class OpcionPlataforma(QFrame):
    """Tarjeta seleccionable (como un botón de opción grande) con texto que se ajusta."""

    clic = Signal()

    def __init__(self, icono: str, titulo: str, texto: str, color: str):
        super().__init__(objectName="opcion")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.marca = QLabel("○")
        textos = QVBoxLayout()
        textos.setSpacing(3)
        textos.addWidget(QLabel(titulo, objectName="tituloTarjeta"))
        d = QLabel(texto, objectName="nota")
        d.setWordWrap(True)
        textos.addWidget(d)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(ESP_MD)
        lay.addWidget(insignia_icono(icono, color, 46), 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(textos, 1)
        lay.addWidget(self.marca, 0, Qt.AlignmentFlag.AlignTop)
        self.color = color
        self.setStyleSheet(f"QFrame#opcion[seleccionado=\"true\"] {{ border-color: {color}; "
                           f"background: {tinte(color, 0.07)}; }}")
        self.fijar(False)
        elevar_al_pasar(self, color)

    def fijar(self, seleccionado: bool):
        self.setProperty("seleccionado", seleccionado)
        self.marca.setText("●" if seleccionado else "○")
        self.marca.setStyleSheet(f"font-size:18px; color:{self.color if seleccionado else C['tenue']};")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, e):
        self.clic.emit()
        super().mousePressEvent(e)


class Chips(QWidget):
    """Filtros rápidos tipo 'píldora'."""

    cambiado = Signal(str)

    def __init__(self, opciones: list[tuple[str, str]]):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.grupo = QButtonGroup(self)
        self.claves: list[str] = []
        for i, (clave, texto) in enumerate(opciones):
            b = QPushButton(texto, objectName="chip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.grupo.addButton(b, i)
            self.claves.append(clave)
            lay.addWidget(b)
        lay.addStretch()
        self.grupo.button(0).setChecked(True)
        self.grupo.idClicked.connect(lambda i: self.cambiado.emit(self.claves[i]))

    def actual(self) -> str:
        return self.claves[max(0, self.grupo.checkedId())]

    def elegir(self, clave: str):
        if clave in self.claves:
            self.grupo.button(self.claves.index(clave)).setChecked(True)

    def texto(self, clave: str, texto: str):
        self.grupo.button(self.claves.index(clave)).setText(texto)


class TarjetaTema(QFrame):
    """Vista previa de un tema (mini ventana con sus colores). Al elegirla se marca con una palomita."""

    clic = Signal(str)

    def __init__(self, clave: str, tema: dict):
        super().__init__(objectName="temaTarjeta")
        self.clave, self.tema = clave, tema
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(188, 150)
        self._marca = 0.0
        self._anim = QVariantAnimation(self, duration=ms(320) or 1)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.valueChanged.connect(self._fijar)
        self.setToolTip(tema["descripcion"])
        elevar_al_pasar(self, tema["acento"])

    def _fijar(self, v):
        self._marca = float(v)
        self.update()

    def elegir(self, elegido: bool):
        self.setProperty("elegido", elegido)
        self.style().unpolish(self)
        self.style().polish(self)
        destino = 1.0 if elegido else 0.0
        if ms(1) and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self._marca)
            self._anim.setEndValue(destino)
            self._anim.start()
        else:
            self._fijar(destino)

    def mousePressEvent(self, e):
        self.clic.emit(self.clave)

    def paintEvent(self, e):
        super().paintEvent(e)
        T = self.tema
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(10, 10, self.width() - 20, 92)
        forma = QPainterPath()
        forma.addRoundedRect(r, 8, 8)
        p.fillPath(forma, QColor(T["fondo"]))
        p.setPen(QPen(QColor(T["borde2"]), 1))
        p.drawPath(forma)
        lateral = QRectF(r.left() + 1, r.top() + 1, 40, r.height() - 2)
        p.fillRect(lateral, QColor(T["panel"]))
        for i in range(4):
            c = QColor(T["acento"] if i == 0 else T["borde2"])
            p.fillRect(QRectF(lateral.left() + 8, lateral.top() + 12 + i * 14, 24 if i else 20, 5), c)
        for i, color in enumerate((T["acento"], T["ok"], T["info"])):
            caja = QRectF(r.left() + 50 + i * 40, r.top() + 12, 34, 30)
            camino = QPainterPath()
            camino.addRoundedRect(caja, 4, 4)
            p.fillPath(camino, QColor(T["panel"]))
            p.fillRect(QRectF(caja.left() + 5, caja.top() + 18, 18, 5), QColor(color))
        for i in range(5):
            alto = 10 + (i * 7) % 26
            p.fillRect(QRectF(r.left() + 52 + i * 22, r.bottom() - 8 - alto, 12, alto), QColor(T["acento2"]))
        p.setPen(QColor(C["titulo"]))
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSizeF(10)
        p.setFont(f)
        p.drawText(QRectF(12, 108, self.width() - 40, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   T["nombre"])
        f.setBold(False)
        f.setPointSizeF(8)
        p.setFont(f)
        p.setPen(QColor(C["tenue"]))
        p.drawText(QRectF(12, 126, self.width() - 20, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "Oscuro" if T["oscuro"] else "Claro")
        if self._marca > 0:
            c = QPointF(self.width() - 24, 118)
            radio = 10 * self._marca
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["acento"]))
            p.drawEllipse(c, radio, radio)
            if self._marca > 0.5:
                p.setPen(QPen(QColor(C["sobre_acento"]), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(c.x() - 4, c.y()), QPointF(c.x() - 1, c.y() + 3))
                p.drawLine(QPointF(c.x() - 1, c.y() + 3), QPointF(c.x() + 4, c.y() - 3))


# ============================================================ más animaciones

class _Onda(QWidget):
    """Círculo de luz que se expande desde donde se hizo clic (efecto "ripple")."""

    def __init__(self, boton_: QWidget, centro: QPoint, radio_borde: float = 10):
        super().__init__(boton_)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(boton_.rect())
        self.centro, self.radio_borde, self._p = QPointF(centro), radio_borde, 0.0
        self._max = math.hypot(max(centro.x(), self.width() - centro.x()), max(centro.y(), self.height() - centro.y()))
        anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=ms(520))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._avanzar)
        anim.finished.connect(self.deleteLater)
        self.show()
        anim.start()

    def _avanzar(self, v):
        self._p = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        forma = QPainterPath()
        forma.addRoundedRect(QRectF(self.rect()), self.radio_borde, self.radio_borde)
        p.setClipPath(forma)
        p.setPen(Qt.PenStyle.NoPen)
        luz = QColor("#ffffff" if C.get("oscuro", True) else C["acento"])
        luz.setAlpha(int((95 if C.get("oscuro", True) else 50) * (1 - self._p)))
        p.setBrush(luz)
        r = self._max * (0.2 + 0.8 * self._p)
        p.drawEllipse(self.centro, r, r)


class _FiltroOnda(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.MouseButtonPress and ms(1) and obj.isEnabled():
            _Onda(obj, ev.position().toPoint())
        return False


_FILTRO_ONDA: _FiltroOnda | None = None


def con_onda(widget: QWidget):
    global _FILTRO_ONDA
    if _FILTRO_ONDA is None:
        _FILTRO_ONDA = _FiltroOnda()
    widget.installEventFilter(_FILTRO_ONDA)


class _Elevar(QObject):
    """Sombra que crece al pasar el ratón: la tarjeta parece levantarse."""

    def __init__(self, widget: QWidget, color: QColor):
        super().__init__(widget)
        self.sombra = QGraphicsDropShadowEffect(widget, blurRadius=0, offset=QPoint(0, 0), color=color)
        widget.setGraphicsEffect(self.sombra)
        self._v = 0.0
        self.anim = QVariantAnimation(self, duration=260)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._aplicar)
        widget.installEventFilter(self)

    def _aplicar(self, v):
        # en reposo la sombra queda escondida detrás; al pasar el ratón crece y baja
        self._v = float(v)
        self.sombra.setBlurRadius(34 * self._v)
        self.sombra.setOffset(0, 10 * self._v)

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            destino = 1.0 if ev.type() == QEvent.Type.Enter else 0.0
            self.anim.stop()
            if ms(1):
                self.anim.setDuration(ms(260))
                self.anim.setStartValue(self._v)
                self.anim.setEndValue(destino)
                self.anim.start()
            else:
                self._aplicar(destino)
        return False


def elevar_al_pasar(widget: QWidget, color: str = "#000000"):
    c = QColor(color)
    c.setAlpha(150 if C.get("oscuro", True) else 80)
    _Elevar(widget, c)


def entrada_escalonada(widgets: list[QWidget], desplazamiento: int = 22, retraso: int = 70, duracion: int = 520):
    """Los widgets suben a su sitio uno tras otro (como cartas que se reparten)."""
    if not ms(1):
        return
    for i, w in enumerate(widgets):
        final = w.pos()
        w.move(final + QPoint(0, desplazamiento))
        anim = QPropertyAnimation(w, b"pos", w)
        anim.setDuration(ms(duracion))
        anim.setStartValue(final + QPoint(0, desplazamiento))
        anim.setEndValue(final)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        QTimer.singleShot(int(i * retraso * ANIM["factor"]), anim.start)


def latido(widget: QWidget, color: str | None = None, veces: int = 3):
    """Destello suave para llamar la atención (por ejemplo, actividad nueva)."""
    if not ms(1):
        return
    original = widget.styleSheet()
    c = QColor(color or C["acento"])
    anim = QVariantAnimation(widget, startValue=0.0, endValue=1.0, duration=900)
    anim.setLoopCount(veces)

    def pintar(v):
        a = math.sin(math.pi * float(v))
        widget.setStyleSheet(original + f"QPushButton {{ background: rgba({c.red()},{c.green()},{c.blue()},"
                                        f"{int(80 * a)}); }}")

    anim.valueChanged.connect(pintar)
    anim.finished.connect(lambda: widget.setStyleSheet(original))
    anim.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)


class BloqueCarga(QWidget):
    """Rectángulo con un brillo que lo recorre: indica que los datos están cargando."""

    def __init__(self, alto: int = 0, radio: int = RADIO_LG):
        super().__init__()
        if alto:
            self.setFixedHeight(alto)
        self.radio, self._fase = radio, 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1400)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._avanzar)

    def _avanzar(self, v):
        self._fase = float(v)
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if ms(1):
            self._anim.start()

    def hideEvent(self, e):
        self._anim.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        grad = QLinearGradient(r.left(), 0, r.right(), 0)
        centro = -0.3 + self._fase * 1.6
        base = QColor(C["panel"])
        luz = QColor(C["panel2"]).lighter(125) if C.get("oscuro", True) else QColor(C["panel2"]).darker(104)
        grad.setColorAt(0, base)
        for t, color in ((centro - 0.25, base), (centro, luz), (centro + 0.25, base)):
            if 0 <= t <= 1:
                grad.setColorAt(t, color)
        grad.setColorAt(1, base)
        p.setPen(QPen(QColor(C["borde"]), 1))
        p.setBrush(grad)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), self.radio, self.radio)


class Interruptor(QCheckBox):
    """Interruptor deslizante (on/off) con la bolita animada."""

    def __init__(self, texto: str = ""):
        super().__init__(texto)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 0.0
        self._anim = QVariantAnimation(self, duration=200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.valueChanged.connect(self._mover)
        self.toggled.connect(self._cambiar)

    def _mover(self, v):
        self._pos = float(v)
        self.update()

    def _cambiar(self, activo: bool):
        destino = 1.0 if activo else 0.0
        self._anim.stop()
        if self.isVisible() and ms(1):
            self._anim.setDuration(ms(200))
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(destino)
            self._anim.start()
        else:
            self._mover(destino)

    def sizeHint(self) -> QSize:
        return QSize(52 + self.fontMetrics().horizontalAdvance(self.text()) + 10, 28)

    def hitButton(self, pos) -> bool:
        return self.contentsRect().contains(pos)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pista = QRectF(1, (self.height() - 24) / 2, 44, 24)
        color = mezclar(C["borde2"], C["acento"], min(1.0, self._pos))
        if not self.isEnabled():
            color.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(pista, 12, 12)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(pista.left() + 12 + self._pos * 20, pista.center().y()), 9, 9)
        p.setPen(QColor(C["texto"] if self.isEnabled() else C["tenue"]))
        p.drawText(QRectF(pista.right() + 10, 0, self.width(), self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


class MarcaExito(QWidget):
    """Círculo que se dibuja y una palomita (✓) que aparece trazo a trazo."""

    def __init__(self, color: str | None = None, tam: int = 60):
        super().__init__()
        self.setFixedSize(tam, tam)
        self.color, self._p = QColor(color or C["ok"]), 0.0 if ms(1) else 1.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=ms(900))
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._avanzar)

    def _avanzar(self, v):
        self._p = float(v)
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if ms(1) and self._anim.state() != QVariantAnimation.State.Running and self._p == 0:
            QTimer.singleShot(150, self._anim.start)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(4, 4, self.width() - 8, self.height() - 8)
        fondo = QColor(self.color)
        fondo.setAlpha(int(40 * min(1, self._p * 2)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fondo)
        p.drawEllipse(r)
        p.setPen(QPen(self.color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        circulo = min(1.0, self._p / 0.6)
        p.drawArc(r, 90 * 16, int(-360 * 16 * circulo))
        trazo = max(0.0, (self._p - 0.45) / 0.55)
        if trazo > 0:
            a = QPointF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.52)
            b = QPointF(r.left() + r.width() * 0.44, r.top() + r.height() * 0.68)
            c = QPointF(r.left() + r.width() * 0.74, r.top() + r.height() * 0.36)
            camino = QPainterPath(a)
            primero = min(1.0, trazo / 0.4)
            camino.lineTo(a + (b - a) * primero)
            if trazo > 0.4:
                camino.lineTo(b + (c - b) * ((trazo - 0.4) / 0.6))
            p.drawPath(camino)


class Aurora(QFrame):
    """Marco con luces de color que se mueven lentamente detrás del contenido."""

    def __init__(self, colores=None, objectName="heroe"):
        super().__init__(objectName=objectName)
        self.colores = [QColor(c) for c in (colores or (C["acento"], C["acento2"], C["oro"]))]
        self._fase = 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=2 * math.pi, duration=14000)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._avanzar)

    def _avanzar(self, v):
        self._fase = float(v)
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if ms(1):
            self._anim.start()

    def hideEvent(self, e):
        self._anim.stop()
        super().hideEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        forma = QPainterPath()
        forma.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), RADIO_XL, RADIO_XL)
        p.setClipPath(forma)
        w, h = self.width(), self.height()
        alfa = 55 if C.get("oscuro", True) else 38
        for i, color in enumerate(self.colores):
            fase = self._fase + i * 2.1
            centro = QPointF(w * (0.5 + 0.38 * math.cos(fase * (1 + i * 0.3))), h * (0.5 + 0.45 * math.sin(fase)))
            radial = QRadialGradient(centro, max(w, h) * 0.45)
            c1, c2 = QColor(color), QColor(color)
            c1.setAlpha(alfa)
            c2.setAlpha(0)
            radial.setColorAt(0, c1)
            radial.setColorAt(1, c2)
            p.fillRect(self.rect(), radial)


class Bienvenida(QWidget):
    """Pantalla de carga: el icono aparece con un rebote, luego la marca Cinema Productions y la barra."""

    def __init__(self, titulo: str, subtitulo: str):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 330)
        self.titulo, self.subtitulo = titulo, subtitulo
        self._intro, self._barra = (0.0, 0.0) if ms(1) else (1.0, 0.0)
        self.logo = icono_cinema(192)
        self.marca = logo_cinema(16, "#ffffff")
        self._a_intro = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=ms(750))
        self._a_intro.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_intro.valueChanged.connect(lambda v: self._fijar("_intro", v))
        self._a_barra = QVariantAnimation(self, duration=ms(450))
        self._a_barra.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_barra.valueChanged.connect(lambda v: self._fijar("_barra", v))
        pantalla = QApplication.primaryScreen()
        if pantalla:
            self.move(pantalla.availableGeometry().center() - self.rect().center())

    def _fijar(self, nombre, v):
        setattr(self, nombre, float(v))
        self.update()

    def mostrar(self):
        """Muestra la pantalla y espera a que el logo termine de aparecer (mientras se arma la ventana
        principal no se pueden dibujar animaciones, así que primero se completa la entrada)."""
        self.show()
        if not ms(1):
            QApplication.processEvents()
            return
        bucle = QEventLoop()
        self._a_intro.finished.connect(bucle.quit)
        QTimer.singleShot(1600, bucle.quit)          # por si acaso
        self._a_intro.start()
        bucle.exec()

    def avanzar(self, valor: float):
        self._a_barra.stop()
        self._a_barra.setStartValue(self._barra)
        self._a_barra.setEndValue(valor)
        self._a_barra.start()
        QApplication.processEvents()

    def terminar(self, ventana: QWidget):
        """Llena la barra, se desvanece y muestra la ventana principal con un fundido."""
        def mostrar_ventana():
            ventana.setWindowOpacity(0.0 if ms(1) else 1.0)
            ventana.show()
            if ms(1):
                a = QPropertyAnimation(ventana, b"windowOpacity", ventana)
                a.setDuration(ms(350))
                a.setStartValue(0.0)
                a.setEndValue(1.0)
                a.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            salida = QPropertyAnimation(self, b"windowOpacity", self)
            salida.setDuration(ms(300))
            salida.setStartValue(1.0)
            salida.setEndValue(0.0)
            salida.finished.connect(self.close)
            salida.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        self.avanzar(1.0)
        QTimer.singleShot(ms(550), mostrar_ventana)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        fondo = QLinearGradient(r.topLeft(), r.bottomRight())
        fondo.setColorAt(0, QColor("#1a0a0d"))
        fondo.setColorAt(1, QColor("#08080b"))
        p.setPen(QPen(QColor("#33333c"), 1))
        p.setBrush(fondo)
        p.drawRoundedRect(r, 22, 22)
        luz = QRadialGradient(QPointF(r.center().x(), 100), 190)
        rojo = QColor("#e50914")
        rojo.setAlpha(int(70 * self._intro))
        luz.setColorAt(0, rojo)
        rojo.setAlpha(0)
        luz.setColorAt(1, rojo)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(luz)
        p.drawRoundedRect(r, 22, 22)
        # icono con rebote (escala con sobrepaso)
        escala = QEasingCurve(QEasingCurve.Type.OutBack).valueForProgress(min(1.0, self._intro / 0.7))
        lado = 92 * max(0.0, escala)
        if lado > 1:
            p.drawPixmap(QRectF(r.center().x() - lado / 2, 54 + (92 - lado) / 2, lado, lado), self.logo,
                         QRectF(self.logo.rect()))
        opacidad = max(0.0, min(1.0, (self._intro - 0.35) / 0.65))
        p.setOpacity(opacidad)
        f = QFont()
        f.setFamilies(LETRA)
        f.setPointSizeF(17)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(r.left(), 160, r.width(), 32), Qt.AlignmentFlag.AlignCenter, self.titulo)
        f.setPointSizeF(10)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#a1a1aa"))
        p.drawText(QRectF(r.left(), 192, r.width(), 22), Qt.AlignmentFlag.AlignCenter, self.subtitulo)
        if not self.marca.isNull():
            ancho = self.marca.width() / self.marca.devicePixelRatio()
            alto = self.marca.height() / self.marca.devicePixelRatio()
            p.setOpacity(opacidad * 0.85)
            p.drawPixmap(QRectF(r.center().x() - ancho / 2, 228, ancho, alto), self.marca, QRectF(self.marca.rect()))
        p.setOpacity(1.0)
        # barra de progreso
        pista = QRectF(r.left() + 80, r.bottom() - 40, r.width() - 160, 5)
        p.setBrush(QColor(255, 255, 255, 28))
        p.drawRoundedRect(pista, 2.5, 2.5)
        lleno = QRectF(pista.left(), pista.top(), pista.width() * self._barra, pista.height())
        grad = QLinearGradient(lleno.topLeft(), lleno.topRight())
        grad.setColorAt(0, QColor("#e50914"))
        grad.setColorAt(1, QColor("#f5c518"))
        p.setBrush(grad)
        p.drawRoundedRect(lleno, 2.5, 2.5)


# ============================================================ ayudas

def fuente_mono(puntos: float = -1, negrita=False) -> QFont:
    f = QFont()
    f.setFamilies(FUENTE_MONO)
    f.setStyleHint(QFont.StyleHint.Monospace)
    if puntos > 0:
        f.setPointSizeF(puntos)
    f.setBold(negrita)
    return f


def boton(texto: str, estilo="secundario", tip="") -> QPushButton:
    b = QPushButton(texto, objectName=estilo)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setAutoDefault(False)   # Enter en un campo de texto no debe "pulsar" otro botón del diálogo
    con_onda(b)
    if tip:
        b.setToolTip(tip)
    return b


def etiqueta(texto: str, estilo="", ajustar=False) -> QLabel:
    l = QLabel(texto, objectName=estilo) if estilo else QLabel(texto)
    l.setWordWrap(ajustar)
    return l


def tarjeta(*widgets, estilo="tarjeta", margen=18, espacio=10) -> QFrame:
    f = QFrame(objectName=estilo)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(margen, margen, margen, margen)
    lay.setSpacing(espacio)
    for w in widgets:
        if isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    return f


def fila(*widgets, espacio=8) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(espacio)
    for w in widgets:
        if w is None:
            lay.addStretch()
        elif isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    return lay


class CeldaOrdenable(QTableWidgetItem):
    """Celda que se ordena por un valor propio (números, fechas) en lugar del texto."""

    def __lt__(self, otra):
        a, b = self.data(ROL_ORDEN), otra.data(ROL_ORDEN)
        if a is not None and b is not None:
            try:
                return a < b
            except TypeError:
                pass
        return super().__lt__(otra)


def tabla(columnas: list[str], anchos: list[int] | None = None, pildoras: tuple[int, ...] = (),
          ordenable: bool = True) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(TABLA["alto"])
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.setWordWrap(False)
    t.setMouseTracking(True)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    t.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    h.setStretchLastSection(True)
    h.setHighlightSections(False)
    h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    t.setProperty("ordenable", ordenable)
    if ordenable:
        h.setSectionsClickable(True)
        h.setSortIndicatorShown(True)
        h.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        h.sectionClicked.connect(lambda c: t.sortItems(c, h.sortIndicatorOrder()))
    for i, ancho in enumerate(anchos or []):
        t.setColumnWidth(i, ancho)
    delegado = DelegadoPildora(t)
    for c in pildoras:
        t.setItemDelegateForColumn(c, delegado)
    return t


def celda(texto, color: str | None = None, dato=None, negrita=False, mono=False, pildora: str | None = None,
          tip: str = "", orden=None) -> QTableWidgetItem:
    it = CeldaOrdenable(str(texto) if texto not in (None, "") else "—")
    if color:
        it.setForeground(QColor(legible(color)))
    if negrita or mono:
        f = fuente_mono() if mono else QFont(QApplication.font())
        f.setBold(negrita)
        it.setFont(f)
    if dato is not None:
        it.setData(ROL_DATO, dato)
    if pildora:
        it.setData(ROL_COLOR, pildora)
    if tip:
        it.setToolTip(tip)
    if orden is not None:
        it.setData(ROL_ORDEN, orden)
    return it


def llenar_tabla(t: QTableWidget, filas: list[list[QTableWidgetItem]]):
    """Rellena la tabla conservando la fila seleccionada (por el dato de la columna 0) y el orden elegido."""
    sel = dato_seleccionado(t)
    h = t.horizontalHeader()
    columna, orden = h.sortIndicatorSection(), h.sortIndicatorOrder()
    t.setUpdatesEnabled(False)
    t.setSortingEnabled(False)
    t.setRowCount(len(filas))
    for r, celdas in enumerate(filas):
        for c, it in enumerate(celdas):
            t.setItem(r, c, it)
    if t.property("ordenable") and 0 <= columna < t.columnCount():
        t.sortItems(columna, orden)
    t.clearSelection()
    if sel is not None:
        for r in range(t.rowCount()):
            if t.item(r, 0) and t.item(r, 0).data(ROL_DATO) == sel:
                t.selectRow(r)
                break
    t.setUpdatesEnabled(True)


def dato_seleccionado(t: QTableWidget):
    filas = t.selectionModel().selectedRows() if t.selectionModel() else []
    return t.item(filas[0].row(), 0).data(ROL_DATO) if filas and t.item(filas[0].row(), 0) else None
