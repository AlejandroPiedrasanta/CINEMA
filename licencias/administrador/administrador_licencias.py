"""Administrador de Licencias — Resolve Creator Subtitles.

Panel SOLO para ti (el vendedor). Se conecta a tus plataformas de venta:
  - Lemon Squeezy: licencias, equipos activados y ventas.
  - Hotmart: ventas y compradores.
Funciona en Windows, macOS y Linux (Python 3.10+ y PySide6).
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout,
                               QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QPushButton, QScrollArea, QSpinBox, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

from interfaz import (ANIMACIONES, C, QSS, Chips, ContadorAnimado, DialogoBase, EstadoVacio, GraficoBarras,
                      NavLateral, OpcionPlataforma, PanelDeslizante, Pila, Spinner, TarjetaKPI, Toast, boton, celda,
                      color_estado, dato_seleccionado, en_hilo, estilo_pildora, etiqueta, fila, fuente_mono, fundido,
                      icono_app, insignia_icono, llenar_tabla, pildora, sacudir, tabla, tarjeta)
from plataformas import (ESTADOS_LICENCIA, PLATAFORMAS, ErrorApi, Hotmart, LemonSqueezy, ahora_iso, crear_cliente,
                         dinero, resumen_ventas)

APP_TITULO = "Administrador de Licencias"
VERSION = "3.0"
CARPETA_CONFIG = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "RCS-Administrador"
ARCHIVO_CONFIG = CARPETA_CONFIG / "config.json"
ARCHIVO_CONFIG_V2 = CARPETA_CONFIG / "config_lemonsqueezy.json"
INTERVALOS = [("15 segundos", 15), ("30 segundos", 30), ("1 minuto", 60), ("5 minutos", 300)]
EVENTOS = {
    "venta": ("Nueva venta", C["ok"]), "reembolso": ("Reembolso", C["error"]),
    "activacion": ("Activación", C["info"]), "desactivacion": ("Equipo desactivado", C["aviso"]),
}


# ============================================================ configuración

def config_base() -> dict:
    return {"version": 3, "nombre_app": "Resolve Creator Subtitles", "animaciones": True, "intervalo": 30,
            "telefonos": {}, "plataformas": {"lemonsqueezy": {}, "hotmart": {}}}


def cargar_config() -> dict:
    cfg = config_base()
    try:
        guardado = json.loads(ARCHIVO_CONFIG.read_text(encoding="utf-8"))
        cfg |= {k: v for k, v in guardado.items() if k != "plataformas"}
        for p, datos in (guardado.get("plataformas") or {}).items():
            cfg["plataformas"][p] = datos or {}
        return cfg
    except Exception:
        pass
    try:   # migrar la configuración de la versión 2 (solo Lemon Squeezy)
        v2 = json.loads(ARCHIVO_CONFIG_V2.read_text(encoding="utf-8"))
        if v2.get("api_key"):
            cfg["plataformas"]["lemonsqueezy"] = {k: v2.get(k) for k in (
                "api_key", "tienda_id", "tienda_nombre", "tienda_url", "moneda", "producto_id",
                "producto_nombre", "url_compra")}
        cfg["nombre_app"] = v2.get("nombre_app") or cfg["nombre_app"]
        cfg["telefonos"] = v2.get("telefonos") or {}
    except Exception:
        pass
    return cfg


def guardar_config(cfg: dict) -> None:
    CARPETA_CONFIG.mkdir(parents=True, exist_ok=True)
    ARCHIVO_CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def datos_para_programa(ls: dict) -> str:
    """Líneas para pegar en la sección CONFIGURACIÓN de licencia_cliente.py."""
    productos = f"({ls['producto_id']},)" if ls.get("producto_id") else "()"
    url = ls.get("url_compra") or ls.get("tienda_url") or ""
    return (f"TIENDA_ID = {ls.get('tienda_id') or 0}\n"
            f"PRODUCTOS_ID = {productos}\n"
            f"URL_COMPRA = \"{url}\"")


# ============================================================ utilidades

def a_fecha(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def fmt_fecha(iso: str | None, hora=True) -> str:
    f = a_fecha(iso)
    return f.strftime("%d/%m/%Y %H:%M" if hora else "%d/%m/%Y") if f else "—"


def hace(iso: str | None) -> str:
    f = a_fecha(iso)
    if not f:
        return "—"
    s = int((datetime.now(timezone.utc) - f).total_seconds())
    if s < 60:
        return "hace un momento"
    if s < 3600:
        return f"hace {s // 60} min"
    if s < 86400:
        return f"hace {s // 3600} h"
    if s < 86400 * 30:
        return f"hace {s // 86400} días"
    return fmt_fecha(iso, hora=False)


def solo_digitos(tel: str) -> str:
    return re.sub(r"\D", "", tel or "")


def partir_instancia(nombre: str) -> tuple[str, str]:
    """'PC-JUAN · 3F2A-91BC-04DE-77A1' → ('PC-JUAN', '3F2A-91BC-04DE-77A1')."""
    pc, _, equipo = (nombre or "").partition(" · ")
    return pc, equipo


def estado_licencia(lic: dict) -> str:
    return ESTADOS_LICENCIA.get(lic.get("status"), lic.get("status_formatted") or "—")


def abrir_url(url: str):
    if url:
        QDesktopServices.openUrl(QUrl(url))


def abrir_whatsapp(telefono: str, texto: str):
    abrir_url(f"https://wa.me/{solo_digitos(telefono)}?text={urllib.parse.quote(texto)}")


def abrir_correo(correo: str, asunto: str, texto: str):
    abrir_url(f"mailto:{correo}?subject={urllib.parse.quote(asunto)}&body={urllib.parse.quote(texto)}")


def copiar(texto: str):
    QGuiApplication.clipboard().setText(texto or "")


def nombre_plataforma(clave: str) -> str:
    p = PLATAFORMAS.get(clave) or {}
    return f"{p.get('icono', '')} {p.get('nombre', clave)}".strip()


def confirmar(parent, titulo: str, texto: str, si="Sí, continuar") -> bool:
    caja = QMessageBox(QMessageBox.Icon.Warning, titulo, texto, parent=parent)
    boton_si = caja.addButton(si, QMessageBox.ButtonRole.AcceptRole)
    caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    caja.exec()
    return caja.clickedButton() is boton_si


# ============================================================ modelo de datos

def cargar_todo(clientes: dict, cfg: dict) -> dict:
    """Se ejecuta en segundo plano: trae los datos de cada plataforma conectada.
    Un error en una plataforma no impide ver la otra."""
    resultado = {}
    for clave, cliente in clientes.items():
        pc = cfg["plataformas"].get(clave) or {}
        try:
            if isinstance(cliente, LemonSqueezy):
                resultado[clave] = cliente.datos(pc.get("tienda_id"), pc.get("producto_id") or 0)
            elif isinstance(cliente, Hotmart):
                resultado[clave] = {"ventas": cliente.ventas(pc.get("producto_id") or 0)}
        except Exception as e:  # noqa: BLE001
            resultado[clave] = {"error": str(e)}
    return resultado


def construir_modelo(resultados: dict) -> dict:
    ls = resultados.get("lemonsqueezy") or {}
    hm = resultados.get("hotmart") or {}
    licencias = sorted(ls.get("licencias") or [], key=lambda x: x.get("created_at") or "", reverse=True)
    instancias = sorted(ls.get("instancias") or [], key=lambda x: x.get("created_at") or "", reverse=True)
    ventas = sorted((ls.get("ventas") or []) + (hm.get("ventas") or []), key=lambda v: v["fecha"] or "",
                    reverse=True)
    por_licencia: dict[int, list[dict]] = {}
    for i in instancias:
        por_licencia.setdefault(i["license_key_id"], []).append(i)

    personas: dict[str, dict] = {}

    def persona(nombre: str, correo: str) -> dict:
        clave = (correo or "").strip().lower() or "nombre:" + (nombre or "?").strip().lower()
        p = personas.setdefault(clave, {"clave": clave, "nombre": nombre, "correo": correo, "plataformas": set(),
                                        "compras": 0, "reembolsos": 0, "licencias": [], "equipos": 0,
                                        "ultima": None})
        p["nombre"] = p["nombre"] or nombre
        return p

    for v in ventas:
        p = persona(v["cliente"], v["correo"])
        p["plataformas"].add(v["plataforma"])
        if v["valida"]:
            p["compras"] += 1
        elif v["estado"] in ("Reembolsada", "Contracargo"):
            p["reembolsos"] += 1
        p["ultima"] = max(p["ultima"] or "", v["fecha"] or "") or None
    for lic in licencias:
        p = persona(lic.get("user_name") or "", lic.get("user_email") or "")
        p["plataformas"].add("lemonsqueezy")
        p["licencias"].append(lic)
        p["equipos"] += len(por_licencia.get(lic["id"], []))
    for p in personas.values():
        activa = any(l.get("status") in ("active", "inactive") for l in p["licencias"])
        p["tiene"] = p["compras"] > 0 or activa
        if p["tiene"]:
            p["estado"] = "Con el programa"
        elif p["reembolsos"]:
            p["estado"] = "Reembolsada"
        elif p["licencias"]:
            p["estado"] = estado_licencia(p["licencias"][0])
        else:
            p["estado"] = "Sin compra válida"
    lista = sorted(personas.values(), key=lambda p: p["ultima"] or "", reverse=True)

    # ventas de los últimos 30 días, por plataforma
    hoy = datetime.now().astimezone().date()
    dias = [hoy - timedelta(days=29 - i) for i in range(30)]
    serie = {k: [0.0] * 30 for k in PLATAFORMAS if resultados.get(k) and "error" not in resultados[k]}
    ingresos: dict[str, float] = {}
    for v in ventas:
        f = a_fecha(v["fecha"])
        if not f or not v["valida"]:
            continue
        d = (f.date() - dias[0]).days
        if 0 <= d < 30 and v["plataforma"] in serie:
            serie[v["plataforma"]][d] += 1
            if v["total"] is not None:
                ingresos[v["moneda"]] = ingresos.get(v["moneda"], 0) + v["total"]

    return {
        "licencias": licencias, "instancias": instancias, "ventas": ventas, "personas": lista,
        "por_licencia": por_licencia, "lic_por_id": {l["id"]: l for l in licencias},
        "venta_por_pedido": {v["id"]: v for v in ventas},
        "dias": [d.strftime("%d/%m") for d in dias], "serie": serie, "ingresos_30": ingresos,
        "ventas_30": int(sum(sum(s) for s in serie.values())),
    }


# ============================================================ diálogos

class DialogoConectar(DialogoBase):
    """Asistente: 1) elegir plataforma  2) pegar credenciales  3) conectar."""

    def __init__(self, parent=None, plataforma: str = "", actual: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Conectar plataforma de ventas")
        self.setMinimumWidth(620)
        self.resultado: tuple[str, dict, dict, object] | None = None
        self.actual = actual or {}
        self.plataforma = plataforma or "lemonsqueezy"

        self.pila = Pila()
        self.pila.addWidget(self._pagina_elegir())
        self.pila.addWidget(self._pagina_credenciales())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.addWidget(self.pila)
        if plataforma:
            self._mostrar_formulario(plataforma, animar=False)

    # ---- paso 1
    def _pagina_elegir(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(etiqueta("¿Dónde vendes tu programa?", "tituloPagina"))
        lay.addWidget(etiqueta("Elige la plataforma que quieres conectar. Puedes conectar las dos.", "nota"))
        lay.addSpacing(6)
        self.opciones: dict[str, OpcionPlataforma] = {}
        for clave, p in PLATAFORMAS.items():
            extra = ("Ideal para licencias: tu programa se activa con la clave que recibe el cliente al comprar."
                     if clave == "lemonsqueezy" else
                     "Mira cuántas personas compraron, reembolsos e ingresos. Hotmart no genera claves de "
                     "licencia: puedes darlas con Lemon Squeezy desde este panel.")
            b = OpcionPlataforma(p["icono"], p["nombre"], f"{p['descripcion']} {extra}", p["color"])
            b.clic.connect(lambda c=clave: self._elegir(c))
            b.fijar(clave == self.plataforma)
            self.opciones[clave] = b
            lay.addWidget(b)
        lay.addStretch()
        seguir = boton("Continuar  →", "primario")
        seguir.clicked.connect(lambda: self._mostrar_formulario(self.plataforma))
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        lay.addLayout(fila(None, cancelar, seguir))
        return w

    def _elegir(self, clave: str):
        self.plataforma = clave
        for c, b in self.opciones.items():
            b.fijar(c == clave)

    # ---- paso 2
    def _pagina_credenciales(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.titulo = etiqueta("", "tituloPagina")
        self.pasos = etiqueta("", "nota", ajustar=True)
        self.pasos.setTextFormat(Qt.TextFormat.RichText)
        self.pasos.setOpenExternalLinks(True)
        lay.addWidget(self.titulo)
        lay.addWidget(self.pasos)

        # Lemon Squeezy
        self.form_ls = QWidget()
        f1 = QFormLayout(self.form_ls)
        f1.setContentsMargins(0, 6, 0, 0)
        f1.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.api_key = QLineEdit(placeholderText="Pega aquí tu API key (empieza por eyJ0…)")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        f1.addRow("API key", self._con_mostrar(self.api_key))

        # Hotmart
        self.form_hm = QWidget()
        f2 = QFormLayout(self.form_hm)
        f2.setContentsMargins(0, 6, 0, 0)
        f2.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.client_id = QLineEdit(placeholderText="Client ID")
        self.client_secret = QLineEdit(placeholderText="Client Secret")
        self.client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.basic = QLineEdit(placeholderText="Opcional: se calcula solo (Basic …)")
        self.sandbox = QCheckBox("Son credenciales de Sandbox (pruebas)")
        f2.addRow("Client ID", self.client_id)
        f2.addRow("Client Secret", self._con_mostrar(self.client_secret))
        f2.addRow("Basic", self.basic)
        f2.addRow("", self.sandbox)
        lay.addWidget(self.form_ls)
        lay.addWidget(self.form_hm)

        self.error = etiqueta("", ajustar=True)
        self.error.setStyleSheet(f"color:{C['error']}")
        lay.addWidget(self.error)
        lay.addStretch()
        self.spinner = Spinner()
        self.estado = etiqueta("", "nota")
        atras = boton("←  Atrás")
        atras.clicked.connect(lambda: self.pila.ir_a(0))
        self.btn_conectar = boton("Conectar", "primario")
        self.btn_conectar.setMinimumWidth(130)
        self.btn_conectar.clicked.connect(self.conectar)
        lay.addLayout(fila(atras, None, self.spinner, self.estado, self.btn_conectar))
        for campo in (self.api_key, self.client_id, self.client_secret):
            campo.returnPressed.connect(self.conectar)
        return w

    @staticmethod
    def _con_mostrar(campo: QLineEdit) -> QHBoxLayout:
        ver = QCheckBox("Mostrar")
        ver.toggled.connect(lambda v: campo.setEchoMode(QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password))
        return fila(campo, ver)

    def _mostrar_formulario(self, clave: str, animar=True):
        self.plataforma = clave
        p = PLATAFORMAS[clave]
        self.titulo.setText(f"{p['icono']}  Conectar {p['nombre']}")
        enlace = f"<a href='{p['ayuda_url']}' style='color:{C['info']}'>"
        if clave == "lemonsqueezy":
            self.pasos.setText(
                f"1. Entra a {enlace}app.lemonsqueezy.com → Settings → API</a><br>"
                "2. Pulsa <b>+</b> para crear una API key, cópiala y pégala aquí.<br>"
                "Solo se guarda en esta computadora.")
            self.api_key.setText(self.actual.get("api_key", ""))
        else:
            self.pasos.setText(
                f"1. Entra a {enlace}Hotmart → Herramientas → Credenciales Hotmart</a><br>"
                "2. Crea una credencial (API Hotmart) y copia el <b>Client ID</b> y el <b>Client Secret</b>.<br>"
                "Solo se guardan en esta computadora.")
            self.client_id.setText(self.actual.get("client_id", ""))
            self.client_secret.setText(self.actual.get("client_secret", ""))
            self.basic.setText(self.actual.get("basic", ""))
            self.sandbox.setChecked(bool(self.actual.get("sandbox")))
        self.form_ls.setVisible(clave == "lemonsqueezy")
        self.form_hm.setVisible(clave == "hotmart")
        self.error.clear()
        if animar:
            self.pila.ir_a(1)
        else:
            self.pila.setCurrentIndex(1)
        (self.api_key if clave == "lemonsqueezy" else self.client_id).setFocus()

    def _datos(self) -> dict:
        if self.plataforma == "lemonsqueezy":
            return {"api_key": self.api_key.text().strip()}
        return {"client_id": self.client_id.text().strip(), "client_secret": self.client_secret.text().strip(),
                "basic": self.basic.text().strip(), "sandbox": self.sandbox.isChecked()}

    def conectar(self):
        datos = self._datos()
        faltan = [k for k in ("api_key", "client_id", "client_secret") if k in datos and not datos[k]]
        if faltan:
            self.error.setText("Completa los datos para conectar.")
            sacudir(self)
            return
        cliente = crear_cliente(self.plataforma, datos)
        self.btn_conectar.setEnabled(False)
        self.spinner.iniciar()
        self.estado.setText(f"Conectando con {PLATAFORMAS[self.plataforma]['nombre']}…")
        self.error.clear()

        def ok(resumen):
            self.spinner.detener()
            self.btn_conectar.setEnabled(True)
            self.resultado = (self.plataforma, self.actual | datos, resumen, cliente)
            self.accept()

        def error(e):
            self.spinner.detener()
            self.btn_conectar.setEnabled(True)
            self.estado.clear()
            self.error.setText(f"✕  {e}")
            sacudir(self)

        en_hilo(cliente.conectar, ok=ok, error=error)


class DialogoResumen(DialogoBase):
    """Ventana emergente con toda la información de la plataforma recién conectada."""

    def __init__(self, plataforma: str, cliente, resumen: dict, datos: dict, parent=None):
        super().__init__(parent)
        self.plataforma, self.cliente, self.resumen = plataforma, cliente, resumen
        self.datos = dict(datos)
        p = PLATAFORMAS[plataforma]
        self.setWindowTitle(f"Conectado a {p['nombre']}")
        self.setMinimumWidth(660)

        icono = insignia_icono(p["icono"], p["color"], 60)
        titulo = etiqueta(f"¡Conectado a {p['nombre']}!", "tituloPagina")
        self.subtitulo = etiqueta("", "nota")
        cab = QVBoxLayout()
        cab.setSpacing(2)
        cab.addWidget(titulo)
        cab.addWidget(self.subtitulo)
        self.modo = pildora()

        self.cuerpo = QVBoxLayout()
        self.cuerpo.setSpacing(12)
        guardar = boton("Guardar y continuar  →", "primario")
        guardar.clicked.connect(self.guardar)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(16)
        lay.addLayout(fila(icono, cab, None, self.modo, espacio=14))
        lay.addLayout(self.cuerpo)
        lay.addLayout(fila(None, cancelar, guardar))
        (self._armar_ls if plataforma == "lemonsqueezy" else self._armar_hotmart)()

    def _fijar_modo(self, texto: str, color: str):
        estilo_pildora(self.modo, texto, color)

    @staticmethod
    def _dato(titulo: str, valor) -> QWidget:
        caja = QFrame(objectName="tarjeta")
        l = QVBoxLayout(caja)
        l.setContentsMargins(14, 10, 14, 10)
        l.setSpacing(2)
        l.addWidget(etiqueta(titulo.upper(), "kpiTitulo"))
        if isinstance(valor, QWidget):
            l.addWidget(valor)
        else:
            v = etiqueta(str(valor), ajustar=True)
            v.setStyleSheet("font-size:14px; font-weight:600; color:#ffffff;")
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            l.addWidget(v)
        return caja

    @staticmethod
    def _contador(valor: float, color: str) -> ContadorAnimado:
        c = ContadorAnimado()
        c.setStyleSheet(f"font-size:24px; font-weight:800; color:{color};")
        QTimer.singleShot(150, lambda: c.fijar(valor))
        return c

    def _vaciar_grid(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()

    # ---- Lemon Squeezy
    def _armar_ls(self):
        u = self.resumen["usuario"]
        self.subtitulo.setText(f"Cuenta de {u.get('name') or '—'}  ·  {u.get('email') or ''}")
        prueba = u.get("modo_prueba")
        self._fijar_modo("MODO PRUEBA" if prueba else ("MODO REAL" if prueba is False else "CONECTADO"),
                         C["aviso"] if prueba else C["ok"])
        tiendas = self.resumen.get("tiendas") or []
        if not tiendas:
            self.cuerpo.addWidget(etiqueta("Tu cuenta aún no tiene tiendas. Crea una en app.lemonsqueezy.com "
                                           "y vuelve a conectar.", "nota", ajustar=True))
            return
        self.tienda = QComboBox()
        for t in tiendas:
            self.tienda.addItem(f"{t.get('name') or 'Tienda'}   (ID {t['id']})", t["id"])
        indice = self.tienda.findData(self.datos.get("tienda_id"))
        self.producto = QComboBox()
        self.producto.currentIndexChanged.connect(self._actualizar_codigo)
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.cuerpo.addLayout(fila(self._dato("Tienda", self.tienda), self._dato("Producto a vigilar", self.producto)))
        self.cuerpo.addLayout(self.grid)
        self.lista_productos = etiqueta("", "nota", ajustar=True)
        self.lista_productos.setTextFormat(Qt.TextFormat.RichText)
        self.cuerpo.addWidget(self.lista_productos)
        self.cuerpo.addWidget(etiqueta("<b>Datos para tu programa</b> — pégalos en <i>licencia_cliente.py</i>:"))
        self.codigo = etiqueta("", "codigo")
        self.codigo.setFont(fuente_mono(10))
        self.codigo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        b_copiar = boton("Copiar")
        b_copiar.clicked.connect(lambda: (copiar(self.codigo.text()), b_copiar.setText("✓ Copiado")))
        cod = fila(self.codigo, b_copiar)
        cod.setStretch(0, 1)
        self.cuerpo.addLayout(cod)
        self.tienda.setCurrentIndex(max(0, indice))
        self.tienda.currentIndexChanged.connect(self._cargar_tienda)
        detalle = self.resumen.get("tienda") or {}
        if detalle.get("id") == self.tienda.currentData():
            self._mostrar_tienda(detalle)
        else:
            self._cargar_tienda()

    def _cargar_tienda(self):
        tienda = self.tienda.currentData()
        self.lista_productos.setText("Cargando productos…")
        en_hilo(self.cliente.detalle_tienda, tienda,
                ok=lambda d: d["id"] == self.tienda.currentData() and self._mostrar_tienda(d),
                error=lambda e: self.lista_productos.setText(f"⚠ {e}"))

    def _mostrar_tienda(self, d: dict):
        self.detalle = d
        t = next((t for t in self.resumen["tiendas"] if t["id"] == d["id"]), {})
        self._vaciar_grid()
        self.grid.addWidget(self._dato("Licencias", self._contador(d["licencias"], C["acento"])), 0, 0)
        self.grid.addWidget(self._dato("Ventas", self._contador(d["ventas"], C["ok"])), 0, 1)
        self.grid.addWidget(self._dato("Productos", self._contador(len(d["productos"]), C["info"])), 0, 2)
        self.grid.addWidget(self._dato("Moneda", t.get("currency") or "—"), 0, 3)
        self.producto.blockSignals(True)
        self.producto.clear()
        self.producto.addItem("Todos los productos", 0)
        for p in d["productos"]:
            self.producto.addItem(f"{p.get('name')}   (ID {p['id']})", p["id"])
        guardado = self.producto.findData(self.datos.get("producto_id"))
        self.producto.setCurrentIndex(guardado if guardado > 0 else (1 if len(d["productos"]) == 1 else 0))
        self.producto.blockSignals(False)
        lineas = []
        for v in d["variantes"]:
            nombre = v["producto"] if v.get("name") in (None, "", "Default") else f"{v['producto']} — {v['name']}"
            claves = (f"<span style='color:{C['ok']}'>✓ genera claves</span>" if v.get("has_license_keys")
                      else f"<span style='color:{C['aviso']}'>⚠ sin claves de licencia</span>")
            precio = f"{v['price'] / 100:,.2f} {t.get('currency') or ''}" if v.get("price") is not None else ""
            lineas.append(f"• <b>{nombre}</b>  {precio}  {claves}")
        self.lista_productos.setText("<br>".join(lineas) or "Esta tienda aún no tiene productos.")
        fundido(self.lista_productos, duracion=300)
        self._actualizar_codigo()

    def _seleccion_ls(self) -> dict:
        t = next((t for t in self.resumen["tiendas"] if t["id"] == self.tienda.currentData()), {})
        prods = (getattr(self, "detalle", None) or {}).get("productos") or []
        p = next((p for p in prods if p["id"] == self.producto.currentData()), {})
        u = self.resumen["usuario"]
        return {"tienda_id": t.get("id", 0), "tienda_nombre": t.get("name", ""), "tienda_url": t.get("url", ""),
                "moneda": t.get("currency", ""), "producto_id": p.get("id", 0), "producto_nombre": p.get("name", ""),
                "url_compra": p.get("buy_now_url", ""), "cuenta": u.get("name", ""), "correo": u.get("email", ""),
                "modo_prueba": u.get("modo_prueba")}

    def _actualizar_codigo(self):
        self.codigo.setText(datos_para_programa(self._seleccion_ls()))

    # ---- Hotmart
    def _armar_hotmart(self):
        r = self.resumen
        sandbox = "Sandbox" in r.get("entorno", "")
        self.subtitulo.setText(f"Credencial {self.datos.get('client_id', '')[:8]}…  ·  token válido "
                               f"{r.get('token_horas', 0):g} h")
        self._fijar_modo("SANDBOX" if sandbox else "PRODUCCIÓN", C["aviso"] if sandbox else C["ok"])
        self.producto = QComboBox()
        self.producto.addItem("Todos los productos", 0)
        for p in r.get("productos") or []:
            self.producto.addItem(f"{p.get('name')}   (ID {p.get('id')})", p.get("id"))
        self.producto.setCurrentIndex(max(0, self.producto.findData(self.datos.get("producto_id"))))
        self.producto.currentIndexChanged.connect(self._recalcular_hotmart)
        self.cuerpo.addLayout(fila(self._dato("Entorno", r.get("entorno", "—")),
                                   self._dato("Producto a vigilar", self.producto)))
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.cuerpo.addLayout(self.grid)
        self._mostrar_hotmart(r)
        nota = etiqueta("Hotmart no crea claves de licencia. Para que un comprador de Hotmart active tu programa, "
                        "usa <b>🎁 Dar licencia</b> en Personas o Ventas (crea una licencia gratis en Lemon Squeezy).",
                        "nota", ajustar=True)
        nota.setTextFormat(Qt.TextFormat.RichText)
        self.cuerpo.addWidget(nota)

    def _mostrar_hotmart(self, r: dict):
        self._vaciar_grid()
        self.grid.addWidget(self._dato("Personas con el programa", self._contador(r["compradores"], C["acento"])), 0, 0)
        self.grid.addWidget(self._dato("Ventas aprobadas", self._contador(r["ventas_validas"], C["ok"])), 0, 1)
        self.grid.addWidget(self._dato("Reembolsos", self._contador(r["reembolsos"], C["error"])), 0, 2)
        self.grid.addWidget(self._dato("Productos", self._contador(len(r.get("productos") or []), C["info"])), 0, 3)
        ingresos = "   ·   ".join(dinero(v, m) for m, v in sorted(r["ingresos"].items())) or "—"
        self.grid.addWidget(self._dato("Ingresos totales", ingresos), 1, 0, 1, 4)

    def _recalcular_hotmart(self):
        producto = self.producto.currentData()

        def ok(ventas):
            if producto == self.producto.currentData():
                self._mostrar_hotmart(self.resumen | resumen_ventas(ventas))

        en_hilo(self.cliente.ventas, producto, 0, ok=ok, error=lambda e: Toast.mostrar(self, "Hotmart", e, "error"))

    def guardar(self):
        if self.plataforma == "lemonsqueezy":
            if not self.resumen.get("tiendas"):
                self.reject()
                return
            self.datos |= self._seleccion_ls()
        else:
            p = self.producto.currentData() or 0
            self.datos |= {"producto_id": p,
                           "producto_nombre": self.producto.currentText().split("   (")[0] if p else "",
                           "entorno": self.resumen.get("entorno", "")}
        self.accept()


class DialogoEditar(DialogoBase):
    """Cambiar los equipos permitidos y la fecha de vencimiento de una licencia."""

    def __init__(self, lic: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar licencia")
        self.setMinimumWidth(500)
        self.limite = QSpinBox(minimum=1, maximum=1000, value=lic.get("activation_limit") or 1)
        self.ilimitado = QCheckBox("Ilimitados")
        self.ilimitado.toggled.connect(lambda v: self.limite.setEnabled(not v))
        self.ilimitado.setChecked(not lic.get("activation_limit"))
        self.vence = QComboBox()
        self.vence.addItems(["Nunca", "Fecha exacta…"])
        self.fecha = QDateEdit(calendarPopup=True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        expira = a_fecha(lic.get("expires_at"))
        self.fecha.setDate(QDate(expira.year, expira.month, expira.day) if expira
                           else QDate.currentDate().addDays(30))
        self.vence.currentIndexChanged.connect(lambda i: self.fecha.setEnabled(i == 1))
        self.vence.setCurrentIndex(1 if expira else 0)
        self.fecha.setEnabled(bool(expira))
        extras = []
        for texto, dias in (("+30 días", 30), ("+1 año", 365)):
            b = boton(texto)
            b.clicked.connect(lambda _=False, d=dias: self._sumar(d))
            extras.append(b)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.addRow("Cliente", etiqueta(f"<b>{lic.get('user_name') or '—'}</b>  {lic.get('user_email') or ''}"))
        form.addRow("Equipos permitidos", fila(self.limite, self.ilimitado))
        form.addRow("Vence", fila(self.vence, self.fecha, *extras))
        guardar = boton("Guardar", "primario")
        guardar.clicked.connect(self.accept)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(14)
        lay.addWidget(etiqueta("✏️  Editar licencia", "tituloPagina"))
        lay.addLayout(form)
        lay.addWidget(etiqueta("«+30 días» y «+1 año» se suman desde hoy, o desde el vencimiento actual si aún no "
                               "ha llegado.", "tenue", ajustar=True))
        lay.addLayout(fila(None, cancelar, guardar))

    def _sumar(self, dias: int):
        desde = self.fecha.date() if self.vence.currentIndex() == 1 else QDate.currentDate()
        self.vence.setCurrentIndex(1)
        self.fecha.setDate(max(desde, QDate.currentDate()).addDays(dias))

    def datos(self) -> dict:
        expira = None
        if self.vence.currentIndex() == 1:
            d = self.fecha.date().toPython()
            expira = datetime(d.year, d.month, d.day, 23, 59, 59).astimezone().isoformat()
        return {"activation_limit": None if self.ilimitado.isChecked() else self.limite.value(),
                "expires_at": expira}


class DialogoVenta(DialogoBase):
    """Crear un enlace de compra (checkout de Lemon Squeezy) para un cliente."""

    VIGENCIA = [("7 días", 7), ("1 día", 1), ("30 días", 30), ("Sin vencimiento", None)]

    def __init__(self, variantes: list[dict], moneda: str, parent=None, previo: dict | None = None):
        super().__init__(parent)
        previo = previo or {}
        self.setWindowTitle("Nuevo enlace de compra")
        self.setMinimumWidth(560)
        self.cliente = QLineEdit(previo.get("cliente", ""), placeholderText="Opcional: se rellena en el pago")
        self.correo = QLineEdit(previo.get("correo", ""), placeholderText="Opcional: ahí le llegará la clave")
        self.telefono = QLineEdit(previo.get("telefono", ""),
                                  placeholderText="Opcional: WhatsApp con código de país, ej. 50255551234")
        self.variante = QComboBox()
        for v in variantes:
            nombre = v["producto"] if v.get("name") in (None, "", "Default") else f"{v['producto']} — {v['name']}"
            precio = f"  ·  {v['price'] / 100:,.2f} {moneda}".rstrip() if v.get("price") is not None else ""
            aviso = "" if v.get("has_license_keys") else "  ⚠ sin claves de licencia"
            self.variante.addItem(nombre + precio + aviso, v["id"])
        self.precio = QComboBox()
        self.precio.addItems(["Precio normal", "Precio especial…", "Gratis (cupón 100 %, un solo uso)"])
        self.monto = QDoubleSpinBox(minimum=0.5, maximum=100000, decimals=2, value=10)
        self.monto.setSuffix(f" {moneda}" if moneda else "")
        self.monto.setVisible(False)
        self.precio.currentIndexChanged.connect(lambda i: self.monto.setVisible(i == 1))
        self.precio.setCurrentIndex({"normal": 0, "especial": 1, "gratis": 2}.get(previo.get("precio"), 0))
        self.vigencia = QComboBox()
        for texto, dias in self.VIGENCIA:
            self.vigencia.addItem(texto, dias)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.addRow("Producto", self.variante)
        form.addRow("Precio", fila(self.precio, self.monto))
        form.addRow("Cliente", self.cliente)
        form.addRow("Correo", self.correo)
        form.addRow("WhatsApp", self.telefono)
        form.addRow("El enlace vence en", self.vigencia)
        crear = boton("Crear enlace", "primario")
        crear.clicked.connect(self.validar)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(14)
        lay.addWidget(etiqueta("🔗  Nuevo enlace de compra", "tituloPagina"))
        lay.addLayout(form)
        lay.addWidget(etiqueta("Lemon Squeezy crea la clave de licencia cuando el cliente completa la compra y se la "
                               "envía por correo. Aparecerá sola en Licencias.", "tenue", ajustar=True))
        lay.addLayout(fila(None, cancelar, crear))

    def validar(self):
        if self.variante.currentData() is None:
            QMessageBox.warning(self, "Sin productos", "Tu tienda no tiene productos. Créalo en Lemon Squeezy "
                                "y activa «Generate license keys».")
            return
        correo = self.correo.text().strip()
        if correo and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
            self.correo.setProperty("error", True)
            self.correo.style().unpolish(self.correo)
            self.correo.style().polish(self.correo)
            sacudir(self)
            return
        self.accept()

    def datos(self) -> dict:
        dias = self.vigencia.currentData()
        return {
            "variante_id": self.variante.currentData(),
            "cliente": self.cliente.text().strip(), "correo": self.correo.text().strip(),
            "telefono": solo_digitos(self.telefono.text()),
            "precio": ("normal", "especial", "gratis")[self.precio.currentIndex()],
            "centavos": round(self.monto.value() * 100),
            "expira": (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat() if dias else None,
        }


class DialogoEnlace(DialogoBase):
    def __init__(self, url: str, venta: dict, nombre_app: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enlace de compra creado")
        self.setMinimumWidth(580)
        texto = (f"Hola{' ' + venta['cliente'] if venta['cliente'] else ''}, aquí puedes obtener tu licencia de "
                 f"{nombre_app}:\n{url}\n\nAl terminar te llegará la clave por correo. Abre el programa, pégala en "
                 "la ventana de activación y presiona *Activar*.")
        enlace = QLineEdit(url, readOnly=True)
        enlace.setFont(fuente_mono(10))
        b_copiar = boton("Copiar enlace")
        b_copiar.clicked.connect(lambda: (copiar(url), b_copiar.setText("✓ Copiado")))
        abrir = boton("Abrir")
        abrir.clicked.connect(lambda: abrir_url(url))
        wa = boton("WhatsApp", "whatsapp")
        wa.clicked.connect(lambda: abrir_whatsapp(venta["telefono"], texto))
        correo = boton("Correo")
        correo.clicked.connect(lambda: abrir_correo(venta["correo"], f"Tu licencia de {nombre_app}", texto))
        correo.setVisible(bool(venta["correo"]))
        listo = boton("Listo", "primario")
        listo.clicked.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(14)
        lay.addWidget(etiqueta(f"✓  Enlace listo para {venta['cliente'] or 'tu cliente'}", "tituloPagina"))
        lay.addWidget(enlace)
        lay.addLayout(fila(b_copiar, abrir, wa, correo, None, listo))


# ============================================================ páginas

class Pagina(QWidget):
    titulo = ""
    subtitulo = ""

    def __init__(self, ventana: "Ventana"):
        super().__init__(objectName="pagina")
        self.v = ventana
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(14)

    def pintar(self, m: dict):
        pass


def _vaciar(lay):
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _vaciar(item.layout())


class PaginaInicio(Pagina):
    titulo = "Inicio"
    subtitulo = "Así va tu programa hoy."

    def __init__(self, v):
        super().__init__(v)
        self.pila = Pila()
        self.pila.addWidget(self._heroe())
        self.pila.addWidget(self._panel())
        self.lay.addWidget(self.pila)

    def _heroe(self) -> QWidget:
        w = QWidget(objectName="pagina")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        heroe = QFrame(objectName="heroe")
        h = QVBoxLayout(heroe)
        h.setContentsMargins(36, 34, 36, 34)
        h.setSpacing(10)
        h.addWidget(etiqueta("👋  ¡Bienvenido!", "heroeTitulo"))
        h.addWidget(etiqueta("Conecta la plataforma donde vendes tu programa para ver quién lo tiene, sus "
                             "licencias, equipos y ventas — todo en un solo lugar.", "nota", ajustar=True))
        h.addSpacing(14)
        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(14)
        for clave, p in PLATAFORMAS.items():
            caja = QFrame(objectName="plataforma")
            c = QVBoxLayout(caja)
            c.setContentsMargins(22, 20, 22, 20)
            c.setSpacing(6)
            c.addWidget(insignia_icono(p["icono"], p["color"], 56))
            c.addWidget(etiqueta(p["nombre"], "tituloTarjeta"))
            c.addWidget(etiqueta(p["descripcion"], "nota", ajustar=True))
            c.addSpacing(6)
            b = boton(f"Conectar {p['nombre']}", "primario")
            b.clicked.connect(lambda _=False, k=clave: self.v.conectar(k))
            c.addWidget(b)
            tarjetas.addWidget(caja)
        h.addLayout(tarjetas)
        lay.addWidget(heroe)
        lay.addStretch()
        return w

    def _panel(self) -> QWidget:
        w = QWidget(objectName="pagina")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        self.k_personas = TarjetaKPI("Personas con el programa", C["acento"], ayuda="Compradores únicos con acceso")
        self.k_licencias = TarjetaKPI("Licencias activas", C["ok"], ayuda="Activadas en al menos un equipo")
        self.k_equipos = TarjetaKPI("Equipos activados", C["info"], ayuda="PCs con tu programa")
        self.k_ventas = TarjetaKPI("Ventas · 30 días", C["aviso"], ayuda="Todas las plataformas")
        self.k_ingresos = TarjetaKPI("Ingresos · 30 días", C["ok"], ayuda="")
        for k in (self.k_personas, self.k_licencias, self.k_equipos, self.k_ventas, self.k_ingresos):
            kpis.addWidget(k)
        lay.addLayout(kpis)

        self.grafico = GraficoBarras()
        self.leyenda = etiqueta("", "tenue")
        self.leyenda.setTextFormat(Qt.TextFormat.RichText)
        graf = tarjeta(fila(etiqueta("Ventas de los últimos 30 días", "tituloTarjeta"), None, self.leyenda),
                       self.grafico)
        graf.layout().setStretch(1, 1)
        self.actividad = QVBoxLayout()
        self.actividad.setSpacing(2)
        ver = boton("Ver toda la actividad  →", "enlace")
        ver.clicked.connect(lambda: self.v.ir_a(5))
        act = tarjeta(etiqueta("Actividad reciente", "tituloTarjeta"), self.actividad, ver)
        act.layout().addStretch()
        abajo = QHBoxLayout()
        abajo.setSpacing(14)
        abajo.addWidget(graf, 3)
        abajo.addWidget(act, 2)
        lay.addLayout(abajo, 1)
        return w

    def pintar(self, m: dict):
        if not self.v.clientes:
            self.pila.setCurrentIndex(0)
            return
        self.pila.setCurrentIndex(1)
        self.k_personas.valor.fijar(sum(1 for p in m["personas"] if p["tiene"]))
        self.k_licencias.valor.fijar(sum(1 for l in m["licencias"] if l.get("status") == "active"))
        self.k_equipos.valor.fijar(len(m["instancias"]))
        self.k_ventas.valor.fijar(m["ventas_30"])
        ingresos = sorted(m["ingresos_30"].items(), key=lambda x: -x[1])
        moneda, total = ingresos[0] if ingresos else ("", 0.0)
        self.k_ingresos.valor.formato = lambda v, mo=moneda: f"{v:,.0f} {mo}".strip()
        self.k_ingresos.valor.fijar(total)
        self.k_ingresos.sub.setText("+ " + ", ".join(dinero(v, mo) for mo, v in ingresos[1:]) if len(ingresos) > 1
                                    else "Ventas válidas")
        conectadas = list(m["serie"])
        self.grafico.fijar(m["dias"], m["serie"], {k: PLATAFORMAS[k]["color"] for k in conectadas},
                           {k: PLATAFORMAS[k]["nombre"] for k in conectadas})
        self.leyenda.setText("   ".join(f"<span style='color:{PLATAFORMAS[k]['color']}'>●</span> "
                                        f"{PLATAFORMAS[k]['nombre']}" for k in conectadas))
        _vaciar(self.actividad)
        eventos = self.v.eventos()[:7]
        if not eventos:
            self.actividad.addWidget(etiqueta("Aún no hay movimientos. Las ventas y activaciones aparecerán aquí.",
                                              "tenue", ajustar=True))
        for e in eventos:
            nombre, color = EVENTOS[e["tipo"]]
            linea = etiqueta(f"<span style='color:{color}; font-size:16px'>●</span>&nbsp; <b>{nombre}</b> · "
                             f"{e['persona'] or '—'}<br><span style='color:{C['tenue']}'>{e['detalle']} · "
                             f"{hace(e['fecha'])}</span>", ajustar=True)
            linea.setTextFormat(Qt.TextFormat.RichText)
            linea.setStyleSheet("padding:5px 2px;")
            self.actividad.addWidget(linea)


class PaginaPersonas(Pagina):
    titulo = "Personas"
    subtitulo = "Quién tiene tu programa, en todas tus plataformas."

    def __init__(self, v):
        super().__init__(v)
        self.total = ContadorAnimado()
        self.total.setStyleSheet(f"font-size:34px; font-weight:800; color:{C['acento']};")
        self.total_txt = etiqueta("personas tienen tu programa", "nota")
        self.desglose = etiqueta("", "tenue")
        self.desglose.setTextFormat(Qt.TextFormat.RichText)
        cab = QVBoxLayout()
        cab.setSpacing(0)
        cab.addWidget(self.total_txt)
        cab.addWidget(self.desglose)
        self.lay.addWidget(tarjeta(fila(self.total, cab, None, espacio=14), margen=16))
        self.chips = Chips([("todas", "Todas"), ("con", "Con el programa"), ("sin", "Sin acceso"),
                            ("lemonsqueezy", "🍋 Lemon Squeezy"), ("hotmart", "🔥 Hotmart")])
        self.chips.cambiado.connect(lambda _: self.pintar(self.v.modelo))
        self.b_copiar = boton("Copiar correo")
        self.b_copiar.clicked.connect(lambda: (p := self.sel()) and (copiar(p["correo"]),
                                                                     self.v.aviso("Correo copiado", p["correo"], "ok")))
        self.b_wa = boton("WhatsApp", "whatsapp")
        self.b_wa.clicked.connect(lambda: (p := self.sel()) and self.v.whatsapp_persona(p))
        self.b_lic = boton("Ver licencia")
        self.b_lic.clicked.connect(lambda: (p := self.sel()) and p["licencias"] and
                                   self.v.ver_licencia(p["licencias"][0]["id"]))
        self.b_dar = boton("🎁  Dar licencia", "primario",
                           "Crea una licencia gratis en Lemon Squeezy para esta persona (ideal para compradores de Hotmart).")
        self.b_dar.clicked.connect(lambda: (p := self.sel()) and self.v.dar_licencia(p["nombre"], p["correo"]))
        self.lay.addLayout(fila(self.chips, None, self.b_copiar, self.b_wa, self.b_lic, self.b_dar))
        self.t = tabla(["Persona", "Correo", "Plataforma", "Estado", "Compras", "Licencia", "Equipos", "Última compra"],
                       [190, 230, 170, 170, 80, 140, 80], pildoras=(3, 5))
        self.t.itemSelectionChanged.connect(self._botones)
        self.vacio = EstadoVacio("👥", "Aún no hay personas", "Cuando alguien compre tu programa aparecerá aquí.")
        self.lay.addWidget(self.t, 1)
        self.lay.addWidget(self.vacio, 1)
        self._botones()

    def sel(self) -> dict | None:
        clave = dato_seleccionado(self.t)
        return next((p for p in self.v.modelo["personas"] if p["clave"] == clave), None)

    def _botones(self):
        p = self.sel()
        self.b_copiar.setEnabled(bool(p and p["correo"]))
        self.b_wa.setEnabled(p is not None)
        self.b_lic.setEnabled(bool(p and p["licencias"]))
        self.b_dar.setEnabled(p is not None and "lemonsqueezy" in self.v.clientes)

    def pintar(self, m: dict):
        personas = m["personas"]
        con = [p for p in personas if p["tiene"]]
        self.total.fijar(len(con))
        por = {k: sum(1 for p in con if k in p["plataformas"]) for k in PLATAFORMAS if k in self.v.clientes}
        self.desglose.setText("   ".join(f"<span style='color:{PLATAFORMAS[k]['color']}'>●</span> "
                                         f"{PLATAFORMAS[k]['nombre']}: <b>{n}</b>" for k, n in por.items())
                              + f"   ·   {len(personas)} en total")
        filtro = self.chips.actual()
        filas = []
        for p in personas:
            if (filtro == "con" and not p["tiene"]) or (filtro == "sin" and p["tiene"]):
                continue
            if filtro in PLATAFORMAS and filtro not in p["plataformas"]:
                continue
            if not self.v.coincide(p["nombre"], p["correo"]):
                continue
            lic = p["licencias"][0] if p["licencias"] else None
            est_lic = estado_licencia(lic) if lic else ""
            color = C["ok"] if p["tiene"] else (C["error"] if p["estado"] == "Reembolsada" else C["tenue"])
            filas.append([
                celda(p["nombre"], dato=p["clave"], negrita=True),
                celda(p["correo"]),
                celda("  ".join(nombre_plataforma(k) for k in sorted(p["plataformas"]))),
                celda(p["estado"], pildora=color),
                celda(p["compras"]),
                celda(est_lic or "Sin licencia", pildora=color_estado(est_lic) if lic else C["tenue"]),
                celda(p["equipos"] or "—"),
                celda(fmt_fecha(p["ultima"], hora=False)),
            ])
        llenar_tabla(self.t, filas)
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        self._botones()


class PaginaLicencias(Pagina):
    titulo = "Licencias"
    subtitulo = "Claves de Lemon Squeezy: bloquea, edita, reenvía o libera equipos."

    def __init__(self, v):
        super().__init__(v)
        self.sin_ls = EstadoVacio("🔑", "Las licencias funcionan con Lemon Squeezy",
                                  "Conecta tu cuenta de Lemon Squeezy para ver y controlar las claves de tu programa.",
                                  "Conectar Lemon Squeezy")
        self.sin_ls.boton.clicked.connect(lambda: self.v.conectar("lemonsqueezy"))
        self.contenido = QWidget(objectName="pagina")
        c = QVBoxLayout(self.contenido)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(12)
        self.chips = Chips([("todas", "Todas"), ("active", "Activas"), ("inactive", "Sin activar"),
                            ("disabled", "Bloqueadas"), ("expired", "Vencidas")])
        self.chips.cambiado.connect(lambda _: self.pintar(self.v.modelo))
        nuevo = boton("＋  Nuevo enlace de compra", "primario",
                      "Enlace de pago (o de regalo) para un cliente. Al completarlo recibe su clave.")
        nuevo.clicked.connect(lambda: self.v.nueva_venta())
        c.addLayout(fila(self.chips, None, nuevo))
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(0)
        self.t = tabla(["Cliente", "Estado", "Clave", "Equipos", "Comprada", "Vence", "Correo"],
                       [180, 140, 330, 80, 120, 100], pildoras=(1,))
        self.t.itemSelectionChanged.connect(self._seleccion)
        self.vacio = EstadoVacio("🔑", "Sin licencias todavía",
                                 "Cuando alguien compre tu programa, Lemon Squeezy creará su clave y aparecerá aquí.",
                                 "Crear enlace de compra")
        self.vacio.boton.clicked.connect(lambda: self.v.nueva_venta())
        izquierda = QVBoxLayout()
        izquierda.addWidget(self.t)
        izquierda.addWidget(self.vacio)
        cuerpo.addLayout(izquierda, 1)
        self.panel = PanelDeslizante(380)
        self.panel_lay = QVBoxLayout(self.panel)
        self.panel_lay.setContentsMargins(22, 18, 22, 18)
        self.panel_lay.setSpacing(10)
        cuerpo.addSpacing(12)
        cuerpo.addWidget(self.panel)
        c.addLayout(cuerpo, 1)
        self.lay.addWidget(self.sin_ls, 1)
        self.lay.addWidget(self.contenido, 1)
        self._lic_panel = None

    def sel(self) -> dict | None:
        return self.v.modelo["lic_por_id"].get(dato_seleccionado(self.t))

    def _seleccion(self):
        lic = self.sel()
        if lic:
            if lic["id"] != self._lic_panel or not self.panel.abierto():
                self._armar_panel(lic)
            if not self.panel.abierto():
                self.panel.abrir()
        else:
            self._lic_panel = None
            self.panel.cerrar()

    def _armar_panel(self, lic: dict):
        self._lic_panel = lic["id"]
        _vaciar(self.panel_lay)
        est = estado_licencia(lic)
        cerrar = QPushButton("✕", objectName="enlace")
        cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        cerrar.clicked.connect(lambda: (self.t.clearSelection(), self.panel.cerrar()))
        nombre = etiqueta(lic.get("user_name") or "—", "tituloTarjeta", ajustar=True)
        nombre.setStyleSheet("font-size:18px;")
        self.panel_lay.addLayout(fila(nombre, None, cerrar))
        self.panel_lay.addWidget(etiqueta(lic.get("user_email") or "", "nota"))
        color = color_estado(est)
        self.panel_lay.addLayout(fila(pildora(f"●  {est}" + ("  ·  prueba" if lic.get("test_mode") else ""), color),
                                      None))
        clave = etiqueta(lic.get("key", ""), "codigo", ajustar=True)
        clave.setFont(fuente_mono(10.5, True))
        clave.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.panel_lay.addWidget(clave)
        limite = lic.get("activation_limit")
        pedido = (self.v.modelo["venta_por_pedido"].get(f"ls-{lic.get('order_id')}") or {}).get("referencia", "—")
        datos = QGridLayout()
        datos.setVerticalSpacing(4)
        for i, (t, valor) in enumerate((("Equipos", f"{lic.get('instances_count', 0)} de {limite or '∞'}"),
                                        ("Vence", fmt_fecha(lic.get("expires_at"), False)
                                         if lic.get("expires_at") else "Nunca"),
                                        ("Comprada", fmt_fecha(lic.get("created_at"), False)),
                                        ("Pedido", pedido))):
            datos.addWidget(etiqueta(t.upper(), "kpiTitulo"), (i // 2) * 2, i % 2)
            datos.addWidget(etiqueta(valor), (i // 2) * 2 + 1, i % 2)
        self.panel_lay.addLayout(datos)
        self.panel_lay.addWidget(QFrame(objectName="separador"))
        self.panel_lay.addWidget(etiqueta("Equipos activados", "tituloTarjeta"))
        equipos = self.v.modelo["por_licencia"].get(lic["id"], [])
        if not equipos:
            self.panel_lay.addWidget(etiqueta("Todavía no la ha activado en ningún equipo.", "tenue", ajustar=True))
        for ins in equipos:
            pc, equipo = partir_instancia(ins.get("name", ""))
            txt = etiqueta(f"💻  <b>{pc or ins.get('name')}</b><br><span style='color:{C['tenue']}'>"
                           f"{equipo or ''}<br>{hace(ins.get('created_at'))}</span>", ajustar=True)
            txt.setTextFormat(Qt.TextFormat.RichText)
            quitar = boton("Quitar", "peligro", "Desactiva esta computadora y libera un equipo de la licencia.")
            quitar.clicked.connect(lambda _=False, i=ins: self.v.quitar_equipo(lic, i))
            self.panel_lay.addLayout(fila(txt, None, quitar))
        self.panel_lay.addStretch()
        b_copiar = boton("Copiar clave")
        b_copiar.clicked.connect(lambda: (copiar(lic["key"]), self.v.aviso("Clave copiada", lic.get("user_name", ""), "ok")))
        wa = boton("WhatsApp", "whatsapp")
        wa.clicked.connect(lambda: self.v.enviar_clave_whatsapp(lic))
        correo = boton("Correo")
        correo.setEnabled(bool(lic.get("user_email")))
        correo.clicked.connect(lambda: self.v.enviar_clave_correo(lic))
        editar = boton("✏️  Editar", tip="Equipos permitidos y fecha de vencimiento")
        editar.clicked.connect(lambda: self.v.editar_licencia(lic))
        self.b_bloquear = boton("Desbloquear" if lic.get("disabled") else "Bloquear",
                                "secundario" if lic.get("disabled") else "peligro")
        self.b_bloquear.clicked.connect(lambda: self.v.alternar_bloqueo(lic))
        self.panel_lay.addLayout(fila(b_copiar, wa, correo))
        self.panel_lay.addLayout(fila(editar, self.b_bloquear, None))
        fundido(self.panel, 0.4, 1.0, 220)

    def pintar(self, m: dict):
        conectado = "lemonsqueezy" in self.v.clientes
        self.sin_ls.setVisible(not conectado)
        self.contenido.setVisible(conectado)
        if not conectado:
            return
        cuenta = {k: sum(1 for l in m["licencias"] if l.get("status") == k)
                  for k in ("active", "inactive", "disabled", "expired")}
        self.chips.texto("todas", f"Todas  {len(m['licencias'])}")
        for k, t in (("active", "Activas"), ("inactive", "Sin activar"), ("disabled", "Bloqueadas"),
                     ("expired", "Vencidas")):
            self.chips.texto(k, f"{t}  {cuenta[k]}")
        filtro = self.chips.actual()
        filas = []
        for lic in m["licencias"]:
            if filtro != "todas" and lic.get("status") != filtro:
                continue
            nombres = [i.get("name") for i in m["por_licencia"].get(lic["id"], [])]
            if not self.v.coincide(lic.get("user_name"), lic.get("user_email"), lic.get("key"), *nombres):
                continue
            est = estado_licencia(lic)
            filas.append([
                celda(lic.get("user_name"), dato=lic["id"], negrita=True),
                celda(est, pildora=color_estado(est)),
                celda(lic.get("key"), "#c9d1e6", mono=True),
                celda(f"{lic.get('instances_count', 0)} / {lic.get('activation_limit') or '∞'}"),
                celda(fmt_fecha(lic.get("created_at"), False)),
                celda(fmt_fecha(lic.get("expires_at"), False) if lic.get("expires_at") else "Nunca",
                      C["aviso"] if est == "Vencida" else None),
                celda(lic.get("user_email")),
            ])
        self.t.blockSignals(True)
        llenar_tabla(self.t, filas)
        self.t.blockSignals(False)
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        lic = self.sel()
        if lic and self.panel.abierto():
            self._armar_panel(lic)        # datos frescos en el panel abierto
        elif not lic and self.panel.abierto():
            self._lic_panel = None
            self.panel.cerrar()


class PaginaEquipos(Pagina):
    titulo = "Equipos"
    subtitulo = "Computadoras donde se activó tu programa."

    def __init__(self, v):
        super().__init__(v)
        self.b_ver = boton("Ver licencia")
        self.b_ver.clicked.connect(lambda: (i := self.sel()) and self.v.ver_licencia(i["license_key_id"]))
        self.b_copiar = boton("Copiar ID")
        self.b_copiar.clicked.connect(lambda: (i := self.sel()) and (
            copiar(partir_instancia(i["name"])[1] or i["identifier"]), self.v.aviso("ID copiado", "", "ok")))
        self.b_quitar = boton("Quitar equipo", "peligro", "Desactiva esta computadora y libera un equipo de la licencia.")
        self.b_quitar.clicked.connect(self._quitar)
        self.lay.addLayout(fila(etiqueta("Cada fila es una computadora con una licencia activada.", "nota"), None,
                                self.b_ver, self.b_copiar, self.b_quitar))
        self.t = tabla(["Equipo", "ID de equipo", "Licencia de", "Estado de la licencia", "Activado"],
                       [210, 200, 200, 170], pildoras=(3,))
        self.t.itemSelectionChanged.connect(self._botones)
        self.vacio = EstadoVacio("💻", "Ningún equipo activado",
                                 "Cuando un cliente active su licencia, su computadora aparecerá aquí.")
        self.lay.addWidget(self.t, 1)
        self.lay.addWidget(self.vacio, 1)
        self._botones()

    def sel(self):
        id_ = dato_seleccionado(self.t)
        return next((i for i in self.v.modelo["instancias"] if i["id"] == id_), None)

    def _botones(self):
        for b in (self.b_ver, self.b_copiar, self.b_quitar):
            b.setEnabled(self.sel() is not None)

    def _quitar(self):
        ins = self.sel()
        lic = self.v.modelo["lic_por_id"].get(ins["license_key_id"]) if ins else None
        if ins and lic:
            self.v.quitar_equipo(lic, ins)

    def pintar(self, m: dict):
        filas = []
        for ins in m["instancias"]:
            lic = m["lic_por_id"].get(ins["license_key_id"]) or {}
            if not self.v.coincide(ins.get("name"), lic.get("user_name"), lic.get("user_email"), lic.get("key")):
                continue
            pc, equipo = partir_instancia(ins.get("name", ""))
            est = estado_licencia(lic) if lic else "—"
            filas.append([celda(pc or ins.get("name"), dato=ins["id"], negrita=True),
                          celda(equipo, "#c9d1e6", mono=True), celda(lic.get("user_name")),
                          celda(est, pildora=color_estado(est)), celda(fmt_fecha(ins.get("created_at")))])
        llenar_tabla(self.t, filas)
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        if "lemonsqueezy" not in self.v.clientes:
            self.vacio.titulo.setText("Los equipos se controlan con Lemon Squeezy")
            self.vacio.texto.setText("Conecta Lemon Squeezy para ver en qué computadoras se activó tu programa.")
        else:
            self.vacio.titulo.setText("Ningún equipo activado")
            self.vacio.texto.setText("Cuando un cliente active su licencia, su computadora aparecerá aquí.")
        self._botones()


class PaginaVentas(Pagina):
    titulo = "Ventas"
    subtitulo = "Todas tus ventas de Lemon Squeezy y Hotmart."

    def __init__(self, v):
        super().__init__(v)
        self.chips = Chips([("todas", "Todas"), ("lemonsqueezy", "🍋 Lemon Squeezy"), ("hotmart", "🔥 Hotmart"),
                            ("reembolsos", "Reembolsos")])
        self.chips.cambiado.connect(lambda _: self.pintar(self.v.modelo))
        self.b_recibo = boton("Abrir recibo")
        self.b_recibo.clicked.connect(lambda: (s := self.sel()) and abrir_url(s["recibo"]))
        self.b_correo = boton("Copiar correo")
        self.b_correo.clicked.connect(lambda: (s := self.sel()) and (copiar(s["correo"]),
                                                                     self.v.aviso("Correo copiado", s["correo"], "ok")))
        self.b_dar = boton("🎁  Dar licencia", tip="Crea una licencia gratis en Lemon Squeezy para este comprador.")
        self.b_dar.clicked.connect(lambda: (s := self.sel()) and self.v.dar_licencia(s["cliente"], s["correo"]))
        nuevo = boton("＋  Nuevo enlace de compra", "primario")
        nuevo.clicked.connect(lambda: self.v.nueva_venta())
        self.resumen = etiqueta("", "nota")
        self.lay.addLayout(fila(self.chips, None, self.b_recibo, self.b_correo, self.b_dar, nuevo))
        self.lay.addWidget(self.resumen)
        self.t = tabla(["Fecha", "Plataforma", "Cliente", "Correo", "Producto", "Total", "Estado", "Referencia"],
                       [140, 150, 170, 210, 220, 110, 150], pildoras=(1, 6))
        self.t.itemSelectionChanged.connect(self._botones)
        self.vacio = EstadoVacio("🛒", "Sin ventas todavía", "Tus ventas aparecerán aquí en cuanto ocurran.")
        self.lay.addWidget(self.t, 1)
        self.lay.addWidget(self.vacio, 1)
        self._botones()

    def sel(self):
        return self.v.modelo["venta_por_pedido"].get(dato_seleccionado(self.t))

    def _botones(self):
        s = self.sel()
        self.b_recibo.setEnabled(bool(s and s["recibo"]))
        self.b_correo.setEnabled(bool(s and s["correo"]))
        self.b_dar.setEnabled(bool(s) and "lemonsqueezy" in self.v.clientes)

    def pintar(self, m: dict):
        filtro = self.chips.actual()
        filas, validas = [], 0
        for s in m["ventas"]:
            if filtro in PLATAFORMAS and s["plataforma"] != filtro:
                continue
            if filtro == "reembolsos" and s["estado"] not in ("Reembolsada", "Contracargo", "Reembolso parcial"):
                continue
            if not self.v.coincide(s["cliente"], s["correo"], s["producto"], s["referencia"]):
                continue
            validas += s["valida"]
            p = PLATAFORMAS[s["plataforma"]]
            filas.append([
                celda(fmt_fecha(s["fecha"]), dato=s["id"]),
                celda(p["nombre"], pildora=p["color"]),
                celda(s["cliente"], negrita=True), celda(s["correo"]), celda(s["producto"]),
                celda(s["total_txt"]),
                celda(s["estado"] + ("  · prueba" if s["prueba"] else ""), pildora=color_estado(s["estado"])),
                celda(s["referencia"], C["suave"]),
            ])
        llenar_tabla(self.t, filas)
        self.resumen.setText(f"{len(filas)} ventas mostradas · {validas} válidas")
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        self._botones()


class PaginaActividad(Pagina):
    titulo = "Actividad"
    subtitulo = "Ventas, reembolsos, activaciones y equipos desactivados."

    def __init__(self, v):
        super().__init__(v)
        self.t = tabla(["Fecha", "Evento", "Plataforma", "Persona", "Detalle"], [150, 190, 170, 200], pildoras=(1,))
        self.vacio = EstadoVacio("⚡", "Sin actividad", "Aquí verás cada venta y activación en cuanto ocurra.")
        self.lay.addWidget(self.t, 1)
        self.lay.addWidget(self.vacio, 1)

    def pintar(self, m: dict):
        filas = []
        for e in self.v.eventos():
            if not self.v.coincide(e["persona"], e["detalle"]):
                continue
            nombre, color = EVENTOS[e["tipo"]]
            filas.append([celda(fmt_fecha(e["fecha"]), dato=str(e["clave"])), celda(nombre, pildora=color),
                          celda(nombre_plataforma(e["plataforma"])), celda(e["persona"], negrita=True),
                          celda(e["detalle"])])
        llenar_tabla(self.t, filas)
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)


class PaginaConexiones(Pagina):
    titulo = "Conexiones"
    subtitulo = "Tus plataformas de venta y los ajustes del panel."

    def __init__(self, v):
        super().__init__(v)
        area = QScrollArea()
        area.setWidgetResizable(True)
        cont = QWidget(objectName="pagina")
        self.c = QVBoxLayout(cont)
        self.c.setContentsMargins(0, 0, 8, 0)
        self.c.setSpacing(14)
        area.setWidget(cont)
        self.lay.addWidget(area)
        self.tarjetas = QHBoxLayout()
        self.tarjetas.setSpacing(14)
        self.c.addLayout(self.tarjetas)
        self.cajas: dict[str, dict] = {}
        for clave, p in PLATAFORMAS.items():
            caja = QFrame(objectName="plataforma")
            l = QVBoxLayout(caja)
            l.setContentsMargins(22, 20, 22, 20)
            l.setSpacing(8)
            icono = insignia_icono(p["icono"], p["color"], 48)
            estado = pildora()
            l.addLayout(fila(icono, etiqueta(p["nombre"], "tituloTarjeta"), None, estado))
            l.addWidget(etiqueta(p["descripcion"], "nota", ajustar=True))
            detalle = etiqueta("", "tenue", ajustar=True)
            detalle.setTextFormat(Qt.TextFormat.RichText)
            l.addWidget(detalle)
            l.addStretch()
            conectar = boton("Conectar", "primario")
            conectar.clicked.connect(lambda _=False, k=clave: self.v.conectar(k))
            info = boton("Ver información")
            info.clicked.connect(lambda _=False, k=clave: self.v.ver_informacion(k))
            quitar = boton("Desconectar", "peligro")
            quitar.clicked.connect(lambda _=False, k=clave: self.v.desconectar(k))
            l.addLayout(fila(conectar, info, None, quitar))
            self.tarjetas.addWidget(caja, 1)
            self.cajas[clave] = {"estado": estado, "detalle": detalle, "conectar": conectar, "info": info,
                                 "quitar": quitar}

        self.codigo = etiqueta("", "codigo")
        self.codigo.setFont(fuente_mono(10))
        self.codigo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        b_copiar = boton("Copiar")
        b_copiar.clicked.connect(lambda: (copiar(self.codigo.text()),
                                          self.v.aviso("Copiado", "Pégalo en licencia_cliente.py", "ok")))
        cod = fila(self.codigo, b_copiar)
        cod.setStretch(0, 1)
        self.caja_codigo = tarjeta(etiqueta("Datos para tu programa", "tituloTarjeta"),
                                   etiqueta("Pega estas líneas en la sección CONFIGURACIÓN de licencia_cliente.py.",
                                            "nota"), cod)
        self.c.addWidget(self.caja_codigo)

        self.nombre = QLineEdit(self.v.cfg["nombre_app"])
        self.nombre.editingFinished.connect(self._guardar_ajustes)
        self.animar = QCheckBox("Animaciones en la interfaz")
        self.animar.setChecked(self.v.cfg.get("animaciones", True))
        self.animar.toggled.connect(self._guardar_ajustes)
        self.intervalo = QComboBox()
        for texto, seg in INTERVALOS:
            self.intervalo.addItem(texto, seg)
        self.intervalo.setCurrentIndex(max(0, self.intervalo.findData(self.v.cfg.get("intervalo", 30))))
        self.intervalo.currentIndexChanged.connect(self._guardar_ajustes)
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.addRow("Nombre del programa", self.nombre)
        form.addRow("Actualizar cada", self.intervalo)
        form.addRow("", self.animar)
        self.c.addWidget(tarjeta(etiqueta("Ajustes", "tituloTarjeta"), form))
        self.c.addStretch()

    def _guardar_ajustes(self):
        self.v.cfg["nombre_app"] = self.nombre.text().strip() or "Mi programa"
        self.v.cfg["animaciones"] = self.animar.isChecked()
        self.v.cfg["intervalo"] = self.intervalo.currentData()
        ANIMACIONES["activas"] = self.v.cfg["animaciones"]
        self.v.timer.setInterval(self.v.cfg["intervalo"] * 1000)
        guardar_config(self.v.cfg)

    def pintar(self, m: dict):
        for clave, caja in self.cajas.items():
            pc = self.v.cfg["plataformas"].get(clave) or {}
            conectado = clave in self.v.clientes
            error = self.v.errores.get(clave)
            color = C["error"] if error else (C["ok"] if conectado else C["tenue"])
            texto = "Con error" if error else ("Conectado" if conectado else "No conectado")
            estilo_pildora(caja["estado"], f"●  {texto}", color)
            if clave == "lemonsqueezy" and conectado:
                det = (f"Cuenta: <b>{pc.get('cuenta') or '—'}</b><br>Tienda: <b>{pc.get('tienda_nombre') or '—'}</b>"
                       f" (ID {pc.get('tienda_id')})<br>Producto: <b>{pc.get('producto_nombre') or 'Todos'}</b>")
            elif clave == "hotmart" and conectado:
                det = (f"Entorno: <b>{pc.get('entorno') or ('Sandbox' if pc.get('sandbox') else 'Producción')}</b>"
                       f"<br>Credencial: <b>{(pc.get('client_id') or '')[:8]}…</b><br>"
                       f"Producto: <b>{pc.get('producto_nombre') or 'Todos'}</b>")
            else:
                det = ""
            if error:
                det += f"<br><span style='color:{C['error']}'>⚠ {error}</span>"
            caja["detalle"].setText(det)
            caja["conectar"].setText("Cambiar credenciales" if conectado else f"Conectar {PLATAFORMAS[clave]['nombre']}")
            caja["conectar"].setObjectName("secundario" if conectado else "primario")
            caja["conectar"].style().unpolish(caja["conectar"])
            caja["conectar"].style().polish(caja["conectar"])
            caja["info"].setVisible(conectado)
            caja["quitar"].setVisible(conectado)
        ls = self.v.cfg["plataformas"].get("lemonsqueezy") or {}
        self.caja_codigo.setVisible("lemonsqueezy" in self.v.clientes)
        self.codigo.setText(datos_para_programa(ls))


# ============================================================ ventana principal

class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITULO)
        self.setWindowIcon(icono_app())
        self.resize(1320, 820)
        self.setMinimumSize(1040, 640)
        self.cfg = cargar_config()
        ANIMACIONES["activas"] = self.cfg.get("animaciones", True)
        self.clientes: dict = {}
        self.errores: dict[str, str] = {}
        self._crear_clientes()
        self.resultados: dict = {}
        self.modelo = construir_modelo({})
        self._huella = None
        self.vistos: set | None = None
        self.desactivaciones: list[dict] = []
        self.no_vistos = 0
        self.cargando = False

        self.timer = QTimer(self, interval=self.cfg.get("intervalo", 30) * 1000, timeout=self.refrescar)
        self._construir()
        self.tray = QSystemTrayIcon(icono_app(), self)
        self.tray.setToolTip(APP_TITULO)
        self.tray.activated.connect(lambda *_: (self.showNormal(), self.activateWindow()))
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        QTimer.singleShot(0, self.iniciar)

    def _crear_clientes(self):
        self.clientes = {}
        for clave in PLATAFORMAS:
            pc = self.cfg["plataformas"].get(clave) or {}
            cliente = crear_cliente(clave, pc)
            if cliente and (clave != "lemonsqueezy" or pc.get("tienda_id")):
                self.clientes[clave] = cliente

    # ---------------------------------------------------------------- UI
    def _construir(self):
        raiz = QWidget(objectName="raiz")
        self.setCentralWidget(raiz)
        h = QHBoxLayout(raiz)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        lateral = QFrame(objectName="lateral")
        lateral.setFixedWidth(236)
        l = QVBoxLayout(lateral)
        l.setContentsMargins(14, 20, 14, 16)
        l.setSpacing(4)
        logo = QLabel()
        logo.setPixmap(icono_app().pixmap(38, 38))
        marca = QVBoxLayout()
        marca.setSpacing(0)
        marca.addWidget(etiqueta("Licencias", "marca"))
        marca.addWidget(etiqueta("Administrador", "marcaSub"))
        l.addLayout(fila(logo, marca, None, espacio=10))
        l.addSpacing(18)
        self.nav = NavLateral()
        self.paginas: list[Pagina] = []
        for icono, clase in (("🏠", PaginaInicio), ("👥", PaginaPersonas), ("🔑", PaginaLicencias),
                             ("💻", PaginaEquipos), ("🛒", PaginaVentas), ("⚡", PaginaActividad),
                             ("🔌", PaginaConexiones)):
            self.paginas.append(clase(self))
            self.nav.agregar(icono, clase.titulo)
        self.nav.cambiado.connect(self.ir_a)
        l.addWidget(self.nav)
        l.addStretch()
        l.addWidget(etiqueta("PLATAFORMAS", "seccionLateral"))
        self.chips_plataforma: dict[str, QPushButton] = {}
        for clave in PLATAFORMAS:
            b = QPushButton(objectName="plataformaChip")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=clave: self.ir_a(6) if k in self.clientes else self.conectar(k))
            self.chips_plataforma[clave] = b
            l.addWidget(b)
        l.addSpacing(6)
        l.addWidget(etiqueta(f"v{VERSION} · Windows, macOS y Linux", "tenue"))
        h.addWidget(lateral)

        derecha = QVBoxLayout()
        derecha.setContentsMargins(28, 22, 28, 18)
        derecha.setSpacing(16)
        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        self.lbl_titulo = etiqueta("", "tituloPagina")
        self.lbl_sub = etiqueta("", "subtitulo")
        titulos.addWidget(self.lbl_titulo)
        titulos.addWidget(self.lbl_sub)
        self.buscar = QLineEdit(placeholderText="🔍  Buscar persona, correo, clave, equipo…", objectName="buscar")
        self.buscar.setFixedWidth(320)
        self.buscar.setClearButtonEnabled(True)
        self.buscar.textChanged.connect(lambda: self.pintar(forzar=True))
        self.spinner = Spinner(20)
        self.btn_refrescar = boton("⟳  Actualizar")
        self.btn_refrescar.clicked.connect(self.refrescar)
        derecha.addLayout(fila(titulos, None, self.spinner, self.buscar, self.btn_refrescar, espacio=10))
        self.pila = Pila()
        for p in self.paginas:
            self.pila.addWidget(p)
        derecha.addWidget(self.pila, 1)
        h.addLayout(derecha, 1)
        self.estado = etiqueta("", "nota")
        self.estado.setContentsMargins(12, 0, 0, 0)
        self.statusBar().addWidget(self.estado, 1)
        self.nav.seleccionar(0)
        self._titulos(0)
        self._chips()

    def _titulos(self, i: int):
        p = self.paginas[i]
        self.lbl_titulo.setText(p.titulo)
        self.lbl_sub.setText(p.subtitulo)
        fundido(self.lbl_titulo, 0.2, 1.0, 260)

    def _chips(self):
        for clave, b in self.chips_plataforma.items():
            p = PLATAFORMAS[clave]
            if clave in self.clientes:
                color = C["error"] if clave in self.errores else C["ok"]
                b.setText(f"{p['icono']}  {p['nombre']}")
                b.setToolTip(self.errores.get(clave, "Conectado"))
                b.setStyleSheet(f"QPushButton#plataformaChip {{ border-left: 3px solid {color}; }}")
            else:
                b.setText(f"＋  Conectar {p['nombre']}")
                b.setToolTip("")
                b.setStyleSheet(f"QPushButton#plataformaChip {{ color: {C['suave']}; }}")

    def ir_a(self, i: int):
        self.nav.seleccionar(i)
        self.pila.ir_a(i)
        self._titulos(i)
        if i == 5:
            self.no_vistos = 0
            self.nav.insignia(5, 0)

    def aviso(self, titulo: str, texto: str = "", tipo: str = "info"):
        Toast.mostrar(self, titulo, texto, tipo)

    def coincide(self, *campos) -> bool:
        f = self.buscar.text().strip().lower()
        return not f or any(f in str(c or "").lower() for c in campos)

    # ---------------------------------------------------------------- conexión
    def iniciar(self):
        self.pintar(forzar=True)
        if self.clientes:
            self.refrescar()
            self.timer.start()

    def conectar(self, plataforma: str = ""):
        d = DialogoConectar(self, plataforma, self.cfg["plataformas"].get(plataforma) or {})
        if d.exec() != DialogoConectar.DialogCode.Accepted or not d.resultado:
            return
        clave, datos, resumen, cliente = d.resultado
        r = DialogoResumen(clave, cliente, resumen, datos, self)
        if r.exec() != DialogoResumen.DialogCode.Accepted:
            return
        self._guardar_conexion(clave, r.datos)

    def _guardar_conexion(self, clave: str, datos: dict):
        self.cfg["plataformas"][clave] = datos
        guardar_config(self.cfg)
        self._crear_clientes()
        self.errores.pop(clave, None)
        self.vistos = None
        self._huella = None
        self._chips()
        self.aviso(f"{PLATAFORMAS[clave]['nombre']} conectado", "Cargando tus datos…", "ok")
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
            r = DialogoResumen(clave, cliente, resumen, pc, self)
            if r.exec() == DialogoResumen.DialogCode.Accepted:
                self.cfg["plataformas"][clave] = r.datos
                guardar_config(self.cfg)
                self._huella = None
                self.pintar(forzar=True)
                self.refrescar()

        def error(e):
            QGuiApplication.restoreOverrideCursor()
            self.aviso(PLATAFORMAS[clave]["nombre"], e, "error")

        en_hilo(cliente.conectar, *((pc.get("producto_id") or 0,) if clave == "hotmart" else ()), ok=ok, error=error)

    def desconectar(self, clave: str):
        nombre = PLATAFORMAS[clave]["nombre"]
        if not confirmar(self, f"Desconectar {nombre}", f"¿Quitar la conexión con <b>{nombre}</b>?<br><br>"
                         "Se borran las credenciales de esta computadora. Tus datos en la plataforma no cambian.",
                         "Sí, desconectar"):
            return
        self.cfg["plataformas"][clave] = {}
        guardar_config(self.cfg)
        self._crear_clientes()
        self.errores.pop(clave, None)
        self.resultados.pop(clave, None)
        self.aviso(f"{nombre} desconectado", "", "info")
        self._aplicar(dict(self.resultados))

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
                self.aviso(f"Problema con {PLATAFORMAS[k]['nombre']}", e, "error")
        self.errores = nuevos_errores
        # si una plataforma falla, se conservan sus últimos datos buenos
        combinados = {k: (self.resultados.get(k, {}) if "error" in r else r) for k, r in resultados.items()
                      if k in self.clientes}
        anteriores = {i["id"]: i for i in self.modelo["instancias"]}
        self.resultados = combinados
        self.modelo = construir_modelo(combinados)
        self._detectar_desactivaciones(anteriores)
        self.estado.setText(f"Actualizado {datetime.now().strftime('%H:%M:%S')}")
        self._chips()
        self.pintar()
        self._notificar_nuevos()

    def pintar(self, forzar=False):
        huella = json.dumps([self.resultados, len(self.desactivaciones), sorted(self.clientes), self.errores],
                            sort_keys=True, default=str)
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
                                             "equipo": partir_instancia(ins["name"])[0] or ins["name"]})

    def eventos(self) -> list[dict]:
        m, evs = self.modelo, []
        for s in m["ventas"]:
            if s["valida"] or s["estado"] in ("Reembolsada", "Contracargo"):
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
                        "plataforma": "lemonsqueezy", "persona": lic.get("user_name", ""),
                        "detalle": f"Activó en {partir_instancia(i.get('name', ''))[0] or i.get('name', '')}"})
        for d in self.desactivaciones:
            evs.append({"clave": ("desactivacion", d["id"]), "tipo": "desactivacion", "fecha": d["fecha"],
                        "plataforma": "lemonsqueezy", "persona": d["persona"], "detalle": f"Se desactivó {d['equipo']}"})
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
        if self.pila.currentIndex() != 5:
            self.no_vistos += len(nuevos)
            self.nav.insignia(5, self.no_vistos)
        for e in nuevos[:3]:
            titulo = EVENTOS[e["tipo"]][0]
            texto = f"{e['persona'] or '—'} — {e['detalle']}"
            self.aviso(f"{titulo} · {PLATAFORMAS[e['plataforma']]['nombre']}", texto,
                       "venta" if e["tipo"] == "venta" else ("error" if e["tipo"] == "reembolso" else "info"))
            if self.tray.isVisible():
                self.tray.showMessage(titulo, texto, QSystemTrayIcon.MessageIcon.Information, 6000)
        QApplication.alert(self)

    # ---------------------------------------------------------------- acciones
    def accion(self, fn, *args, mensaje=""):
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def ok(_):
            QGuiApplication.restoreOverrideCursor()
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
            self.aviso("Conecta Lemon Squeezy", "Las licencias se crean y controlan con Lemon Squeezy.", "info")
        return cliente

    def ver_licencia(self, id_: int):
        self.buscar.clear()
        self.ir_a(2)
        pag: PaginaLicencias = self.paginas[2]
        pag.chips.grupo.button(0).click()
        for r in range(pag.t.rowCount()):
            if pag.t.item(r, 0).data(Qt.ItemDataRole.UserRole) == id_:
                pag.t.selectRow(r)
                pag.t.scrollToItem(pag.t.item(r, 0))
                break

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
                self.aviso("Enlace de compra creado", venta["cliente"] or "", "ok")
                DialogoEnlace(url, venta, self.cfg["nombre_app"], self).exec()

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
        if d.exec() == DialogoEditar.DialogCode.Accepted and (ls := self.ls()):
            self.accion(ls.editar_licencia, lic["id"], d.datos(), mensaje="Licencia actualizada")

    def alternar_bloqueo(self, lic: dict):
        ls = self.ls()
        if not ls:
            return
        bloquear = not lic.get("disabled")
        if bloquear and not confirmar(self, "Bloquear licencia",
                                      f"¿Bloquear la licencia de <b>{lic.get('user_name')}</b>?<br><br>El programa "
                                      "dejará de funcionar en sus equipos la próxima vez que lo abran.",
                                      "Sí, bloquear"):
            return
        self.accion(ls.editar_licencia, lic["id"], {"disabled": bloquear},
                    mensaje=f"Licencia {'bloqueada' if bloquear else 'desbloqueada'}")

    def quitar_equipo(self, lic: dict, ins: dict):
        ls = self.ls()
        if ls and confirmar(self, "Quitar equipo",
                            f"¿Desactivar <b>{partir_instancia(ins['name'])[0] or ins['name']}</b> de la licencia "
                            f"de <b>{lic.get('user_name')}</b>?<br><br>Ese equipo dejará de funcionar y la clave "
                            "quedará libre para activarse en otra computadora.", "Sí, quitar"):
            self.accion(ls.quitar_equipo, lic["key"], ins["identifier"], mensaje="Equipo desactivado")

    def _pedir_telefono(self, clave: str, nombre: str) -> str:
        guardado = self.cfg["telefonos"].get(clave, "")
        tel, ok = QInputDialog.getText(self, "Enviar por WhatsApp",
                                       f"WhatsApp de {nombre or 'la persona'} (con código de país):", text=guardado)
        if not ok or not solo_digitos(tel):
            return ""
        self.cfg["telefonos"][clave] = solo_digitos(tel)
        guardar_config(self.cfg)
        return tel

    def _texto_clave(self, lic: dict) -> str:
        return (f"Hola {lic.get('user_name') or ''}, aquí está tu licencia de {self.cfg['nombre_app']}:\n\n"
                f"{lic['key']}\n\nAbre el programa, pega la clave en la ventana de activación y presiona *Activar*.")

    def enviar_clave_whatsapp(self, lic: dict):
        if tel := self._pedir_telefono((lic.get("user_email") or str(lic["id"])).lower(), lic.get("user_name")):
            abrir_whatsapp(tel, self._texto_clave(lic))

    def enviar_clave_correo(self, lic: dict):
        if lic.get("user_email"):
            abrir_correo(lic["user_email"], f"Tu licencia de {self.cfg['nombre_app']}", self._texto_clave(lic))

    def whatsapp_persona(self, p: dict):
        if tel := self._pedir_telefono(p["clave"], p["nombre"]):
            abrir_whatsapp(tel, f"Hola {p['nombre'] or ''}, te escribo sobre {self.cfg['nombre_app']}.")

    def closeEvent(self, e):
        self.tray.hide()
        super().closeEvent(e)


def _preparar_registro():
    """En el .exe sin consola no hay salida estándar: los avisos de Python y de Qt van a un archivo
    (registro.log en la carpeta de configuración) en vez de perderse o fallar al escribirse."""
    from PySide6.QtCore import qInstallMessageHandler
    try:
        CARPETA_CONFIG.mkdir(parents=True, exist_ok=True)
        registro = open(CARPETA_CONFIG / "registro.log", "w", encoding="utf-8", buffering=1)
    except OSError:
        registro = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None or getattr(sys, "frozen", False):
        sys.stdout = registro
    if sys.stderr is None or getattr(sys, "frozen", False):
        sys.stderr = registro
    qInstallMessageHandler(lambda _tipo, _ctx, mensaje: registro.write(f"[Qt] {mensaje}\n"))


def main():
    _preparar_registro()
    if getattr(sys, "frozen", False):   # dentro del .exe: indicar a Qt dónde están sus plugins
        os.environ.setdefault("QT_PLUGIN_PATH", str(Path(sys._MEIPASS) / "PySide6" / "plugins"))
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_TITULO)
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(icono_app())
    app.setStyleSheet(QSS)
    fuente = QFont()
    fuente.setFamilies(["Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Inter", "Helvetica Neue",
                        "Noto Sans", "DejaVu Sans"])
    fuente.setPointSizeF(10)
    app.setFont(fuente)
    app.setQuitOnLastWindowClosed(True)
    v = Ventana()
    v.show()
    sys.exit(app.exec())


__all__ = ["ErrorApi", "Hotmart", "LemonSqueezy", "Ventana", "main"]

if __name__ == "__main__":
    main()
