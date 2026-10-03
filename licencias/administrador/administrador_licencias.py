"""Administrador de Licencias — Resolve Creator Subtitles (Lemon Squeezy).

Programa SOLO para ti (el vendedor). Usa tu API key de Lemon Squeezy:
no lo compartas ni lo incluyas en el instalador del programa.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QDate, QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateEdit,
                               QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSystemTrayIcon,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

APP_TITULO = "Administrador de Licencias"
CARPETA_CONFIG = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "RCS-Administrador"
ARCHIVO_CONFIG = CARPETA_CONFIG / "config_lemonsqueezy.json"
INTERVALO_REFRESCO_MS = 30_000
API_BASE = "https://api.lemonsqueezy.com/v1/"
URL_API_KEYS = "https://app.lemonsqueezy.com/settings/api"

ESTADOS = {"active": "Activa", "inactive": "Sin activar", "expired": "Vencida", "disabled": "Bloqueada"}
ESTADOS_VENTA = {"paid": "Pagada", "refunded": "Reembolsada", "partial_refund": "Reembolso parcial",
                 "pending": "Pendiente", "failed": "Fallida"}
COLOR = {
    "Activa": "#3ddc84", "Sin activar": "#7cc4ff", "Bloqueada": "#ff6b6b", "Vencida": "#ffb454",
    "Pagada": "#3ddc84", "Reembolsada": "#ff6b6b", "Reembolso parcial": "#ffb454",
    "Pendiente": "#7cc4ff", "Fallida": "#ff6b6b",
}
EVENTOS = {
    "venta": ("Nueva venta", "#3ddc84"),
    "reembolso": ("Reembolso", "#ff6b6b"),
    "activacion": ("Activación", "#7cc4ff"),
    "desactivacion": ("Equipo desactivado", "#ffb454"),
}


# ============================================================ configuración

def cargar_config() -> dict:
    base = {"api_key": "", "tienda_id": 0, "tienda_nombre": "", "tienda_url": "", "moneda": "",
            "producto_id": 0, "producto_nombre": "", "url_compra": "",
            "nombre_app": "Resolve Creator Subtitles", "telefonos": {}}
    try:
        base.update(json.loads(ARCHIVO_CONFIG.read_text(encoding="utf-8")))
    except Exception:
        pass
    return base


def guardar_config(cfg: dict) -> None:
    CARPETA_CONFIG.mkdir(parents=True, exist_ok=True)
    ARCHIVO_CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def datos_para_programa(cfg: dict) -> str:
    """Líneas para pegar en la sección CONFIGURACIÓN de licencia_cliente.py."""
    productos = f"({cfg['producto_id']},)" if cfg.get("producto_id") else "()"
    url = cfg.get("url_compra") or cfg.get("tienda_url") or ""
    return (f"TIENDA_ID = {cfg.get('tienda_id') or 0}\n"
            f"PRODUCTOS_ID = {productos}\n"
            f"URL_COMPRA = \"{url}\"\n")


# ============================================================ API Lemon Squeezy

class ErrorApi(Exception):
    pass


def plano(objeto: dict) -> dict:
    """Recurso JSON:API → diccionario simple con 'id' + atributos."""
    id_ = str(objeto["id"])
    return {"id": int(id_) if id_.isdigit() else id_, **(objeto.get("attributes") or {})}


class Api:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()

    def _abrir(self, req: urllib.request.Request):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                texto = r.read()
                return json.loads(texto) if texto else None
        except urllib.error.HTTPError as e:
            detalle = ""
            try:
                cuerpo = json.loads(e.read())
                errores = cuerpo.get("errors") or []
                if errores:
                    detalle = errores[0].get("detail") or errores[0].get("title") or ""
                else:
                    detalle = cuerpo.get("error") or cuerpo.get("message") or ""
            except Exception:
                pass
            if e.code == 401:
                raise ErrorApi("API key incorrecta o vencida. Crea una nueva en Lemon Squeezy → "
                               "Settings → API y pégala en ⚙ Configuración.") from e
            if e.code == 403:
                raise ErrorApi(f"Lemon Squeezy no permitió la acción. {detalle}") from e
            if e.code == 404:
                raise ErrorApi(f"No se encontró en Lemon Squeezy. {detalle}") from e
            if e.code == 429:
                raise ErrorApi("Demasiadas peticiones a Lemon Squeezy. Espera un minuto.") from e
            raise ErrorApi(f"Error de Lemon Squeezy ({e.code}). {detalle}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ErrorApi("No hay conexión con Lemon Squeezy. Revisa internet.") from e

    def _req(self, metodo: str, ruta: str, consulta: dict | None = None, cuerpo=None):
        url = API_BASE + ruta + ("?" + urllib.parse.urlencode(consulta) if consulta else "")
        req = urllib.request.Request(
            url, data=json.dumps(cuerpo).encode() if cuerpo is not None else None, method=metodo,
            headers={"Accept": "application/vnd.api+json", "Content-Type": "application/vnd.api+json",
                     "Authorization": f"Bearer {self.api_key}", "User-Agent": "RCS-Administrador/2.0"})
        return self._abrir(req)

    def _todas(self, ruta: str, filtros: dict | None = None, max_paginas: int = 50) -> list[dict]:
        resultado, pagina = [], 1
        while True:
            consulta = {f"filter[{k}]": v for k, v in (filtros or {}).items() if v}
            consulta |= {"page[number]": pagina, "page[size]": 100}
            r = self._req("GET", ruta, consulta) or {}
            resultado += [plano(o) for o in r.get("data") or []]
            ultima = int(((r.get("meta") or {}).get("page") or {}).get("lastPage") or 1)
            if pagina >= ultima or pagina >= max_paginas:
                return resultado
            pagina += 1

    # --- cuenta
    def usuario(self) -> dict:
        return plano((self._req("GET", "users/me") or {})["data"])

    def tiendas(self) -> list[dict]:
        return self._todas("stores")

    def productos(self, tienda_id: int) -> list[dict]:
        return self._todas("products", {"store_id": tienda_id})

    def conectar(self) -> dict:
        return {"usuario": self.usuario(), "tiendas": self.tiendas()}

    def variantes(self, tienda_id: int, producto_id: int = 0) -> list[dict]:
        productos = {p["id"]: p for p in self.productos(tienda_id)}
        if producto_id:
            variantes = self._todas("variants", {"product_id": producto_id})
        else:
            variantes = [v for v in self._todas("variants") if v.get("product_id") in productos]
        for v in variantes:
            v["producto"] = (productos.get(v.get("product_id")) or {}).get("name", "")
        return variantes

    # --- lectura
    def todo(self, tienda_id: int, producto_id: int = 0) -> dict:
        licencias = self._todas("license-keys", {"store_id": tienda_id, "product_id": producto_id})
        ids = {l["id"] for l in licencias}
        instancias = [i for i in self._todas("license-key-instances") if i.get("license_key_id") in ids]
        ventas = self._todas("orders", {"store_id": tienda_id})
        if producto_id:
            ventas = [v for v in ventas if (v.get("first_order_item") or {}).get("product_id") == producto_id]
        orden = lambda x: x.get("created_at") or ""   # noqa: E731
        return {"licencias": sorted(licencias, key=orden, reverse=True),
                "instancias": sorted(instancias, key=orden, reverse=True),
                "ventas": sorted(ventas, key=orden, reverse=True)}

    # --- licencias
    def editar_licencia(self, id_: int, atributos: dict) -> dict:
        cuerpo = {"data": {"type": "license-keys", "id": str(id_), "attributes": atributos}}
        return plano(self._req("PATCH", f"license-keys/{id_}", cuerpo=cuerpo)["data"])

    def quitar_equipo(self, clave: str, instancia: str):
        """Desactiva un equipo con la API de licencias (la misma que usa el programa del cliente)."""
        req = urllib.request.Request(
            API_BASE + "licenses/deactivate", method="POST",
            data=urllib.parse.urlencode({"license_key": clave, "instance_id": instancia}).encode(),
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": "RCS-Administrador/2.0"})
        try:
            r = self._abrir(req) or {}
        except ErrorApi as e:
            if "No se encontró" in str(e):   # el equipo ya estaba desactivado
                return
            raise
        if not r.get("deactivated"):
            raise ErrorApi(r.get("error") or "Lemon Squeezy no desactivó el equipo.")

    # --- ventas
    def crear_cupon_gratis(self, tienda_id: int, variante_id: int) -> str:
        codigo = "REGALO" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        cuerpo = {"data": {
            "type": "discounts",
            "attributes": {"name": f"Licencia de regalo {codigo}", "code": codigo, "amount": 100,
                           "amount_type": "percent", "duration": "once", "is_limited_to_products": True,
                           "is_limited_redemptions": True, "max_redemptions": 1},
            "relationships": {"store": {"data": {"type": "stores", "id": str(tienda_id)}},
                              "variants": {"data": [{"type": "variants", "id": str(variante_id)}]}}}}
        self._req("POST", "discounts", cuerpo=cuerpo)
        return codigo

    def crear_enlace(self, tienda_id: int, venta: dict) -> str:
        """Crea un checkout de Lemon Squeezy y devuelve su URL. Al pagar, Lemon Squeezy genera la
        clave de licencia y se la envía al cliente por correo."""
        datos = {k: v for k, v in (("name", venta["cliente"]), ("email", venta["correo"])) if v}
        if venta["precio"] == "gratis":
            datos["discount_code"] = self.crear_cupon_gratis(tienda_id, venta["variante_id"])
        atributos = {"product_options": {"enabled_variants": [venta["variante_id"]]},
                     "checkout_data": datos or None,
                     "custom_price": venta["centavos"] if venta["precio"] == "especial" else None,
                     "expires_at": venta["expira"]}
        cuerpo = {"data": {
            "type": "checkouts",
            "attributes": {k: v for k, v in atributos.items() if v is not None},
            "relationships": {"store": {"data": {"type": "stores", "id": str(tienda_id)}},
                              "variant": {"data": {"type": "variants", "id": str(venta["variante_id"])}}}}}
        return self._req("POST", "checkouts", cuerpo=cuerpo)["data"]["attributes"]["url"]


# ============================================================ utilidades

class _Senales(QObject):
    ok = Signal(object)
    error = Signal(str)


class Tarea(QRunnable):
    """Ejecuta una llamada de red fuera del hilo de la interfaz."""

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args, self.senales = fn, args, _Senales()

    def run(self):
        try:
            self.senales.ok.emit(self.fn(*self.args))
        except Exception as e:  # noqa: BLE001
            self.senales.error.emit(str(e))


_TAREAS: set[Tarea] = set()


def en_hilo(fn, *args, ok=None, error=None):
    """Lanza fn(*args) en segundo plano; ok(resultado) o error(texto) se llaman en la interfaz."""
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


def a_fecha(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def fmt_fecha(iso: str | None, hora=True) -> str:
    f = a_fecha(iso)
    if not f:
        return "—"
    return f.strftime("%d/%m/%Y %H:%M" if hora else "%d/%m/%Y")


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


def estado_licencia(lic: dict) -> str:
    return ESTADOS.get(lic.get("status"), lic.get("status_formatted") or "—")


def partir_instancia(nombre: str) -> tuple[str, str]:
    """'PC-JUAN · 3F2A-91BC-04DE-77A1' → ('PC-JUAN', '3F2A-91BC-04DE-77A1')."""
    pc, _, equipo = (nombre or "").partition(" · ")
    return pc, equipo


def limite_txt(lic: dict) -> str:
    limite = lic.get("activation_limit")
    return f"{lic.get('instances_count', 0)} / {limite if limite else '∞'}"


def solo_digitos(tel: str) -> str:
    return re.sub(r"\D", "", tel or "")


def icono_app() -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(4, 4)   # se dibuja en una cuadrícula de 64x64
    p.setBrush(QColor("#4c8dff"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, 64, 64, 14, 14)
    p.setBrush(QColor("white"))
    p.drawEllipse(10, 18, 26, 26)
    p.drawRect(30, 27, 26, 8)
    p.drawRect(46, 35, 6, 9)
    p.drawRect(38, 35, 5, 6)
    p.setBrush(QColor("#4c8dff"))
    p.drawEllipse(17, 25, 12, 12)
    p.end()
    return QIcon(pm)


def fuente_mono(puntos: int = -1) -> QFont:
    f = QFont("Consolas", puntos)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def item(texto, color: str | None = None, dato=None, negrita=False, mono=False) -> QTableWidgetItem:
    it = QTableWidgetItem(str(texto) if texto not in (None, "") else "—")
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if color:
        it.setForeground(QColor(color))
    if negrita or mono:
        f = fuente_mono() if mono else QFont(QApplication.font())
        f.setBold(negrita)
        it.setFont(f)
    if dato is not None:
        it.setData(Qt.ItemDataRole.UserRole, dato)
    return it


def boton(texto: str, nombre="secundario", tip="") -> QPushButton:
    b = QPushButton(texto, objectName=nombre)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if tip:
        b.setToolTip(tip)
    return b


def tabla(columnas: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(36)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.setWordWrap(False)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    h.setStretchLastSection(True)
    h.setHighlightSections(False)
    return t


def fila_seleccionada(t: QTableWidget):
    filas = t.selectionModel().selectedRows() if t.selectionModel() else []
    return t.item(filas[0].row(), 0).data(Qt.ItemDataRole.UserRole) if filas else None


def abrir_whatsapp(telefono: str, texto: str):
    QDesktopServices.openUrl(QUrl(f"https://wa.me/{solo_digitos(telefono)}?text={urllib.parse.quote(texto)}"))


def abrir_correo(correo: str, asunto: str, texto: str):
    QDesktopServices.openUrl(QUrl(f"mailto:{correo}?subject={urllib.parse.quote(asunto)}"
                                  f"&body={urllib.parse.quote(texto)}"))


# ============================================================ diálogos

class DialogoConfig(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.setMinimumWidth(600)
        self.cfg = dict(cfg)
        self.tiendas: list[dict] = []
        self.productos: list[dict] = []

        intro = QLabel(
            f"Pega tu <b>API key</b> de Lemon Squeezy (<a href='{URL_API_KEYS}' style='color:#7cc4ff'>"
            "Settings → API</a>) y pulsa <b>Conectar</b>.<br>Solo se guarda en esta computadora: "
            "nunca la pongas en el programa que vendes.")
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(True)
        self.clave = QLineEdit(cfg["api_key"], placeholderText="eyJ0eXAiOiJKV1QiLCJhbGciOi…")
        self.clave.setEchoMode(QLineEdit.EchoMode.Password)
        ver = QCheckBox("Mostrar")
        ver.toggled.connect(lambda v: self.clave.setEchoMode(
            QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password))
        self.btn_conectar = boton("Conectar", "primario")
        self.btn_conectar.clicked.connect(self.conectar)
        fila_clave = QHBoxLayout()
        fila_clave.addWidget(self.clave, 1)
        fila_clave.addWidget(ver)
        fila_clave.addWidget(self.btn_conectar)

        self.tienda = QComboBox()
        self.tienda.currentIndexChanged.connect(self._tienda_cambiada)
        self.producto = QComboBox()
        self.producto.currentIndexChanged.connect(self._actualizar_datos)
        self.nombre = QLineEdit(cfg["nombre_app"])

        form = QFormLayout()
        form.addRow("API key", fila_clave)
        form.addRow("Tienda", self.tienda)
        form.addRow("Producto", self.producto)
        form.addRow("Nombre del programa", self.nombre)

        self.estado = QLabel(objectName="nota")
        self.estado.setWordWrap(True)

        titulo_datos = QLabel("<b>Datos para tu programa</b> — pégalos en la sección CONFIGURACIÓN "
                              "de <i>licencia_cliente.py</i>:")
        titulo_datos.setWordWrap(True)
        self.datos = QPlainTextEdit(readOnly=True)
        self.datos.setFont(fuente_mono(10))
        self.datos.setFixedHeight(72)
        copiar = boton("Copiar")
        copiar.clicked.connect(lambda: (QGuiApplication.clipboard().setText(self.datos.toPlainText()),
                                        copiar.setText("✔ Copiado")))

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.guardar)
        botones.rejected.connect(self.reject)
        abajo = QHBoxLayout()
        abajo.addWidget(copiar)
        abajo.addStretch()
        abajo.addWidget(botones)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(intro)
        lay.addLayout(form)
        lay.addWidget(self.estado)
        lay.addWidget(titulo_datos)
        lay.addWidget(self.datos)
        lay.addLayout(abajo)

        # Mientras no se conecte, se muestra lo guardado.
        if cfg.get("tienda_id"):
            self.tiendas = [{"id": cfg["tienda_id"], "name": cfg["tienda_nombre"], "url": cfg["tienda_url"],
                             "currency": cfg["moneda"]}]
            self.productos = ([{"id": cfg["producto_id"], "name": cfg["producto_nombre"],
                                "buy_now_url": cfg["url_compra"]}] if cfg.get("producto_id") else [])
            self._llenar_tiendas(cargar_productos=False)
            self._llenar_productos()
        self._actualizar_datos()
        if cfg["api_key"]:
            QTimer.singleShot(0, self.conectar)

    def _aviso(self, texto: str, color: str = ""):
        self.estado.setText(texto)
        self.estado.setStyleSheet(f"color:{color}" if color else "")

    def conectar(self):
        clave = self.clave.text().strip()
        if not clave:
            self._aviso("Pega tu API key.", "#ff6b6b")
            return
        self.btn_conectar.setEnabled(False)
        self._aviso("Conectando con Lemon Squeezy…")

        def ok(r):
            self.btn_conectar.setEnabled(True)
            self.tiendas = r["tiendas"]
            u = r["usuario"]
            if not self.tiendas:
                self._aviso(f"✔ Conectado como {u.get('name')}, pero tu cuenta no tiene tiendas. "
                            "Crea una en app.lemonsqueezy.com.", "#ffb454")
                return
            self._aviso(f"✔ Conectado como {u.get('name')} ({u.get('email')})", "#3ddc84")
            self._llenar_tiendas()

        def error(e):
            self.btn_conectar.setEnabled(True)
            self._aviso(e, "#ff6b6b")

        en_hilo(Api(clave).conectar, ok=ok, error=error)

    def _llenar_tiendas(self, cargar_productos=True):
        self.tienda.blockSignals(True)
        self.tienda.clear()
        for t in self.tiendas:
            self.tienda.addItem(f"{t.get('name') or 'Tienda'}  (ID {t['id']})", t["id"])
        indice = max(0, self.tienda.findData(self.cfg.get("tienda_id")))
        self.tienda.setCurrentIndex(indice)
        self.tienda.blockSignals(False)
        if cargar_productos:
            self._tienda_cambiada()

    def _tienda_actual(self) -> dict:
        return next((t for t in self.tiendas if t["id"] == self.tienda.currentData()), {})

    def _tienda_cambiada(self):
        tienda = self.tienda.currentData()
        clave = self.clave.text().strip()
        self.productos = []
        self._llenar_productos()
        if not tienda or not clave:
            return

        def ok(productos):
            if tienda == self.tienda.currentData():
                self.productos = productos
                self._llenar_productos()

        en_hilo(Api(clave).productos, tienda, ok=ok, error=lambda e: self._aviso(e, "#ff6b6b"))

    def _llenar_productos(self):
        self.producto.blockSignals(True)
        self.producto.clear()
        self.producto.addItem("Todos los productos de la tienda", 0)
        for p in self.productos:
            self.producto.addItem(f"{p.get('name') or 'Producto'}  (ID {p['id']})", p["id"])
        if len(self.productos) == 1 and not self.cfg.get("producto_id"):
            self.producto.setCurrentIndex(1)
        else:
            self.producto.setCurrentIndex(max(0, self.producto.findData(self.cfg.get("producto_id"))))
        self.producto.blockSignals(False)
        self._actualizar_datos()

    def valores(self) -> dict:
        tienda = self._tienda_actual()
        producto = next((p for p in self.productos if p["id"] == self.producto.currentData()), {})
        return {"api_key": self.clave.text().strip(),
                "tienda_id": tienda.get("id", 0), "tienda_nombre": tienda.get("name", ""),
                "tienda_url": tienda.get("url", ""), "moneda": tienda.get("currency", ""),
                "producto_id": producto.get("id", 0), "producto_nombre": producto.get("name", ""),
                "url_compra": producto.get("buy_now_url", ""),
                "nombre_app": self.nombre.text().strip() or "Mi programa"}

    def _actualizar_datos(self):
        self.datos.setPlainText(datos_para_programa(self.valores()))

    def guardar(self):
        v = self.valores()
        if not v["api_key"] or not v["tienda_id"]:
            QMessageBox.warning(self, "Faltan datos", "Pega tu API key, pulsa Conectar y elige tu tienda.")
            return
        self.cfg.update(v)
        self.accept()


class DialogoEditar(QDialog):
    """Cambiar el número de equipos permitidos y la fecha de vencimiento de una licencia."""

    def __init__(self, lic: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar licencia")
        self.setMinimumWidth(460)

        self.limite = QSpinBox(minimum=1, maximum=1000, value=lic.get("activation_limit") or 1)
        self.ilimitado = QCheckBox("Ilimitados")
        self.ilimitado.toggled.connect(lambda v: self.limite.setEnabled(not v))
        self.ilimitado.setChecked(not lic.get("activation_limit"))
        fila_limite = QHBoxLayout()
        fila_limite.addWidget(self.limite, 1)
        fila_limite.addWidget(self.ilimitado)

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
        fila_vence = QHBoxLayout()
        fila_vence.addWidget(self.vence, 1)
        fila_vence.addWidget(self.fecha)
        for texto, dias in (("+30 días", 30), ("+1 año", 365)):
            b = boton(texto)
            b.clicked.connect(lambda _=False, d=dias: self._sumar(d))
            fila_vence.addWidget(b)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Cliente", QLabel(f"<b>{lic.get('user_name') or '—'}</b>  {lic.get('user_email') or ''}"))
        form.addRow("Equipos permitidos", fila_limite)
        form.addRow("Vence", fila_vence)
        nota = QLabel("«+30 días» y «+1 año» se suman desde hoy o desde la fecha de vencimiento actual "
                      "si aún no ha llegado.", objectName="nota")
        nota.setWordWrap(True)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primario")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addLayout(form)
        lay.addWidget(nota)
        lay.addWidget(botones)

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


class DialogoVenta(QDialog):
    """Crear un enlace de compra (checkout) para enviárselo a un cliente."""

    VIGENCIA = [("7 días", 7), ("1 día", 1), ("30 días", 30), ("Sin vencimiento", None)]

    def __init__(self, variantes: list[dict], moneda: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo enlace de compra")
        self.setMinimumWidth(500)

        self.cliente = QLineEdit(placeholderText="Opcional: se rellena en el pago")
        self.correo = QLineEdit(placeholderText="Opcional: ahí le llegará la clave")
        self.telefono = QLineEdit(placeholderText="Opcional: WhatsApp con código de país, ej. 50255551234")
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
        fila_precio = QHBoxLayout()
        fila_precio.addWidget(self.precio, 1)
        fila_precio.addWidget(self.monto)
        self.vigencia = QComboBox()
        for texto, dias in self.VIGENCIA:
            self.vigencia.addItem(texto, dias)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Producto", self.variante)
        form.addRow("Precio", fila_precio)
        form.addRow("Cliente", self.cliente)
        form.addRow("Correo", self.correo)
        form.addRow("WhatsApp", self.telefono)
        form.addRow("El enlace vence en", self.vigencia)

        ayuda = QLabel("Lemon Squeezy crea la clave de licencia cuando el cliente completa la compra y se la "
                       "envía por correo. Aparecerá sola en la pestaña Licencias.", objectName="nota")
        ayuda.setWordWrap(True)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Crear enlace")
        botones.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primario")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.validar)
        botones.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addLayout(form)
        lay.addWidget(ayuda)
        lay.addWidget(botones)

    def validar(self):
        if self.variante.currentData() is None:
            QMessageBox.warning(self, "Sin productos", "Tu tienda no tiene productos. Créalo en Lemon Squeezy "
                                "y activa «Generate license keys».")
            return
        correo = self.correo.text().strip()
        if correo and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
            QMessageBox.warning(self, "Correo no válido", "Revisa el correo del cliente.")
            return
        self.accept()

    def datos(self) -> dict:
        dias = self.vigencia.currentData()
        return {
            "variante_id": self.variante.currentData(),
            "cliente": self.cliente.text().strip(),
            "correo": self.correo.text().strip(),
            "telefono": solo_digitos(self.telefono.text()),
            "precio": ("normal", "especial", "gratis")[self.precio.currentIndex()],
            "centavos": round(self.monto.value() * 100),
            "expira": (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat() if dias else None,
        }


class DialogoEnlace(QDialog):
    def __init__(self, url: str, venta: dict, nombre_app: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enlace de compra creado")
        self.setMinimumWidth(520)
        quien = venta["cliente"] or "el cliente"
        texto = (f"Hola{' ' + venta['cliente'] if venta['cliente'] else ''}, aquí puedes obtener tu licencia de "
                 f"{nombre_app}:\n{url}\n\nAl terminar te llegará la clave por correo. Abre el programa, pégala en "
                 "la ventana de activación y presiona *Activar*.")

        titulo = QLabel(f"Enlace para {quien}", objectName="titulo")
        enlace = QLineEdit(url, readOnly=True)
        enlace.setFont(fuente_mono(10))
        copiar = boton("Copiar enlace")
        copiar.clicked.connect(lambda: (QGuiApplication.clipboard().setText(url), copiar.setText("✔ Copiado")))
        abrir = boton("Abrir")
        abrir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        wa = boton("Enviar por WhatsApp", "whatsapp")
        wa.clicked.connect(lambda: abrir_whatsapp(venta["telefono"], texto))
        correo = boton("Enviar por correo")
        correo.clicked.connect(lambda: abrir_correo(venta["correo"], f"Tu licencia de {nombre_app}", texto))
        correo.setVisible(bool(venta["correo"]))
        cerrar = boton("Cerrar")
        cerrar.clicked.connect(self.accept)
        fila = QHBoxLayout()
        for b in (copiar, abrir, wa, correo):
            fila.addWidget(b)
        fila.addStretch()
        fila.addWidget(cerrar)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(titulo)
        lay.addWidget(enlace)
        lay.addLayout(fila)


# ============================================================ ventana principal

class Tarjeta(QFrame):
    def __init__(self, titulo: str, color: str):
        super().__init__(objectName="tarjeta")
        self.valor = QLabel("—", objectName="tarjetaValor")
        self.valor.setStyleSheet(f"color:{color}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        lay.addWidget(QLabel(titulo.upper(), objectName="tarjetaTitulo"))
        lay.addWidget(self.valor)


class Ventana(QMainWindow):
    TAB_ACTIVIDAD = 3

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITULO)
        self.setWindowIcon(icono_app())
        self.resize(1260, 760)
        self.cfg = cargar_config()
        self.api: Api | None = None
        self.datos = {"licencias": [], "instancias": [], "ventas": []}
        self.vistos: set | None = None            # eventos ya notificados
        self.desactivaciones: list[dict] = []     # equipos que desaparecieron durante esta sesión
        self.no_vistos = 0
        self.cargando = False

        self._construir()
        self.tray = QSystemTrayIcon(icono_app(), self)
        self.tray.setToolTip(APP_TITULO)
        self.tray.activated.connect(lambda *_: (self.showNormal(), self.activateWindow()))
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.timer = QTimer(self, interval=INTERVALO_REFRESCO_MS, timeout=self.refrescar)
        QTimer.singleShot(0, self.iniciar)

    # ---------------------------------------------------------------- UI
    def _construir(self):
        central = QWidget()
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(22, 18, 22, 12)
        raiz.setSpacing(14)

        cab = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(0)
        textos.addWidget(QLabel(APP_TITULO, objectName="titulo"))
        self.lbl_sub = QLabel(objectName="nota")
        textos.addWidget(self.lbl_sub)
        cab.addLayout(textos)
        cab.addStretch()
        self.buscar = QLineEdit(placeholderText="Buscar cliente, correo, equipo, clave…", objectName="buscar")
        self.buscar.setFixedWidth(280)
        self.buscar.setClearButtonEnabled(True)
        self.buscar.textChanged.connect(self.pintar)
        cab.addWidget(self.buscar)
        self.btn_refrescar = boton("⟳  Actualizar")
        self.btn_refrescar.clicked.connect(self.refrescar)
        cab.addWidget(self.btn_refrescar)
        cfg = boton("⚙  Configuración")
        cfg.clicked.connect(self.configurar)
        cab.addWidget(cfg)
        raiz.addLayout(cab)

        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(12)
        self.t_lic = Tarjeta("Licencias", "#ffffff")
        self.t_act = Tarjeta("Activas", COLOR["Activa"])
        self.t_pend = Tarjeta("Sin activar", COLOR["Sin activar"])
        self.t_bloq = Tarjeta("Bloqueadas / vencidas", COLOR["Bloqueada"])
        self.t_eq = Tarjeta("Equipos activados", "#ffffff")
        self.t_ventas = Tarjeta("Ventas pagadas", COLOR["Pagada"])
        for t in (self.t_lic, self.t_act, self.t_pend, self.t_bloq, self.t_eq, self.t_ventas):
            tarjetas.addWidget(t)
        raiz.addLayout(tarjetas)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._tab_cambiada)
        self.tabs.addTab(self._tab_licencias(), "Licencias")
        self.tabs.addTab(self._tab_equipos(), "Equipos")
        self.tabs.addTab(self._tab_ventas(), "Ventas")
        self.tabs.addTab(self._tab_actividad(), "Actividad")
        raiz.addWidget(self.tabs, 1)

        self.estado = QLabel(objectName="nota")
        self.statusBar().addWidget(self.estado, 1)
        self._subtitulo()

    def _subtitulo(self):
        c = self.cfg
        partes = [c["nombre_app"], c["tienda_nombre"], c["producto_nombre"] or "todos los productos"]
        self.lbl_sub.setText("  ·  ".join(p for p in partes if p) + "  ·  Lemon Squeezy")

    def _barra(self, *widgets) -> QHBoxLayout:
        b = QHBoxLayout()
        b.setSpacing(8)
        for w in widgets:
            if w is None:
                b.addStretch()
            else:
                b.addWidget(w)
        return b

    def _tab_licencias(self) -> QWidget:
        w = QWidget()
        nueva = boton("＋  Nuevo enlace de compra", "primario",
                      "Crea un enlace de pago (o de regalo) para un cliente. Al completarlo recibe su clave.")
        nueva.clicked.connect(self.nueva_venta)
        self.b_editar = boton("Editar", tip="Equipos permitidos y fecha de vencimiento.")
        self.b_editar.clicked.connect(self.editar_licencia)
        self.b_copiar = boton("Copiar clave")
        self.b_copiar.clicked.connect(self.copiar_clave)
        self.b_wa = boton("Enviar por WhatsApp", "whatsapp")
        self.b_wa.clicked.connect(self.enviar_whatsapp)
        self.b_correo = boton("Enviar por correo")
        self.b_correo.clicked.connect(self.enviar_correo)
        self.b_quitar = boton("Quitar equipo", tip="Desactiva una computadora de esta licencia. "
                                                   "El cliente podrá activarla en otra PC.")
        self.b_quitar.clicked.connect(self.quitar_equipo)
        self.b_bloq = boton("Bloquear", "peligro")
        self.b_bloq.clicked.connect(self.alternar_bloqueo)

        self.tl = tabla(["Cliente", "Estado", "Clave", "Equipos", "Equipos activados", "Comprada",
                         "Vence", "Correo", "Producto"])
        for i, ancho in enumerate([170, 125, 340, 70, 190, 140, 95, 200]):
            self.tl.setColumnWidth(i, ancho)
        self.tl.itemSelectionChanged.connect(self._botones_licencia)
        self.tl.doubleClicked.connect(self.editar_licencia)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addLayout(self._barra(nueva, None, self.b_editar, self.b_copiar, self.b_wa, self.b_correo,
                                  self.b_quitar, self.b_bloq))
        lay.addWidget(self.tl)
        self._botones_licencia()
        return w

    def _tab_equipos(self) -> QWidget:
        w = QWidget()
        self.b_ver_lic = boton("Ver licencia")
        self.b_ver_lic.clicked.connect(self.ver_licencia_de_equipo)
        self.b_copiar_id = boton("Copiar ID")
        self.b_copiar_id.clicked.connect(
            lambda: (i := self.instancia_sel()) and QGuiApplication.clipboard().setText(
                partir_instancia(i["name"])[1] or i["identifier"]))
        self.b_quitar_eq = boton("Quitar equipo", "peligro",
                                 tip="Desactiva esta computadora: deja de funcionar y libera un equipo "
                                     "de la licencia.")
        self.b_quitar_eq.clicked.connect(self.quitar_equipo_seleccionado)

        self.te = tabla(["Nombre del equipo", "ID de equipo", "Licencia de", "Estado de la licencia",
                         "Clave", "Activado"])
        for i, ancho in enumerate([190, 185, 180, 150, 300]):
            self.te.setColumnWidth(i, ancho)
        self.te.itemSelectionChanged.connect(self._botones_equipo)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addLayout(self._barra(QLabel("Computadoras donde se activó una licencia.", objectName="nota"),
                                  None, self.b_ver_lic, self.b_copiar_id, self.b_quitar_eq))
        lay.addWidget(self.te)
        self._botones_equipo()
        return w

    def _tab_ventas(self) -> QWidget:
        w = QWidget()
        nueva = boton("＋  Nuevo enlace de compra", "primario")
        nueva.clicked.connect(self.nueva_venta)
        self.b_recibo = boton("Abrir recibo")
        self.b_recibo.clicked.connect(
            lambda: (v := self.venta_sel()) and QDesktopServices.openUrl(QUrl((v.get("urls") or {}).get("receipt", ""))))
        self.b_copiar_correo = boton("Copiar correo")
        self.b_copiar_correo.clicked.connect(
            lambda: (v := self.venta_sel()) and QGuiApplication.clipboard().setText(v.get("user_email") or ""))
        self.tv = tabla(["Fecha", "Pedido", "Cliente", "Correo", "Producto", "Total", "Estado"])
        for i, ancho in enumerate([140, 80, 170, 220, 230, 110]):
            self.tv.setColumnWidth(i, ancho)
        self.tv.itemSelectionChanged.connect(self._botones_venta)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addLayout(self._barra(nueva, None, self.b_recibo, self.b_copiar_correo))
        lay.addWidget(self.tv)
        self._botones_venta()
        return w

    def _tab_actividad(self) -> QWidget:
        w = QWidget()
        self.ta = tabla(["Fecha", "Evento", "Cliente", "Detalle"])
        for i, ancho in enumerate([145, 200, 200]):
            self.ta.setColumnWidth(i, ancho)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addLayout(self._barra(QLabel(f"Ventas y activaciones. Se actualiza sola cada "
                                         f"{INTERVALO_REFRESCO_MS // 1000} segundos.", objectName="nota"), None))
        lay.addWidget(self.ta)
        return w

    # ---------------------------------------------------------------- datos
    def iniciar(self):
        if not (self.cfg["api_key"] and self.cfg["tienda_id"]):
            if not self.configurar(primera=True):
                self.estado.setText("Sin configurar. Pulsa ⚙ Configuración.")
            return
        self.api = Api(self.cfg["api_key"])
        self.refrescar()
        self.timer.start()

    def configurar(self, primera=False) -> bool:
        d = DialogoConfig(self.cfg, self)
        if primera:
            d.setWindowTitle("Bienvenido — conecta tu cuenta de Lemon Squeezy")
        if d.exec() != QDialog.DialogCode.Accepted:
            return False
        cambio_tienda = (d.cfg["tienda_id"], d.cfg["producto_id"]) != (self.cfg["tienda_id"], self.cfg["producto_id"])
        self.cfg = d.cfg
        guardar_config(self.cfg)
        self._subtitulo()
        self.api = Api(self.cfg["api_key"])
        if cambio_tienda:
            self.vistos = None
            self.desactivaciones = []
            self.datos = {"licencias": [], "instancias": [], "ventas": []}
        self.refrescar()
        if not self.timer.isActive():
            self.timer.start()
        return True

    def accion(self, fn, *args, mensaje=""):
        """Ejecuta un cambio en Lemon Squeezy y luego refresca."""
        if not self.api:
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def ok(_):
            QGuiApplication.restoreOverrideCursor()
            if mensaje:
                self.estado.setStyleSheet("")
                self.estado.setText(mensaje)
            self.refrescar()

        def error(e):
            QGuiApplication.restoreOverrideCursor()
            self.mostrar_error(e)

        en_hilo(fn, *args, ok=ok, error=error)

    def mostrar_error(self, e: str):
        self.estado.setText(f"⚠ {e}")
        self.estado.setStyleSheet("color:#ff6b6b")

    def refrescar(self):
        if not self.api or self.cargando:
            return
        self.cargando = True
        self.btn_refrescar.setEnabled(False)
        tienda = (self.cfg["tienda_id"], self.cfg["producto_id"])

        def ok(datos):
            self.cargando = False
            self.btn_refrescar.setEnabled(True)
            if tienda != (self.cfg["tienda_id"], self.cfg["producto_id"]):
                return self.refrescar()   # se cambió de tienda mientras cargaba
            anteriores = {i["id"]: i for i in self.datos["instancias"]}
            self.datos = datos
            self._detectar_desactivaciones(anteriores)
            self.estado.setStyleSheet("")
            self.estado.setText(f"Actualizado {datetime.now().strftime('%H:%M:%S')}")
            self.pintar()
            self._notificar_nuevos()

        def error(e):
            self.cargando = False
            self.btn_refrescar.setEnabled(True)
            self.mostrar_error(e)

        en_hilo(self.api.todo, *tienda, ok=ok, error=error)

    def _detectar_desactivaciones(self, anteriores: dict):
        if self.vistos is None:
            return
        actuales = {i["id"] for i in self.datos["instancias"]}
        licencias = {l["id"]: l for l in self.datos["licencias"]}
        ahora = datetime.now(timezone.utc).isoformat()
        for id_, ins in anteriores.items():
            if id_ not in actuales:
                lic = licencias.get(ins.get("license_key_id")) or {}
                self.desactivaciones.append({"id": id_, "fecha": ahora, "cliente": lic.get("user_name", ""),
                                             "equipo": partir_instancia(ins["name"])[0] or ins["name"]})

    def eventos(self) -> list[dict]:
        licencias = {l["id"]: l for l in self.datos["licencias"]}
        evs = []
        for v in self.datos["ventas"]:
            producto = (v.get("first_order_item") or {}).get("product_name", "")
            evs.append({"clave": ("venta", v["id"]), "tipo": "venta", "fecha": v.get("created_at"),
                        "cliente": v.get("user_name", ""),
                        "detalle": f"Pedido #{v.get('order_number')} · {producto} · {v.get('total_formatted', '')}"})
            if v.get("refunded_at"):
                evs.append({"clave": ("reembolso", v["id"]), "tipo": "reembolso", "fecha": v.get("refunded_at"),
                            "cliente": v.get("user_name", ""),
                            "detalle": f"Pedido #{v.get('order_number')} · {v.get('refunded_amount_formatted', '')}"})
        for i in self.datos["instancias"]:
            lic = licencias.get(i.get("license_key_id")) or {}
            evs.append({"clave": ("activacion", i["id"]), "tipo": "activacion", "fecha": i.get("created_at"),
                        "cliente": lic.get("user_name", ""), "detalle": f"Activó en {i.get('name', '')}"})
        for d in self.desactivaciones:
            evs.append({"clave": ("desactivacion", d["id"]), "tipo": "desactivacion", "fecha": d["fecha"],
                        "cliente": d["cliente"], "detalle": f"Se desactivó {d['equipo']}"})
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
        if self.tabs.currentIndex() != self.TAB_ACTIVIDAD:
            self.no_vistos += len(nuevos)
            self.tabs.setTabText(self.TAB_ACTIVIDAD, f"Actividad  ●{self.no_vistos}")
        e = nuevos[0]
        titulo = EVENTOS[e["tipo"]][0]
        texto = f"{e['cliente'] or '—'} — {e['detalle']}" + (f"  (+{len(nuevos) - 1} más)" if len(nuevos) > 1 else "")
        icono = (QSystemTrayIcon.MessageIcon.Warning if e["tipo"] in ("reembolso", "desactivacion")
                 else QSystemTrayIcon.MessageIcon.Information)
        if self.tray.isVisible():
            self.tray.showMessage(titulo, texto, icono, 8000)
        self.estado.setText(f"🔔 {titulo}: {texto}")
        QApplication.alert(self)

    def _tab_cambiada(self, i):
        if i == self.TAB_ACTIVIDAD:
            self.no_vistos = 0
            self.tabs.setTabText(self.TAB_ACTIVIDAD, "Actividad")

    # ---------------------------------------------------------------- pintar
    def _coincide(self, *campos) -> bool:
        f = self.buscar.text().strip().lower()
        return not f or any(f in str(c or "").lower() for c in campos)

    def pintar(self):
        lics = self.datos["licencias"]
        insts = self.datos["instancias"]
        ventas = self.datos["ventas"]
        estados = [estado_licencia(l) for l in lics]
        por_licencia: dict[int, list[dict]] = {}
        for i in insts:
            por_licencia.setdefault(i["license_key_id"], []).append(i)
        venta_de = {v["id"]: v for v in ventas}
        lic_de = {l["id"]: l for l in lics}

        self.t_lic.valor.setText(str(len(lics)))
        self.t_act.valor.setText(str(estados.count("Activa")))
        self.t_pend.valor.setText(str(estados.count("Sin activar")))
        self.t_bloq.valor.setText(str(estados.count("Bloqueada") + estados.count("Vencida")))
        self.t_eq.valor.setText(str(len(insts)))
        self.t_ventas.valor.setText(str(sum(1 for v in ventas if v.get("status") == "paid")))

        # --- licencias
        sel = fila_seleccionada(self.tl)
        self.tl.setRowCount(0)
        for lic, est in zip(lics, estados):
            acts = por_licencia.get(lic["id"], [])
            if not self._coincide(lic.get("user_name"), lic.get("user_email"), lic.get("key"),
                                  *[a.get("name") for a in acts]):
                continue
            r = self.tl.rowCount()
            self.tl.insertRow(r)
            equipos = ", ".join(partir_instancia(a["name"])[0] or a["name"] for a in acts)
            producto = ((venta_de.get(lic.get("order_id")) or {}).get("first_order_item") or {}).get("product_name")
            celdas = [
                item(lic.get("user_name"), dato=lic["id"], negrita=True),
                item(f"● {est}" + ("  (prueba)" if lic.get("test_mode") else ""), COLOR.get(est)),
                item(lic.get("key"), "#c9d1e0", mono=True),
                item(limite_txt(lic)),
                item(equipos or "—", None if acts else "#6b7280"),
                item(fmt_fecha(lic.get("created_at"))),
                item(fmt_fecha(lic.get("expires_at"), False) if lic.get("expires_at") else "Nunca",
                     COLOR["Vencida"] if est == "Vencida" else None),
                item(lic.get("user_email")),
                item(producto),
            ]
            for c, it in enumerate(celdas):
                self.tl.setItem(r, c, it)
            if lic["id"] == sel:
                self.tl.selectRow(r)

        # --- equipos
        sel = fila_seleccionada(self.te)
        self.te.setRowCount(0)
        for ins in insts:
            lic = lic_de.get(ins["license_key_id"]) or {}
            pc, equipo = partir_instancia(ins.get("name", ""))
            if not self._coincide(ins.get("name"), lic.get("user_name"), lic.get("user_email"), lic.get("key")):
                continue
            est = estado_licencia(lic) if lic else "—"
            r = self.te.rowCount()
            self.te.insertRow(r)
            celdas = [
                item(pc or ins.get("name"), dato=ins["id"], negrita=True),
                item(equipo, "#c9d1e0", mono=True),
                item(lic.get("user_name")),
                item(f"● {est}", COLOR.get(est)),
                item(lic.get("key"), "#c9d1e0", mono=True),
                item(fmt_fecha(ins.get("created_at"))),
            ]
            for c, it in enumerate(celdas):
                self.te.setItem(r, c, it)
            if ins["id"] == sel:
                self.te.selectRow(r)

        # --- ventas
        sel = fila_seleccionada(self.tv)
        self.tv.setRowCount(0)
        for v in ventas:
            producto = (v.get("first_order_item") or {}).get("product_name", "")
            variante = (v.get("first_order_item") or {}).get("variant_name", "")
            if variante and variante != "Default":
                producto = f"{producto} — {variante}"
            if not self._coincide(v.get("user_name"), v.get("user_email"), v.get("order_number"), producto):
                continue
            est = ESTADOS_VENTA.get(v.get("status"), v.get("status_formatted") or "—")
            r = self.tv.rowCount()
            self.tv.insertRow(r)
            celdas = [
                item(fmt_fecha(v.get("created_at")), dato=v["id"]),
                item(f"#{v.get('order_number')}"),
                item(v.get("user_name"), negrita=True),
                item(v.get("user_email")),
                item(producto),
                item(v.get("total_formatted")),
                item(f"● {est}" + ("  (prueba)" if v.get("test_mode") else ""), COLOR.get(est)),
            ]
            for c, it in enumerate(celdas):
                self.tv.setItem(r, c, it)
            if v["id"] == sel:
                self.tv.selectRow(r)

        # --- actividad
        self.ta.setRowCount(0)
        for ev in self.eventos():
            if not self._coincide(ev["cliente"], ev["detalle"]):
                continue
            nombre, color = EVENTOS[ev["tipo"]]
            r = self.ta.rowCount()
            self.ta.insertRow(r)
            celdas = [item(fmt_fecha(ev["fecha"])), item(f"● {nombre}", color), item(ev["cliente"]),
                      item(ev["detalle"])]
            for c, it in enumerate(celdas):
                self.ta.setItem(r, c, it)

        self._botones_licencia()
        self._botones_equipo()
        self._botones_venta()

    # ---------------------------------------------------------------- selección
    def lic_sel(self) -> dict | None:
        id_ = fila_seleccionada(self.tl)
        return next((l for l in self.datos["licencias"] if l["id"] == id_), None)

    def instancia_sel(self) -> dict | None:
        id_ = fila_seleccionada(self.te)
        return next((i for i in self.datos["instancias"] if i["id"] == id_), None)

    def venta_sel(self) -> dict | None:
        id_ = fila_seleccionada(self.tv)
        return next((v for v in self.datos["ventas"] if v["id"] == id_), None)

    def instancias_de(self, lic: dict) -> list[dict]:
        return [i for i in self.datos["instancias"] if i["license_key_id"] == lic["id"]]

    def _botones_licencia(self):
        lic = self.lic_sel()
        for b in (self.b_editar, self.b_copiar, self.b_wa, self.b_bloq):
            b.setEnabled(lic is not None)
        self.b_correo.setEnabled(bool(lic and lic.get("user_email")))
        self.b_quitar.setEnabled(bool(lic and self.instancias_de(lic)))
        bloqueada = bool(lic and lic.get("disabled"))
        self.b_bloq.setText("Desbloquear" if bloqueada else "Bloquear")
        self.b_bloq.setObjectName("secundario" if bloqueada else "peligro")
        self.b_bloq.style().unpolish(self.b_bloq)
        self.b_bloq.style().polish(self.b_bloq)

    def _botones_equipo(self):
        ins = self.instancia_sel()
        for b in (self.b_ver_lic, self.b_copiar_id, self.b_quitar_eq):
            b.setEnabled(ins is not None)

    def _botones_venta(self):
        v = self.venta_sel()
        self.b_recibo.setEnabled(bool(v and (v.get("urls") or {}).get("receipt")))
        self.b_copiar_correo.setEnabled(bool(v and v.get("user_email")))

    # ---------------------------------------------------------------- acciones licencias
    def nueva_venta(self):
        if not self.api:
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        tienda = self.cfg["tienda_id"]

        def mostrar(variantes):
            QGuiApplication.restoreOverrideCursor()
            d = DialogoVenta(variantes, self.cfg.get("moneda", ""), self)
            if d.exec() != QDialog.DialogCode.Accepted:
                return
            venta = d.datos()
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            def creado(url):
                QGuiApplication.restoreOverrideCursor()
                self.estado.setStyleSheet("")
                self.estado.setText("Enlace de compra creado.")
                DialogoEnlace(url, venta, self.cfg["nombre_app"], self).exec()

            en_hilo(self.api.crear_enlace, tienda, venta, ok=creado, error=error)

        def error(e):
            QGuiApplication.restoreOverrideCursor()
            self.mostrar_error(e)
            QMessageBox.warning(self, "Lemon Squeezy", e)

        en_hilo(self.api.variantes, tienda, self.cfg["producto_id"], ok=mostrar, error=error)

    def editar_licencia(self, *_):
        lic = self.lic_sel()
        if not lic:
            return
        d = DialogoEditar(lic, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.accion(self.api.editar_licencia, lic["id"], d.datos(), mensaje="Licencia actualizada.")

    def copiar_clave(self):
        if lic := self.lic_sel():
            QGuiApplication.clipboard().setText(lic["key"])
            self.estado.setStyleSheet("")
            self.estado.setText(f"Clave de {lic.get('user_name')} copiada.")

    def _texto_clave(self, lic: dict) -> str:
        return (f"Hola {lic.get('user_name') or ''}, aquí está tu licencia de {self.cfg['nombre_app']}:\n\n"
                f"{lic['key']}\n\nAbre el programa, pega la clave en la ventana de activación y presiona *Activar*.")

    def enviar_whatsapp(self):
        lic = self.lic_sel()
        if not lic:
            return
        telefonos = self.cfg.setdefault("telefonos", {})
        tel, ok = QInputDialog.getText(self, "Enviar por WhatsApp",
                                       f"WhatsApp de {lic.get('user_name') or 'el cliente'} (con código de país):",
                                       text=telefonos.get(str(lic["id"]), ""))
        if not ok or not solo_digitos(tel):
            return
        telefonos[str(lic["id"])] = solo_digitos(tel)
        guardar_config(self.cfg)
        abrir_whatsapp(tel, self._texto_clave(lic))

    def enviar_correo(self):
        if (lic := self.lic_sel()) and lic.get("user_email"):
            abrir_correo(lic["user_email"], f"Tu licencia de {self.cfg['nombre_app']}", self._texto_clave(lic))

    def alternar_bloqueo(self):
        lic = self.lic_sel()
        if not lic:
            return
        bloquear = not lic.get("disabled")
        if bloquear and not self.confirmar(
                "Bloquear licencia",
                f"¿Bloquear la licencia de <b>{lic.get('user_name')}</b>?<br><br>"
                "El programa dejará de funcionar en sus equipos la próxima vez que lo abran "
                "(o al pasar los días sin internet permitidos)."):
            return
        self.accion(self.api.editar_licencia, lic["id"], {"disabled": bloquear},
                    mensaje=f"Licencia {'bloqueada' if bloquear else 'desbloqueada'}.")

    def quitar_equipo(self):
        lic = self.lic_sel()
        acts = self.instancias_de(lic) if lic else []
        if not acts:
            return
        if len(acts) == 1:
            act = acts[0]
        else:
            nombres = [a["name"] for a in acts]
            elegido, ok = QInputDialog.getItem(self, "Quitar equipo", "¿Qué equipo quieres desactivar?",
                                               nombres, 0, False)
            if not ok:
                return
            act = acts[nombres.index(elegido)]
        self._quitar(lic, act)

    def quitar_equipo_seleccionado(self):
        ins = self.instancia_sel()
        lic = next((l for l in self.datos["licencias"] if ins and l["id"] == ins["license_key_id"]), None)
        if ins and lic:
            self._quitar(lic, ins)

    def _quitar(self, lic: dict, act: dict):
        if self.confirmar("Quitar equipo",
                          f"¿Desactivar <b>{partir_instancia(act['name'])[0] or act['name']}</b> de la licencia de "
                          f"<b>{lic.get('user_name')}</b>?<br><br>Ese equipo dejará de funcionar y la clave "
                          "quedará libre para activarse en otra computadora."):
            self.accion(self.api.quitar_equipo, lic["key"], act["identifier"], mensaje="Equipo desactivado.")

    def ver_licencia_de_equipo(self):
        ins = self.instancia_sel()
        if not ins:
            return
        self.buscar.clear()
        self.tabs.setCurrentIndex(0)
        for r in range(self.tl.rowCount()):
            if self.tl.item(r, 0).data(Qt.ItemDataRole.UserRole) == ins["license_key_id"]:
                self.tl.selectRow(r)
                self.tl.scrollToItem(self.tl.item(r, 0))
                break

    def confirmar(self, titulo: str, texto: str) -> bool:
        caja = QMessageBox(QMessageBox.Icon.Warning, titulo, texto, parent=self)
        si = caja.addButton("Sí, continuar", QMessageBox.ButtonRole.AcceptRole)
        caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caja.exec()
        return caja.clickedButton() is si

    def closeEvent(self, e):
        self.tray.hide()
        super().closeEvent(e)


QSS = """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; }
QMainWindow, QDialog, QWidget { background: #15171c; color: #d8dbe2; }
QLabel { background: transparent; }
QLabel#titulo { font-size: 21px; font-weight: 700; color: #ffffff; }
QLabel#nota { color: #8a92a0; }
QFrame#tarjeta { background: #1c1f26; border: 1px solid #272b34; border-radius: 12px; }
QLabel#tarjetaTitulo { color: #8a92a0; font-size: 10px; font-weight: 600; letter-spacing: 1px; }
QLabel#tarjetaValor { font-size: 26px; font-weight: 700; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit {
    background: #1e2129; color: #fff; border: 1px solid #343946; border-radius: 7px; padding: 7px 9px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
QPlainTextEdit:focus { border-color: #4c8dff; }
QSpinBox:disabled, QDateEdit:disabled { color: #5b6270; }
QComboBox QAbstractItemView { background: #1e2129; selection-background-color: #2d4a80; }
QPushButton { border-radius: 7px; padding: 8px 14px; font-weight: 600; }
QPushButton#primario { background: #4c8dff; color: white; border: none; }
QPushButton#primario:hover { background: #6aa0ff; }
QPushButton#secundario { background: #232731; color: #d8dbe2; border: 1px solid #343946; }
QPushButton#secundario:hover { background: #2c313d; }
QPushButton#peligro { background: #2a1d21; color: #ff8a8a; border: 1px solid #5a2a31; }
QPushButton#peligro:hover { background: #3a2329; }
QPushButton#whatsapp { background: #1f7a45; color: #eafff1; border: none; }
QPushButton#whatsapp:hover { background: #25934f; }
QPushButton:disabled { background: #1b1e24; color: #4b5260; border: 1px solid #23262e; }
QDialogButtonBox QPushButton { background: #232731; border: 1px solid #343946; min-width: 90px; }
QDialogButtonBox QPushButton#primario { background: #4c8dff; border: none; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: transparent; color: #8a92a0; padding: 9px 18px; margin-right: 4px;
               border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #4c8dff; }
QTabBar::tab:hover { color: #d8dbe2; }
QTableWidget { background: #181a20; alternate-background-color: #1b1e25; border: 1px solid #262a33;
               border-radius: 10px; selection-background-color: #24395f; selection-color: #ffffff; }
QTableWidget::item { padding: 0 8px; border: none; }
QHeaderView::section { background: #1c1f26; color: #8a92a0; border: none; border-bottom: 1px solid #262a33;
                       padding: 8px; font-weight: 600; font-size: 11px; }
QScrollBar:vertical, QScrollBar:horizontal { background: transparent; width: 10px; height: 10px; }
QScrollBar::handle { background: #343946; border-radius: 5px; min-height: 30px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QStatusBar { background: #121419; }
QToolTip { background: #232731; color: #fff; border: 1px solid #343946; padding: 6px; }
QMessageBox QLabel { min-width: 320px; }
"""


def main():
    if getattr(sys, "frozen", False):   # dentro del .exe: indicar a Qt dónde están sus plugins
        os.environ.setdefault("QT_PLUGIN_PATH", str(Path(sys._MEIPASS) / "PySide6" / "plugins"))
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_TITULO)
    app.setWindowIcon(icono_app())
    app.setStyleSheet(QSS)
    app.setQuitOnLastWindowClosed(True)
    v = Ventana()
    v.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
