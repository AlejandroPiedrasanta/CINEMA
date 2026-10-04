"""Cinema Productions · Administrador de Licencias.

Panel SOLO para ti (el vendedor). Se conecta a tus plataformas de venta y a tu servidor de control:
  - Lemon Squeezy, Gumroad y Polar: licencias, equipos activados, ventas y reembolsos.
  - Hotmart: ventas y compradores.
  - Servidor de control (Supabase): tiempo de uso, avisos a tus clientes y bloqueos al instante.
Funciona en Windows, macOS y Linux (Python 3.10+ y PySide6).

Creado por Cinema Productions.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
                               QPushButton, QSystemTrayIcon, QTableWidget, QVBoxLayout, QWidget)

import interfaz as ui
import modelo
from control import ServidorControl, crear_servidor
from dialogos import (DialogoAviso, DialogoConectar, DialogoEditar, DialogoEnlace, DialogoPersona, DialogoResumen,
                      DialogoServidor, DialogoVenta)
from interfaz import (C, PRIVACIDAD, TABLA, BarraTitulo, Bienvenida, BotonVentana, NavLateral, Pila, Spinner, Toast,
                      aplicar_tema, banderas_sin_marco, boton, construir_qss, en_hilo, esquinas_redondeadas_windows,
                      etiqueta, fijar_animaciones, fila, fundido, icono_app, informar, instalar_agarraderas, latido,
                      logo_cinema, pedir_texto, preguntar, priv_nombre)
from modelo import (APP_TITULO, MARCA, VERSION, cargar_config, cargar_todo, config_base,  # noqa: F401
                    construir_modelo, datos_para_programa, estado_licencia,  # noqa: F401
                     fmt_fecha, guardar_config, partir_instancia, solo_digitos,
                    texto_config_programa)
from paginas import (EVENTOS, P_ACTIVIDAD, P_AJUSTES, P_CONEXIONES, P_INICIO, P_LICENCIAS, P_USO, PAGINAS,
                     Pagina)
from plataformas import (PLATAFORMAS, ErrorApi, Gumroad, Hotmart, LemonSqueezy, Polar, ahora_iso,  # noqa: F401
                         crear_cliente)
from temas import DENSIDADES, ESP_LG, ESP_SM, TEMAS

__author__ = "Cinema Productions"

SECCIONES = {P_INICIO: "Panel", P_USO: "Control", P_CONEXIONES: "Sistema"}
ANCHO_LATERAL, ANCHO_PLEGADO = 236, 72
_VENTANAS: list = []           # referencia a la ventana activa (al cambiar de tema se crea otra)


def abrir_url(url: str):
    if url:
        QDesktopServices.openUrl(QUrl(url))


class Ventana(QMainWindow):
    def __init__(self, estado: dict | None = None):
        super().__init__()
        estado = estado or {}
        self.setWindowFlags(banderas_sin_marco())
        self.setWindowTitle(f"{APP_TITULO}  ·  {MARCA}")
        self.setWindowIcon(icono_app())
        self.resize(1360, 860)
        self.setMinimumSize(1080, 680)
        self.cfg = estado.get("cfg") or cargar_config()
        self.escala_inicial = estado.get("escala_inicial", self.cfg.get("escala", 1.0))
        self.aplicar_preferencias(guardar=False)
        self.clientes: dict = {}
        self.errores: dict[str, str] = {}
        self._crear_clientes()
        self.resultados: dict = estado.get("resultados") or {}
        self.modelo = construir_modelo(self.resultados)
        self._huella = None
        self.vistos: set | None = estado.get("vistos")
        self.desactivaciones: list[dict] = estado.get("desactivaciones") or []
        self.registro_auto: list[dict] = estado.get("registro_auto") or []
        self.usos_gumroad: dict[str, int | None] = estado.get("usos_gumroad") or {}
        self.no_vistos = 0
        self.cargando = False
        self._automatico = False
        self._reemplazada = False
        self._salir = False
        self.timer = QTimer(self, interval=self.cfg.get("intervalo", 30) * 1000, timeout=self.refrescar)
        self._construir()
        self._bandeja()
        self._atajos()
        QTimer.singleShot(0, self.iniciar)

    # ---------------------------------------------------------------- utilidades
    def estado(self) -> dict:
        """Lo que pasa a la ventana nueva cuando se cambia de tema (sin volver a descargar todo)."""
        return {"cfg": self.cfg, "resultados": self.resultados, "vistos": self.vistos,
                "desactivaciones": self.desactivaciones, "registro_auto": self.registro_auto,
                "usos_gumroad": self.usos_gumroad, "escala_inicial": self.escala_inicial}

    def guardar(self):
        guardar_config(self.cfg)

    def servidor(self) -> ServidorControl | None:
        return self.clientes.get("control")

    def aviso(self, titulo: str, texto: str = "", tipo: str = "info"):
        Toast.mostrar(self, titulo, texto, tipo)

    def coincide(self, *campos) -> bool:
        f = self.buscar.text().strip().lower()
        return not f or any(f in str(c or "").lower() for c in campos)

    abrir_url = staticmethod(abrir_url)

    def abrir_whatsapp(self, telefono: str, texto: str):
        abrir_url(f"https://wa.me/{solo_digitos(telefono)}?text={urllib.parse.quote(texto)}")

    def abrir_correo(self, correo: str, asunto: str, texto: str):
        abrir_url(f"mailto:{correo}?subject={urllib.parse.quote(asunto)}&body={urllib.parse.quote(texto)}")

    def _crear_clientes(self):
        self.clientes = {}
        for clave in PLATAFORMAS:
            pc = self.cfg["plataformas"].get(clave) or {}
            cliente = crear_cliente(clave, pc)
            if cliente and (clave != "lemonsqueezy" or pc.get("tienda_id")) and \
                    (clave != "polar" or pc.get("organizacion_id")):
                self.clientes[clave] = cliente
        servidor = crear_servidor(self.cfg.get("servidor") or {})
        if servidor:
            self.clientes["control"] = servidor

    # ---------------------------------------------------------------- preferencias
    def aplicar_preferencias(self, guardar: bool = True):
        cfg = self.cfg
        fijar_animaciones(cfg.get("animaciones", True), float(cfg.get("velocidad", 1.0) or 1.0))
        PRIVACIDAD["activa"] = bool(cfg.get("privacidad"))
        PRIVACIDAD["claves"] = bool(cfg.get("privacidad_claves"))
        alto = DENSIDADES.get(cfg.get("densidad", "normal"), DENSIDADES["normal"])
        if alto != TABLA["alto"]:
            TABLA["alto"] = alto
            for t in self.findChildren(QTableWidget):
                t.verticalHeader().setDefaultSectionSize(alto)
        if hasattr(self, "timer"):
            self.timer.setInterval(int(cfg.get("intervalo", 30)) * 1000)
        if guardar:
            self.guardar()

    def fijar_privacidad(self, activa: bool):
        if bool(self.cfg.get("privacidad")) == activa:
            return
        self.cfg["privacidad"] = activa
        self.aplicar_preferencias()
        for control in (self.boton_ojo, getattr(self.paginas[P_AJUSTES], "privado", None)):
            if control is not None and control.isChecked() != activa:
                control.blockSignals(True)
                control.setChecked(activa)
                control.blockSignals(False)
                control.update()
        self.pintar(forzar=True)
        self.aviso("Modo privado activado" if activa else "Modo privado desactivado",
                   "Los nombres y correos se ven ocultos." if activa else "", "info")

    def cambiar_tema(self, nombre: str):
        """Aplica el tema: la ventana se vuelve a construir con los nuevos colores y se funde con la anterior."""
        if nombre not in TEMAS or nombre == C.get("clave"):
            return
        self.cfg["tema"] = nombre
        self.guardar()
        captura = self.grab()
        aplicar_tema(nombre)
        QApplication.instance().setStyleSheet(construir_qss())
        nueva = Ventana(self.estado())
        _VENTANAS[:] = [nueva]
        if self.isMaximized():
            nueva.showMaximized()
        else:
            nueva.setGeometry(self.geometry())
            nueva.show()
        nueva.ir_a(self.pila.currentIndex(), animar=False)
        nueva.plegar_lateral(self.cfg.get("nav_plegada", False), animar=False)
        cubierta = QLabel(nueva)
        cubierta.setPixmap(captura)
        cubierta.setGeometry(0, 0, captura.width(), captura.height())
        cubierta.show()
        cubierta.raise_()
        ui.fundido(cubierta, 1.0, 0.0, 480, cubierta.deleteLater)
        nueva.aviso(f"Tema {TEMAS[nombre]['nombre']}", TEMAS[nombre]["descripcion"], "ok")
        self._reemplazada = True
        self.timer.stop()
        self.tray.hide()
        self.close()
        self.deleteLater()

    def reiniciar(self):
        """Vuelve a abrir el programa (para aplicar el tamaño de la interfaz)."""
        self.guardar()
        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, sys.argv[1:])
        else:
            QProcess.startDetached(sys.executable, [os.path.abspath(sys.argv[0])] + sys.argv[1:])
        self._salir = True
        QApplication.quit()

    # ---------------------------------------------------------------- interfaz
    def _construir(self):
        raiz = QWidget(objectName="raiz")
        self.raiz = raiz
        self.setCentralWidget(raiz)
        v = QVBoxLayout(raiz)
        v.setContentsMargins(1, 1, 1, 1)
        v.setSpacing(0)
        self.barra = BarraTitulo(self, f"{APP_TITULO}  ·  {MARCA}", icono_app())
        self.barra.setProperty("principal", True)
        self.boton_tema = BotonVentana("tema")
        self.boton_tema.clicked.connect(self._menu_temas)
        self.boton_ojo = BotonVentana("ojo")
        self.boton_ojo.setChecked(bool(self.cfg.get("privacidad")))
        self.boton_ojo.toggled.connect(self.fijar_privacidad)
        self.barra.agregar(self.boton_tema)
        self.barra.agregar(self.boton_ojo)
        v.addWidget(self.barra)
        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        v.addLayout(cuerpo, 1)

        self.lateral = QFrame(objectName="lateral")
        self.lateral.setFixedWidth(ANCHO_LATERAL)
        l = QVBoxLayout(self.lateral)
        l.setContentsMargins(12, 16, 12, 14)
        l.setSpacing(4)
        self.logo = QLabel()
        self.logo.setPixmap(icono_app().pixmap(36, 36))
        self.marca = QWidget()
        marca = QVBoxLayout(self.marca)
        marca.setContentsMargins(0, 0, 0, 0)
        marca.setSpacing(0)
        marca.addWidget(etiqueta("Licencias", "marca"))
        marca.addWidget(etiqueta(MARCA, "marcaSub"))
        self.b_plegar = QPushButton("⟨", objectName="colapsar")
        self.b_plegar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_plegar.setToolTip("Plegar el menú")
        self.b_plegar.clicked.connect(lambda: self.plegar_lateral(not self.cfg.get("nav_plegada", False)))
        l.addLayout(fila(self.logo, self.marca, None, self.b_plegar, espacio=10))
        l.addSpacing(ESP_SM)
        self.nav = NavLateral()
        self.paginas: list[Pagina] = []
        for i, clase in enumerate(PAGINAS):
            if i in SECCIONES:
                self.nav.seccion(SECCIONES[i])
            self.paginas.append(clase(self))
            atajo = f"Ctrl+{(i + 1) % 10}"
            self.nav.agregar(clase.icono, clase.titulo, atajo)
        self.nav.cambiado.connect(self.ir_a)
        l.addWidget(self.nav)
        l.addStretch()
        self.seccion_plataformas = etiqueta("CONEXIONES", "seccionLateral")
        l.addWidget(self.seccion_plataformas)
        self.chips_plataforma: dict[str, QPushButton] = {}
        for clave in list(PLATAFORMAS) + ["control"]:
            b = QPushButton(objectName="plataformaChip")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if clave == "control":
                b.clicked.connect(lambda: self.ir_a(P_USO) if self.servidor() else self.conectar_servidor())
            else:
                b.clicked.connect(lambda _=False, k=clave: self.ir_a(P_CONEXIONES) if k in self.clientes
                                  else self.conectar(k))
            self.chips_plataforma[clave] = b
            l.addWidget(b)
        l.addSpacing(ESP_SM)
        self.pie = QLabel()
        self.pie.setPixmap(logo_cinema(10, C["tenue"]))
        self.pie.setToolTip(f"Creado por {MARCA}")
        self.version = etiqueta(f"v{VERSION}", "tenue")
        l.addLayout(fila(self.pie, None, self.version))
        cuerpo.addWidget(self.lateral)

        derecha = QVBoxLayout()
        derecha.setContentsMargins(ESP_LG + 4, 18, ESP_LG + 4, 10)
        derecha.setSpacing(14)
        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        self.lbl_titulo = etiqueta("", "tituloPagina")
        self.lbl_sub = etiqueta("", "subtitulo")
        titulos.addWidget(self.lbl_titulo)
        titulos.addWidget(self.lbl_sub)
        self.buscar = QLineEdit(placeholderText="🔍  Buscar persona, correo, clave, equipo…  (Ctrl+F)",
                                objectName="buscar")
        self.buscar.setFixedWidth(330)
        self.buscar.setClearButtonEnabled(True)
        self.buscar.textChanged.connect(lambda: self.pintar(forzar=True))
        self.spinner = Spinner(20)
        self.btn_refrescar = boton("⟳  Actualizar", tip="Actualizar ahora (F5)")
        self.btn_refrescar.clicked.connect(self.refrescar)
        derecha.addLayout(fila(titulos, None, self.spinner, self.buscar, self.btn_refrescar, espacio=10))
        self.pila = Pila()
        for p in self.paginas:
            self.pila.addWidget(p)
        derecha.addWidget(self.pila, 1)
        self.estado_txt = etiqueta("", "barraEstado")
        self.estado_srv = etiqueta("", "barraEstado")
        self.estado_srv.setTextFormat(Qt.TextFormat.RichText)
        derecha.addLayout(fila(self.estado_txt, None, self.estado_srv))
        cuerpo.addLayout(derecha, 1)
        self._agarraderas = instalar_agarraderas(self, 5)
        self.nav.seleccionar(0)
        self._titulos(0)
        self._chips()
        if self.cfg.get("nav_plegada"):
            self.plegar_lateral(True, animar=False)

    def _menu_temas(self):
        menu = QMenu(self)
        for clave, t in TEMAS.items():
            accion = QAction(("●  " if clave == C.get("clave") else "     ") + t["nombre"], menu)
            accion.triggered.connect(lambda _=False, k=clave: self.cambiar_tema(k))
            menu.addAction(accion)
        menu.addSeparator()
        ajustes = QAction("Más ajustes…", menu)
        ajustes.triggered.connect(lambda: self.ir_a(P_AJUSTES))
        menu.addAction(ajustes)
        menu.exec(self.boton_tema.mapToGlobal(self.boton_tema.rect().bottomLeft()))

    def plegar_lateral(self, plegada: bool, animar: bool = True):
        self.cfg["nav_plegada"] = plegada
        self.guardar()
        self.marca.setVisible(not plegada)
        self.logo.setVisible(not plegada)
        self.version.setVisible(not plegada)
        self.pie.setVisible(not plegada)
        self.seccion_plataformas.setVisible(not plegada)
        self.b_plegar.setText("⟩" if plegada else "⟨")
        self.b_plegar.setToolTip("Mostrar el menú" if plegada else "Plegar el menú")
        self.nav.plegar(plegada)
        self._chips()
        destino = ANCHO_PLEGADO if plegada else ANCHO_LATERAL
        if not animar or not ui.ms(1):
            self.lateral.setFixedWidth(destino)
            return
        from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation
        grupo = QParallelAnimationGroup(self)
        for prop in (b"minimumWidth", b"maximumWidth"):
            a = QPropertyAnimation(self.lateral, prop)
            a.setDuration(ui.ms(260))
            a.setStartValue(self.lateral.width())
            a.setEndValue(destino)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            grupo.addAnimation(a)
        grupo.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)

    def _atajos(self):
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: (self.buscar.setFocus(), self.buscar.selectAll()))
        QShortcut(QKeySequence("F5"), self, self.refrescar)
        QShortcut(QKeySequence("Ctrl+R"), self, self.refrescar)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, lambda: self.boton_ojo.toggle())
        QShortcut(QKeySequence("Escape"), self, lambda: self.buscar.clear() if self.buscar.text() else None)
        for i in range(len(PAGINAS)):
            QShortcut(QKeySequence(f"Ctrl+{(i + 1) % 10}"), self, lambda i=i: self.ir_a(i))

    def _bandeja(self):
        self.tray = QSystemTrayIcon(icono_app(), self)
        self.tray.setToolTip(f"{APP_TITULO} — {MARCA}")
        menu = QMenu()
        abrir = QAction("Abrir el panel", menu)
        abrir.triggered.connect(self.mostrar)
        salir = QAction("Salir", menu)
        salir.triggered.connect(self.salir_de_verdad)
        menu.addAction(abrir)
        menu.addSeparator()
        menu.addAction(salir)
        self.tray.setContextMenu(menu)
        self._menu_bandeja = menu
        self.tray.activated.connect(lambda motivo: self.mostrar() if motivo != QSystemTrayIcon.ActivationReason.Context
                                    else None)
        if QSystemTrayIcon.isSystemTrayAvailable() and self.cfg.get("bandeja", True):
            self.tray.show()

    def mostrar(self):
        self.showNormal() if self.isMinimized() or not self.isVisible() else None
        self.raise_()
        self.activateWindow()

    def salir_de_verdad(self):
        self._salir = True
        self.close()
        QApplication.quit()

    def changeEvent(self, e):
        from PySide6.QtCore import QEvent
        if e.type() == QEvent.Type.WindowStateChange and hasattr(self, "raiz"):
            maxi = self.isMaximized() or self.isFullScreen()
            self.raiz.layout().setContentsMargins(*([0 if maxi else 1] * 4))
            self.raiz.setProperty("maximizada", maxi)
            self.raiz.style().unpolish(self.raiz)
            self.raiz.style().polish(self.raiz)
        super().changeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        esquinas_redondeadas_windows(self)

    def _titulos(self, i: int):
        p = self.paginas[i]
        self.lbl_titulo.setText(p.titulo)
        self.lbl_sub.setText(p.subtitulo)
        fundido(self.lbl_titulo, 0.2, 1.0, 260)

    def _chips(self):
        plegada = self.cfg.get("nav_plegada", False)
        for clave, b in self.chips_plataforma.items():
            p = PLATAFORMAS.get(clave) or {"icono": "📡", "nombre": "Servidor"}
            conectado = clave in self.clientes
            color = C["error"] if clave in self.errores else (C["ok"] if conectado else C["borde2"])
            if plegada:
                b.setText(p["icono"])
            elif conectado:
                b.setText(f"{p['icono']}  {p['nombre']}")
            else:
                b.setText(f"＋  {p['nombre']}")
            b.setToolTip(self.errores.get(clave, "Conectado" if conectado else f"Conectar {p['nombre']}"))
            b.setStyleSheet(f"QPushButton#plataformaChip {{ border-left: 3px solid {color}; "
                            f"color: {C['texto'] if conectado else C['suave']}; }}")

    def ir_a(self, i: int, animar: bool = True):
        cambia = i != self.pila.currentIndex()
        self.nav.seleccionar(i)
        if animar:
            self.pila.ir_a(i)
        else:
            self.pila.setCurrentIndex(i)
        self._titulos(i)
        if cambia:
            self.paginas[i].al_mostrar()
        if i == P_ACTIVIDAD:
            self.no_vistos = 0
            self.nav.insignia(P_ACTIVIDAD, 0)

    # ---------------------------------------------------------------- conexión
    def iniciar(self):
        self.pintar(forzar=True)
        if self.clientes:
            if not self.resultados:
                self.refrescar()
            self.timer.start()

    def conectar(self, plataforma: str = ""):
        d = DialogoConectar(self, plataforma, self.cfg["plataformas"].get(plataforma) or {})
        if d.exec() != DialogoConectar.DialogCode.Accepted or not d.resultado:
            return
        clave, datos, resumen, cliente = d.resultado
        r = DialogoResumen(clave, cliente, resumen, datos, self, self.cfg)
        if r.exec() != DialogoResumen.DialogCode.Accepted:
            return
        self._guardar_conexion(clave, r.datos)

    def _guardar_conexion(self, clave: str, datos: dict):
        if clave == "control":
            self.cfg["servidor"] = datos
        else:
            self.cfg["plataformas"][clave] = datos
        self.guardar()
        self._crear_clientes()
        self.errores.pop(clave, None)
        self.vistos = None
        self._huella = None
        self._chips()
        nombre = "Servidor de control" if clave == "control" else PLATAFORMAS[clave]["nombre"]
        self.aviso(f"{nombre} conectado", "Cargando tus datos…", "ok")
        self.pintar(forzar=True)
        self.refrescar()
        if not self.timer.isActive():
            self.timer.start()

    def ver_informacion(self, clave: str):
        cliente = self.clientes.get(clave)
        if not cliente:
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        pc = self.cfg["plataformas"][clave]

        def ok(resumen):
            QGuiApplication.restoreOverrideCursor()
            r = DialogoResumen(clave, cliente, resumen, pc, self, self.cfg)
            if r.exec() == DialogoResumen.DialogCode.Accepted:
                self.cfg["plataformas"][clave] = r.datos
                self.guardar()
                self._huella = None
                self.pintar(forzar=True)
                self.refrescar()

        def error(e):
            QGuiApplication.restoreOverrideCursor()
            self.aviso(PLATAFORMAS[clave]["nombre"], e, "error")

        args = (pc.get("producto_id") or 0,) if clave == "hotmart" else ((pc.get("producto_id") or "",) if clave in
                                                                          ("gumroad", "polar") else ())
        en_hilo(cliente.conectar, *args, ok=ok, error=error)

    def desconectar(self, clave: str):
        nombre = PLATAFORMAS[clave]["nombre"]
        if not preguntar(self, f"Desconectar {nombre}", f"¿Quitar la conexión con <b>{nombre}</b>?<br><br>"
                         "Se borran las credenciales de esta computadora. Tus datos en la plataforma no cambian.",
                         "Sí, desconectar"):
            return
        self.cfg["plataformas"][clave] = {}
        self._quitar_conexion(clave, nombre)

    def _quitar_conexion(self, clave: str, nombre: str):
        self.guardar()
        self._crear_clientes()
        self.errores.pop(clave, None)
        self.resultados.pop(clave, None)
        self.aviso(f"{nombre} desconectado", "", "info")
        self._aplicar(dict(self.resultados))

    def conectar_servidor(self):
        d = DialogoServidor(self, self.cfg.get("servidor") or {})
        if d.exec() == DialogoServidor.DialogCode.Accepted and d.datos:
            self._guardar_conexion("control", d.datos)

    def desconectar_servidor(self):
        if preguntar(self, "Desconectar el servidor", "¿Quitar la conexión con el servidor de control?<br><br>Tus "
                     "programas seguirán enviando datos al servidor; solo dejarás de verlos aquí.", "Sí, desconectar"):
            self.cfg["servidor"] = {}
            self._quitar_conexion("control", "Servidor de control")

    # ---------------------------------------------------------------- datos
    def refrescar(self):
        if not self.clientes:
            self.pintar(forzar=True)
            return
        if self.cargando:
            return
        self.cargando = True
        self.btn_refrescar.setEnabled(False)
        self.spinner.iniciar()
        clientes, cfg = dict(self.clientes), json.loads(json.dumps(self.cfg))

        def ok(resultados):
            self.cargando = False
            self.btn_refrescar.setEnabled(True)
            self.spinner.detener()
            if set(clientes) != set(self.clientes):
                return self.refrescar()   # cambió la conexión mientras cargaba
            self._aplicar(resultados)

        def error(e):
            self.cargando = False
            self.btn_refrescar.setEnabled(True)
            self.spinner.detener()
            self.aviso("No se pudo actualizar", e, "error")

        en_hilo(cargar_todo, clientes, cfg, ok=ok, error=error)

    def _aplicar(self, resultados: dict):
        nuevos_errores = {k: r["error"] for k, r in resultados.items() if "error" in r}
        for k, e in nuevos_errores.items():
            if self.errores.get(k) != e:
                nombre = "el servidor de control" if k == "control" else PLATAFORMAS[k]["nombre"]
                self.aviso(f"Problema con {nombre}", e, "error")
        self.errores = nuevos_errores
        # si una plataforma falla, se conservan sus últimos datos buenos
        combinados = {k: (self.resultados.get(k, {}) if "error" in r else r) for k, r in resultados.items()
                      if k in self.clientes}
        anteriores = {i["id"]: i for i in self.modelo["instancias"]}
        self.resultados = combinados
        self.modelo = construir_modelo(combinados)
        self._detectar_desactivaciones(anteriores)
        self.estado_txt.setText(f"Actualizado {datetime.now().strftime('%H:%M:%S')}  ·  cada "
                                f"{self.cfg.get('intervalo', 30)} s")
        srv = self.servidor()
        if srv:
            color = C["error"] if "control" in self.errores else C["ok"]
            self.estado_srv.setText(f"<span style='color:{color}'>●</span> Servidor de control  ·  "
                                    f"{self.modelo['en_linea']} en línea")
        else:
            self.estado_srv.setText("")
        self._chips()
        self.pintar()
        self._notificar_nuevos()
        self._control_automatico(nuevos_errores)

    def pintar(self, forzar=False):
        huella = json.dumps([self.resultados, len(self.desactivaciones), sorted(self.clientes), self.errores,
                             len(self.registro_auto)], sort_keys=True, default=str)
        if not forzar and huella == self._huella:
            return
        self._huella = huella
        for p in self.paginas:
            p.pintar(self.modelo)

    def _detectar_desactivaciones(self, anteriores: dict):
        if self.vistos is None:
            return
        actuales = {i["id"] for i in self.modelo["instancias"]}
        for id_, ins in anteriores.items():
            if id_ not in actuales:
                lic = self.modelo["lic_por_id"].get(ins.get("license_key_id")) or {}
                self.desactivaciones.append({"id": id_, "fecha": ahora_iso(), "persona": lic.get("user_name", ""),
                                             "plataforma": ins.get("plataforma", "lemonsqueezy"),
                                             "equipo": partir_instancia(ins["name"])[0] or ins["name"]})

    def eventos(self) -> list[dict]:
        m, evs = self.modelo, []
        for s in m["ventas"]:
            if s["valida"] or s["estado"] in ("Reembolsada", "Contracargo", "En disputa"):
                evs.append({"clave": ("venta", s["id"]), "tipo": "venta", "fecha": s["fecha"],
                            "plataforma": s["plataforma"], "persona": s["cliente"],
                            "detalle": f"{s['producto']} · {s['total_txt']}"})
            if s["reembolso"]:
                evs.append({"clave": ("reembolso", s["id"]), "tipo": "reembolso", "fecha": s["reembolso"],
                            "plataforma": s["plataforma"], "persona": s["cliente"],
                            "detalle": f"{s['referencia']} · {s['estado']}"})
        for i in m["instancias"]:
            lic = m["lic_por_id"].get(i.get("license_key_id")) or {}
            evs.append({"clave": ("activacion", i["id"]), "tipo": "activacion", "fecha": i.get("created_at"),
                        "plataforma": i.get("plataforma", "lemonsqueezy"), "persona": lic.get("user_name", ""),
                        "detalle": f"Activó en {partir_instancia(i.get('name', ''))[0] or i.get('name', '')}"})
        for d in self.desactivaciones:
            evs.append({"clave": ("desactivacion", d["id"]), "tipo": "desactivacion", "fecha": d["fecha"],
                        "plataforma": d.get("plataforma", "lemonsqueezy"), "persona": d["persona"],
                        "detalle": f"Se desactivó {d['equipo']}"})
        for e in m["eventos_srv"]:
            lic = m["lic_por_id"].get(e.get("lic_id")) or {}
            tipo = e.get("tipo")
            if tipo in ("activacion", "desactivacion") and lic.get("plataforma") in ("lemonsqueezy", "polar"):
                continue      # ya aparecen por la tienda
            detalle = {"licencia_perdida": f"El programa se cerró: {e.get('detalle') or ''}",
                       "reactivada": "El programa volvió a funcionar", "activacion": "Activó el programa",
                       "desactivacion": "Desactivó el programa"}.get(tipo, e.get("detalle") or "")
            evs.append({"clave": ("srv", e.get("id")), "tipo": tipo if tipo in EVENTOS else "auto",
                        "fecha": e.get("creado"), "plataforma": lic.get("plataforma") or "", "persona": e["persona"],
                        "detalle": f"{detalle} · equipo {e.get('equipo') or ''}".strip(" ·"), "desde_programa": True})
        for r in self.registro_auto:
            evs.append({"clave": ("auto", r["id"]), "tipo": "auto", "fecha": r["fecha"],
                        "plataforma": r.get("plataforma") or "", "persona": r.get("persona") or "",
                        "detalle": r["detalle"]})
        return sorted(evs, key=lambda e: e["fecha"] or "", reverse=True)

    def _notificar_nuevos(self):
        evs = self.eventos()
        claves = {e["clave"] for e in evs}
        if self.vistos is None:            # primera carga: no avisar de lo viejo
            self.vistos = claves
            return
        nuevos = [e for e in evs if e["clave"] not in self.vistos]
        self.vistos |= claves
        if not nuevos:
            return
        if self.pila.currentIndex() != P_ACTIVIDAD:
            self.no_vistos += len(nuevos)
            self.nav.insignia(P_ACTIVIDAD, self.no_vistos)
            latido(self.nav.botones[P_ACTIVIDAD], C["ok"] if any(e["tipo"] == "venta" for e in nuevos) else C["acento"])
        if not self.cfg.get("notificaciones", True):
            return
        for e in [e for e in nuevos if e["tipo"] != "auto"][:3]:     # el automático ya avisó al ocurrir
            titulo = EVENTOS.get(e["tipo"], EVENTOS["auto"])[0]
            texto = f"{priv_nombre(e['persona']) or '—'} — {e['detalle']}"
            origen = PLATAFORMAS.get(e["plataforma"], {}).get("nombre", "Programa")
            self.aviso(f"{titulo} · {origen}", texto,
                       "venta" if e["tipo"] == "venta" else ("error" if e["tipo"] in ("reembolso", "licencia_perdida")
                                                             else "info"))
            if self.tray.isVisible():
                self.tray.showMessage(titulo, texto, QSystemTrayIcon.MessageIcon.Information, 6000)
        QApplication.alert(self)

    # ---------------------------------------------------------------- control automático
    def _registrar(self, detalle: str, lic: dict | None = None):
        self.registro_auto.append({"id": f"{len(self.registro_auto)}-{ahora_iso()}", "fecha": ahora_iso(),
                                   "detalle": detalle, "persona": (lic or {}).get("user_name") or
                                   (lic or {}).get("user_email") or "", "plataforma": (lic or {}).get("plataforma")})
        self.registro_auto = self.registro_auto[-200:]

    def _bloquear_en_tienda(self, lic: dict, bloquear: bool):
        """Bloquea o desbloquea la clave en su plataforma (se llama en segundo plano)."""
        pl = lic["plataforma"]
        if pl == "lemonsqueezy" and (ls := self.clientes.get("lemonsqueezy")):
            ls.editar_licencia(lic["id"], {"disabled": bloquear})
        elif pl == "gumroad" and (gr := self.clientes.get("gumroad")):
            gr.bloquear(self._producto_gumroad(lic), lic["key"], bloquear)
        elif pl == "polar" and (po := self.clientes.get("polar")):
            if bloquear or lic.get("status") in ("disabled", "revoked"):
                po.editar_licencia(lic["polar_id"], {"status": "disabled" if bloquear else "granted"})

    def _gumroad_bloqueadas(self, lic: dict, bloquear: bool):
        if lic["plataforma"] != "gumroad":
            return
        pc = self.cfg["plataformas"]["gumroad"]
        bloq = set(pc.get("bloqueadas") or [])
        (bloq.add if bloquear else bloq.discard)(lic["key"])
        pc["bloqueadas"] = sorted(bloq)

    def _control_automatico(self, errores: dict):
        """Reembolsos → bloquear; reembolso cancelado → reactivar; bloqueos programados de los avisos."""
        if self._automatico or not self.modelo["licencias"]:
            return
        cfg, srv = self.cfg, self.servidor()
        ahora = datetime.now(timezone.utc)
        tareas: list[tuple[str, dict, dict]] = []     # (accion, licencia, extra)
        for lic in self.modelo["licencias"]:
            if lic["plataforma"] in errores:
                continue
            auto = cfg["auto_bloqueadas"].get(lic["id"])
            if cfg.get("auto_bloquear_reembolsos", True) and lic["reembolsada"] and not auto:
                tareas.append(("reembolso", lic, {}))
            elif cfg.get("auto_reactivar", True) and auto and auto.get("motivo") == "reembolso" \
                    and lic["compra_valida"]:
                tareas.append(("reactivar", lic, {}))
        for aviso_id, info in list(cfg["remociones"].items()):
            fecha = modelo.a_fecha(info.get("fecha"))
            if fecha and fecha <= ahora:
                for lic_id in info.get("licencias") or []:
                    lic = self.modelo["lic_por_id"].get(lic_id)
                    if lic:
                        tareas.append(("remocion", lic, {"aviso": aviso_id}))
                cfg["remociones"].pop(aviso_id, None)
        if not tareas:
            return
        self._automatico = True
        avisar = cfg.get("avisar_al_bloquear", True)
        nombre_app = cfg.get("nombre_app", "")

        def trabajar():
            hechos = []
            for accion, lic, extra in tareas:
                try:
                    if accion in ("reembolso", "remocion"):
                        if not lic.get("disabled") and lic.get("status") != "revoked":
                            self._bloquear_en_tienda(lic, True)
                        if srv and lic.get("hash"):
                            estado = "reembolsada" if accion == "reembolso" else "revocada"
                            motivo = ("La compra de esta licencia fue reembolsada." if accion == "reembolso"
                                      else "El vendedor retiró esta licencia en la fecha avisada.")
                            srv.fijar_estado(lic["hash"], estado, motivo)
                    else:
                        if lic.get("disabled") or lic.get("status") in ("disabled", "revoked"):
                            self._bloquear_en_tienda(lic, False)
                        if srv and lic.get("hash"):
                            srv.fijar_estado(lic["hash"], "activa", "")
                            if avisar:
                                srv.enviar_aviso([lic["hash"]], "reactivada",
                                                 f"Tu licencia de {nombre_app} está activa otra vez",
                                                 "Se canceló el reembolso de tu compra: tu licencia volvió a estar "
                                                 "activa. ¡Gracias!")
                    hechos.append((accion, lic, None))
                except Exception as e:  # noqa: BLE001
                    hechos.append((accion, lic, str(e)))
            return hechos

        def listo(hechos):
            self._automatico = False
            textos = {"reembolso": "Licencia bloqueada por reembolso", "reactivar": "Reembolso cancelado: licencia "
                                                                                  "reactivada",
                      "remocion": "Licencia removida (fecha del aviso)"}
            for accion, lic, error in hechos:
                if error:
                    self.aviso("No se pudo aplicar el control automático", error, "error")
                    continue
                if accion == "reactivar":
                    cfg["auto_bloqueadas"].pop(lic["id"], None)
                else:
                    cfg["auto_bloqueadas"][lic["id"]] = {"motivo": "reembolso" if accion == "reembolso" else "remocion",
                                                         "fecha": ahora_iso(), "hash": lic.get("hash")}
                self._gumroad_bloqueadas(lic, accion != "reactivar")
                self._registrar(textos[accion], lic)
                self.aviso(textos[accion], priv_nombre(lic.get("user_name") or lic.get("user_email")),
                           "ok" if accion == "reactivar" else "error")
            self.guardar()
            self.refrescar()

        def fallo(e):
            self._automatico = False
            self.aviso("Control automático", e, "error")

        en_hilo(trabajar, ok=listo, error=fallo)

    # ---------------------------------------------------------------- acciones
    def accion(self, fn, *args, mensaje="", despues=None):
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def ok(r):
            QGuiApplication.restoreOverrideCursor()
            if despues:
                despues(r)
            if mensaje:
                self.aviso(mensaje, "", "ok")
            self.refrescar()

        def error(e):
            QGuiApplication.restoreOverrideCursor()
            self.aviso("No se pudo completar", e, "error")

        en_hilo(fn, *args, ok=ok, error=error)

    def ls(self) -> LemonSqueezy | None:
        cliente = self.clientes.get("lemonsqueezy")
        if not cliente:
            self.aviso("Conecta Lemon Squeezy", "Los enlaces de compra y las licencias de regalo se crean con Lemon "
                                                "Squeezy.", "info")
        return cliente

    def ver_licencia(self, id_):
        self.buscar.clear()
        self.ir_a(P_LICENCIAS)
        pag = self.paginas[P_LICENCIAS]
        pag.chips.grupo.button(0).click()
        for r in range(pag.t.rowCount()):
            if pag.t.item(r, 0).data(Qt.ItemDataRole.UserRole) == id_:
                pag.t.selectRow(r)
                pag.t.scrollToItem(pag.t.item(r, 0))
                break

    def ver_persona(self, clave: str):
        if clave in self.modelo["persona_por_clave"]:
            DialogoPersona(self, clave).exec()

    def nueva_venta(self, previo: dict | None = None):
        ls = self.ls()
        if not ls:
            return
        pc = self.cfg["plataformas"]["lemonsqueezy"]
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def mostrar(variantes):
            QGuiApplication.restoreOverrideCursor()
            d = DialogoVenta(variantes, pc.get("moneda", ""), self, previo)
            if d.exec() != DialogoVenta.DialogCode.Accepted:
                return
            venta = d.datos()
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            def creado(url):
                QGuiApplication.restoreOverrideCursor()
                self.aviso("Enlace de compra creado", priv_nombre(venta["cliente"]) or "", "ok")
                DialogoEnlace(url, venta, self.cfg["nombre_app"], self, self).exec()

            en_hilo(ls.crear_enlace, pc["tienda_id"], venta, ok=creado, error=error)

        def error(e):
            QGuiApplication.restoreOverrideCursor()
            self.aviso("Lemon Squeezy", e, "error")

        en_hilo(ls.variantes, pc["tienda_id"], pc.get("producto_id") or 0, ok=mostrar, error=error)

    def dar_licencia(self, nombre: str, correo: str):
        self.nueva_venta({"cliente": nombre, "correo": correo, "precio": "gratis",
                          "telefono": self.cfg["telefonos"].get((correo or "").lower(), "")})

    def editar_licencia(self, lic: dict):
        d = DialogoEditar(lic, self)
        if d.exec() != DialogoEditar.DialogCode.Accepted:
            return
        datos = d.datos()
        if lic["plataforma"] == "polar" and (po := self.clientes.get("polar")):
            self.accion(po.editar_licencia, lic["polar_id"], {"limit_activations": datos["activation_limit"],
                                                              "expires_at": datos["expires_at"]},
                        mensaje="Licencia actualizada")
        elif lic["plataforma"] == "lemonsqueezy" and (ls := self.ls()):
            self.accion(ls.editar_licencia, lic["id"], datos, mensaje="Licencia actualizada")

    def alternar_bloqueo(self, lic: dict):
        bloquear = not lic.get("disabled")
        nombre = priv_nombre(lic.get("user_name") or lic.get("user_email"))
        srv = self.servidor()
        if bloquear and not preguntar(self, "Bloquear licencia",
                                      f"¿Bloquear la licencia de <b>{nombre}</b>?<br><br>"
                                      + ("Su programa mostrará un aviso, se cerrará y pedirá licencia en unos minutos."
                                         if srv else "El programa dejará de funcionar la próxima vez que lo revise.")
                                      + " Si la desbloqueas, vuelve a funcionar solo.", "Sí, bloquear"):
            return
        avisar = self.cfg.get("avisar_al_bloquear", True)
        app = self.cfg.get("nombre_app", "")

        def trabajar():
            self._bloquear_en_tienda(lic, bloquear)
            if srv and lic.get("hash"):
                srv.fijar_estado(lic["hash"], "suspendida" if bloquear else "activa",
                                 "El vendedor bloqueó esta licencia." if bloquear else "")
                if avisar and not bloquear:
                    srv.enviar_aviso([lic["hash"]], "reactivada", f"Tu licencia de {app} está activa otra vez",
                                     "El vendedor reactivó tu licencia. Ya puedes seguir usando el programa.")

        def despues(_):
            self._gumroad_bloqueadas(lic, bloquear)
            if not bloquear:
                self.cfg["auto_bloqueadas"].pop(lic["id"], None)
            self.guardar()

        self.accion(trabajar, mensaje=f"Licencia {'bloqueada' if bloquear else 'desbloqueada'}", despues=despues)

    def bloquear_persona(self, clave: str, bloquear: bool) -> bool:
        p = self.modelo["persona_por_clave"].get(clave)
        if not p or not p["licencias"]:
            return False
        nombre = priv_nombre(p["nombre"]) or p["correo"]
        if not preguntar(self, "Bloquear todo" if bloquear else "Reactivar todo",
                         (f"¿Bloquear las <b>{len(p['licencias'])}</b> licencias de <b>{nombre}</b>? Su programa se "
                          "cerrará y pedirá licencia." if bloquear else
                          f"¿Reactivar las licencias de <b>{nombre}</b>? Su programa volverá a funcionar solo."),
                         "Sí, bloquear" if bloquear else "Sí, reactivar", peligro=bloquear):
            return False
        srv = self.servidor()
        licencias = list(p["licencias"])

        def trabajar():
            for lic in licencias:
                if bool(lic.get("disabled")) != bloquear or not bloquear:
                    self._bloquear_en_tienda(lic, bloquear)
                if srv and lic.get("hash"):
                    srv.fijar_estado(lic["hash"], "revocada" if bloquear else "activa",
                                     "El vendedor retiró esta licencia." if bloquear else "")

        def despues(_):
            for lic in licencias:
                self._gumroad_bloqueadas(lic, bloquear)
            self._registrar("Bloqueó todas sus licencias" if bloquear else "Reactivó todas sus licencias",
                            licencias[0])
            self.guardar()

        self.accion(trabajar, mensaje="Licencias bloqueadas" if bloquear else "Licencias reactivadas", despues=despues)
        return True

    def quitar_equipo(self, lic: dict, ins: dict):
        nombre_pc = priv_nombre(partir_instancia(ins["name"])[0] or ins["name"])
        if not preguntar(self, "Quitar equipo",
                         f"¿Desactivar <b>{nombre_pc}</b> de la licencia de <b>{priv_nombre(lic.get('user_name'))}</b>?"
                         "<br><br>Ese equipo dejará de funcionar y la clave quedará libre para activarse en otra "
                         "computadora.", "Sí, quitar"):
            return
        if lic["plataforma"] == "polar" and (po := self.clientes.get("polar")):
            org = self.cfg["plataformas"]["polar"].get("organizacion_id", "")
            self.accion(po.quitar_equipo, org, lic["key"], ins["identifier"], lic["polar_id"],
                        mensaje="Equipo desactivado")
        elif ls := self.ls():
            self.accion(ls.quitar_equipo, lic["key"], ins["identifier"], mensaje="Equipo desactivado")

    def fijar_estado_programa(self, lic: dict, estado: str):
        srv = self.servidor()
        if not srv or not lic.get("hash"):
            return
        motivo = ""
        if estado != "activa":
            motivo = pedir_texto(self, "Suspender en el programa", "¿Qué mensaje verá tu cliente? (el programa se "
                                 "cerrará y pedirá licencia)", "Tu licencia fue suspendida por el vendedor.")
            if motivo is None:
                return
        app = self.cfg.get("nombre_app", "")

        def trabajar():
            srv.fijar_estado(lic["hash"], estado, motivo)
            if estado == "activa" and self.cfg.get("avisar_al_bloquear", True):
                srv.enviar_aviso([lic["hash"]], "reactivada", f"Tu licencia de {app} está activa otra vez",
                                 "El vendedor reactivó tu licencia. Ya puedes seguir usando el programa.")

        self.accion(trabajar, mensaje="Licencia suspendida en el programa" if estado != "activa" else
                    "Licencia reactivada en el programa")

    def nuevo_aviso(self, persona: str | None = None, lic: str | None = None, tipo: str = "info", todos: bool = False):
        srv = self.servidor()
        if not srv:
            self.conectar_servidor()
            return
        destinos: list[tuple[str, list]] = [("📢  Todas las licencias", [None])]
        elegido = 0
        for p in self.modelo["personas"]:
            hashes = [l["hash"] for l in p["licencias"] if l.get("hash")]
            if not hashes:
                continue
            if p["clave"] == persona:
                elegido = len(destinos)
            destinos.append((f"👤  {priv_nombre(p['nombre']) or '—'}  ·  {ui.priv_correo(p['correo'])}"
                             f"  ({len(hashes)} licencia{'s' if len(hashes) > 1 else ''})", hashes))
        if lic and (l := self.modelo["lic_por_id"].get(lic)) and l.get("hash"):
            destinos.append((f"🔑  Solo la clave {ui.priv_clave(l['key'])[-14:]} de "
                             f"{priv_nombre(l.get('user_name')) or '—'}", [l["hash"]]))
            elegido = len(destinos) - 1
        if todos:
            elegido = 0
        d = DialogoAviso(destinos, self.cfg.get("nombre_app", ""), self, elegido, tipo)
        if d.exec() != DialogoAviso.DialogCode.Accepted:
            return
        datos = d.datos()
        hashes = datos["licencias"]

        def creado(filas):
            if datos["bloquear"] and filas:
                ids = [l["id"] for l in self.modelo["licencias"] if l.get("hash") in set(hashes)]
                self.cfg["remociones"][str(filas[0]["id"])] = {"licencias": ids, "fecha": datos["fecha_limite"],
                                                               "destino": datos["destino"]}
                self.guardar()

        self.accion(srv.enviar_aviso, hashes, datos["tipo"], datos["titulo"], datos["mensaje"], datos["fecha_limite"],
                    mensaje="Aviso enviado", despues=creado)

    def borrar_aviso(self, aviso_id):
        srv = self.servidor()
        if srv and preguntar(self, "Borrar aviso", "¿Borrar este aviso? Quienes aún no lo leyeron ya no lo verán.",
                             "Sí, borrar"):
            self.cfg["remociones"].pop(str(aviso_id), None)
            self.accion(srv.borrar_aviso, aviso_id, mensaje="Aviso borrado", despues=lambda _: self.guardar())

    def _pedir_telefono(self, clave: str, nombre: str) -> str:
        guardado = self.cfg["telefonos"].get(clave, "")
        tel = pedir_texto(self, "Enviar por WhatsApp", f"WhatsApp de {priv_nombre(nombre) or 'la persona'} (con "
                          "código de país):", guardado, "50255551234")
        if not tel or not solo_digitos(tel):
            return ""
        self.cfg["telefonos"][clave] = solo_digitos(tel)
        self.guardar()
        return tel

    def _texto_clave(self, lic: dict) -> str:
        return (f"Hola {lic.get('user_name') or ''}, aquí está tu licencia de {self.cfg['nombre_app']}:\n\n"
                f"{lic['key']}\n\nAbre el programa, pega la clave en la ventana de activación y presiona *Activar*.")

    def enviar_clave_whatsapp(self, lic: dict):
        if tel := self._pedir_telefono((lic.get("user_email") or str(lic["id"])).lower(), lic.get("user_name")):
            self.abrir_whatsapp(tel, self._texto_clave(lic))

    def enviar_clave_correo(self, lic: dict):
        if lic.get("user_email"):
            self.abrir_correo(lic["user_email"], f"Tu licencia de {self.cfg['nombre_app']}", self._texto_clave(lic))

    def whatsapp_persona(self, p: dict):
        if tel := self._pedir_telefono(p["clave"], p["nombre"]):
            self.abrir_whatsapp(tel, f"Hola {p['nombre'] or ''}, te escribo sobre {self.cfg['nombre_app']}.")

    # ---------------------------------------------------------------- Gumroad
    def _producto_gumroad(self, lic: dict) -> str:
        return lic.get("producto_id") or (self.cfg["plataformas"].get("gumroad") or {}).get("producto_id") or ""

    def consultar_gumroad(self, lic: dict, listo):
        """Pide a Gumroad los usos y si la clave está bloqueada (sin gastar un uso)."""
        if not (gr := self.clientes.get("gumroad")):
            return

        def ok(info):
            self.usos_gumroad[lic["key"]] = info.get("usos")
            pc = self.cfg["plataformas"]["gumroad"]
            bloq = set(pc.get("bloqueadas") or [])
            if info.get("bloqueada") != (lic["key"] in bloq):      # alguien la cambió desde la web de Gumroad
                (bloq.add if info.get("bloqueada") else bloq.discard)(lic["key"])
                pc["bloqueadas"] = sorted(bloq)
                self.guardar()
                self.refrescar()
            listo(info)

        en_hilo(gr.licencia, self._producto_gumroad(lic), lic["key"], ok=ok, error=lambda e: listo({"error": e}))

    def bloquear_gumroad(self, lic: dict):
        self.alternar_bloqueo(lic)

    def liberar_uso_gumroad(self, lic: dict):
        gr = self.clientes.get("gumroad")
        if gr and preguntar(self, "Liberar un uso",
                            f"¿Restar un uso a la clave de <b>{priv_nombre(lic.get('user_name') or lic.get('user_email'))}"
                            "</b>?<br><br>Así podrá activarla en otra computadora (por ejemplo, si formateó o cambió de "
                            "PC).", "Sí, liberar", peligro=False):
            self.accion(gr.liberar_uso, self._producto_gumroad(lic), lic["key"], mensaje="Uso liberado",
                        despues=lambda usos: self.usos_gumroad.__setitem__(lic["key"], usos))

    # ---------------------------------------------------------------- archivos
    def guardar_config_programa(self):
        try:
            texto = texto_config_programa(self.cfg)
        except ValueError as e:
            informar(self, "No se puede guardar", str(e), "error")
            return
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar cinema_licencias.json",
                                              str(Path.home() / "cinema_licencias.json"), "JSON (*.json)")
        if ruta:
            Path(ruta).write_text(texto, encoding="utf-8")
            self.aviso("Archivo guardado", "Cópialo junto a tu programa (con la carpeta cinema_licencias).", "ok")

    def exportar_csv(self, tipo: str):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar", str(Path.home() / f"{tipo}.csv"), "CSV (*.csv)")
        if not ruta:
            return
        m = self.modelo
        if tipo == "personas":
            cab = ["Nombre", "Correo", "Plataformas", "Estado", "Compras", "Reembolsos", "Licencias", "Equipos",
                   "Horas de uso", "Última vez", "Última compra", "Etiquetas", "Notas"]
            filas = [[p["nombre"], p["correo"], ", ".join(sorted(p["plataformas"])), p["estado"], p["compras"],
                      p["reembolsos"], len(p["licencias"]), max(p["equipos"], p["equipos_tel"]),
                      round(p["uso_seg"] / 3600, 2), fmt_fecha(p["ultima_vez"]), fmt_fecha(p["ultima"]),
                      ", ".join(self.cfg["etiquetas"].get(p["clave"], [])), self.cfg["notas"].get(p["clave"], "")]
                     for p in m["personas"]]
        elif tipo == "licencias":
            cab = ["Cliente", "Correo", "Plataforma", "Estado", "Clave", "Equipos", "Límite", "Horas de uso",
                   "Comprada", "Vence"]
            filas = [[l.get("user_name"), l.get("user_email"), l["plataforma"], estado_licencia(l), l.get("key"),
                      l.get("instances_count"), l.get("activation_limit") or "∞", round(l["uso_seg"] / 3600, 2),
                      fmt_fecha(l.get("created_at")), fmt_fecha(l.get("expires_at"))] for l in m["licencias"]]
        else:
            cab = ["Fecha", "Plataforma", "Cliente", "Correo", "Producto", "Total", "Moneda", "Estado", "Referencia"]
            filas = [[fmt_fecha(s["fecha"]), s["plataforma"], s["cliente"], s["correo"], s["producto"], s["total"],
                      s["moneda"], s["estado"], s["referencia"]] for s in m["ventas"]]
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cab)
            w.writerows(filas)
        self.aviso("Exportado", f"{len(filas)} filas en {Path(ruta).name}", "ok")

    def abrir_carpeta_config(self):
        modelo.CARPETA_CONFIG.mkdir(parents=True, exist_ok=True)
        abrir_url(QUrl.fromLocalFile(str(modelo.CARPETA_CONFIG)).toString())

    def abrir_registro(self):
        abrir_url(QUrl.fromLocalFile(str(modelo.CARPETA_CONFIG / "registro.log")).toString())

    def closeEvent(self, e):
        if (not self._salir and not self._reemplazada and self.cfg.get("cerrar_a_bandeja")
                and self.tray.isVisible()):
            e.ignore()
            self.hide()
            self.tray.showMessage(APP_TITULO, "Sigo vigilando tus ventas y licencias desde aquí.",
                                  QSystemTrayIcon.MessageIcon.Information, 4000)
            return
        if not self._reemplazada:
            self.tray.hide()
        super().closeEvent(e)


def _preparar_registro():
    """En el .exe sin consola no hay salida estándar: los avisos de Python y de Qt van a un archivo
    (registro.log en la carpeta de configuración) en vez de perderse o fallar al escribirse."""
    from PySide6.QtCore import qInstallMessageHandler
    try:
        modelo.CARPETA_CONFIG.mkdir(parents=True, exist_ok=True)
        registro = open(modelo.CARPETA_CONFIG / "registro.log", "w", encoding="utf-8", buffering=1)
    except OSError:
        registro = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None or getattr(sys, "frozen", False):
        sys.stdout = registro
    if sys.stderr is None or getattr(sys, "frozen", False):
        sys.stderr = registro
    qInstallMessageHandler(lambda _tipo, _ctx, mensaje: registro.write(f"[Qt] {mensaje}\n"))


def preparar_aplicacion(argv=None) -> QApplication:
    cfg = cargar_config()
    escala = float(cfg.get("escala") or 1.0)
    if abs(escala - 1.0) > 0.001 and not QApplication.instance():
        os.environ["QT_SCALE_FACTOR"] = f"{escala:g}"
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_TITULO)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName(MARCA)
    app.setWindowIcon(icono_app())
    aplicar_tema(cfg.get("tema"))
    app.setStyleSheet(construir_qss())
    fuente = QFont()
    fuente.setFamilies(ui.LETRA)
    fuente.setPointSizeF(10)
    app.setFont(fuente)
    app.setQuitOnLastWindowClosed(True)
    fijar_animaciones(cfg.get("animaciones", True), float(cfg.get("velocidad", 1.0) or 1.0))
    return app


def main():
    _preparar_registro()
    if getattr(sys, "frozen", False):   # dentro del .exe: indicar a Qt dónde están sus plugins
        os.environ.setdefault("QT_PLUGIN_PATH", str(Path(sys._MEIPASS) / "PySide6" / "plugins"))
    app = preparar_aplicacion()
    bienvenida = Bienvenida(APP_TITULO, f"Lemon Squeezy · Hotmart · Gumroad · Polar   —   v{VERSION}")
    bienvenida.mostrar()
    bienvenida.avanzar(0.45)
    v = Ventana()
    _VENTANAS[:] = [v]
    bienvenida.terminar(v)
    sys.exit(app.exec())


__all__ = ["ErrorApi", "Hotmart", "LemonSqueezy", "Gumroad", "Polar", "Ventana", "main"]

if __name__ == "__main__":
    main()
