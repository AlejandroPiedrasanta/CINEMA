"""Tema visual y componentes animados del Administrador de Licencias (PySide6)."""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QObject, QParallelAnimationGroup, QPoint, QPropertyAnimation, QRectF,
                            QRunnable, QSequentialAnimationGroup, Qt, QThreadPool, QTimer, QVariantAnimation,
                            Signal)
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QDialog, QFrame,
                               QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QSizePolicy, QStackedWidget, QStyle, QStyledItemDelegate,
                               QTableWidget, QTableWidgetItem, QToolTip, QVBoxLayout, QWidget)

ANIMACIONES = {"activas": True}

C = {
    "fondo": "#0d0f14", "panel": "#141823", "panel2": "#1a1f2d", "borde": "#252b3b", "borde2": "#323a50",
    "texto": "#e8ebf3", "suave": "#8d95aa", "tenue": "#5d6579",
    "acento": "#7c5cff", "acento2": "#4f8cff", "ok": "#22c55e", "aviso": "#f59e0b", "error": "#ef4444",
    "info": "#38bdf8",
}
ESTADO_COLOR = {
    "Activa": C["ok"], "Sin activar": C["info"], "Bloqueada": C["error"], "Vencida": C["aviso"],
    "Pagada": C["ok"], "Aprobada": C["ok"], "Completada": C["ok"], "Reembolsada": C["error"],
    "Contracargo": C["error"], "Reembolso parcial": C["aviso"], "Cancelada": C["tenue"],
    "Pendiente": C["info"], "Esperando pago": C["info"], "Fallida": C["error"],
}
FUENTE_MONO = ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "monospace"]
ROL_DATO = Qt.ItemDataRole.UserRole
ROL_COLOR = Qt.ItemDataRole.UserRole + 1


def ms(duracion: int) -> int:
    """Duración de una animación (0 si el usuario las desactivó)."""
    return duracion if ANIMACIONES["activas"] else 0


def color_estado(texto: str) -> str:
    return ESTADO_COLOR.get(texto, C["suave"])


def tinte(color: str, alfa: float = 0.14) -> str:
    """Versión translúcida de un color para fondos (Qt lee #RRGGBBAA al revés, por eso rgba)."""
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {int(alfa * 255)})"


def estilo_pildora(etiqueta_: QLabel, texto: str, color: str):
    etiqueta_.setText(texto)
    etiqueta_.setStyleSheet(f"color:{color}; background:{tinte(color)}; border-radius:12px; padding:2px 12px;"
                            "font-weight:700;")


def pildora(texto: str = "", color: str = "#8d95aa") -> QLabel:
    """Etiqueta de estado redondeada (Activa, Conectado, Modo prueba…)."""
    l = QLabel()
    l.setFixedHeight(24)
    l.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    estilo_pildora(l, texto, color)
    return l


def insignia_icono(icono: str, color: str, tam: int = 52) -> QLabel:
    l = QLabel(icono)
    l.setAlignment(Qt.AlignmentFlag.AlignCenter)
    l.setFixedSize(tam, tam)
    l.setStyleSheet(f"font-size:{int(tam * 0.5)}px; background:{tinte(color, 0.16)}; border-radius:{tam // 3}px;")
    return l


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
            widget.setGraphicsEffect(None)
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

class DialogoBase(QDialog):
    """Diálogo que aparece con un fundido suave."""

    def showEvent(self, e):
        super().showEvent(e)
        if ms(1) and not getattr(self, "_animado", False):
            self._animado = True
            self.setWindowOpacity(0.0)
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(ms(220))
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class Pila(QStackedWidget):
    """Páginas que entran deslizándose y con fundido."""

    def ir_a(self, indice: int):
        if indice == self.currentIndex():
            return
        self.setCurrentIndex(indice)
        nueva = self.currentWidget()
        if not ms(1):
            return
        final = nueva.pos()
        efecto = QGraphicsOpacityEffect(nueva)
        nueva.setGraphicsEffect(efecto)
        opacidad = QPropertyAnimation(efecto, b"opacity")
        opacidad.setStartValue(0.0)
        opacidad.setEndValue(1.0)
        mover = QPropertyAnimation(nueva, b"pos")
        mover.setStartValue(final + QPoint(32, 0))
        mover.setEndValue(final)
        grupo = QParallelAnimationGroup(self)
        for a in (opacidad, mover):
            a.setDuration(ms(300))
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            grupo.addAnimation(a)

        def fin():
            nueva.setGraphicsEffect(None)
            nueva.move(final)

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


class Toast(QFrame):
    """Aviso flotante que entra desde abajo a la derecha y se va solo."""

    _activos: list["Toast"] = []
    ICONOS = {"ok": ("✓", C["ok"]), "error": ("!", C["error"]), "info": ("i", C["info"]), "venta": ("$", C["ok"])}

    def __init__(self, ventana: QWidget, titulo: str, texto: str, tipo: str):
        super().__init__(ventana, objectName="toast")
        icono, color = self.ICONOS.get(tipo, self.ICONOS["info"])
        marca = QLabel(icono, objectName="toastIcono")
        marca.setAlignment(Qt.AlignmentFlag.AlignCenter)
        marca.setFixedSize(30, 30)
        marca.setStyleSheet(f"background:{tinte(color, 0.2)}; color:{color}; border-radius:15px; font-weight:800;")
        textos = QVBoxLayout()
        textos.setSpacing(1)
        t = QLabel(titulo, objectName="toastTitulo")
        textos.addWidget(t)
        if texto:
            d = QLabel(texto, objectName="toastTexto")
            d.setWordWrap(True)
            textos.addWidget(d)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 18, 12)
        lay.setSpacing(12)
        lay.addWidget(marca, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(textos, 1)
        self.setFixedWidth(340)
        self.adjustSize()
        sombra = QGraphicsDropShadowEffect(self, blurRadius=32, offset=QPoint(0, 8), color=QColor(0, 0, 0, 160))
        self.setGraphicsEffect(sombra)

    @classmethod
    def mostrar(cls, ventana: QWidget, titulo: str, texto: str = "", tipo: str = "info", segundos: float = 4):
        if ventana is None:
            return
        t = cls(ventana, titulo, texto, tipo)
        cls._activos.append(t)
        t.show()
        t.raise_()
        cls._recolocar(ventana, nuevo=t)
        QTimer.singleShot(int(segundos * 1000), t._salir)

    @classmethod
    def _recolocar(cls, ventana, nuevo=None):
        y = ventana.height() - 24
        for t in reversed(cls._activos):
            if t.parent() is not ventana:
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
        try:
            ventana = self.parent()
        except RuntimeError:
            return

        def quitar():
            if self in Toast._activos:
                Toast._activos.remove(self)
            self.deleteLater()
            Toast._recolocar(ventana)

        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(ms(220))
        anim.setEndValue(self.pos() + QPoint(40, 0))
        anim.finished.connect(quitar)
        if ms(1):
            self.setGraphicsEffect(None)
            fundido(self, 1.0, 0.0, 220)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        else:
            quitar()


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
    """Menú lateral con indicador que se desliza hasta la opción elegida."""

    cambiado = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent, objectName="nav")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(4)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.botones: list[QPushButton] = []
        self.textos: list[str] = []
        self.indicador = QFrame(self, objectName="navIndicador")
        self.indicador.setFixedWidth(4)
        self.indicador.hide()
        self._anim = QPropertyAnimation(self.indicador, b"geometry", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def agregar(self, icono: str, texto: str) -> int:
        b = QPushButton(f"  {icono}   {texto}", objectName="navBoton")
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        indice = len(self.botones)
        self.grupo.addButton(b, indice)
        b.clicked.connect(lambda: self.seleccionar(indice, emitir=True))
        self.botones.append(b)
        self.textos.append(f"  {icono}   {texto}")
        self.lay.addWidget(b)
        return indice

    def insignia(self, indice: int, valor: int):
        self.botones[indice].setText(self.textos[indice] + (f"   ● {valor}" if valor else ""))

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
        self.valor.setStyleSheet(f"color:{color}")
        self.sub = QLabel(ayuda, objectName="kpiSub")
        self.sub.setWordWrap(True)
        cab = QLabel(titulo.upper(), objectName="kpiTitulo")
        barra = QFrame(objectName="kpiBarra")
        barra.setFixedHeight(3)
        barra.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {color}, stop:1 transparent);"
                            "border-radius:1px;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        lay.addWidget(barra)
        lay.addSpacing(4)
        lay.addWidget(cab)
        lay.addWidget(self.valor)
        lay.addWidget(self.sub)
        self._sombra = QGraphicsDropShadowEffect(self, blurRadius=0, offset=QPoint(0, 6),
                                                 color=QColor(color).darker(150))
        self.setGraphicsEffect(self._sombra)
        self._brillo = QVariantAnimation(self, duration=220)
        self._brillo.valueChanged.connect(lambda v: self._sombra.setBlurRadius(float(v)))

    def _animar_brillo(self, hasta):
        self._brillo.stop()
        if not ms(1):
            self._sombra.setBlurRadius(hasta)
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
    """Barras apiladas por plataforma que crecen al aparecer. Muestra el detalle al pasar el ratón."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.setMouseTracking(True)
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
            self._anim.setDuration(ms(800))
            self._anim.start()
        else:
            self._progreso = 1.0
            self.update()

    def _totales(self):
        n = len(self.etiquetas)
        return [sum(s[i] for s in self.series.values()) for i in range(n)]

    def _geometria(self):
        izq, der, arriba, abajo = 34, 8, 10, 26
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
        # líneas guía
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
        for i, etiqueta in enumerate(self.etiquetas):
            x = izq + i * paso + (paso - barra) / 2
            base = arriba + alto
            if i == self._resaltada:
                p.fillRect(QRectF(izq + i * paso, arriba, paso, alto), QColor(255, 255, 255, 10))
            for clave, valores in self.series.items():
                h = alto * valores[i] / maximo * self._progreso
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
                           Qt.AlignmentFlag.AlignHCenter, etiqueta)

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
                                  f"{self.nombres.get(clave, clave)}: {valores[i]:g}")
            if len(lineas) == 1:
                lineas.append("Sin ventas")
            QToolTip.showText(e.globalPosition().toPoint(), "<br>".join(lineas), self)

    def leaveEvent(self, e):
        self._resaltada = -1
        self.update()
        super().leaveEvent(e)


class DelegadoPildora(QStyledItemDelegate):
    """Dibuja las celdas de estado como 'píldoras' de color."""

    def paint(self, painter, opcion, indice):
        color = indice.data(ROL_COLOR)
        if not color:
            return super().paint(painter, opcion, indice)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if opcion.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(opcion.rect, QColor("#243156"))
        elif indice.row() % 2:
            painter.fillRect(opcion.rect, QColor(C["panel2"]))
        texto = str(indice.data(Qt.ItemDataRole.DisplayRole) or "")
        f = QFont(opcion.font)
        f.setPointSizeF(max(7.5, f.pointSizeF() - 1))
        f.setBold(True)
        painter.setFont(f)
        ancho = painter.fontMetrics().horizontalAdvance(texto) + 26
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
        painter.setPen(base.lighter(115))
        painter.drawText(r.adjusted(18, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, texto)
        painter.restore()


class EstadoVacio(QWidget):
    """Mensaje amable cuando una lista está vacía, con un botón de acción opcional."""

    def __init__(self, icono: str, titulo: str, texto: str, boton_texto: str = ""):
        super().__init__(objectName="vacio")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(8)
        i = QLabel(icono, objectName="vacioIcono")
        i.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titulo = QLabel(titulo, objectName="vacioTitulo")
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texto = QLabel(texto, objectName="vacioTexto")
        self.texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texto.setWordWrap(True)
        self.texto.setMaximumWidth(460)
        lay.addWidget(i)
        lay.addWidget(self.titulo)
        lay.addWidget(self.texto, 0, Qt.AlignmentFlag.AlignHCenter)
        self.boton = boton(boton_texto, "primario") if boton_texto else None
        if self.boton:
            lay.addSpacing(8)
            lay.addWidget(self.boton, 0, Qt.AlignmentFlag.AlignHCenter)


class OpcionPlataforma(QFrame):
    """Tarjeta seleccionable (como un botón de opción grande) con texto que se ajusta."""

    clic = Signal()

    def __init__(self, icono: str, titulo: str, texto: str, color: str):
        super().__init__(objectName="opcion")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.marca = QLabel("○")
        self.marca.setStyleSheet(f"font-size:18px; color:{C['tenue']};")
        textos = QVBoxLayout()
        textos.setSpacing(3)
        textos.addWidget(QLabel(titulo, objectName="tituloTarjeta"))
        d = QLabel(texto, objectName="nota")
        d.setWordWrap(True)
        textos.addWidget(d)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(16)
        lay.addWidget(insignia_icono(icono, color), 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(textos, 1)
        lay.addWidget(self.marca, 0, Qt.AlignmentFlag.AlignTop)
        self.color = color
        self.setStyleSheet(f"QFrame#opcion[seleccionado=\"true\"] {{ border-color: {color}; "
                           f"background: {tinte(color, 0.07)}; }}")
        self.fijar(False)

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

    def texto(self, clave: str, texto: str):
        self.grupo.button(self.claves.index(clave)).setText(texto)


# ============================================================ helpers

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


def tabla(columnas: list[str], anchos: list[int] | None = None, pildoras: tuple[int, ...] = ()) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(42)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.setWordWrap(False)
    t.setMouseTracking(True)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    h.setStretchLastSection(True)
    h.setHighlightSections(False)
    h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for i, ancho in enumerate(anchos or []):
        t.setColumnWidth(i, ancho)
    delegado = DelegadoPildora(t)
    for c in pildoras:
        t.setItemDelegateForColumn(c, delegado)
    return t


def celda(texto, color: str | None = None, dato=None, negrita=False, mono=False, pildora: str | None = None,
          tip: str = "") -> QTableWidgetItem:
    it = QTableWidgetItem(str(texto) if texto not in (None, "") else "—")
    if color:
        it.setForeground(QColor(color))
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
    return it


def llenar_tabla(t: QTableWidget, filas: list[list[QTableWidgetItem]]):
    """Rellena la tabla conservando la fila seleccionada (por el dato de la columna 0)."""
    sel = dato_seleccionado(t)
    t.setUpdatesEnabled(False)
    t.setRowCount(len(filas))
    for r, celdas in enumerate(filas):
        for c, it in enumerate(celdas):
            t.setItem(r, c, it)
    t.clearSelection()
    if sel is not None:
        for r in range(t.rowCount()):
            if t.item(r, 0).data(ROL_DATO) == sel:
                t.selectRow(r)
                break
    t.setUpdatesEnabled(True)


def dato_seleccionado(t: QTableWidget):
    filas = t.selectionModel().selectedRows() if t.selectionModel() else []
    return t.item(filas[0].row(), 0).data(ROL_DATO) if filas and t.item(filas[0].row(), 0) else None


def icono_app() -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(4, 4)   # cuadrícula de 64x64
    grad = QLinearGradient(0, 0, 64, 64)
    grad.setColorAt(0, QColor(C["acento"]))
    grad.setColorAt(1, QColor(C["acento2"]))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, 64, 64, 15, 15)
    p.setBrush(QColor("white"))
    p.drawEllipse(10, 18, 26, 26)
    p.drawRect(30, 27, 26, 8)
    p.drawRect(46, 35, 6, 9)
    p.drawRect(38, 35, 5, 6)
    p.setBrush(QColor(C["acento"]))
    p.drawEllipse(17, 25, 12, 12)
    p.end()
    return QIcon(pm)


QSS = """
* { font-family: "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Inter", "Helvetica Neue", "Noto Sans",
    sans-serif; font-size: 13px; }
QMainWindow, QDialog { background: %(fondo)s; }
QWidget { color: %(texto)s; }
QWidget#raiz, QWidget#pagina, QStackedWidget, QWidget#vacio { background: %(fondo)s; }
QLabel { background: transparent; }
QToolTip { background: %(panel2)s; color: %(texto)s; border: 1px solid %(borde2)s; padding: 7px 9px;
           border-radius: 8px; }

/* ---- barra lateral ---- */
QFrame#lateral { background: %(panel)s; border-right: 1px solid %(borde)s; }
QLabel#marca { font-size: 16px; font-weight: 800; color: #ffffff; }
QLabel#marcaSub { color: %(suave)s; font-size: 11px; }
QWidget#nav { background: transparent; }
QPushButton#navBoton { text-align: left; padding: 10px 12px; border: none; border-radius: 10px;
                       color: %(suave)s; font-weight: 600; background: transparent; }
QPushButton#navBoton:hover { background: %(panel2)s; color: %(texto)s; }
QPushButton#navBoton:checked { background: #1f1a3d; color: #ffffff; }
QFrame#navIndicador { background: %(acento)s; border-radius: 2px; }
QLabel#seccionLateral { color: %(tenue)s; font-size: 10px; font-weight: 700;
                        padding: 10px 12px 2px 12px; }
QPushButton#plataformaChip { text-align: left; background: %(panel2)s; border: 1px solid %(borde)s;
                             border-radius: 10px; padding: 8px 10px; color: %(texto)s; font-weight: 600; }
QPushButton#plataformaChip:hover { border-color: %(borde2)s; }

/* ---- cabecera ---- */
QLabel#tituloPagina { font-size: 24px; font-weight: 800; color: #ffffff; }
QLabel#subtitulo { color: %(suave)s; }
QLineEdit#buscar { background: %(panel)s; border: 1px solid %(borde)s; border-radius: 10px; padding: 8px 12px; }
QLineEdit#buscar:focus { border-color: %(acento)s; }

/* ---- tarjetas ---- */
QFrame#tarjeta, QFrame#kpi { background: %(panel)s; border: 1px solid %(borde)s; border-radius: 16px; }
QFrame#kpi:hover { border-color: %(borde2)s; }
QLabel#kpiTitulo { color: %(suave)s; font-size: 10px; font-weight: 700; }
QLabel#kpiValor { font-size: 30px; font-weight: 800; }
QLabel#kpiSub { color: %(tenue)s; font-size: 11px; }
QLabel#tituloTarjeta { font-size: 15px; font-weight: 700; color: #ffffff; }
QLabel#nota { color: %(suave)s; }
QLabel#tenue { color: %(tenue)s; font-size: 12px; }
QLabel#codigo { background: %(fondo)s; border: 1px dashed %(borde2)s; border-radius: 10px; padding: 12px;
                color: #ffffff; }
QFrame#heroe { border: 1px solid %(borde2)s; border-radius: 20px;
               background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #1d1840, stop:1 #10203a); }
QLabel#heroeTitulo { font-size: 26px; font-weight: 800; color: #ffffff; }
QFrame#plataforma { background: %(panel)s; border: 1px solid %(borde)s; border-radius: 18px; }
QFrame#plataforma:hover { border-color: %(acento)s; }
QFrame#opcion { background: %(panel)s; border: 2px solid %(borde)s; border-radius: 16px; }
QFrame#opcion:hover { border-color: %(borde2)s; }
QFrame#panelDetalle { background: %(panel)s; border-left: 1px solid %(borde)s; }
QFrame#separador { background: %(borde)s; max-height: 1px; min-height: 1px; }

/* ---- vacío ---- */
QLabel#vacioIcono { font-size: 44px; }
QLabel#vacioTitulo { font-size: 18px; font-weight: 700; color: #ffffff; }
QLabel#vacioTexto { color: %(suave)s; }

/* ---- avisos ---- */
QFrame#toast { background: %(panel2)s; border: 1px solid %(borde2)s; border-radius: 14px; }
QLabel#toastTitulo { font-weight: 700; color: #ffffff; }
QLabel#toastTexto { color: %(suave)s; font-size: 12px; }

/* ---- controles ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit {
    background: %(fondo)s; color: %(texto)s; border: 1px solid %(borde2)s; border-radius: 10px;
    padding: 8px 10px; selection-background-color: %(acento)s; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QPlainTextEdit:focus {
    border-color: %(acento)s; }
QLineEdit[error="true"] { border-color: %(error)s; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: %(panel2)s; border: 1px solid %(borde2)s; border-radius: 8px;
                              selection-background-color: #2a2457; outline: none; padding: 4px; }
QSpinBox:disabled, QDateEdit:disabled { color: %(tenue)s; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid %(borde2)s;
                       background: %(fondo)s; }
QCheckBox::indicator:checked { background: %(acento)s; border-color: %(acento)s; }
QPushButton { border-radius: 10px; padding: 9px 16px; font-weight: 600; }
QPushButton#primario { color: white; border: none;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 %(acento)s, stop:1 %(acento2)s); }
QPushButton#primario:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #8f74ff, stop:1 #6a9dff); }
QPushButton#primario:pressed { background: %(acento)s; }
QPushButton#secundario { background: %(panel2)s; color: %(texto)s; border: 1px solid %(borde2)s; }
QPushButton#secundario:hover { background: #222838; border-color: #3d4660; }
QPushButton#peligro { background: #2a1519; color: #ff8a8a; border: 1px solid #55232b; }
QPushButton#peligro:hover { background: #3a1a20; }
QPushButton#whatsapp { background: #15803d; color: #ecfdf3; border: none; }
QPushButton#whatsapp:hover { background: #16a34a; }
QPushButton#enlace { background: transparent; border: none; color: %(info)s; padding: 4px 2px; }
QPushButton#enlace:hover { color: #7dd3fc; }
QPushButton#chip { background: transparent; color: %(suave)s; border: 1px solid %(borde2)s; border-radius: 12px;
                   padding: 4px 14px; font-weight: 600; font-size: 12px; }
QPushButton#chip:hover { color: %(texto)s; border-color: #3d4660; }
QPushButton#chip:checked { background: #251f4d; color: #ffffff; border-color: %(acento)s; }
QPushButton:disabled { background: %(panel)s; color: %(tenue)s; border: 1px solid %(borde)s; }

/* ---- tablas ---- */
QTableWidget { background: %(panel)s; alternate-background-color: %(panel2)s; border: 1px solid %(borde)s;
               border-radius: 14px; selection-background-color: #243156; selection-color: #ffffff;
               gridline-color: transparent; }
QTableWidget::item { padding: 0 10px; border: none; }
QTableWidget::item:hover { background: #1f2536; }
QTableWidget::item:selected { background: #243156; }
QHeaderView { background: transparent; }
QHeaderView::section { background: %(panel)s; color: %(tenue)s; border: none; border-bottom: 1px solid %(borde)s;
                       padding: 10px; font-weight: 700; font-size: 11px; }
QTableCornerButton::section { background: %(panel)s; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
QScrollBar::handle { background: %(borde2)s; border-radius: 4px; min-height: 30px; min-width: 30px; }
QScrollBar::handle:hover { background: #46506b; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { width: 0; height: 0;
                                                                                         background: none; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QStatusBar { background: %(panel)s; color: %(suave)s; border-top: 1px solid %(borde)s; padding-left: 12px; }
QMessageBox { background: %(panel)s; }
QMessageBox QLabel { min-width: 320px; }
QMenu { background: %(panel2)s; border: 1px solid %(borde2)s; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 8px 18px; border-radius: 6px; }
QMenu::item:selected { background: #2a2457; }
""" % C
