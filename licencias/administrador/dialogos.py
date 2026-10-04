"""Cinema Productions · Administrador de Licencias — ventanas emergentes.

Todas son sin marco, con barra propia (minimizar, maximizar y cerrar dibujados) y animación al abrir.

Creado por Cinema Productions.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget)

from control import TIPOS_AVISO, ServidorControl
from interfaz import (C, Avatar, Chips, ContadorAnimado, DialogoBase, EstadoVacio, GraficoBarras, Interruptor,
                      MarcaExito, OpcionPlataforma, Pila, Spinner, Toast, boton, celda, color_estado, en_hilo,
                      estilo_pildora, etiqueta, fila, fuente_mono, fundido, informar, legible, llenar_tabla, pildora,
                      priv_clave, priv_correo, priv_nombre, priv_tel, sacudir, tabla, tarjeta)
from modelo import (a_fecha, config_programa, duracion, estado_licencia, fmt_fecha, hace,
                    nombre_plataforma, partir_instancia, solo_digitos)
from plataformas import PLATAFORMAS, crear_cliente, dinero, resumen_ventas
from temas import ESP_SM

__author__ = "Cinema Productions"

_SQL = Path("servidor") / "supabase_cinema.sql"
RUTA_SQL = next((r for r in (Path(getattr(__import__("sys"), "_MEIPASS", ".")) / _SQL,      # dentro del .exe
                             Path(__file__).resolve().parent.parent / _SQL) if r.exists()),
                Path(__file__).resolve().parent.parent / _SQL)


def copiar(texto: str):
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.clipboard().setText(texto or "")


def caja_codigo(texto: str = "") -> tuple[QLabel, QHBoxLayout]:
    codigo = etiqueta(texto, "codigo", ajustar=True)
    codigo.setFont(fuente_mono(10))
    codigo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    b = boton("Copiar")
    b.clicked.connect(lambda: (copiar(codigo.text()), b.setText("✓ Copiado")))
    lay = fila(codigo, b)
    lay.setStretch(0, 1)
    return codigo, lay


def dato(titulo: str, valor) -> QWidget:
    caja = QFrame(objectName="tarjeta")
    l = QVBoxLayout(caja)
    l.setContentsMargins(14, 10, 14, 10)
    l.setSpacing(2)
    l.addWidget(etiqueta(titulo.upper(), "kpiTitulo"))
    if isinstance(valor, QWidget):
        l.addWidget(valor)
    else:
        v = etiqueta(str(valor), "valorFuerte", ajustar=True)
        v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        l.addWidget(v)
    return caja


def contador(valor: float, color: str) -> ContadorAnimado:
    c = ContadorAnimado()
    c.setStyleSheet(f"font-size:24px; font-weight:800; color:{legible(color)};")
    QTimer.singleShot(150, lambda: c.fijar(valor))
    return c


def formulario() -> QFormLayout:
    f = QFormLayout()
    f.setSpacing(12)
    f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return f


# ============================================================ conectar plataforma

class DialogoConectar(DialogoBase):
    """Asistente: 1) elegir plataforma  2) pegar credenciales  3) conectar."""

    TEXTOS = {
        "lemonsqueezy": "Ideal para licencias: tu programa se activa con la clave que recibe el cliente al comprar.",
        "hotmart": "Mira cuántas personas compraron, reembolsos e ingresos. Hotmart no genera claves: puedes darlas "
                   "con Lemon Squeezy desde este panel.",
        "gumroad": "Ventas y claves de licencia por compra (cuenta usos en lugar de equipos).",
        "polar": "Claves de licencia con activaciones por equipo, pedidos y reembolsos.",
    }

    def __init__(self, parent=None, plataforma: str = "", actual: dict | None = None):
        super().__init__(parent, "Conectar plataforma de ventas", ancho=640)
        self.resultado: tuple[str, dict, dict, object] | None = None
        self.actual = actual or {}
        self.plataforma = plataforma or "lemonsqueezy"
        self.pila = Pila()
        self.pila.addWidget(self._pagina_elegir())
        self.pila.addWidget(self._pagina_credenciales())
        self.cuerpo.addWidget(self.pila)
        if plataforma:
            self._mostrar_formulario(plataforma, animar=False)

    # ---- paso 1
    def _pagina_elegir(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(etiqueta("¿Dónde vendes tu programa?", "tituloPagina"))
        lay.addWidget(etiqueta("Elige la plataforma que quieres conectar. Puedes conectar varias.", "nota"))
        self.opciones: dict[str, OpcionPlataforma] = {}
        for clave, p in PLATAFORMAS.items():
            b = OpcionPlataforma(p["icono"], p["nombre"], f"{p['descripcion']} {self.TEXTOS[clave]}", p["color"])
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

        self.form_ls = QWidget()
        f1 = formulario()
        self.form_ls.setLayout(f1)
        self.api_key = QLineEdit(placeholderText="Pega aquí tu API key (empieza por eyJ0…)")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        f1.addRow("API key", self._con_mostrar(self.api_key))

        self.form_hm = QWidget()
        f2 = formulario()
        self.form_hm.setLayout(f2)
        self.client_id = QLineEdit(placeholderText="Client ID")
        self.client_secret = QLineEdit(placeholderText="Client Secret")
        self.client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.basic = QLineEdit(placeholderText="Opcional: se calcula solo (Basic …)")
        self.sandbox = Interruptor("Son credenciales de Sandbox (pruebas)")
        f2.addRow("Client ID", self.client_id)
        f2.addRow("Client Secret", self._con_mostrar(self.client_secret))
        f2.addRow("Basic", self.basic)
        f2.addRow("", self.sandbox)

        self.form_gr = QWidget()
        f3 = formulario()
        self.form_gr.setLayout(f3)
        self.token_gr = QLineEdit(placeholderText="Pega aquí tu access token de Gumroad")
        self.token_gr.setEchoMode(QLineEdit.EchoMode.Password)
        f3.addRow("Access token", self._con_mostrar(self.token_gr))

        self.form_po = QWidget()
        f4 = formulario()
        self.form_po.setLayout(f4)
        self.token_po = QLineEdit(placeholderText="polar_oat_…")
        self.token_po.setEchoMode(QLineEdit.EchoMode.Password)
        self.sandbox_po = Interruptor("Es de sandbox.polar.sh (pruebas)")
        f4.addRow("Access token", self._con_mostrar(self.token_po))
        f4.addRow("", self.sandbox_po)
        for form in (self.form_ls, self.form_hm, self.form_gr, self.form_po):
            form.layout().setContentsMargins(0, 6, 0, 0)
            lay.addWidget(form)

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
        for campo in (self.api_key, self.client_id, self.client_secret, self.token_gr, self.token_po):
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
        elif clave == "gumroad":
            self.pasos.setText(
                f"1. Entra a {enlace}Gumroad → Settings → Advanced → Applications</a><br>"
                "2. Crea una aplicación (nombre libre; en <i>Redirect URI</i> pon <b>http://127.0.0.1</b>) y "
                "pulsa <b>Generate access token</b>.<br>3. Copia el token y pégalo aquí. Solo se guarda en esta "
                "computadora.")
            self.token_gr.setText(self.actual.get("token", ""))
        elif clave == "polar":
            self.pasos.setText(
                f"1. Entra a {enlace}polar.sh → Settings → General → Developers</a> y pulsa <b>New Token</b>.<br>"
                "2. Marca los permisos <b>organizations:read, products:read, orders:read, customers:read, "
                "benefits:read, license_keys:read, license_keys:write</b> (y <i>checkout_links:read</i> para el "
                "enlace de compra).<br>3. Copia el token (empieza por <b>polar_oat_</b>) y pégalo aquí.")
            self.token_po.setText(self.actual.get("token", ""))
            self.sandbox_po.setChecked(bool(self.actual.get("sandbox")))
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
        self.form_gr.setVisible(clave == "gumroad")
        self.form_po.setVisible(clave == "polar")
        self.error.clear()
        if animar:
            self.pila.ir_a(1)
        else:
            self.pila.setCurrentIndex(1)
        {"lemonsqueezy": self.api_key, "hotmart": self.client_id, "gumroad": self.token_gr,
         "polar": self.token_po}[clave].setFocus()

    def _datos(self) -> dict:
        if self.plataforma == "lemonsqueezy":
            return {"api_key": self.api_key.text().strip()}
        if self.plataforma == "gumroad":
            return {"token": self.token_gr.text().strip()}
        if self.plataforma == "polar":
            return {"token": self.token_po.text().strip(), "sandbox": self.sandbox_po.isChecked()}
        return {"client_id": self.client_id.text().strip(), "client_secret": self.client_secret.text().strip(),
                "basic": self.basic.text().strip(), "sandbox": self.sandbox.isChecked()}

    def conectar(self):
        datos = self._datos()
        faltan = [k for k in ("api_key", "client_id", "client_secret", "token") if k in datos and not datos[k]]
        if faltan:
            self.error.setText("Completa los datos para conectar.")
            sacudir(self.tarjeta)
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
            sacudir(self.tarjeta)

        en_hilo(cliente.conectar, ok=ok, error=error)


# ============================================================ resumen al conectar

class DialogoResumen(DialogoBase):
    """Ventana emergente con toda la información de la plataforma recién conectada."""

    def __init__(self, plataforma: str, cliente, resumen: dict, datos: dict, parent=None, cfg: dict | None = None):
        p = PLATAFORMAS[plataforma]
        super().__init__(parent, f"Conectado a {p['nombre']}", ancho=700)
        self.plataforma, self.cliente, self.resumen = plataforma, cliente, resumen
        self.datos = dict(datos)
        self.cfg = cfg or {}

        icono = MarcaExito(C["ok"], 60)
        titulo = etiqueta(f"¡Conectado a {p['nombre']}!", "tituloPagina")
        self.subtitulo = etiqueta("", "nota")
        cab = QVBoxLayout()
        cab.setSpacing(2)
        cab.addWidget(titulo)
        cab.addWidget(self.subtitulo)
        self.modo = pildora()
        self.cuerpo_datos = QVBoxLayout()
        self.cuerpo_datos.setSpacing(12)
        guardar = boton("Guardar y continuar  →", "primario")
        guardar.clicked.connect(self.guardar)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.cuerpo.setSpacing(16)
        self.cuerpo.addLayout(fila(icono, cab, None, pildora(f"{p['icono']} {p['nombre']}", p["color"]), self.modo,
                                   espacio=14))
        self.cuerpo.addLayout(self.cuerpo_datos)
        self.cuerpo.addLayout(fila(None, cancelar, guardar))
        {"lemonsqueezy": self._armar_ls, "hotmart": self._armar_hotmart, "gumroad": self._armar_gumroad,
         "polar": self._armar_polar}[plataforma]()

    def _fijar_modo(self, texto: str, color: str):
        estilo_pildora(self.modo, texto, color)

    def _vaciar_grid(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _nuevo_grid(self):
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.cuerpo_datos.addLayout(self.grid)

    def _codigo(self, texto_ayuda: str):
        self.cuerpo_datos.addWidget(etiqueta(texto_ayuda))
        self.codigo, lay = caja_codigo()
        self.cuerpo_datos.addLayout(lay)

    # ---- Lemon Squeezy
    def _armar_ls(self):
        u = self.resumen["usuario"]
        self.subtitulo.setText(f"Cuenta de {priv_nombre(u.get('name')) or '—'}  ·  {priv_correo(u.get('email'))}")
        prueba = u.get("modo_prueba")
        self._fijar_modo("MODO PRUEBA" if prueba else ("MODO REAL" if prueba is False else "CONECTADO"),
                         C["aviso"] if prueba else C["ok"])
        tiendas = self.resumen.get("tiendas") or []
        if not tiendas:
            self.cuerpo_datos.addWidget(etiqueta("Tu cuenta aún no tiene tiendas. Crea una en app.lemonsqueezy.com "
                                                 "y vuelve a conectar.", "nota", ajustar=True))
            return
        self.tienda = QComboBox()
        for t in tiendas:
            self.tienda.addItem(f"{t.get('name') or 'Tienda'}   (ID {t['id']})", t["id"])
        indice = self.tienda.findData(self.datos.get("tienda_id"))
        self.producto = QComboBox()
        self.producto.currentIndexChanged.connect(self._actualizar_codigo)
        self.cuerpo_datos.addLayout(fila(dato("Tienda", self.tienda), dato("Producto a vigilar", self.producto)))
        self._nuevo_grid()
        self.lista_productos = etiqueta("", "nota", ajustar=True)
        self.lista_productos.setTextFormat(Qt.TextFormat.RichText)
        self.cuerpo_datos.addWidget(self.lista_productos)
        self._codigo("<b>Datos para tu programa</b> — van en <i>cinema_licencias.json</i>:")
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
        self.grid.addWidget(dato("Licencias", contador(d["licencias"], C["acento"])), 0, 0)
        self.grid.addWidget(dato("Ventas", contador(d["ventas"], C["ok"])), 0, 1)
        self.grid.addWidget(dato("Productos", contador(len(d["productos"]), C["info"])), 0, 2)
        self.grid.addWidget(dato("Moneda", t.get("currency") or "—"), 0, 3)
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

    def _fragmento(self, datos_plataforma: dict) -> str:
        import json
        cfg = {"plataformas": {k: {} for k in PLATAFORMAS}, "nombre_app": self.cfg.get("nombre_app", "Mi programa"),
               "servidor": {}, "tema": self.cfg.get("tema", "cinema")}
        cfg["plataformas"][self.plataforma] = self.datos | datos_plataforma
        seccion = config_programa(cfg)[self.plataforma]
        return f'"{self.plataforma}": ' + json.dumps(seccion, ensure_ascii=False)

    def _actualizar_codigo(self):
        self.codigo.setText(self._fragmento(self._seleccion_ls()))

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
        self.cuerpo_datos.addLayout(fila(dato("Entorno", r.get("entorno", "—")), dato("Producto a vigilar",
                                                                                      self.producto)))
        self._nuevo_grid()
        self._mostrar_ventas(r)
        nota = etiqueta("Hotmart no crea claves de licencia. Para que un comprador de Hotmart active tu programa, "
                        "usa <b>🎁 Dar licencia</b> en Personas o Ventas (crea una licencia gratis en Lemon Squeezy).",
                        "nota", ajustar=True)
        nota.setTextFormat(Qt.TextFormat.RichText)
        self.cuerpo_datos.addWidget(nota)

    def _mostrar_ventas(self, r: dict, extra: tuple[str, float, str] | None = None):
        self._vaciar_grid()
        self.grid.addWidget(dato("Personas con el programa", contador(r["compradores"], C["acento"])), 0, 0)
        self.grid.addWidget(dato("Ventas válidas", contador(r["ventas_validas"], C["ok"])), 0, 1)
        self.grid.addWidget(dato("Reembolsos", contador(r["reembolsos"], C["error"])), 0, 2)
        titulo, valor, color = extra or ("Productos", len(r.get("productos") or []), C["info"])
        self.grid.addWidget(dato(titulo, contador(valor, color)), 0, 3)
        ingresos = "   ·   ".join(dinero(v, m) for m, v in sorted(r["ingresos"].items())) or "—"
        self.grid.addWidget(dato("Ingresos totales", ingresos), 1, 0, 1, 4)

    def _recalcular_hotmart(self):
        producto = self.producto.currentData()

        def ok(ventas):
            if producto == self.producto.currentData():
                self._mostrar_ventas(self.resumen | resumen_ventas(ventas))

        en_hilo(self.cliente.ventas, producto, 0, ok=ok, error=lambda e: Toast.mostrar(self, "Hotmart", e, "error"))

    # ---- Gumroad
    def _armar_gumroad(self):
        r = self.resumen
        u = r.get("usuario") or {}
        self.subtitulo.setText(f"Cuenta de {priv_nombre(u.get('name')) or '—'}  ·  {priv_correo(u.get('email'))}")
        self._fijar_modo("CONECTADO", C["ok"])
        self.producto = QComboBox()
        self.producto.addItem("Todos los productos", "")
        for p in r.get("productos") or []:
            self.producto.addItem(f"{p.get('name')}   {p.get('formatted_price') or ''}", p.get("id"))
        guardado = self.producto.findData(self.datos.get("producto_id"))
        self.producto.setCurrentIndex(guardado if guardado > 0 else (1 if len(r.get("productos") or []) == 1 else 0))
        self.producto.currentIndexChanged.connect(self._recalcular_gumroad)
        self.cuerpo_datos.addLayout(fila(dato("Tienda", u.get("url") or "—"),
                                         dato("Producto de tu programa", self.producto)))
        self._nuevo_grid()
        self._mostrar_ventas(r, ("Claves de licencia", r.get("claves", 0), C["info"]))
        self._codigo("<b>Datos para tu programa</b> — van en <i>cinema_licencias.json</i>:")
        nota = etiqueta("Activa <b>«Generate a unique license key per sale»</b> en tu producto de Gumroad para que "
                        "cada comprador reciba su clave.", "nota", ajustar=True)
        nota.setTextFormat(Qt.TextFormat.RichText)
        self.cuerpo_datos.addWidget(nota)
        self.codigo.setText(self._fragmento(self._seleccion_gumroad()))

    def _seleccion_gumroad(self) -> dict:
        p = next((p for p in self.resumen.get("productos") or [] if p.get("id") == self.producto.currentData()), {})
        u = self.resumen.get("usuario") or {}
        return {"producto_id": p.get("id", ""), "producto_nombre": p.get("name", ""),
                "url_compra": p.get("short_url", ""), "cuenta": u.get("name", ""), "correo": u.get("email", "")}

    def _recalcular_gumroad(self):
        self.codigo.setText(self._fragmento(self._seleccion_gumroad()))
        producto = self.producto.currentData()

        def ok(ventas):
            if producto == self.producto.currentData():
                self._mostrar_ventas(self.resumen | resumen_ventas(ventas),
                                     ("Claves de licencia", sum(1 for v in ventas if v.get("clave_licencia")),
                                      C["info"]))

        en_hilo(self.cliente.ventas, producto, 0, ok=ok, error=lambda e: Toast.mostrar(self, "Gumroad", e, "error"))

    # ---- Polar
    def _armar_polar(self):
        r = self.resumen
        org = r.get("organizacion") or {}
        self.subtitulo.setText(f"Organización {org.get('name') or '—'}  ·  polar.sh/{org.get('slug') or ''}")
        self._fijar_modo("SANDBOX" if r.get("sandbox") else "PRODUCCIÓN", C["aviso"] if r.get("sandbox") else C["ok"])
        self.producto = QComboBox()
        self.producto.addItem("Todos los productos", "")
        for p in r.get("productos") or []:
            self.producto.addItem(p.get("name") or p.get("id"), p.get("id"))
        guardado = self.producto.findData(self.datos.get("producto_id"))
        self.producto.setCurrentIndex(guardado if guardado > 0 else (1 if len(r.get("productos") or []) == 1 else 0))
        self.beneficio = QComboBox()
        self.beneficio.addItem("Todas las claves de licencia", "")
        for b in r.get("beneficios") or []:
            props = b.get("properties") or {}
            limite = (props.get("activations") or {}).get("limit")
            self.beneficio.addItem(f"{b.get('description') or 'Claves de licencia'}"
                                   + (f"   ·  {limite} equipos" if limite else ""), b.get("id"))
        guardado = self.beneficio.findData(self.datos.get("beneficio_id"))
        self.beneficio.setCurrentIndex(guardado if guardado > 0 else (1 if len(r.get("beneficios") or []) == 1 else 0))
        for combo in (self.producto, self.beneficio):
            combo.currentIndexChanged.connect(self._codigo_polar)
        self.cuerpo_datos.addLayout(fila(dato("Producto de tu programa", self.producto),
                                         dato("Beneficio de claves", self.beneficio)))
        self._nuevo_grid()
        self._mostrar_ventas(r, ("Claves de licencia", r.get("claves", 0), C["info"]))
        if not r.get("beneficios"):
            aviso = etiqueta("⚠ Tu organización aún no tiene un beneficio de <b>License Keys</b>. Créalo en Polar → "
                             "Benefits y agrégalo a tu producto para que cada compra genere una clave.", "nota",
                             ajustar=True)
            aviso.setTextFormat(Qt.TextFormat.RichText)
            self.cuerpo_datos.addWidget(aviso)
        self._codigo("<b>Datos para tu programa</b> — van en <i>cinema_licencias.json</i>:")
        self._codigo_polar()

    def _seleccion_polar(self) -> dict:
        org = self.resumen.get("organizacion") or {}
        producto = self.producto.currentData() or ""
        enlaces = [e for e in self.resumen.get("enlaces") or []
                   if not producto or producto in [p.get("id") for p in e.get("products") or []]
                   or e.get("product_id") == producto]
        url = (enlaces[0].get("url") if enlaces else "") or (f"https://polar.sh/{org.get('slug')}" if org.get("slug")
                                                               else "")
        return {"organizacion_id": org.get("id", ""), "organizacion": org.get("name", ""), "slug": org.get("slug", ""),
                "producto_id": producto, "producto_nombre": self.producto.currentText() if producto else "",
                "beneficio_id": self.beneficio.currentData() or "", "url_compra": url}

    def _codigo_polar(self):
        self.codigo.setText(self._fragmento(self._seleccion_polar()))

    def guardar(self):
        if self.plataforma == "gumroad":
            self.datos |= self._seleccion_gumroad()
        elif self.plataforma == "polar":
            self.datos |= self._seleccion_polar()
        elif self.plataforma == "lemonsqueezy":
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


# ============================================================ servidor de control

class DialogoServidor(DialogoBase):
    """Conectar el servidor de control (Supabase): avisos, bloqueos y tiempo de uso."""

    def __init__(self, parent=None, actual: dict | None = None):
        super().__init__(parent, "Servidor de control", ancho=640)
        self.actual = actual or {}
        self.datos: dict = {}
        self.pila = Pila()
        self.pila.addWidget(self._pagina_formulario())
        self.pila.addWidget(self._pagina_listo())
        self.cuerpo.addWidget(self.pila)

    def _pagina_formulario(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(etiqueta("📡  Servidor de control", "tituloPagina"))
        pasos = etiqueta(
            "Con un proyecto gratis de <b>Supabase</b> verás cuánto usan tu programa, podrás enviar avisos a tus "
            "clientes y bloquear o reactivar licencias al instante.<br><br>"
            "1. Crea un proyecto en <a href='https://supabase.com/dashboard' style='color:%s'>supabase.com</a>.<br>"
            "2. Abre <b>SQL Editor → New query</b>, pega el script (botón <b>Copiar script SQL</b>) y pulsa "
            "<b>Run</b>.<br>"
            "3. En <b>Project Settings → API Keys</b> copia la URL, la clave <b>publicable</b> y la <b>secreta</b>."
            % C["info"], "nota", ajustar=True)
        pasos.setTextFormat(Qt.TextFormat.RichText)
        pasos.setOpenExternalLinks(True)
        lay.addWidget(pasos)
        b_sql = boton("📋  Copiar script SQL")
        b_sql.clicked.connect(self._copiar_sql)
        lay.addLayout(fila(b_sql, None))
        f = formulario()
        self.url = QLineEdit(self.actual.get("url", ""), placeholderText="https://xxxxxxxx.supabase.co")
        self.publica = QLineEdit(self.actual.get("clave_publica", ""), placeholderText="sb_publishable_… (va en tu "
                                                                                       "programa)")
        self.secreta = QLineEdit(self.actual.get("clave_secreta", ""), placeholderText="sb_secret_… (solo aquí)")
        self.secreta.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow("URL del proyecto", self.url)
        f.addRow("Clave publicable", self.publica)
        f.addRow("Clave secreta", DialogoConectar._con_mostrar(self.secreta))
        lay.addLayout(f)
        self.error = etiqueta("", ajustar=True)
        self.error.setStyleSheet(f"color:{C['error']}")
        lay.addWidget(self.error)
        lay.addStretch()
        self.spinner = Spinner()
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.btn = boton("Conectar", "primario")
        self.btn.setMinimumWidth(130)
        self.btn.clicked.connect(self.conectar)
        lay.addLayout(fila(None, self.spinner, cancelar, self.btn))
        return w

    def _pagina_listo(self) -> QWidget:
        w = QWidget()
        self.lay_listo = QVBoxLayout(w)
        self.lay_listo.setContentsMargins(0, 0, 0, 0)
        self.lay_listo.setSpacing(14)
        return w

    def _copiar_sql(self):
        try:
            copiar(RUTA_SQL.read_text(encoding="utf-8"))
            Toast.mostrar(self, "Script copiado", "Pégalo en Supabase → SQL Editor y pulsa Run.", "ok")
        except OSError:
            Toast.mostrar(self, "No se encontró el script", str(RUTA_SQL), "error")

    def conectar(self):
        datos = {"url": self.url.text().strip().rstrip("/"), "clave_publica": self.publica.text().strip(),
                 "clave_secreta": self.secreta.text().strip()}
        if not datos["url"] or not datos["clave_secreta"] or not datos["clave_publica"]:
            self.error.setText("Completa la URL y las dos claves.")
            sacudir(self.tarjeta)
            return
        if datos["clave_publica"].startswith("sb_secret_"):
            self.error.setText("En «Clave publicable» va la PUBLICABLE (sb_publishable_…): esa se copia dentro de tu "
                               "programa.")
            sacudir(self.tarjeta)
            return
        self.btn.setEnabled(False)
        self.spinner.iniciar()
        self.error.clear()
        servidor = ServidorControl(datos["url"], datos["clave_secreta"], datos["clave_publica"])

        def ok(r):
            self.spinner.detener()
            self.btn.setEnabled(True)
            self.datos = datos
            self._mostrar(r)

        def error(e):
            self.spinner.detener()
            self.btn.setEnabled(True)
            self.error.setText(f"✕  {e}")
            sacudir(self.tarjeta)

        en_hilo(servidor.probar, ok=ok, error=error)

    def _mostrar(self, r: dict):
        cab = QVBoxLayout()
        cab.setSpacing(2)
        cab.addWidget(etiqueta("¡Servidor conectado!", "tituloPagina"))
        cab.addWidget(etiqueta(r["url"], "nota"))
        self.lay_listo.addLayout(fila(MarcaExito(C["ok"], 60), cab, None, espacio=14))
        g = QGridLayout()
        g.setSpacing(10)
        g.addWidget(dato("Equipos registrados", contador(r["equipos"], C["acento"])), 0, 0)
        g.addWidget(dato("Licencias en uso", contador(r["licencias"], C["ok"])), 0, 1)
        g.addWidget(dato("Horas de uso", contador(r["horas"], C["info"])), 0, 2)
        g.addWidget(dato("Avisos", contador(r["avisos"], C["aviso"])), 0, 3)
        self.lay_listo.addLayout(g)
        nota = etiqueta("La URL y la clave <b>publicable</b> se agregan solas a <i>cinema_licencias.json</i> "
                        "(Conexiones → Datos para tu programa). La clave secreta se queda solo en esta computadora.",
                        "nota", ajustar=True)
        nota.setTextFormat(Qt.TextFormat.RichText)
        self.lay_listo.addWidget(nota)
        self.lay_listo.addStretch()
        guardar = boton("Guardar y continuar  →", "primario")
        guardar.clicked.connect(self.accept)
        self.lay_listo.addLayout(fila(None, guardar))
        self.pila.ir_a(1)


# ============================================================ licencias

class DialogoEditar(DialogoBase):
    """Cambiar los equipos permitidos y la fecha de vencimiento de una licencia (Lemon Squeezy o Polar)."""

    def __init__(self, lic: dict, parent=None):
        super().__init__(parent, "Editar licencia", ancho=520)
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
        form = formulario()
        form.addRow("Cliente", etiqueta(f"<b>{priv_nombre(lic.get('user_name')) or '—'}</b>  "
                                        f"{priv_correo(lic.get('user_email'))}"))
        form.addRow("Plataforma", etiqueta(nombre_plataforma(lic["plataforma"])))
        form.addRow("Equipos permitidos", fila(self.limite, self.ilimitado))
        form.addRow("Vence", fila(self.vence, self.fecha, *extras))
        guardar = boton("Guardar", "primario")
        guardar.clicked.connect(self.accept)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.cuerpo.addWidget(etiqueta("✏️  Editar licencia", "tituloPagina"))
        self.cuerpo.addLayout(form)
        self.cuerpo.addWidget(etiqueta("«+30 días» y «+1 año» se suman desde hoy, o desde el vencimiento actual si "
                                       "aún no ha llegado.", "tenue", ajustar=True))
        self.cuerpo.addLayout(fila(None, cancelar, guardar))

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
        super().__init__(parent, "Nuevo enlace de compra", ancho=580)
        previo = previo or {}
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
        form = formulario()
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
        self.cuerpo.addWidget(etiqueta("🔗  Nuevo enlace de compra", "tituloPagina"))
        self.cuerpo.addLayout(form)
        self.cuerpo.addWidget(etiqueta("Lemon Squeezy crea la clave de licencia cuando el cliente completa la compra y "
                                       "se la envía por correo. Aparecerá sola en Licencias.", "tenue", ajustar=True))
        self.cuerpo.addLayout(fila(None, cancelar, crear))

    def validar(self):
        if self.variante.currentData() is None:
            informar(self, "Sin productos", "Tu tienda no tiene productos. Créalo en Lemon Squeezy y activa "
                                            "«Generate license keys».", "aviso")
            return
        correo = self.correo.text().strip()
        if correo and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
            self.correo.setProperty("error", True)
            self.correo.style().unpolish(self.correo)
            self.correo.style().polish(self.correo)
            sacudir(self.tarjeta)
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
    def __init__(self, url: str, venta: dict, nombre_app: str, acciones, parent=None):
        super().__init__(parent, "Enlace de compra creado", ancho=600)
        texto = (f"Hola{' ' + venta['cliente'] if venta['cliente'] else ''}, aquí puedes obtener tu licencia de "
                 f"{nombre_app}:\n{url}\n\nAl terminar te llegará la clave por correo. Abre el programa, pégala en "
                 "la ventana de activación y presiona *Activar*.")
        enlace = QLineEdit(url, readOnly=True)
        enlace.setFont(fuente_mono(10))
        b_copiar = boton("Copiar enlace")
        b_copiar.clicked.connect(lambda: (copiar(url), b_copiar.setText("✓ Copiado")))
        abrir = boton("Abrir")
        abrir.clicked.connect(lambda: acciones.abrir_url(url))
        wa = boton("WhatsApp", "whatsapp")
        wa.clicked.connect(lambda: acciones.abrir_whatsapp(venta["telefono"], texto))
        correo = boton("Correo")
        correo.clicked.connect(lambda: acciones.abrir_correo(venta["correo"], f"Tu licencia de {nombre_app}", texto))
        correo.setVisible(bool(venta["correo"]))
        listo = boton("Listo", "primario")
        listo.clicked.connect(self.accept)
        self.cuerpo.addWidget(etiqueta(f"✓  Enlace listo para {priv_nombre(venta['cliente']) or 'tu cliente'}",
                                       "tituloPagina"))
        self.cuerpo.addWidget(enlace)
        self.cuerpo.addLayout(fila(b_copiar, abrir, wa, correo, None, listo))


# ============================================================ avisos

PLANTILLAS = {
    "info": ("Novedades de {app}", "Hola, hay una nueva versión de {app} disponible. ¡Gracias por tu compra!"),
    "advertencia": ("Revisa tu licencia de {app}", "Hola, notamos un problema con tu compra de {app}. Por favor "
                                                    "contáctanos para resolverlo."),
    "remocion": ("Tu licencia de {app} será removida", "Hola, tu licencia de {app} será removida en la fecha "
                                                       "indicada. Si crees que es un error o quieres conservarla, "
                                                       "contáctanos antes de esa fecha."),
    "reactivada": ("Tu licencia de {app} está activa otra vez", "¡Buenas noticias! Tu licencia de {app} volvió a "
                                                                 "estar activa. Ya puedes seguir usando el programa."),
    "bloqueo": ("Tu licencia de {app} fue bloqueada", "Hola, tu licencia de {app} fue bloqueada. Contáctanos para "
                                                      "más información."),
}


class DialogoAviso(DialogoBase):
    """Enviar un aviso a una persona (todas sus licencias), a una licencia o a todas."""

    def __init__(self, destinos: list[tuple[str, list[str]]], nombre_app: str, parent=None, elegido: int = 0,
                 tipo: str = "info"):
        super().__init__(parent, "Nuevo aviso", ancho=600)
        self.nombre_app = nombre_app
        self.destino = QComboBox()
        for texto, hashes in destinos:
            self.destino.addItem(texto, hashes)
        self.destino.setCurrentIndex(max(0, elegido))
        self.tipo = QComboBox()
        for clave, texto in TIPOS_AVISO.items():
            self.tipo.addItem(texto, clave)
        self.titulo = QLineEdit(placeholderText="Título del aviso")
        self.mensaje = QPlainTextEdit()
        self.mensaje.setPlaceholderText("Escribe el mensaje que verá tu cliente al abrir el programa…")
        self.mensaje.setFixedHeight(120)
        self.con_fecha = QCheckBox("Fecha límite")
        self.fecha = QDateEdit(calendarPopup=True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setDate(QDate.currentDate().addDays(7))
        self.fecha.setEnabled(False)
        self.con_fecha.toggled.connect(self.fecha.setEnabled)
        self.bloquear = Interruptor("Bloquear la licencia automáticamente en la fecha límite")
        self.tipo.currentIndexChanged.connect(self._plantilla)
        form = formulario()
        form.addRow("Para", self.destino)
        form.addRow("Tipo", self.tipo)
        form.addRow("Título", self.titulo)
        form.addRow("Mensaje", self.mensaje)
        form.addRow("", fila(self.con_fecha, self.fecha, None))
        form.addRow("", self.bloquear)
        enviar = boton("📣  Enviar aviso", "primario")
        enviar.clicked.connect(self.validar)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.cuerpo.addWidget(etiqueta("📣  Nuevo aviso", "tituloPagina"))
        self.cuerpo.addWidget(etiqueta("Tu cliente lo verá en una ventana la próxima vez que su programa se conecte "
                                       "(en unos minutos si lo tiene abierto).", "nota", ajustar=True))
        self.cuerpo.addLayout(form)
        self.cuerpo.addLayout(fila(None, cancelar, enviar))
        self.tipo.setCurrentIndex(max(0, self.tipo.findData(tipo)))
        self._plantilla()

    def _plantilla(self):
        tipo = self.tipo.currentData()
        titulo, mensaje = PLANTILLAS.get(tipo, ("", ""))
        textos_plantilla = {t.format(app=self.nombre_app) for t, _ in PLANTILLAS.values()}
        if not self.titulo.text() or self.titulo.text() in textos_plantilla:
            self.titulo.setText(titulo.format(app=self.nombre_app))
            self.mensaje.setPlainText(mensaje.format(app=self.nombre_app))
        remocion = tipo == "remocion"
        self.bloquear.setVisible(remocion)
        if remocion:
            self.con_fecha.setChecked(True)

    def validar(self):
        if not self.titulo.text().strip() or not self.mensaje.toPlainText().strip():
            sacudir(self.tarjeta)
            return
        self.accept()

    def datos(self) -> dict:
        fecha = None
        if self.con_fecha.isChecked():
            d = self.fecha.date().toPython()
            fecha = datetime(d.year, d.month, d.day, 23, 59, 59).astimezone().isoformat()
        return {"licencias": self.destino.currentData() or [None], "tipo": self.tipo.currentData(),
                "titulo": self.titulo.text().strip(), "mensaje": self.mensaje.toPlainText().strip(),
                "fecha_limite": fecha, "bloquear": not self.bloquear.isHidden() and self.bloquear.isChecked()
                and fecha is not None, "destino": self.destino.currentText()}


# ============================================================ ficha de una persona

class DialogoPersona(DialogoBase):
    """Todo sobre un comprador: compras, licencias, equipos, tiempo de uso, avisos y notas."""

    def __init__(self, ventana, clave: str):
        self.v = ventana
        self.clave = clave
        p = ventana.modelo["persona_por_clave"][clave]
        super().__init__(ventana, f"Ficha de {priv_nombre(p['nombre']) or priv_correo(p['correo']) or 'la persona'}",
                         ancho=900)
        self.setMinimumHeight(640)
        self.p = p
        cab = QVBoxLayout()
        cab.setSpacing(2)
        nombre = etiqueta(priv_nombre(p["nombre"]) or "Sin nombre", "tituloPagina")
        cab.addWidget(nombre)
        cab.addWidget(etiqueta(priv_correo(p["correo"]) or "Sin correo", "nota"))
        pills = QHBoxLayout()
        pills.setSpacing(6)
        color = C["ok"] if p["tiene"] else (C["error"] if p["estado"] == "Reembolsada" else C["tenue"])
        pills.addWidget(pildora(f"●  {p['estado']}", color))
        if p["en_linea"]:
            pills.addWidget(pildora("●  En línea ahora", C["ok"]))
        for k in sorted(p["plataformas"]):
            pills.addWidget(pildora(nombre_plataforma(k), PLATAFORMAS[k]["color"]))
        for t in self.v.cfg["etiquetas"].get(clave, []):
            pills.addWidget(pildora(f"#{t}", C["acento"]))
        pills.addStretch()
        cab.addLayout(pills)
        self.cuerpo.addLayout(fila(Avatar(p["nombre"] or p["correo"], clave, 64), cab, espacio=16))
        self.chips = Chips([("resumen", "Resumen"), ("licencias", f"Licencias  {len(p['licencias'])}"),
                            ("equipos", "Equipos y uso"), ("avisos", "Avisos"), ("notas", "Notas")])
        self.cuerpo.addWidget(self.chips)
        self.pila = Pila()
        for armar in (self._resumen, self._licencias, self._equipos, self._avisos, self._notas):
            self.pila.addWidget(armar())
        self.chips.cambiado.connect(lambda k: self.pila.ir_a(self.chips.claves.index(k)))
        self.cuerpo.addWidget(self.pila, 1)
        hay_lic = bool(p["licencias"])
        bloquear = boton("⛔  Bloquear todo", "peligro", "Bloquea todas sus licencias en las tiendas y en el programa.")
        bloquear.setEnabled(hay_lic)
        bloquear.clicked.connect(lambda: self.v.bloquear_persona(self.clave, True) and self.accept())
        reactivar = boton("↺  Reactivar todo", tip="Desbloquea sus licencias y avisa a su programa.")
        reactivar.setEnabled(hay_lic)
        reactivar.clicked.connect(lambda: self.v.bloquear_persona(self.clave, False) and self.accept())
        aviso = boton("📣  Enviar aviso", tip="Mensaje que verá al abrir el programa.")
        aviso.setEnabled(hay_lic and self.v.servidor() is not None)
        aviso.clicked.connect(lambda: self.v.nuevo_aviso(persona=self.clave))
        wa = boton("WhatsApp", "whatsapp")
        wa.clicked.connect(lambda: self.v.whatsapp_persona(p))
        correo = boton("Correo")
        correo.setEnabled(bool(p["correo"]))
        correo.clicked.connect(lambda: self.v.abrir_correo(p["correo"], self.v.cfg["nombre_app"], ""))
        cerrar = boton("Cerrar", "primario")
        cerrar.clicked.connect(self.reject)
        self.cuerpo.addLayout(fila(bloquear, reactivar, aviso, None, wa, correo, cerrar))

    # ---- pestañas
    def _contenedor(self) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget(objectName="pagina")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, ESP_SM, 0, 0)
        lay.setSpacing(12)
        return w, lay

    def _resumen(self) -> QWidget:
        w, lay = self._contenedor()
        p = self.p
        g = QGridLayout()
        g.setSpacing(10)
        gastado = "   ·   ".join(dinero(v, m) for m, v in sorted(p["gastado"].items())) or "—"
        datos = [("Compras válidas", contador(p["compras"], C["ok"])),
                 ("Reembolsos", contador(p["reembolsos"], C["error"])),
                 ("Licencias", contador(len(p["licencias"]), C["acento"])),
                 ("Equipos", contador(max(p["equipos"], p["equipos_tel"]), C["info"])),
                 ("Gastado", gastado), ("Tiempo de uso", duracion(p["uso_seg"])),
                 ("Última vez en el programa", hace(p["ultima_vez"])), ("Cliente desde", fmt_fecha(p["primera"],
                                                                                                    False))]
        for i, (t, v) in enumerate(datos):
            g.addWidget(dato(t, v), i // 4, i % 4)
        lay.addLayout(g)
        lay.addWidget(etiqueta("Compras", "tituloTarjeta"))
        t = tabla(["Fecha", "Plataforma", "Producto", "Total", "Estado", "Referencia"], [130, 140, 200, 100, 140],
                  pildoras=(1, 4))
        filas = []
        for vid in p["ventas"]:
            s = self.v.modelo["venta_por_pedido"][vid]
            pl = PLATAFORMAS[s["plataforma"]]
            filas.append([celda(fmt_fecha(s["fecha"]), dato=s["id"], orden=s["fecha"] or ""),
                          celda(pl["nombre"], pildora=pl["color"]), celda(s["producto"]), celda(s["total_txt"],
                                                                                                orden=s["total"] or 0),
                          celda(s["estado"], pildora=color_estado(s["estado"])), celda(s["referencia"], C["suave"])])
        llenar_tabla(t, filas)
        lay.addWidget(t, 1)
        return w

    def _licencias(self) -> QWidget:
        w, lay = self._contenedor()
        if not self.p["licencias"]:
            lay.addWidget(EstadoVacio("🔑", "Sin licencias", "Esta persona no tiene claves de licencia.",
                                      "🎁  Dar licencia" if "lemonsqueezy" in self.v.clientes else ""), 1)
            vacio = lay.itemAt(0).widget()
            if vacio.boton:
                vacio.boton.clicked.connect(lambda: (self.accept(),
                                                     self.v.dar_licencia(self.p["nombre"], self.p["correo"])))
            return w
        self.t_lic = tabla(["Clave", "Plataforma", "Estado", "Equipos", "Uso", "Última vez", "Vence"],
                           [300, 130, 120, 80, 100, 120], pildoras=(1, 2))
        filas = []
        for lic in self.p["licencias"]:
            est = estado_licencia(lic)
            pl = PLATAFORMAS[lic["plataforma"]]
            equipos = len(self.v.modelo["por_licencia"].get(lic["id"], [])) or lic.get("equipos_tel") or 0
            filas.append([celda(priv_clave(lic.get("key")), dato=lic["id"], mono=True),
                          celda(pl["nombre"], pildora=pl["color"]), celda(est, pildora=color_estado(est)),
                          celda(equipos, orden=equipos), celda(duracion(lic["uso_seg"]), orden=lic["uso_seg"]),
                          celda(hace(lic["ultima_vez"]), orden=lic["ultima_vez"] or ""),
                          celda(fmt_fecha(lic.get("expires_at"), False) if lic.get("expires_at") else "Nunca")])
        llenar_tabla(self.t_lic, filas)
        lay.addWidget(self.t_lic, 1)
        ver = boton("Abrir en Licencias")
        ver.clicked.connect(self._ver_licencia)
        copiar_b = boton("Copiar clave")
        copiar_b.clicked.connect(lambda: (lic := self._lic_sel()) and (copiar(lic["key"]),
                                                                       Toast.mostrar(self, "Clave copiada", "", "ok")))
        lay.addLayout(fila(ver, copiar_b, None))
        return w

    def _lic_sel(self) -> dict | None:
        from interfaz import dato_seleccionado
        id_ = dato_seleccionado(self.t_lic) if hasattr(self, "t_lic") else None
        return self.v.modelo["lic_por_id"].get(id_) or (self.p["licencias"][0] if self.p["licencias"] else None)

    def _ver_licencia(self):
        lic = self._lic_sel()
        if lic:
            self.accept()
            self.v.ver_licencia(lic["id"])

    def _equipos(self) -> QWidget:
        w, lay = self._contenedor()
        hashes = {l["hash"] for l in self.p["licencias"]}
        tel = [e for e in self.v.modelo["equipos_tel"] if e.get("licencia") in hashes]
        tienda = [i for l in self.p["licencias"] for i in self.v.modelo["por_licencia"].get(l["id"], [])]
        t = tabla(["Equipo", "ID de equipo", "Estado", "Última vez", "Tiempo de uso", "Sesiones", "Versión", "Sistema"],
                  [170, 170, 110, 120, 110, 80, 80], pildoras=(2,))
        filas, vistos = [], set()
        for e in tel:
            vistos.add(e.get("equipo"))
            estado = "En línea" if e["en_linea"] else "Desconectado"
            filas.append([celda(priv_nombre(e.get("nombre_equipo")) or "—", dato=e.get("equipo"), negrita=True),
                          celda(e.get("equipo"), C["suave"], mono=True),
                          celda(estado, pildora=C["ok"] if e["en_linea"] else C["tenue"]),
                          celda(hace(e.get("ultima_vez")), orden=e.get("ultima_vez") or ""),
                          celda(duracion(e.get("segundos_uso")), orden=int(e.get("segundos_uso") or 0)),
                          celda(e.get("sesiones") or 0, orden=int(e.get("sesiones") or 0)),
                          celda(e.get("version_app")), celda(e.get("so"))])
        for i in tienda:
            pc, equipo = partir_instancia(i.get("name", ""))
            if equipo and equipo in vistos:
                continue
            filas.append([celda(priv_nombre(pc or i.get("name")), dato=i["id"], negrita=True),
                          celda(equipo or "—", C["suave"], mono=True),
                          celda("Sin datos de uso", pildora=C["tenue"]), celda(hace(i.get("created_at"))), celda("—"),
                          celda("—"), celda("—"), celda("—")])
        llenar_tabla(t, filas)
        if not filas:
            lay.addWidget(EstadoVacio("💻", "Sin equipos", "Cuando active el programa, sus equipos y su tiempo de uso "
                                                         "aparecerán aquí." + ("" if self.v.servidor() else
                                                                               " (Conecta el servidor de control para "
                                                                               "ver el tiempo de uso.)")), 1)
            return w
        lay.addWidget(t, 1)
        if self.v.modelo["control"]:
            uso = [0.0] * 30
            for u in (self.v.resultados.get("control") or {}).get("uso") or []:
                if u.get("licencia") in hashes:
                    try:
                        d = 29 - (datetime.now().date() - datetime.fromisoformat(str(u["dia"])).date()).days
                    except (KeyError, ValueError):
                        continue
                    if 0 <= d < 30:
                        uso[d] += int(u.get("segundos") or 0) / 3600
            g = GraficoBarras(unidad=" h", sin_datos="Sin uso")
            g.setMinimumHeight(150)
            g.fijar(self.v.modelo["dias"], {"uso": [round(x, 2) for x in uso]}, {"uso": C["acento"]},
                    {"uso": "Horas de uso"})
            lay.addWidget(tarjeta(etiqueta("Horas de uso por día (30 días)", "tituloTarjeta"), g))
        return w

    def _avisos(self) -> QWidget:
        w, lay = self._contenedor()
        hashes = {l["hash"] for l in self.p["licencias"]}
        avisos = [a for a in self.v.modelo["avisos"] if a.get("licencia") in hashes]
        if not self.v.servidor():
            lay.addWidget(EstadoVacio("📡", "Conecta el servidor de control",
                                      "Con el servidor puedes enviar avisos que tu cliente ve al abrir el programa."), 1)
            return w
        t = tabla(["Fecha", "Tipo", "Título", "Leído", "Fecha límite"], [140, 140, 300, 90], pildoras=(1,))
        colores = {"info": C["info"], "advertencia": C["aviso"], "remocion": C["error"], "reactivada": C["ok"],
                   "bloqueo": C["error"]}
        llenar_tabla(t, [[celda(fmt_fecha(a.get("creado")), dato=a.get("id"), orden=a.get("creado") or ""),
                          celda(TIPOS_AVISO.get(a.get("tipo"), a.get("tipo")), pildora=colores.get(a.get("tipo"))),
                          celda(a.get("titulo"), negrita=True),
                          celda("✓ Sí" if a["leidos"] else "Aún no", C["ok"] if a["leidos"] else C["tenue"]),
                          celda(fmt_fecha(a.get("fecha_limite"), False) if a.get("fecha_limite") else "—")]
                         for a in avisos])
        if avisos:
            lay.addWidget(t, 1)
        else:
            lay.addWidget(EstadoVacio("📣", "Sin avisos", "Todavía no le has enviado avisos a esta persona."), 1)
        nuevo = boton("📣  Enviar aviso", "primario")
        nuevo.setEnabled(bool(self.p["licencias"]))
        nuevo.clicked.connect(lambda: self.v.nuevo_aviso(persona=self.clave))
        remover = boton("⚠  Avisar que será removida", "peligro")
        remover.setEnabled(bool(self.p["licencias"]))
        remover.clicked.connect(lambda: self.v.nuevo_aviso(persona=self.clave, tipo="remocion"))
        lay.addLayout(fila(nuevo, remover, None))
        return w

    def _notas(self) -> QWidget:
        w, lay = self._contenedor()
        cfg = self.v.cfg
        self.notas = QPlainTextEdit(cfg["notas"].get(self.clave, ""))
        self.notas.setPlaceholderText("Notas privadas sobre esta persona (solo se guardan en esta computadora).")
        self.etiquetas = QLineEdit(", ".join(cfg["etiquetas"].get(self.clave, [])),
                                   placeholderText="Etiquetas separadas por coma: vip, soporte, revisar…")
        self.telefono = QLineEdit(cfg["telefonos"].get(self.clave, ""),
                                  placeholderText="WhatsApp con código de país, ej. 50255551234")
        if self.telefono.text():
            self.telefono.setToolTip(priv_tel(self.telefono.text()))
        form = formulario()
        form.addRow("Etiquetas", self.etiquetas)
        form.addRow("WhatsApp", self.telefono)
        lay.addLayout(form)
        lay.addWidget(self.notas, 1)
        guardar = boton("Guardar notas", "primario")
        guardar.clicked.connect(self._guardar_notas)
        self.guardado = etiqueta("", "tenue")
        lay.addLayout(fila(self.guardado, None, guardar))
        return w

    def _guardar_notas(self):
        cfg = self.v.cfg
        texto = self.notas.toPlainText().strip()
        etiquetas = [t.strip().lstrip("#") for t in self.etiquetas.text().split(",") if t.strip()]
        for clave_cfg, valor in (("notas", texto), ("etiquetas", etiquetas)):
            if valor:
                cfg[clave_cfg][self.clave] = valor
            else:
                cfg[clave_cfg].pop(self.clave, None)
        if solo_digitos(self.telefono.text()):
            cfg["telefonos"][self.clave] = solo_digitos(self.telefono.text())
        self.v.guardar()
        self.guardado.setText(f"✓ Guardado a las {datetime.now().strftime('%H:%M')}")
        fundido(self.guardado, 0.2, 1.0, 300)
        self.v.pintar(forzar=True)

    def reject(self):
        if hasattr(self, "notas") and self.notas.toPlainText().strip() != self.v.cfg["notas"].get(self.clave, ""):
            self._guardar_notas()
        super().reject()

