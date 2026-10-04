"""Cinema Productions · cinema_licencias — ventanas para tu programa (PySide6).

  - exigir_licencia(): ventana de activación cuando hace falta.
  - mostrar_mi_licencia(): "Ayuda → Mi licencia" (ver datos y desactivar este equipo).
  - VigilanteQt: mientras el programa está abierto muestra los avisos del vendedor y, si la licencia
    deja de valer (reembolso, bloqueo…), avisa con una cuenta regresiva, cierra las ventanas y pide una
    licencia. Si la licencia vuelve a valer (se canceló el reembolso), el programa se abre solo.

Todas las ventanas son sin marco, con botones propios de minimizar, maximizar y cerrar.

Creado por Cinema Productions.
"""
from __future__ import annotations

import math
import time
from datetime import datetime

from PySide6.QtCore import (QEventLoop, QObject, QPoint, QPointF, QPropertyAnimation, QRectF,
                            QRunnable, QSequentialAnimationGroup, Qt, QThreadPool, QTimer, QUrl, QVariantAnimation,
                            Signal)
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, \
    QVBoxLayout, QWidget

from .base import SUSPENSION, Resultado, fecha_texto, ocultar_clave
from .tiendas import NOMBRES
from .ventanas import (ESPACIO, MARCA, PALETA, PALETA_CLARA, PALETA_OSCURA, DialogoSinMarco, IconoEstado,
                       boton_dialogo, dur, fijar_paleta, icono_cinema, informar, logo_cinema, notificar, preguntar,
                       qss_dialogos)

__author__ = "Cinema Productions"

TITULOS_PERDIDA = {
    "reembolsada": "Tu compra fue reembolsada", "bloqueada": "Tu licencia fue bloqueada",
    "revocada": "Tu licencia fue retirada", "vencida": "Tu licencia venció",
    "desactivada": "Este equipo fue desactivado", "invalida": "Tu licencia ya no es válida",
    "sin_conexion": "Hace falta conectarse a internet", "en_uso": "Tu licencia está en uso en otro equipo",
    "otra_tienda": "Tu licencia no es válida", "error": "No se pudo verificar tu licencia",
}
TIPO_AVISO = {"info": "info", "advertencia": "aviso", "remocion": "peligro", "reactivada": "ok",
              "bloqueo": "error"}


# ============================================================ utilidades

def _preparar(lic) -> dict:
    """Colores de las ventanas según la configuración del programa."""
    base = dict(PALETA_CLARA if lic.cfg.tema == "claro" else PALETA_OSCURA)
    if lic.cfg.color_acento:
        acento = QColor(lic.cfg.color_acento)
        base["acento"] = acento.name()
        base["acento2"] = acento.lighter(130).name()
    if PALETA.get("_programa") != lic.cfg.app:
        fijar_paleta(base | {"_programa": lic.cfg.app})
    return PALETA


class _Senales(QObject):
    listo = Signal(object)


class _Trabajo(QRunnable):
    def __init__(self, funcion):
        super().__init__()
        self.funcion, self.senales = funcion, _Senales()

    def run(self):
        try:
            r = self.funcion()
        except Exception as e:  # noqa: BLE001
            r = Resultado(False, "error", str(e) or e.__class__.__name__)
        self.senales.listo.emit(r)


_TRABAJOS: set = set()


def en_segundo_plano(funcion, al_terminar):
    """Ejecuta funcion() fuera del hilo de la ventana y llama al_terminar(resultado) al acabar."""
    t = _Trabajo(funcion)
    _TRABAJOS.add(t)

    def fin(r):
        _TRABAJOS.discard(t)
        try:
            al_terminar(r)
        except RuntimeError:     # la ventana ya se cerró
            pass

    t.senales.listo.connect(fin)
    QThreadPool.globalInstance().start(t)
    return t


class Girador(QWidget):
    """Indicador de carga giratorio."""

    def __init__(self, tam: int = 22, parent=None):
        super().__init__(parent)
        self.setFixedSize(tam, tam)
        self._a = 0
        self._t = QTimer(self, interval=16, timeout=self._girar)

    def _girar(self):
        self._a = (self._a + 7) % 360
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        self._t.start()

    def hideEvent(self, e):
        self._t.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.setPen(QPen(QColor(PALETA["borde2"]), 2.4))
        p.drawEllipse(r)
        p.setPen(QPen(QColor(PALETA["acento"]), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(r, -self._a * 16, 110 * 16)


def _con_espera(funcion, parent=None, texto: str = "Verificando tu licencia…"):
    """Ejecuta funcion() sin congelar la pantalla; si tarda, muestra una ventanita de espera."""
    resultado = {}
    bucle = QEventLoop()
    espera: list[QWidget] = []

    def listo(r):
        resultado["r"] = r
        bucle.quit()

    def mostrar_espera():
        if "r" in resultado:
            return
        w = QWidget(parent, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.WindowStaysOnTopHint)
        w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        w.setStyleSheet(qss_dialogos(PALETA))
        caja = QFrame(w, objectName="dialogoTarjeta")
        lay = QHBoxLayout(caja)
        lay.setContentsMargins(5 * ESPACIO, 4 * ESPACIO, 6 * ESPACIO, 4 * ESPACIO)
        lay.setSpacing(3 * ESPACIO)
        lay.addWidget(Girador(22))
        lay.addWidget(QLabel(texto, objectName="paso"))
        exterior = QVBoxLayout(w)
        exterior.setContentsMargins(0, 0, 0, 0)
        exterior.addWidget(caja)
        w.adjustSize()
        pantalla = QGuiApplication.primaryScreen()
        if pantalla:
            w.move(pantalla.availableGeometry().center() - w.rect().center())
        w.show()
        espera.append(w)

    en_segundo_plano(funcion, listo)
    QTimer.singleShot(400, mostrar_espera)
    if "r" not in resultado:
        bucle.exec()
    for w in espera:
        w.close()
        w.deleteLater()
    return resultado["r"]


def _icono_programa():
    icono = QApplication.windowIcon()
    if icono.isNull():
        from .ventanas import icono_app
        icono = icono_app()
    return icono


def _pie(lic) -> QWidget:
    """ID de equipo y la marca Cinema Productions."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2 * ESPACIO)
    equipo = QLabel(f"ID de equipo: {lic.equipo_id()}", objectName="tenue")
    equipo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lay.addWidget(equipo)
    lay.addStretch(1)
    if lic.cfg.marca:
        lay.addWidget(QLabel("Licencias por", objectName="tenue"))
        logo = QLabel()
        pm = logo_cinema(9, PALETA["tenue"])
        if pm.isNull():
            logo.setText(MARCA)
            logo.setObjectName("tenue")
        else:
            logo.setPixmap(pm)
        logo.setToolTip(f"Sistema de licencias creado por {MARCA}")
        lay.addWidget(logo)
    return w


def _separador() -> QFrame:
    return QFrame(objectName="separador")


def _sacudir(widget: QWidget):
    if not dur(1):
        return
    origen = widget.pos()
    grupo = QSequentialAnimationGroup(widget)
    for dx in (12, -10, 8, -6, 3, 0):
        a = QPropertyAnimation(widget, b"pos")
        a.setDuration(45)
        a.setEndValue(origen + QPoint(dx, 0))
        grupo.addAnimation(a)
    grupo.start(QSequentialAnimationGroup.DeletionPolicy.DeleteWhenStopped)


class Ilustracion(QWidget):
    """Icono del programa que flota suavemente sobre un halo de color."""

    def __init__(self, tam: int = 84):
        super().__init__()
        self.setFixedSize(tam + 24, tam + 24)
        self.pm = _icono_programa().pixmap(tam * 2, tam * 2)
        if self.pm.isNull():
            self.pm = icono_cinema(tam * 2)
        self.tam = tam
        self._f = 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=2 * math.pi, duration=3600)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._fijar)

    def _fijar(self, v):
        self._f = float(v)
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if dur(1):
            self._anim.start()

    def hideEvent(self, e):
        self._anim.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        c = QPointF(self.width() / 2, self.height() / 2)
        halo = QColor(PALETA["acento"])
        for i, alfa in enumerate((26, 16, 8)):
            halo.setAlpha(alfa)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            r = self.tam * (0.42 + 0.1 * i) + 2 * math.sin(self._f + i)
            p.drawEllipse(c, r, r)
        dy = 3 * math.sin(self._f)
        p.drawPixmap(QRectF(c.x() - self.tam / 2, c.y() - self.tam / 2 + dy, self.tam, self.tam), self.pm,
                     QRectF(self.pm.rect()))


# ============================================================ activar

class DialogoActivacion(DialogoSinMarco):
    def __init__(self, lic, resultado: Resultado, parent=None):
        _preparar(lic)
        super().__init__(parent, f"Activar {lic.cfg.app}", ancho=520, icono=_icono_programa())
        self.setStyleSheet(qss_dialogos(PALETA))
        self.lic, self.resultado = lic, resultado
        self._trabajando = False

        self.ilustracion = Ilustracion(80)
        self.exito = IconoEstado("ok", 80)
        self.exito.hide()
        cab = QVBoxLayout()
        cab.setSpacing(ESPACIO)
        cab.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cab.addWidget(self.ilustracion, 0, Qt.AlignmentFlag.AlignHCenter)
        cab.addWidget(self.exito, 0, Qt.AlignmentFlag.AlignHCenter)
        titulo = QLabel(f"Activa {lic.cfg.app}", objectName="titulo")
        titulo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub = QLabel("Para usar el programa necesitas una clave de licencia.", objectName="sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub.setWordWrap(True)
        cab.addWidget(titulo)
        cab.addWidget(sub)
        self.cuerpo.addLayout(cab)

        # aviso del estado (reembolso, bloqueo, sin internet…)
        self.banda = QFrame(objectName="banda")
        banda = QHBoxLayout(self.banda)
        banda.setContentsMargins(3 * ESPACIO, 3 * ESPACIO, 3 * ESPACIO, 3 * ESPACIO)
        banda.setSpacing(3 * ESPACIO)
        tipo = "aviso" if resultado.codigo in ("sin_conexion", "vencida", "desactivada") else "error"
        banda.addWidget(IconoEstado("aviso" if tipo == "aviso" else "error", 30), 0, Qt.AlignmentFlag.AlignTop)
        self.banda_texto = QLabel(f"<b>{TITULOS_PERDIDA.get(resultado.codigo, 'Atención')}</b><br>{resultado.mensaje}")
        self.banda_texto.setWordWrap(True)
        banda.addWidget(self.banda_texto, 1)
        self.banda.setProperty("tipo", tipo)
        self.banda.setVisible(resultado.codigo not in ("sin_licencia",))
        self.cuerpo.addWidget(self.banda)

        compras = lic.enlaces_compra()
        if compras:
            self.cuerpo.addWidget(QLabel("1. Compra tu licencia (te llega la clave por correo):", objectName="paso"))
            fila = QHBoxLayout()
            fila.setSpacing(2 * ESPACIO)
            for tienda, url in compras:
                b = boton_dialogo(tienda if len(compras) > 1 else "Comprar licencia", "comprar")
                b.setToolTip(f"Comprar en {tienda}")
                b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
                fila.addWidget(b)
            self.cuerpo.addLayout(fila)
        self.cuerpo.addWidget(QLabel(("2. " if compras else "") + "Escribe tu clave de licencia:", objectName="paso"))
        self.txt = QLineEdit(placeholderText="Pega aquí tu clave de licencia")
        f = QFont()
        f.setFamilies(["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "monospace"])
        f.setPointSize(12)
        self.txt.setFont(f)
        self.txt.setText((resultado.datos or {}).get("clave", ""))
        self.txt.returnPressed.connect(self.activar)
        pegar = boton_dialogo("Pegar")
        pegar.clicked.connect(lambda: self.txt.setText(QGuiApplication.clipboard().text().strip()))
        fila_clave = QHBoxLayout()
        fila_clave.setSpacing(2 * ESPACIO)
        fila_clave.addWidget(self.txt, 1)
        fila_clave.addWidget(pegar)
        self.cuerpo.addLayout(fila_clave)
        self.msg = QLabel(objectName="msg")
        self.msg.setWordWrap(True)
        self.cuerpo.addWidget(self.msg)

        botones = QHBoxLayout()
        botones.setSpacing(2 * ESPACIO)
        if lic.enlace_whatsapp():
            wa = boton_dialogo("Ayuda por WhatsApp", "whatsapp")
            wa.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(lic.enlace_whatsapp())))
            botones.addWidget(wa)
        if lic.enlace_correo():
            correo = boton_dialogo("Escribir al soporte", "enlace")
            correo.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(lic.enlace_correo())))
            botones.addWidget(correo)
        botones.addStretch(1)
        salir = boton_dialogo("Salir")
        salir.clicked.connect(self.reject)
        self.btn_activar = boton_dialogo("Activar", "primario")
        self.btn_activar.setMinimumWidth(130)
        self.btn_activar.setDefault(True)
        self.btn_activar.clicked.connect(self.activar)
        botones.addWidget(salir)
        botones.addWidget(self.btn_activar)
        self.cuerpo.addLayout(botones)
        self.cuerpo.addWidget(_separador())
        self.cuerpo.addWidget(_pie(lic))

        # Si la licencia guardada quedó suspendida (reembolso, bloqueo…), se vuelve a revisar sola de vez en
        # cuando: si el vendedor la reactiva o se cancela el reembolso, el programa se abre sin hacer nada.
        self._revision = QTimer(self, interval=45_000, timeout=self._revisar)
        if lic.guardada() and resultado.codigo in SUSPENSION | {"sin_conexion"}:
            self._revision.start()
        QTimer.singleShot(0, self.txt.setFocus)

    def mostrar(self, texto: str, error: bool = False, ok: bool = False):
        self.msg.setText(texto)
        self.msg.setProperty("error", error)
        self.msg.setProperty("ok", ok)
        self.msg.style().unpolish(self.msg)
        self.msg.style().polish(self.msg)

    def activar(self):
        if self._trabajando:
            return
        clave = self.txt.text().strip()
        if not clave:
            self.mostrar("Escribe tu clave de licencia.", error=True)
            _sacudir(self.tarjeta)
            return
        self._trabajando = True
        self.btn_activar.setEnabled(False)
        self.btn_activar.setText("Activando…")
        self.mostrar("Verificando con el servidor…")
        en_segundo_plano(lambda: self.lic.activar(clave), self._terminado)

    def _terminado(self, r: Resultado):
        self._trabajando = False
        self.btn_activar.setEnabled(True)
        self.btn_activar.setText("Activar")
        if r.ok:
            self._exito("¡Listo! Tu licencia quedó activada." if r.codigo != "reactivada" else r.mensaje)
        else:
            self.mostrar(r.mensaje, error=True)
            self.txt.setProperty("error", True)
            self.txt.style().unpolish(self.txt)
            self.txt.style().polish(self.txt)
            _sacudir(self.tarjeta)

    def _exito(self, texto: str):
        self._revision.stop()
        self.ilustracion.hide()
        self.exito.show()
        self.banda.hide()
        self.mostrar(texto, ok=True)
        QTimer.singleShot(dur(1100) or 10, self.accept)

    def _revisar(self):
        if self._trabajando:
            return

        def listo(r: Resultado):
            if r.ok and not self._trabajando and self.isVisible():
                if self.lic.servidor:
                    self.lic.servidor.evento(self.lic.guardada() or {}, "reactivada", "")
                self._exito(r.mensaje if r.codigo == "reactivada" else "¡Tu licencia volvió a estar activa!")

        en_segundo_plano(self.lic.comprobar, listo)


def exigir_licencia(lic, parent=None) -> bool:
    """Comprueba la licencia; si no es válida muestra la ventana de activación."""
    _preparar(lic)
    r = _con_espera(lic.comprobar, parent)
    if r.ok:
        if r.codigo == "reactivada":
            notificar("Licencia reactivada", r.mensaje, "ok")
        return True
    return DialogoActivacion(lic, r, parent).exec() == QDialog.DialogCode.Accepted


# ============================================================ mi licencia

class DialogoMiLicencia(DialogoSinMarco):
    def __init__(self, lic, parent=None):
        _preparar(lic)
        super().__init__(parent, "Mi licencia", ancho=500, icono=_icono_programa())
        self.setStyleSheet(qss_dialogos(PALETA))
        self.lic = lic
        self.desactivada = False
        datos = lic.guardada() or {}
        cab = QHBoxLayout()
        cab.setSpacing(3 * ESPACIO)
        cab.addWidget(Ilustracion(56))
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(QLabel(lic.cfg.app, objectName="titulo"))
        suspendida = datos.get("estado") == "suspendida"
        estado = QLabel(("●  Suspendida — " + (datos.get("motivo") or "")) if suspendida else "●  Licencia activa",
                        objectName="msg")
        estado.setWordWrap(True)
        estado.setProperty("error" if suspendida else "ok", True)
        textos.addWidget(estado)
        cab.addLayout(textos, 1)
        self.cuerpo.addLayout(cab)
        self.cuerpo.addWidget(_separador())

        clave = datos.get("clave", "")
        expira = datos.get("expira_ts")
        limite, usados = datos.get("limite"), datos.get("usados")
        ultima = datos.get("ultima_ok")
        grid = QGridLayout()
        grid.setHorizontalSpacing(6 * ESPACIO)
        grid.setVerticalSpacing(ESPACIO)
        pares = [("Licencia de", datos.get("cliente") or "—"), ("Correo", datos.get("correo") or "—"),
                 ("Clave", ocultar_clave(clave) if clave else "—"),
                 ("Comprada en", NOMBRES.get(datos.get("tienda") or "", "—")),
                 ("Vence", fecha_texto(expira) if expira else "Nunca"),
                 ("Usos" if datos.get("tienda") == "gumroad" else "Equipos",
                  (f"{usados} de {limite or 'ilimitados'}" if usados is not None else
                   f"hasta {limite}" if limite else "ilimitados")),
                 ("Este equipo", lic.nombre_equipo()),
                 ("Última verificación", datetime.fromtimestamp(ultima).strftime("%d/%m/%Y %H:%M") if ultima else "—")]
        for i, (t, v) in enumerate(pares):
            fila, col = (i // 2) * 2, i % 2
            grid.addWidget(QLabel(t.upper(), objectName="datoTitulo"), fila, col)
            valor = QLabel(str(v), objectName="dato")
            valor.setWordWrap(True)
            valor.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(valor, fila + 1, col)
        self.cuerpo.addLayout(grid)
        self.msg = QLabel(objectName="msg")
        self.msg.setWordWrap(True)
        self.cuerpo.addWidget(self.msg)
        botones = QHBoxLayout()
        botones.setSpacing(2 * ESPACIO)
        self.btn_desactivar = boton_dialogo("Desactivar este equipo", "peligro")
        self.btn_desactivar.setToolTip("Libera esta computadora para activar la licencia en otra.")
        self.btn_desactivar.setEnabled(bool(clave))
        self.btn_desactivar.clicked.connect(self.desactivar)
        revisar = boton_dialogo("Comprobar ahora")
        revisar.clicked.connect(self.comprobar)
        cerrar = boton_dialogo("Cerrar", "primario")
        cerrar.clicked.connect(self.reject)
        botones.addWidget(self.btn_desactivar)
        botones.addStretch(1)
        botones.addWidget(revisar)
        botones.addWidget(cerrar)
        self.cuerpo.addLayout(botones)
        self.cuerpo.addWidget(_separador())
        self.cuerpo.addWidget(_pie(lic))

    def _mensaje(self, texto: str, error=False, ok=False):
        self.msg.setText(texto)
        self.msg.setProperty("error", error)
        self.msg.setProperty("ok", ok)
        self.msg.style().unpolish(self.msg)
        self.msg.style().polish(self.msg)

    def comprobar(self):
        self._mensaje("Comprobando…")
        en_segundo_plano(self.lic.comprobar, lambda r: self._mensaje(r.mensaje, error=not r.ok, ok=r.ok))

    def desactivar(self):
        if not preguntar(self, "Desactivar licencia", "¿Desactivar la licencia en esta computadora?<br><br>"
                         "El programa se cerrará y podrás activar tu clave en otra computadora.", "Sí, desactivar"):
            return
        self.btn_desactivar.setEnabled(False)
        self._mensaje("Desactivando…")

        def listo(r: Resultado):
            if r.ok:
                self.desactivada = True
                informar(self, "Licencia desactivada", r.mensaje, "ok")
                self.accept()
            else:
                self.btn_desactivar.setEnabled(True)
                self._mensaje(r.mensaje, error=True)

        en_segundo_plano(self.lic.desactivar, listo)


def mostrar_mi_licencia(lic, parent=None) -> bool:
    d = DialogoMiLicencia(lic, parent)
    d.exec()
    return d.desactivada


# ============================================================ avisos y licencia perdida

class DialogoAviso(DialogoSinMarco):
    """Aviso que envió el vendedor desde el Administrador."""

    def __init__(self, lic, aviso: dict, parent=None):
        _preparar(lic)
        super().__init__(parent, f"Aviso de {lic.cfg.app}", ancho=460, icono=_icono_programa())
        self.setStyleSheet(qss_dialogos(PALETA))
        tipo = TIPO_AVISO.get(str(aviso.get("tipo") or "info"), "info")
        cab = QHBoxLayout()
        cab.setSpacing(4 * ESPACIO)
        cab.addWidget(IconoEstado(tipo, 56, latir=tipo in ("peligro", "error")), 0, Qt.AlignmentFlag.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(ESPACIO)
        t = QLabel(aviso.get("titulo") or "Aviso", objectName="mensajeTitulo")
        t.setWordWrap(True)
        m = QLabel(aviso.get("mensaje") or "", objectName="mensajeTexto")
        m.setWordWrap(True)
        m.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        textos.addWidget(t)
        textos.addWidget(m)
        limite = aviso.get("fecha_limite")
        if limite:
            try:
                cuando = datetime.fromisoformat(str(limite).replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y")
            except ValueError:
                cuando = str(limite)
            textos.addWidget(QLabel(f"Fecha límite: <b>{cuando}</b>", objectName="mensajeDetalle"))
        cab.addLayout(textos, 1)
        self.cuerpo.addLayout(cab)
        fila = QHBoxLayout()
        if lic.enlace_whatsapp():
            wa = boton_dialogo("Responder por WhatsApp", "whatsapp")
            wa.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(lic.enlace_whatsapp())))
            fila.addWidget(wa)
        fila.addStretch(1)
        ok = boton_dialogo("Entendido", "primario")
        ok.clicked.connect(self.accept)
        fila.addWidget(ok)
        self.cuerpo.addLayout(fila)
        self.cuerpo.addWidget(_separador())
        self.cuerpo.addWidget(_pie(lic))


class AnilloCuenta(QWidget):
    """Anillo que se vacía durante la cuenta regresiva, con los segundos en el centro."""

    def __init__(self, segundos: int, tam: int = 64):
        super().__init__()
        self.setFixedSize(tam, tam)
        self.total = max(1, segundos)
        self.inicio = time.monotonic()
        self._t = QTimer(self, interval=50, timeout=self.update)
        self._t.start()

    def restante(self) -> float:
        return max(0.0, self.total - (time.monotonic() - self.inicio))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(4, 4, self.width() - 8, self.height() - 8)
        p.setPen(QPen(QColor(PALETA["borde2"]), 4))
        p.drawEllipse(r)
        p.setPen(QPen(QColor(PALETA["error"]), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(r, 90 * 16, int(360 * 16 * self.restante() / self.total))
        f = self.font()
        f.setPixelSize(int(self.height() * 0.32))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(PALETA["titulo"]))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(math.ceil(self.restante())))


class DialogoLicenciaPerdida(DialogoSinMarco):
    """La licencia dejó de valer: avisa y, tras una cuenta regresiva, el programa se cierra."""

    def __init__(self, lic, resultado: Resultado, segundos: int, parent=None):
        _preparar(lic)
        super().__init__(parent, lic.cfg.app, ancho=480, icono=_icono_programa())
        self.setStyleSheet(qss_dialogos(PALETA))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        cab = QHBoxLayout()
        cab.setSpacing(4 * ESPACIO)
        cab.addWidget(IconoEstado("peligro", 56, latir=True), 0, Qt.AlignmentFlag.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(ESPACIO)
        t = QLabel(TITULOS_PERDIDA.get(resultado.codigo, "Tu licencia ya no es válida"), objectName="mensajeTitulo")
        t.setWordWrap(True)
        m = QLabel(resultado.mensaje, objectName="mensajeTexto")
        m.setWordWrap(True)
        textos.addWidget(t)
        textos.addWidget(m)
        cab.addLayout(textos, 1)
        self.cuerpo.addLayout(cab)
        self.anillo = AnilloCuenta(segundos)
        cuenta = QLabel(f"{lic.cfg.app} se cerrará y te pedirá una licencia. Si el vendedor la reactiva, "
                        "se abrirá de nuevo.", objectName="sub")
        cuenta.setWordWrap(True)
        fila = QHBoxLayout()
        fila.setSpacing(4 * ESPACIO)
        fila.addWidget(self.anillo)
        fila.addWidget(cuenta, 1)
        self.cuerpo.addLayout(fila)
        botones = QHBoxLayout()
        botones.addStretch(1)
        ok = boton_dialogo("Entendido", "primario")
        ok.clicked.connect(self.accept)
        botones.addWidget(ok)
        self.cuerpo.addLayout(botones)
        self.cuerpo.addWidget(_separador())
        self.cuerpo.addWidget(_pie(lic))
        QTimer.singleShot(segundos * 1000, self.accept)


class VigilanteQt(QObject):
    """Une el Vigilante (hilo) con las ventanas de Qt. Se crea con licencias.vigilar(ventana)."""

    cambio = Signal(object)
    aviso = Signal(object)

    def __init__(self, lic, ventana=None, al_perder=None, al_recuperar=None, al_aviso=None,
                 cerrar_al_perder: bool = True, mostrar_avisos: bool = True, revisar_min: float | None = None,
                 latido_min: float | None = None):
        super().__init__(QApplication.instance())
        _preparar(lic)
        self.lic, self.ventana = lic, ventana
        self.al_perder, self.al_recuperar, self.al_aviso = al_perder, al_recuperar, al_aviso
        self.cerrar_al_perder, self.mostrar_avisos = cerrar_al_perder, mostrar_avisos
        self._bloqueando = False
        self.cambio.connect(self._cambio)
        self.aviso.connect(self._aviso)
        self.vigilante = lic.iniciar_vigilancia(self.cambio.emit, self.aviso.emit, revisar_min=revisar_min,
                                                latido_min=latido_min)
        self.vigilante.reiniciar(True)
        QApplication.instance().aboutToQuit.connect(self.detener)

    def detener(self):
        self.vigilante.detener()

    def revisar_ya(self):
        self.vigilante.revisar_pronto()

    def _padre(self):
        if self.ventana is not None and self.ventana.isVisible():
            return self.ventana
        return None

    def _aviso(self, aviso: dict):
        if self.al_aviso:
            self.al_aviso(aviso)
        if self.mostrar_avisos:
            DialogoAviso(self.lic, aviso, self._padre()).exec()

    def _cambio(self, r: Resultado):
        if r.ok:
            if r.codigo == "reactivada":
                notificar("Licencia reactivada", r.mensaje, "ok")
            if self.al_recuperar:
                self.al_recuperar(r)
            return
        if self.al_perder:
            self.al_perder(r)
        if self.cerrar_al_perder and not self._bloqueando:
            self._bloquear(r)

    def _bloquear(self, r: Resultado):
        self._bloqueando = True
        try:
            DialogoLicenciaPerdida(self.lic, r, self.lic.cfg.segundos_antes_de_cerrar, self._padre()).exec()
            ocultas = [w for w in QApplication.topLevelWidgets() if w.isVisible() and not isinstance(w, QDialog)]
            for w in ocultas:
                w.hide()
            if DialogoActivacion(self.lic, r).exec() == QDialog.DialogCode.Accepted:
                for w in ocultas:
                    w.show()
                self.vigilante.reiniciar(True)
                if self.al_recuperar:
                    self.al_recuperar(Resultado(True, "activa"))
            else:
                self.detener()
                QApplication.quit()
        finally:
            self._bloqueando = False
