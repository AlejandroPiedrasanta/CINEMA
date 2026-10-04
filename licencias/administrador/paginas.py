"""Cinema Productions · Administrador de Licencias — páginas del panel.

Inicio, Personas, Licencias, Equipos, Ventas, Uso, Avisos, Actividad, Conexiones y Ajustes.

Creado por Cinema Productions.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

import interfaz as ui
from control import ESTADOS_SERVIDOR, TIPOS_AVISO
from dialogos import caja_codigo, copiar
from interfaz import (C, Aurora, BloqueCarga, Chips, ContadorAnimado, EstadoVacio, GraficoBarras, GraficoDona,
                      Interruptor, PanelDeslizante, Pila, TarjetaKPI, TarjetaTema, boton, celda, color_estado,
                      dato_seleccionado, elevar_al_pasar, entrada_escalonada, estilo_pildora, etiqueta, fila,
                      fuente_mono, fundido, insignia_icono, legible, llenar_tabla, logo_cinema, pildora, priv_clave,
                      priv_correo, priv_nombre, tabla, tarjeta)
from modelo import (APP_TITULO, ESCALAS, INTERVALOS, MARCA, VELOCIDADES, VERSION, datos_para_programa, duracion,
                    estado_licencia, fmt_fecha, hace, nombre_plataforma, partir_instancia, texto_config_programa)
from plataformas import PLATAFORMAS, dinero
from temas import DENSIDADES, ESP_LG, ESP_MD, ESP_SM, TEMAS

__author__ = "Cinema Productions"

(P_INICIO, P_PERSONAS, P_LICENCIAS, P_EQUIPOS, P_VENTAS, P_USO, P_AVISOS, P_ACTIVIDAD, P_CONEXIONES,
 P_AJUSTES) = range(10)

EVENTOS = {
    "venta": ("Nueva venta", "ok"), "reembolso": ("Reembolso", "error"), "activacion": ("Activación", "info"),
    "desactivacion": ("Equipo desactivado", "aviso"), "licencia_perdida": ("Licencia perdida en el programa", "error"),
    "reactivada": ("Licencia reactivada", "ok"), "auto": ("Control automático", "acento"),
}
COLOR_AVISO = {"info": "info", "advertencia": "aviso", "remocion": "error", "reactivada": "ok", "bloqueo": "error"}


def _vaciar(lay):
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _vaciar(item.layout())


def _desplazable(contenido: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(contenido)
    return area


class Pagina(QWidget):
    titulo = ""
    subtitulo = ""
    icono = ""

    def __init__(self, ventana):
        super().__init__(objectName="pagina")
        self.v = ventana
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(14)

    def pintar(self, m: dict):
        pass

    def al_mostrar(self):
        pass


def sin_servidor(v, texto: str) -> EstadoVacio:
    vacio = EstadoVacio("📡", "Conecta el servidor de control", texto, "Conectar servidor")
    vacio.boton.clicked.connect(v.conectar_servidor)
    return vacio


# ============================================================ inicio

class PaginaInicio(Pagina):
    titulo = "Inicio"
    subtitulo = "Así va tu programa hoy."
    icono = "🏠"

    def __init__(self, v):
        super().__init__(v)
        self.pila = Pila()
        self.pila.addWidget(self._heroe())
        self.pila.addWidget(self._panel())
        self.pila.addWidget(self._cargando())
        self.lay.addWidget(self.pila)
        self._anim_pendiente = True

    def _heroe(self) -> QWidget:
        w = QWidget(objectName="pagina")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        heroe = Aurora()
        h = QVBoxLayout(heroe)
        h.setContentsMargins(36, 30, 36, 30)
        h.setSpacing(10)
        marca = QLabel()
        marca.setPixmap(logo_cinema(14, C["suave"]))
        h.addWidget(marca)
        h.addWidget(etiqueta("👋  ¡Bienvenido a tu panel de licencias!", "heroeTitulo"))
        h.addWidget(etiqueta("Conecta la plataforma donde vendes tu programa para ver quién lo tiene, sus "
                             "licencias, equipos, ventas y cuánto lo usa — todo en un solo lugar.", "nota",
                             ajustar=True))
        h.addSpacing(10)
        tarjetas = QGridLayout()
        tarjetas.setSpacing(14)
        self.cajas_heroe = []
        for n, (clave, p) in enumerate(PLATAFORMAS.items()):
            caja = QFrame(objectName="plataforma")
            c = QHBoxLayout(caja)
            c.setContentsMargins(18, 16, 18, 16)
            c.setSpacing(14)
            c.addWidget(insignia_icono(p["icono"], p["color"], 48))
            textos = QVBoxLayout()
            textos.setSpacing(2)
            textos.addWidget(etiqueta(p["nombre"], "tituloTarjeta"))
            textos.addWidget(etiqueta(p["descripcion"], "nota", ajustar=True))
            c.addLayout(textos, 1)
            b = boton("Conectar", "primario")
            b.clicked.connect(lambda _=False, k=clave: self.v.conectar(k))
            c.addWidget(b)
            elevar_al_pasar(caja, p["color"])
            tarjetas.addWidget(caja, n // 2, n % 2)
            self.cajas_heroe.append(caja)
        h.addLayout(tarjetas)
        servidor = boton("📡  Conectar el servidor de control (avisos, bloqueos y tiempo de uso)", "enlace")
        servidor.clicked.connect(self.v.conectar_servidor)
        h.addWidget(servidor, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(heroe)
        lay.addStretch()
        return w

    def _cargando(self) -> QWidget:
        """Esqueleto con brillo mientras llegan los primeros datos."""
        w = QWidget(objectName="pagina")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        for _ in range(5):
            kpis.addWidget(BloqueCarga(118))
        lay.addLayout(kpis)
        abajo = QHBoxLayout()
        abajo.setSpacing(14)
        abajo.addWidget(BloqueCarga(0), 3)
        abajo.addWidget(BloqueCarga(0), 2)
        lay.addLayout(abajo, 1)
        return w

    def animar_entrada(self):
        """Las tarjetas suben a su sitio una tras otra."""
        if self.pila.currentIndex() == 1 and self.isVisible():
            QTimer.singleShot(0, lambda: entrada_escalonada([k for k in self.kpis if k.isVisible()]))
        elif self.pila.currentIndex() == 0 and self.isVisible():
            QTimer.singleShot(0, lambda: entrada_escalonada(self.cajas_heroe, 18, 80))

    def al_mostrar(self):
        self.animar_entrada()

    def _panel(self) -> QWidget:
        w = QWidget(objectName="pagina")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        fila_kpis = QHBoxLayout()
        fila_kpis.setSpacing(12)
        self.k_personas = TarjetaKPI("Personas con el programa", C["acento"], ayuda="Compradores únicos con acceso")
        self.k_licencias = TarjetaKPI("Licencias activas", C["ok"], ayuda="Lemon Squeezy, Gumroad y Polar")
        self.k_equipos = TarjetaKPI("Equipos activados", C["info"], ayuda="PCs con tu programa")
        self.k_ventas = TarjetaKPI("Ventas · 30 días", C["aviso"], ayuda="Todas las plataformas")
        self.k_ingresos = TarjetaKPI("Ingresos · 30 días", C["ok"], ayuda="")
        self.k_activos = TarjetaKPI("Usando hoy", C["oro"], ayuda="Personas que abrieron el programa")
        self.kpis = [self.k_personas, self.k_licencias, self.k_equipos, self.k_ventas, self.k_ingresos, self.k_activos]
        for k in self.kpis:
            fila_kpis.addWidget(k)
        lay.addLayout(fila_kpis)

        self.grafico = GraficoBarras()
        self.leyenda = etiqueta("", "tenue")
        self.leyenda.setTextFormat(Qt.TextFormat.RichText)
        graf = tarjeta(fila(etiqueta("Ventas de los últimos 30 días", "tituloTarjeta"), None, self.leyenda),
                       self.grafico)
        graf.layout().setStretch(1, 1)
        self.dona = GraficoDona(132, "licencias")
        self.dona_leyenda = etiqueta("", "tenue", ajustar=True)
        self.dona_leyenda.setTextFormat(Qt.TextFormat.RichText)
        dona = tarjeta(etiqueta("Licencias por estado", "tituloTarjeta"), fila(self.dona, self.dona_leyenda,
                                                                              espacio=14))
        self.actividad = QVBoxLayout()
        self.actividad.setSpacing(2)
        ver = boton("Ver toda la actividad  →", "enlace")
        ver.clicked.connect(lambda: self.v.ir_a(P_ACTIVIDAD))
        act = tarjeta(etiqueta("Actividad reciente", "tituloTarjeta"), self.actividad, ver)
        act.layout().addStretch()
        derecha = QVBoxLayout()
        derecha.setSpacing(14)
        derecha.addWidget(dona)
        derecha.addWidget(act, 1)
        abajo = QHBoxLayout()
        abajo.setSpacing(14)
        abajo.addWidget(graf, 3)
        abajo.addLayout(derecha, 2)
        lay.addLayout(abajo, 1)
        return w

    def pintar(self, m: dict):
        if not self.v.clientes:
            if self.pila.currentIndex() != 0:
                self.pila.setCurrentIndex(0)
                self.animar_entrada()
            return
        if not self.v.resultados:          # conectado, pero aún sin datos: esqueleto con brillo
            self.pila.setCurrentIndex(2)
            self._anim_pendiente = True
            return
        self.pila.setCurrentIndex(1)
        if self._anim_pendiente:
            self._anim_pendiente = False
            self.animar_entrada()
        self.k_personas.valor.fijar(sum(1 for p in m["personas"] if p["tiene"]))
        self.k_licencias.valor.fijar(sum(1 for l in m["licencias"] if l.get("status") == "active"))
        self.k_equipos.valor.fijar(max(len(m["instancias"]), len(m["equipos_tel"])))
        self.k_ventas.valor.fijar(m["ventas_30"])
        ingresos = sorted(m["ingresos_30"].items(), key=lambda x: -x[1])
        moneda, total = ingresos[0] if ingresos else ("", 0.0)
        self.k_ingresos.valor.formato = lambda v, mo=moneda: f"{v:,.0f} {mo}".strip()
        self.k_ingresos.valor.fijar(total)
        self.k_ingresos.sub.setText("+ " + ", ".join(dinero(v, mo) for mo, v in ingresos[1:]) if len(ingresos) > 1
                                    else "Ventas válidas")
        self.k_activos.setVisible(m["control"])
        self.k_activos.valor.fijar(m["activos_hoy"])
        self.k_activos.sub.setText(f"{m['en_linea']} en línea ahora · {m['activos_7']} en 7 días")
        conectadas = list(m["serie"])
        self.grafico.fijar(m["dias"], m["serie"], {k: PLATAFORMAS[k]["color"] for k in conectadas},
                           {k: PLATAFORMAS[k]["nombre"] for k in conectadas})
        self.leyenda.setText("   ".join(f"<span style='color:{PLATAFORMAS[k]['color']}'>●</span> "
                                        f"{PLATAFORMAS[k]['nombre']}" for k in conectadas))
        cuenta: dict[str, int] = {}
        for l in m["licencias"]:
            est = estado_licencia(l)
            cuenta[est] = cuenta.get(est, 0) + 1
        partes = [(e, n, color_estado(e)) for e, n in sorted(cuenta.items(), key=lambda x: -x[1])]
        self.dona.fijar(partes)
        self.dona_leyenda.setText("<br>".join(f"<span style='color:{c}'>●</span> {e}: <b>{n}</b>"
                                              for e, n, c in partes[:6]) or "Sin licencias todavía")
        _vaciar(self.actividad)
        eventos = self.v.eventos()[:6]
        if not eventos:
            self.actividad.addWidget(etiqueta("Aún no hay movimientos. Las ventas y activaciones aparecerán aquí.",
                                              "tenue", ajustar=True))
        for e in eventos:
            nombre, token = EVENTOS.get(e["tipo"], EVENTOS["auto"])
            linea = etiqueta(f"<span style='color:{C[token]}; font-size:16px'>●</span>&nbsp; <b>{nombre}</b> · "
                             f"{priv_nombre(e['persona']) or '—'}<br><span style='color:{C['tenue']}'>"
                             f"{e['detalle']} · {hace(e['fecha'])}</span>", ajustar=True)
            linea.setTextFormat(Qt.TextFormat.RichText)
            linea.setStyleSheet("padding:4px 2px;")
            self.actividad.addWidget(linea)


# ============================================================ personas

class PaginaPersonas(Pagina):
    titulo = "Personas"
    subtitulo = "Quién tiene tu programa, cuánto lo usa y en qué plataformas compró."
    icono = "👥"

    def __init__(self, v):
        super().__init__(v)
        self.total = ContadorAnimado()
        self.total.setStyleSheet(f"font-size:34px; font-weight:800; color:{legible(C['acento'])};")
        self.total_txt = etiqueta("personas tienen tu programa", "nota")
        self.desglose = etiqueta("", "tenue")
        self.desglose.setTextFormat(Qt.TextFormat.RichText)
        cab = QVBoxLayout()
        cab.setSpacing(0)
        cab.addWidget(self.total_txt)
        cab.addWidget(self.desglose)
        self.exportar = boton("⭳  CSV", tip="Guarda la lista de personas en un archivo para Excel.")
        self.exportar.clicked.connect(lambda: self.v.exportar_csv("personas"))
        self.chips = Chips([("todas", "Todas"), ("con", "Con el programa"), ("sin", "Sin acceso"),
                            ("reembolsos", "Reembolsos"), ("activos", "Activos 7 días"), ("linea", "En línea")])
        self.chips.cambiado.connect(lambda _: self.pintar(self.v.modelo))
        self.plataforma = QComboBox()
        self.plataforma.addItem("Todas las plataformas", "")
        for k, p in PLATAFORMAS.items():
            self.plataforma.addItem(f"{p['icono']}  {p['nombre']}", k)
        self.plataforma.currentIndexChanged.connect(lambda _: self.pintar(self.v.modelo))
        self.b_ficha = boton("👤  Ver ficha", "primario", "Compras, licencias, equipos, tiempo de uso, avisos y notas.")
        self.b_ficha.clicked.connect(lambda: (p := self.sel()) and self.v.ver_persona(p["clave"]))
        self.b_wa = boton("WhatsApp", "whatsapp")
        self.b_wa.clicked.connect(lambda: (p := self.sel()) and self.v.whatsapp_persona(p))
        self.b_aviso = boton("📣  Aviso", tip="Mensaje que verá al abrir el programa.")
        self.b_aviso.clicked.connect(lambda: (p := self.sel()) and self.v.nuevo_aviso(persona=p["clave"]))
        self.b_dar = boton("🎁  Dar licencia", tip="Crea una licencia gratis en Lemon Squeezy para esta persona.")
        self.b_dar.clicked.connect(lambda: (p := self.sel()) and self.v.dar_licencia(p["nombre"], p["correo"]))
        self.lay.addWidget(tarjeta(fila(self.total, cab, None, self.b_ficha, self.b_wa, self.b_aviso, self.b_dar,
                                        self.exportar, espacio=10), margen=16))
        self.lay.addLayout(fila(self.chips, None, self.plataforma))
        self.t = tabla(["Persona", "Correo", "Plataforma", "Estado", "Compras", "Licencia", "Equipos", "Tiempo de uso",
                        "Última vez", "Última compra"], [180, 210, 150, 150, 72, 130, 72, 110, 110], pildoras=(3, 5))
        self.t.itemSelectionChanged.connect(self._botones)
        self.t.itemDoubleClicked.connect(lambda *_: (p := self.sel()) and self.v.ver_persona(p["clave"]))
        self.vacio = EstadoVacio("👥", "Aún no hay personas", "Cuando alguien compre tu programa aparecerá aquí.")
        self.lay.addWidget(self.t, 1)
        self.lay.addWidget(self.vacio, 1)
        self._botones()

    def sel(self) -> dict | None:
        return self.v.modelo["persona_por_clave"].get(dato_seleccionado(self.t))

    def _botones(self):
        p = self.sel()
        self.b_ficha.setEnabled(p is not None)
        self.b_wa.setEnabled(p is not None)
        self.b_aviso.setEnabled(bool(p and p["licencias"]) and self.v.servidor() is not None)
        self.b_dar.setEnabled(p is not None and "lemonsqueezy" in self.v.clientes)

    def pintar(self, m: dict):
        personas = m["personas"]
        con = [p for p in personas if p["tiene"]]
        self.total.fijar(len(con))
        por = {k: sum(1 for p in con if k in p["plataformas"]) for k in PLATAFORMAS if k in self.v.clientes}
        self.desglose.setText("   ".join(f"<span style='color:{PLATAFORMAS[k]['color']}'>●</span> "
                                         f"{PLATAFORMAS[k]['nombre']}: <b>{n}</b>" for k, n in por.items())
                              + f"   ·   {len(personas)} en total")
        filtro, plat = self.chips.actual(), self.plataforma.currentData()
        filas = []
        for p in personas:
            if (filtro == "con" and not p["tiene"]) or (filtro == "sin" and p["tiene"]):
                continue
            if filtro == "reembolsos" and not p["reembolsos"]:
                continue
            if filtro == "activos" and not (p["ultima_vez"] and hace(p["ultima_vez"]) and
                                            _dias_desde(p["ultima_vez"]) <= 7):
                continue
            if filtro == "linea" and not p["en_linea"]:
                continue
            if plat and plat not in p["plataformas"]:
                continue
            etiquetas = " ".join(self.v.cfg["etiquetas"].get(p["clave"], []))
            if not self.v.coincide(p["nombre"], p["correo"], etiquetas, self.v.cfg["notas"].get(p["clave"], "")):
                continue
            lic = p["licencias"][0] if p["licencias"] else None
            est_lic = estado_licencia(lic) if lic else ""
            color = C["ok"] if p["tiene"] else (C["error"] if p["estado"] == "Reembolsada" else C["tenue"])
            nombre = priv_nombre(p["nombre"]) + (f"   #{etiquetas.replace(' ', ' #')}" if etiquetas else "")
            filas.append([
                celda(nombre, dato=p["clave"], negrita=True),
                celda(priv_correo(p["correo"])),
                celda("  ".join(nombre_plataforma(k) for k in sorted(p["plataformas"]))),
                celda(p["estado"], pildora=color),
                celda(p["compras"], orden=p["compras"]),
                celda(est_lic or "Sin licencia", pildora=color_estado(est_lic) if lic else C["tenue"]),
                celda(max(p["equipos"], p["equipos_tel"]) or "—", orden=max(p["equipos"], p["equipos_tel"])),
                celda(duracion(p["uso_seg"]), orden=p["uso_seg"]),
                celda("En línea" if p["en_linea"] else hace(p["ultima_vez"]), C["ok"] if p["en_linea"] else None,
                      orden=p["ultima_vez"] or ""),
                celda(fmt_fecha(p["ultima"], hora=False), orden=p["ultima"] or ""),
            ])
        llenar_tabla(self.t, filas)
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        self._botones()


def _dias_desde(iso: str | None) -> float:
    from modelo import a_fecha
    from datetime import datetime, timezone
    f = a_fecha(iso)
    return (datetime.now(timezone.utc) - f).total_seconds() / 86400 if f else 9999


# ============================================================ licencias

class PaginaLicencias(Pagina):
    titulo = "Licencias"
    subtitulo = "Claves de Lemon Squeezy, Gumroad y Polar: bloquea, edita, envía avisos o libera equipos."
    icono = "🔑"

    def __init__(self, v):
        super().__init__(v)
        self.sin_ls = EstadoVacio("🔑", "Las licencias funcionan con Lemon Squeezy, Gumroad o Polar",
                                  "Conecta la plataforma que genera las claves de tu programa para verlas y "
                                  "controlarlas aquí.", "Conectar plataforma")
        self.sin_ls.boton.clicked.connect(lambda: self.v.conectar())
        self.contenido = QWidget(objectName="pagina")
        c = QVBoxLayout(self.contenido)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(12)
        self.chips = Chips([("todas", "Todas"), ("active", "Activas"), ("inactive", "Sin activar"),
                            ("disabled", "Bloqueadas"), ("expired", "Vencidas"), ("refunded", "Reembolsadas"),
                            ("revoked", "Revocadas"), ("servidor", "Suspendidas")])
        self.chips.cambiado.connect(lambda _: self.pintar(self.v.modelo))
        self.nuevo = boton("＋  Enlace de compra", "primario",
                           "Enlace de pago (o de regalo) de Lemon Squeezy. Al completarlo, el cliente recibe su clave.")
        self.nuevo.clicked.connect(lambda: self.v.nueva_venta())
        c.addLayout(fila(self.chips, None, self.nuevo))
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(0)
        self.t = tabla(["Cliente", "Plataforma", "Estado", "Clave", "Equipos / usos", "Uso", "Comprada", "Vence",
                        "Correo"], [160, 130, 120, 310, 100, 90, 100, 90], pildoras=(1, 2))
        self.t.itemSelectionChanged.connect(self._seleccion)
        self.vacio = EstadoVacio("🔑", "Sin licencias todavía", "Cuando alguien compre tu programa, su clave aparecerá "
                                                               "aquí.", "Crear enlace de compra")
        self.vacio.boton.clicked.connect(lambda: self.v.nueva_venta())
        izquierda = QVBoxLayout()
        izquierda.addWidget(self.t)
        izquierda.addWidget(self.vacio)
        cuerpo.addLayout(izquierda, 1)
        self.panel = PanelDeslizante(390)
        self.panel_lay = QVBoxLayout(self.panel)
        self.panel_lay.setContentsMargins(20, 16, 20, 16)
        self.panel_lay.setSpacing(10)
        cuerpo.addSpacing(12)
        cuerpo.addWidget(self.panel)
        c.addLayout(cuerpo, 1)
        self.lay.addWidget(self.sin_ls, 1)
        self.lay.addWidget(self.contenido, 1)
        self._lic_panel = None
        self.lbl_usos: QLabel | None = None

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
        nombre = etiqueta(priv_nombre(lic.get("user_name")) or priv_correo(lic.get("user_email")) or "—",
                          "tituloTarjeta", ajustar=True)
        nombre.setStyleSheet("font-size:18px;")
        self.panel_lay.addLayout(fila(nombre, None, cerrar))
        self.panel_lay.addWidget(etiqueta(priv_correo(lic.get("user_email")) or "", "nota"))
        p = PLATAFORMAS[lic["plataforma"]]
        pills = [pildora(f"●  {est}" + ("  ·  prueba" if lic.get("test_mode") else ""), color_estado(est)),
                 pildora(f"{p['icono']} {p['nombre']}", p["color"])]
        if lic.get("en_linea"):
            pills.append(pildora("●  En línea", C["ok"]))
        self.panel_lay.addLayout(fila(*pills, None))
        clave = etiqueta(priv_clave(lic.get("key", "")), "codigo", ajustar=True)
        clave.setFont(fuente_mono(10.5, True))
        clave.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.panel_lay.addWidget(clave)
        if lic.get("reembolsada"):
            banda = etiqueta("⚠  La compra de esta licencia fue reembolsada.", ajustar=True)
            banda.setStyleSheet(f"color:{legible(C['error'])}; font-weight:600;")
            self.panel_lay.addWidget(banda)
        {"gumroad": self._panel_gumroad, "polar": self._panel_polar}.get(lic["plataforma"], self._panel_ls)(lic)
        fundido(self.panel, 0.4, 1.0, 220)

    def _datos(self, pares):
        datos = QGridLayout()
        datos.setVerticalSpacing(4)
        etiquetas = []
        for i, (t, valor) in enumerate(pares):
            datos.addWidget(etiqueta(t.upper(), "kpiTitulo"), (i // 2) * 2, i % 2)
            e = etiqueta(valor)
            etiquetas.append(e)
            datos.addWidget(e, (i // 2) * 2 + 1, i % 2)
        self.panel_lay.addLayout(datos)
        return etiquetas

    def _uso(self, lic: dict):
        """Tiempo de uso y estado en el programa (servidor de control)."""
        if not self.v.servidor():
            return
        self.panel_lay.addWidget(QFrame(objectName="separador"))
        srv = lic.get("estado_srv") or "activa"
        self._datos((("Tiempo de uso", duracion(lic.get("uso_seg"))),
                     ("Última vez", "En línea ahora" if lic.get("en_linea") else hace(lic.get("ultima_vez"))),
                     ("En el programa", ESTADOS_SERVIDOR.get(srv, srv)), ("Equipos con datos", str(lic.get("equipos_tel")
                                                                                                   or 0))))
        aviso = boton("📣  Aviso", tip="Mensaje que verá al abrir el programa.")
        aviso.clicked.connect(lambda: self.v.nuevo_aviso(lic=lic["id"]))
        if srv == "activa":
            estado = boton("⏸  Suspender en el programa", "peligro",
                           "El programa del cliente se cierra y pide licencia (sin tocar la tienda).")
            estado.clicked.connect(lambda: self.v.fijar_estado_programa(lic, "suspendida"))
        else:
            estado = boton("▶  Reactivar en el programa", tip="El programa vuelve a funcionar solo.")
            estado.clicked.connect(lambda: self.v.fijar_estado_programa(lic, "activa"))
        self.panel_lay.addLayout(fila(aviso, estado, None))

    def _botones_envio(self, lic: dict):
        b_copiar = boton("Copiar", tip="Copiar la clave")
        b_copiar.clicked.connect(lambda: (copiar(lic["key"]),
                                          self.v.aviso("Clave copiada", priv_nombre(lic.get("user_name", "")), "ok")))
        wa = boton("WhatsApp", "whatsapp")
        wa.clicked.connect(lambda: self.v.enviar_clave_whatsapp(lic))
        correo = boton("Correo")
        correo.setEnabled(bool(lic.get("user_email")))
        correo.clicked.connect(lambda: self.v.enviar_clave_correo(lic))
        ficha = boton("👤", tip="Ficha de la persona")
        ficha.clicked.connect(lambda: lic.get("persona") and self.v.ver_persona(lic["persona"]))
        self.panel_lay.addLayout(fila(b_copiar, wa, correo, ficha))

    def _equipos(self, lic: dict, titulo="Equipos activados"):
        self.panel_lay.addWidget(QFrame(objectName="separador"))
        self.panel_lay.addWidget(etiqueta(titulo, "tituloTarjeta"))
        equipos = self.v.modelo["por_licencia"].get(lic["id"], [])
        if not equipos:
            self.panel_lay.addWidget(etiqueta("Todavía no la ha activado en ningún equipo." if
                                              lic.get("instances_count") is not None else
                                              "Los equipos se cargan cuando abres la licencia.", "tenue", ajustar=True))
        for ins in equipos[:6]:
            pc, equipo = partir_instancia(ins.get("name", ""))
            txt = etiqueta(f"💻  <b>{priv_nombre(pc or ins.get('name')) or 'Equipo'}</b><br>"
                           f"<span style='color:{C['tenue']}'>{equipo or ''}<br>{hace(ins.get('created_at'))}</span>",
                           ajustar=True)
            txt.setTextFormat(Qt.TextFormat.RichText)
            quitar = boton("Quitar", "peligro", "Desactiva esta computadora y libera un equipo de la licencia.")
            quitar.clicked.connect(lambda _=False, i=ins: self.v.quitar_equipo(lic, i))
            self.panel_lay.addLayout(fila(txt, None, quitar))
        if len(equipos) > 6:
            self.panel_lay.addWidget(etiqueta(f"y {len(equipos) - 6} más (ver en Equipos)", "tenue"))

    def _acciones(self, lic: dict, editar: bool = True):
        self.panel_lay.addStretch()
        self._botones_envio(lic)
        botones = []
        if editar:
            b = boton("✏️  Editar", tip="Equipos permitidos y fecha de vencimiento")
            b.clicked.connect(lambda: self.v.editar_licencia(lic))
            botones.append(b)
        bloqueada = lic.get("disabled")
        self.b_bloquear = boton("Desbloquear" if bloqueada else "Bloquear", "secundario" if bloqueada else "peligro")
        self.b_bloquear.clicked.connect(lambda: self.v.alternar_bloqueo(lic))
        botones.append(self.b_bloquear)
        return botones

    def _panel_ls(self, lic: dict):
        limite = lic.get("activation_limit")
        pedido = (self.v.modelo["venta_por_pedido"].get(f"ls-{lic.get('order_id')}") or {}).get("referencia", "—")
        self._datos((("Equipos", f"{lic.get('instances_count', 0)} de {limite or '∞'}"),
                     ("Vence", fmt_fecha(lic.get("expires_at"), False) if lic.get("expires_at") else "Nunca"),
                     ("Comprada", fmt_fecha(lic.get("created_at"), False)), ("Pedido", pedido)))
        self._uso(lic)
        self._equipos(lic)
        self.panel_lay.addLayout(fila(*self._acciones(lic), None))

    def _panel_polar(self, lic: dict):
        limite = lic.get("activation_limit")
        usados = lic.get("instances_count")
        self._datos((("Equipos", f"{'—' if usados is None else usados} de {limite or '∞'}"),
                     ("Vence", fmt_fecha(lic.get("expires_at"), False) if lic.get("expires_at") else "Nunca"),
                     ("Validaciones", str(lic.get("validaciones") or 0)),
                     ("Última validación", hace(lic.get("ultima_validacion")))))
        self._uso(lic)
        self._equipos(lic, "Activaciones (equipos)")
        self.panel_lay.addLayout(fila(*self._acciones(lic), None))

    def _panel_gumroad(self, lic: dict):
        venta = self.v.modelo["venta_por_pedido"].get(lic.get("venta_id")) or {}
        usos = self.v.usos_gumroad.get(lic["key"])
        self.lbl_usos = self._datos((("Usos", "Consultando…" if usos is None else f"{usos}"), ("Vence", "Nunca"),
                                     ("Comprada", fmt_fecha(lic.get("created_at"), False)),
                                     ("Pedido", venta.get("referencia") or "—")))[0]
        self._uso(lic)
        self.panel_lay.addWidget(QFrame(objectName="separador"))
        self.panel_lay.addWidget(etiqueta("Usos de la clave", "tituloTarjeta"))
        self.panel_lay.addWidget(etiqueta("Gumroad no registra equipos: cuenta cuántas veces se activó la clave. "
                                          "«Liberar un uso» permite activarla en otra computadora.", "tenue",
                                          ajustar=True))
        liberar = boton("↺  Liberar un uso", tip="Resta un uso para que pueda activarla en otra computadora.")
        liberar.clicked.connect(lambda: self.v.liberar_uso_gumroad(lic))
        self.panel_lay.addLayout(fila(*self._acciones(lic, editar=False), liberar, None))
        id_ = lic["id"]
        self.v.consultar_gumroad(lic, lambda info: self._usos_listos(id_, info))

    def _usos_listos(self, id_, info: dict):
        if self._lic_panel != id_ or self.lbl_usos is None:
            return
        try:
            if info.get("error"):
                self.lbl_usos.setText("No disponible")
                self.lbl_usos.setToolTip(info["error"])
            elif info.get("bloqueada"):
                self.lbl_usos.setText("— (bloqueada)")
            else:
                self.lbl_usos.setText(f"{info.get('usos') or 0}")
            fundido(self.lbl_usos, 0.2, 1.0, 300)
        except RuntimeError:   # el panel se volvió a construir mientras tanto
            pass

    def pintar(self, m: dict):
        conectado = any(k in self.v.clientes for k in ("lemonsqueezy", "gumroad", "polar"))
        self.sin_ls.setVisible(not conectado)
        self.contenido.setVisible(conectado)
        self.nuevo.setVisible("lemonsqueezy" in self.v.clientes)
        self.vacio.boton.setVisible("lemonsqueezy" in self.v.clientes)
        if not conectado:
            return
        estados = ("active", "inactive", "disabled", "expired", "refunded", "revoked")
        cuenta = {k: sum(1 for l in m["licencias"] if l.get("status") == k) for k in estados}
        suspendidas = sum(1 for l in m["licencias"] if l.get("estado_srv") != "activa")
        self.chips.texto("todas", f"Todas  {len(m['licencias'])}")
        for k, t in zip(estados, ("Activas", "Sin activar", "Bloqueadas", "Vencidas", "Reembolsadas", "Revocadas")):
            self.chips.texto(k, f"{t}  {cuenta[k]}")
        self.chips.texto("servidor", f"Suspendidas  {suspendidas}")
        filtro = self.chips.actual()
        filas = []
        for lic in m["licencias"]:
            if filtro == "servidor":
                if lic.get("estado_srv") == "activa":
                    continue
            elif filtro != "todas" and lic.get("status") != filtro:
                continue
            nombres = [i.get("name") for i in m["por_licencia"].get(lic["id"], [])]
            if not self.v.coincide(lic.get("user_name"), lic.get("user_email"), lic.get("key"), *nombres):
                continue
            est = estado_licencia(lic)
            p = PLATAFORMAS[lic["plataforma"]]
            if lic["plataforma"] == "gumroad":
                usos = self.v.usos_gumroad.get(lic["key"])
                equipos = "—" if usos is None else f"{usos} usos"
            else:
                n = lic.get("instances_count")
                equipos = f"{'—' if n is None else n} / {lic.get('activation_limit') or '∞'}"
            filas.append([
                celda(priv_nombre(lic.get("user_name")) or priv_correo(lic.get("user_email")), dato=lic["id"],
                      negrita=True),
                celda(p["nombre"], pildora=p["color"]),
                celda(est, pildora=color_estado(est)),
                celda(priv_clave(lic.get("key")), C["suave"], mono=True),
                celda(equipos),
                celda(duracion(lic.get("uso_seg")), orden=lic.get("uso_seg") or 0),
                celda(fmt_fecha(lic.get("created_at"), False), orden=lic.get("created_at") or ""),
                celda(fmt_fecha(lic.get("expires_at"), False) if lic.get("expires_at") else "Nunca",
                      C["aviso"] if est == "Vencida" else None, orden=lic.get("expires_at") or "9999"),
                celda(priv_correo(lic.get("user_email"))),
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


# ============================================================ equipos

class PaginaEquipos(Pagina):
    titulo = "Equipos"
    subtitulo = "Computadoras donde se activó tu programa y cuánto lo usan."
    icono = "💻"

    def __init__(self, v):
        super().__init__(v)
        self.b_ver = boton("Ver licencia")
        self.b_ver.clicked.connect(lambda: (f := self.sel()) and f.get("lic_id") and self.v.ver_licencia(f["lic_id"]))
        self.b_persona = boton("👤  Persona")
        self.b_persona.clicked.connect(self._persona)
        self.b_copiar = boton("Copiar ID")
        self.b_copiar.clicked.connect(lambda: (f := self.sel()) and (copiar(f["equipo"]),
                                                                     self.v.aviso("ID copiado", f["equipo"], "ok")))
        self.b_quitar = boton("Quitar equipo", "peligro", "Desactiva esta computadora y libera un equipo de la licencia.")
        self.b_quitar.clicked.connect(self._quitar)
        self.resumen = etiqueta("Cada fila es una computadora con una licencia activada.", "nota")
        self.lay.addLayout(fila(self.resumen, None, self.b_ver, self.b_persona, self.b_copiar, self.b_quitar))
        self.t = tabla(["Equipo", "ID de equipo", "Licencia de", "Plataforma", "Licencia", "Última vez",
                        "Tiempo de uso", "Versión", "Sistema", "Activado"],
                       [170, 170, 160, 120, 120, 110, 100, 70, 130], pildoras=(3, 4))
        self.t.itemSelectionChanged.connect(self._botones)
        self.vacio = EstadoVacio("💻", "Ningún equipo activado",
                                 "Cuando un cliente active su licencia, su computadora aparecerá aquí.")
        self.lay.addWidget(self.t, 1)
        self.lay.addWidget(self.vacio, 1)
        self.filas: dict[str, dict] = {}
        self._botones()

    def sel(self) -> dict | None:
        return self.filas.get(dato_seleccionado(self.t))

    def _botones(self):
        f = self.sel()
        self.b_ver.setEnabled(bool(f and f.get("lic_id")))
        self.b_persona.setEnabled(bool(f and f.get("lic_id")))
        self.b_copiar.setEnabled(bool(f and f.get("equipo")))
        self.b_quitar.setEnabled(bool(f and f.get("instancia")))

    def _persona(self):
        f = self.sel()
        lic = self.v.modelo["lic_por_id"].get(f.get("lic_id")) if f else None
        if lic and lic.get("persona"):
            self.v.ver_persona(lic["persona"])

    def _quitar(self):
        f = self.sel()
        lic = self.v.modelo["lic_por_id"].get(f.get("lic_id")) if f else None
        if f and lic and f.get("instancia"):
            self.v.quitar_equipo(lic, f["instancia"])

    def pintar(self, m: dict):
        self.filas = {}
        tel_por = {(e.get("lic_id"), e.get("equipo")): e for e in m["equipos_tel"]}
        usados = set()
        for ins in m["instancias"]:
            pc, equipo = partir_instancia(ins.get("name", ""))
            e = tel_por.get((ins["license_key_id"], equipo))
            if e:
                usados.add((ins["license_key_id"], equipo))
            self.filas[ins["id"]] = {"id": ins["id"], "nombre": pc or ins.get("name"), "equipo": equipo,
                                     "lic_id": ins["license_key_id"], "instancia": ins, "tel": e,
                                     "creado": ins.get("created_at"), "plataforma": ins.get("plataforma")}
        for e in m["equipos_tel"]:
            if (e.get("lic_id"), e.get("equipo")) in usados:
                continue
            lic = m["lic_por_id"].get(e.get("lic_id")) or {}
            self.filas[f"tel-{e.get('licencia')}-{e.get('equipo')}"] = {
                "id": f"tel-{e.get('licencia')}-{e.get('equipo')}", "nombre": e.get("nombre_equipo"),
                "equipo": e.get("equipo"), "lic_id": e.get("lic_id"), "instancia": None, "tel": e,
                "creado": e.get("primera_vez"), "plataforma": lic.get("plataforma") or e.get("tienda")}
        filas, en_linea = [], 0
        for f in self.filas.values():
            lic = m["lic_por_id"].get(f["lic_id"]) or {}
            if not self.v.coincide(f["nombre"], f["equipo"], lic.get("user_name"), lic.get("user_email"),
                                   lic.get("key")):
                continue
            e = f["tel"] or {}
            en_linea += bool(e.get("en_linea"))
            est = estado_licencia(lic) if lic else "Desconocida"
            p = PLATAFORMAS.get(f["plataforma"] or "", {"nombre": f["plataforma"] or "—", "color": C["tenue"]})
            filas.append([
                celda(("● " if e.get("en_linea") else "") + (priv_nombre(f["nombre"]) or "Equipo"), dato=f["id"],
                      negrita=True, color=C["ok"] if e.get("en_linea") else None),
                celda(f["equipo"], C["suave"], mono=True),
                celda(priv_nombre(lic.get("user_name")) or priv_correo(lic.get("user_email"))),
                celda(p["nombre"], pildora=p["color"]),
                celda(est, pildora=color_estado(est)),
                celda("En línea" if e.get("en_linea") else hace(e.get("ultima_vez")) if e else "—",
                      orden=e.get("ultima_vez") or ""),
                celda(duracion(e.get("segundos_uso")), orden=int(e.get("segundos_uso") or 0)),
                celda(e.get("version_app")), celda(e.get("so")),
                celda(fmt_fecha(f["creado"]), orden=f["creado"] or ""),
            ])
        llenar_tabla(self.t, filas)
        self.resumen.setText(f"{len(filas)} equipos" + (f" · {en_linea} en línea ahora" if m["control"] else
                                                        " · conecta el servidor de control para ver el uso"))
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        if not any(k in self.v.clientes for k in ("lemonsqueezy", "polar", "control")):
            self.vacio.titulo.setText("Los equipos se ven con Lemon Squeezy, Polar o el servidor de control")
            self.vacio.texto.setText("Conecta una de ellos para ver en qué computadoras se activó tu programa.")
        self._botones()


# ============================================================ ventas

class PaginaVentas(Pagina):
    titulo = "Ventas"
    subtitulo = "Todas tus ventas de Lemon Squeezy, Hotmart, Gumroad y Polar."
    icono = "🛒"

    def __init__(self, v):
        super().__init__(v)
        self.chips = Chips([("todas", "Todas")] + [(k, f"{p['icono']} {p['nombre']}") for k, p in PLATAFORMAS.items()]
                           + [("reembolsos", "Reembolsos")])
        self.chips.cambiado.connect(lambda _: self.pintar(self.v.modelo))
        self.b_recibo = boton("Recibo")
        self.b_recibo.clicked.connect(lambda: (s := self.sel()) and self.v.abrir_url(s["recibo"]))
        self.b_persona = boton("👤  Persona")
        self.b_persona.clicked.connect(lambda: (s := self.sel()) and self.v.ver_persona(
            (s["correo"] or "").strip().lower() or "nombre:" + (s["cliente"] or "?").strip().lower()))
        self.b_dar = boton("🎁  Dar licencia", tip="Crea una licencia gratis en Lemon Squeezy para este comprador.")
        self.b_dar.clicked.connect(lambda: (s := self.sel()) and self.v.dar_licencia(s["cliente"], s["correo"]))
        self.b_lic = boton("Ver licencia", tip="Abre la clave de licencia de esta venta.")
        self.b_lic.clicked.connect(lambda: (s := self.sel()) and self.v.ver_licencia(f"lic-{s['id']}"))
        exportar = boton("⭳  CSV", tip="Exporta las ventas para Excel.")
        exportar.clicked.connect(lambda: self.v.exportar_csv("ventas"))
        self.resumen = etiqueta("", "nota")
        self.lay.addLayout(fila(self.chips, None))
        self.lay.addLayout(fila(self.resumen, None, self.b_recibo, self.b_persona, self.b_lic, self.b_dar, exportar))
        self.t = tabla(["Fecha", "Plataforma", "Cliente", "Correo", "Producto", "Total", "Estado", "Referencia"],
                       [140, 140, 170, 210, 210, 100, 150], pildoras=(1, 6))
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
        self.b_persona.setEnabled(s is not None)
        self.b_dar.setEnabled(bool(s) and "lemonsqueezy" in self.v.clientes)
        self.b_lic.setEnabled(bool(s and s.get("clave_licencia")))

    def pintar(self, m: dict):
        filtro = self.chips.actual()
        filas, validas, total = [], 0, {}
        for s in m["ventas"]:
            if filtro in PLATAFORMAS and s["plataforma"] != filtro:
                continue
            if filtro == "reembolsos" and s["estado"] not in ("Reembolsada", "Contracargo", "Reembolso parcial",
                                                               "En disputa"):
                continue
            if not self.v.coincide(s["cliente"], s["correo"], s["producto"], s["referencia"]):
                continue
            validas += s["valida"]
            if s["valida"] and s["total"] is not None:
                total[s["moneda"]] = total.get(s["moneda"], 0) + s["total"]
            p = PLATAFORMAS[s["plataforma"]]
            filas.append([
                celda(fmt_fecha(s["fecha"]), dato=s["id"], orden=s["fecha"] or ""),
                celda(p["nombre"], pildora=p["color"]),
                celda(priv_nombre(s["cliente"]), negrita=True), celda(priv_correo(s["correo"])), celda(s["producto"]),
                celda(s["total_txt"], orden=s["total"] or 0),
                celda(s["estado"] + ("  · prueba" if s["prueba"] else ""), pildora=color_estado(s["estado"])),
                celda(s["referencia"], C["suave"]),
            ])
        llenar_tabla(self.t, filas)
        suma = "  ·  ".join(dinero(v, mo) for mo, v in sorted(total.items(), key=lambda x: -x[1]))
        self.resumen.setText(f"{len(filas)} ventas · {validas} válidas" + (f" · {suma}" if suma else ""))
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        self._botones()


# ============================================================ uso (telemetría)

class PaginaUso(Pagina):
    titulo = "Uso"
    subtitulo = "Cuánto y cuándo usan tu programa tus clientes (servidor de control)."
    icono = "📈"

    def __init__(self, v):
        super().__init__(v)
        self.vacio_srv = sin_servidor(v, "Con el servidor de control verás quién está usando tu programa ahora, "
                                         "cuántas horas lo usa cada persona, sus equipos y versiones.")
        self.contenido = QWidget(objectName="pagina")
        c = QVBoxLayout(self.contenido)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(14)
        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        self.k_linea = TarjetaKPI("En línea ahora", C["ok"], ayuda="Último aviso hace menos de 12 min")
        self.k_hoy = TarjetaKPI("Activos hoy", C["acento"], ayuda="Licencias que abrieron el programa")
        self.k_7 = TarjetaKPI("Activos 7 días", C["info"], ayuda="Licencias distintas")
        self.k_horas = TarjetaKPI("Horas de uso · 30 días", C["oro"], formato=lambda v: f"{v:,.1f}")
        self.k_prom = TarjetaKPI("Promedio por licencia", C["aviso"], formato=lambda v: f"{v:,.1f} h",
                                 ayuda="Horas en 30 días")
        self.kpis = [self.k_linea, self.k_hoy, self.k_7, self.k_horas, self.k_prom]
        for k in self.kpis:
            kpis.addWidget(k)
        c.addLayout(kpis)
        self.chips = Chips([("personas", "Personas activas"), ("horas", "Horas de uso")])
        self.chips.cambiado.connect(lambda _: self._grafico(self.v.modelo))
        self.grafico = GraficoBarras(sin_datos="Sin uso")
        graf = tarjeta(fila(etiqueta("Últimos 30 días", "tituloTarjeta"), None, self.chips), self.grafico)
        graf.layout().setStretch(1, 1)
        self.dona = GraficoDona(132, "equipos")
        self.dona_leyenda = etiqueta("", "tenue", ajustar=True)
        self.dona_leyenda.setTextFormat(Qt.TextFormat.RichText)
        versiones = tarjeta(etiqueta("Versiones en uso", "tituloTarjeta"), fila(self.dona, self.dona_leyenda,
                                                                                espacio=14))
        arriba = QHBoxLayout()
        arriba.setSpacing(14)
        arriba.addWidget(graf, 3)
        arriba.addWidget(versiones, 2)
        c.addLayout(arriba)
        self.b_persona = boton("👤  Ver persona")
        self.b_persona.clicked.connect(self._persona)
        self.b_aviso = boton("📣  Aviso")
        self.b_aviso.clicked.connect(lambda: (e := self.sel()) and e.get("lic_id") and
                                     self.v.nuevo_aviso(lic=e["lic_id"]))
        c.addLayout(fila(etiqueta("Equipos con tu programa", "tituloTarjeta"), None, self.b_persona, self.b_aviso))
        self.t = tabla(["Persona", "Equipo", "Estado", "Tiempo de uso", "Sesiones", "Versión", "Sistema", "Tienda",
                        "Desde"], [170, 170, 120, 110, 80, 80, 150, 110], pildoras=(2,))
        self.t.setMinimumHeight(220)
        self.t.itemSelectionChanged.connect(self._botones)
        c.addWidget(self.t, 1)
        self.lay.addWidget(self.vacio_srv, 1)
        self.lay.addWidget(self.contenido, 1)
        self.filas: dict = {}
        self._botones()

    def sel(self):
        return self.filas.get(dato_seleccionado(self.t))

    def _botones(self):
        e = self.sel()
        self.b_persona.setEnabled(bool(e and e.get("lic_id")))
        self.b_aviso.setEnabled(bool(e and e.get("lic_id")))

    def _persona(self):
        e = self.sel()
        lic = self.v.modelo["lic_por_id"].get(e.get("lic_id")) if e else None
        if lic and lic.get("persona"):
            self.v.ver_persona(lic["persona"])

    def al_mostrar(self):
        if self.contenido.isVisible():
            QTimer.singleShot(0, lambda: entrada_escalonada(self.kpis))

    def _grafico(self, m: dict):
        if self.chips.actual() == "horas":
            self.grafico.unidad = " h"
            self.grafico.fijar(m["dias"], {"h": m["horas_dia"]}, {"h": C["oro"]}, {"h": "Horas de uso"})
        else:
            self.grafico.unidad = ""
            self.grafico.fijar(m["dias"], {"p": [float(x) for x in m["activos_dia"]]}, {"p": C["acento"]},
                               {"p": "Licencias activas"})

    def pintar(self, m: dict):
        con = m["control"]
        self.vacio_srv.setVisible(not con)
        self.contenido.setVisible(con)
        if not con:
            return
        self.k_linea.valor.fijar(m["en_linea"])
        self.k_hoy.valor.fijar(m["activos_hoy"])
        self.k_7.valor.fijar(m["activos_7"])
        self.k_horas.valor.fijar(m["horas_30"])
        activos30 = len({e.get("licencia") for e in m["equipos_tel"]})
        self.k_prom.valor.fijar(m["horas_30"] / activos30 if activos30 else 0)
        self._grafico(m)
        versiones: dict[str, int] = {}
        for e in m["equipos_tel"]:
            versiones[e.get("version_app") or "?"] = versiones.get(e.get("version_app") or "?", 0) + 1
        colores = [C["acento"], C["info"], C["ok"], C["aviso"], C["oro"], C["acento2"], C["error"], C["suave"]]
        partes = [(f"v{ver}", n, colores[i % len(colores)])
                  for i, (ver, n) in enumerate(sorted(versiones.items(), key=lambda x: -x[1]))]
        self.dona.fijar(partes)
        self.dona_leyenda.setText("<br>".join(f"<span style='color:{c}'>●</span> {n}: <b>{v}</b>"
                                              for n, v, c in partes[:6]) or "Sin datos todavía")
        self.filas, filas = {}, []
        for e in m["equipos_tel"]:
            lic = m["lic_por_id"].get(e.get("lic_id")) or {}
            persona = lic.get("user_name") or lic.get("user_email") or "Licencia desconocida"
            if not self.v.coincide(persona, lic.get("user_email"), e.get("nombre_equipo"), e.get("equipo")):
                continue
            clave = f"{e.get('licencia')}-{e.get('equipo')}"
            self.filas[clave] = e
            filas.append([
                celda(priv_nombre(persona), dato=clave, negrita=True),
                celda(priv_nombre(e.get("nombre_equipo")) or e.get("equipo")),
                celda("En línea" if e["en_linea"] else hace(e.get("ultima_vez")),
                      pildora=C["ok"] if e["en_linea"] else C["tenue"], orden=e.get("ultima_vez") or ""),
                celda(duracion(e.get("segundos_uso")), orden=int(e.get("segundos_uso") or 0)),
                celda(e.get("sesiones") or 0, orden=int(e.get("sesiones") or 0)),
                celda(e.get("version_app")), celda(e.get("so")), celda(nombre_plataforma(e.get("tienda") or "")),
                celda(fmt_fecha(e.get("primera_vez"), False), orden=e.get("primera_vez") or ""),
            ])
        llenar_tabla(self.t, filas)
        self._botones()


# ============================================================ avisos

class PaginaAvisos(Pagina):
    titulo = "Avisos"
    subtitulo = "Mensajes que tus clientes ven al abrir el programa. También bloqueos programados."
    icono = "📣"

    def __init__(self, v):
        super().__init__(v)
        self.vacio_srv = sin_servidor(v, "Con el servidor de control puedes avisar a una persona o a todas (por "
                                         "ejemplo: «tu licencia será removida»), y ver quién ya lo leyó.")
        self.contenido = QWidget(objectName="pagina")
        c = QVBoxLayout(self.contenido)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(12)
        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        self.k_enviados = TarjetaKPI("Avisos enviados", C["acento"])
        self.k_leidos = TarjetaKPI("Leídos", C["ok"], ayuda="Avisos que ya vio al menos un equipo")
        self.k_remociones = TarjetaKPI("Bloqueos programados", C["error"], ayuda="Se aplican en su fecha límite")
        self.k_suspendidas = TarjetaKPI("Licencias suspendidas", C["aviso"], ayuda="Desde el servidor de control")
        for k in (self.k_enviados, self.k_leidos, self.k_remociones, self.k_suspendidas):
            kpis.addWidget(k)
        c.addLayout(kpis)
        nuevo = boton("📣  Nuevo aviso", "primario")
        nuevo.clicked.connect(lambda: self.v.nuevo_aviso())
        todos = boton("📢  Aviso a todos", tip="Lo verán todas las licencias de tu programa.")
        todos.clicked.connect(lambda: self.v.nuevo_aviso(todos=True))
        self.b_borrar = boton("Borrar aviso", "peligro", "Deja de mostrarse a quienes aún no lo leyeron.")
        self.b_borrar.clicked.connect(lambda: (a := dato_seleccionado(self.t)) is not None and self.v.borrar_aviso(a))
        self.b_cancelar = boton("Cancelar bloqueo programado")
        self.b_cancelar.clicked.connect(self._cancelar_bloqueo)
        c.addLayout(fila(nuevo, todos, None, self.b_cancelar, self.b_borrar))
        self.t = tabla(["Enviado", "Tipo", "Para", "Título", "Leído por", "Fecha límite", "Bloqueo"],
                       [140, 140, 180, 300, 90, 110], pildoras=(1,))
        self.t.itemSelectionChanged.connect(self._botones)
        self.vacio = EstadoVacio("📣", "Aún no has enviado avisos",
                                 "Escribe a un cliente o a todos. Lo verán en una ventana al abrir el programa.")
        c.addWidget(self.t, 1)
        c.addWidget(self.vacio, 1)
        self.lay.addWidget(self.vacio_srv, 1)
        self.lay.addWidget(self.contenido, 1)
        self._botones()

    def _botones(self):
        a = dato_seleccionado(self.t)
        self.b_borrar.setEnabled(a is not None)
        self.b_cancelar.setEnabled(a is not None and str(a) in self.v.cfg["remociones"])

    def _cancelar_bloqueo(self):
        a = dato_seleccionado(self.t)
        if a is not None and self.v.cfg["remociones"].pop(str(a), None):
            self.v.guardar()
            self.v.aviso("Bloqueo programado cancelado", "", "ok")
            self.v.pintar(forzar=True)

    def pintar(self, m: dict):
        con = m["control"]
        self.vacio_srv.setVisible(not con)
        self.contenido.setVisible(con)
        if not con:
            return
        avisos = m["avisos"]
        self.k_enviados.valor.fijar(len(avisos))
        self.k_leidos.valor.fijar(sum(1 for a in avisos if a["leidos"]))
        self.k_remociones.valor.fijar(len(self.v.cfg["remociones"]))
        self.k_suspendidas.valor.fijar(sum(1 for e in m["estados_srv"].values() if e.get("estado") != "activa"))
        filas = []
        for a in avisos:
            para = priv_nombre(a["persona"]) if a.get("licencia") else "Todas las licencias"
            if a.get("licencia") and not a["persona"]:
                para = "Licencia desconocida"
            if not self.v.coincide(para, a.get("titulo"), a.get("mensaje"), a["persona"]):
                continue
            programado = self.v.cfg["remociones"].get(str(a.get("id")))
            filas.append([
                celda(fmt_fecha(a.get("creado")), dato=a.get("id"), orden=a.get("creado") or ""),
                celda(TIPOS_AVISO.get(a.get("tipo"), a.get("tipo")), pildora=C[COLOR_AVISO.get(a.get("tipo"), "info")]),
                celda(para, negrita=True), celda(a.get("titulo"), tip=a.get("mensaje") or ""),
                celda(f"{a['leidos']} equipo{'s' if a['leidos'] != 1 else ''}" if a["leidos"] else "Nadie aún",
                      C["ok"] if a["leidos"] else C["tenue"], orden=a["leidos"]),
                celda(fmt_fecha(a.get("fecha_limite"), False) if a.get("fecha_limite") else "—",
                      orden=a.get("fecha_limite") or ""),
                celda("⏰ Programado" if programado else "—", C["error"] if programado else None),
            ])
        llenar_tabla(self.t, filas)
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        self._botones()


# ============================================================ actividad

class PaginaActividad(Pagina):
    titulo = "Actividad"
    subtitulo = "Ventas, reembolsos, activaciones, equipos desactivados y lo que pasa en el programa."
    icono = "⚡"

    def __init__(self, v):
        super().__init__(v)
        self.chips = Chips([("todo", "Todo"), ("venta", "Ventas"), ("reembolso", "Reembolsos"),
                            ("activacion", "Activaciones"), ("programa", "En el programa"), ("auto", "Automático")])
        self.chips.cambiado.connect(lambda _: self.pintar(self.v.modelo))
        self.lay.addWidget(self.chips)
        self.t = tabla(["Fecha", "Evento", "Plataforma", "Persona", "Detalle"], [150, 230, 160, 200], pildoras=(1,))
        self.vacio = EstadoVacio("⚡", "Sin actividad", "Aquí verás cada venta y activación en cuanto ocurra.")
        self.lay.addWidget(self.t, 1)
        self.lay.addWidget(self.vacio, 1)

    def pintar(self, m: dict):
        filtro = self.chips.actual()
        filas = []
        for e in self.v.eventos():
            if filtro == "programa" and e["tipo"] not in ("licencia_perdida", "reactivada") \
                    and not e.get("desde_programa"):
                continue
            if filtro not in ("todo", "programa") and e["tipo"] != filtro:
                continue
            if not self.v.coincide(e["persona"], e["detalle"]):
                continue
            nombre, token = EVENTOS.get(e["tipo"], EVENTOS["auto"])
            filas.append([celda(fmt_fecha(e["fecha"]), dato=str(e["clave"]), orden=e["fecha"] or ""),
                          celda(nombre, pildora=C[token]),
                          celda(nombre_plataforma(e["plataforma"]) if e["plataforma"] else "📡 Programa"),
                          celda(priv_nombre(e["persona"]), negrita=True), celda(e["detalle"])])
        llenar_tabla(self.t, filas)
        self.t.setVisible(bool(filas))
        self.vacio.setVisible(not filas)


# ============================================================ conexiones

class PaginaConexiones(Pagina):
    titulo = "Conexiones"
    subtitulo = "Tus plataformas de venta, el servidor de control y los datos para tu programa."
    icono = "🔌"

    def __init__(self, v):
        super().__init__(v)
        cont = QWidget(objectName="pagina")
        self.c = QVBoxLayout(cont)
        self.c.setContentsMargins(0, 0, 8, 0)
        self.c.setSpacing(14)
        self.lay.addWidget(_desplazable(cont))
        self.tarjetas = QGridLayout()
        self.tarjetas.setSpacing(14)
        self.c.addLayout(self.tarjetas)
        self.cajas: dict[str, dict] = {}
        entradas = list(PLATAFORMAS.items()) + [("control", {"nombre": "Servidor de control", "icono": "📡",
                                                            "color": C["acento"],
                                                            "descripcion": "Avisos, bloqueos al instante y tiempo de "
                                                                           "uso de tu programa (Supabase)."})]
        for n, (clave, p) in enumerate(entradas):
            caja = QFrame(objectName="plataforma")
            l = QVBoxLayout(caja)
            l.setContentsMargins(20, 18, 20, 18)
            l.setSpacing(8)
            estado = pildora()
            l.addLayout(fila(insignia_icono(p["icono"], p["color"], 44), etiqueta(p["nombre"], "tituloTarjeta"), None,
                             estado))
            l.addWidget(etiqueta(p["descripcion"], "nota", ajustar=True))
            detalle = etiqueta("", "tenue", ajustar=True)
            detalle.setTextFormat(Qt.TextFormat.RichText)
            l.addWidget(detalle)
            l.addStretch()
            conectar = boton("Conectar", "primario")
            info = boton("Información")
            quitar = boton("Desconectar", "peligro")
            if clave == "control":
                conectar.clicked.connect(self.v.conectar_servidor)
                info.clicked.connect(self.v.conectar_servidor)
                quitar.clicked.connect(self.v.desconectar_servidor)
            else:
                conectar.clicked.connect(lambda _=False, k=clave: self.v.conectar(k))
                info.clicked.connect(lambda _=False, k=clave: self.v.ver_informacion(k))
                quitar.clicked.connect(lambda _=False, k=clave: self.v.desconectar(k))
            l.addLayout(fila(conectar, info, None, quitar))
            elevar_al_pasar(caja, p["color"])
            self.tarjetas.addWidget(caja, n // 2, n % 2, 1, 2 if clave == "control" else 1)
            self.cajas[clave] = {"estado": estado, "detalle": detalle, "conectar": conectar, "info": info,
                                 "quitar": quitar}

        self.codigo, cod = caja_codigo()
        guardar = boton("💾  Guardar archivo…", "primario", "Guarda cinema_licencias.json para copiarlo junto a tu "
                                                           "programa.")
        guardar.clicked.connect(self.v.guardar_config_programa)
        lineas = boton("Copiar líneas para licencia_cliente.py",
                       tip="Para programas que usan la forma de la versión 4.")
        lineas.clicked.connect(self._copiar_lineas)
        ayuda = etiqueta("Copia la carpeta <b>cinema_licencias</b> junto a tu programa y guarda este archivo como "
                         "<b>cinema_licencias.json</b>. Solo lleva datos públicos: nunca tus API keys.", "nota",
                         ajustar=True)
        ayuda.setTextFormat(Qt.TextFormat.RichText)
        self.caja_codigo = tarjeta(etiqueta("Datos para tu programa", "tituloTarjeta"), ayuda, cod,
                                   fila(guardar, lineas, None))
        self.c.addWidget(self.caja_codigo)
        self.c.addStretch()

    def _copiar_lineas(self):
        pl = self.v.cfg["plataformas"]
        copiar(datos_para_programa(pl.get("lemonsqueezy") or {}, pl.get("gumroad") or {}, pl.get("polar") or {},
                                   self.v.cfg.get("servidor") or {}))
        self.v.aviso("Copiado", "Pégalo en la sección CONFIGURACIÓN de licencia_cliente.py", "ok")

    def pintar(self, m: dict):
        for clave, caja in self.cajas.items():
            pc = (self.v.cfg.get("servidor") if clave == "control" else self.v.cfg["plataformas"].get(clave)) or {}
            conectado = clave in self.v.clientes
            error = self.v.errores.get(clave)
            color = C["error"] if error else (C["ok"] if conectado else C["tenue"])
            texto = "Con error" if error else ("Conectado" if conectado else "No conectado")
            estilo_pildora(caja["estado"], f"●  {texto}", color)
            det = ""
            if conectado and clave == "lemonsqueezy":
                det = (f"Cuenta: <b>{priv_nombre(pc.get('cuenta')) or '—'}</b><br>Tienda: "
                       f"<b>{pc.get('tienda_nombre') or '—'}</b> (ID {pc.get('tienda_id')})<br>Producto: "
                       f"<b>{pc.get('producto_nombre') or 'Todos'}</b>")
            elif conectado and clave == "gumroad":
                det = (f"Cuenta: <b>{priv_nombre(pc.get('cuenta')) or '—'}</b><br>Producto: <b>"
                       f"{pc.get('producto_nombre') or 'Todos'}</b><br>Claves bloqueadas: "
                       f"<b>{len(pc.get('bloqueadas') or [])}</b>")
            elif conectado and clave == "hotmart":
                det = (f"Entorno: <b>{pc.get('entorno') or ('Sandbox' if pc.get('sandbox') else 'Producción')}</b>"
                       f"<br>Credencial: <b>{(pc.get('client_id') or '')[:8]}…</b><br>"
                       f"Producto: <b>{pc.get('producto_nombre') or 'Todos'}</b>")
            elif conectado and clave == "polar":
                det = (f"Organización: <b>{pc.get('organizacion') or '—'}</b>"
                       f"{' (sandbox)' if pc.get('sandbox') else ''}<br>Producto: "
                       f"<b>{pc.get('producto_nombre') or 'Todos'}</b><br>Beneficio de claves: "
                       f"<b>{'elegido' if pc.get('beneficio_id') else 'todos'}</b>")
            elif conectado and clave == "control":
                det = (f"Proyecto: <b>{pc.get('url', '').replace('https://', '')}</b><br>Equipos con datos: "
                       f"<b>{len(m['equipos_tel'])}</b>  ·  Avisos: <b>{len(m['avisos'])}</b>")
            if error:
                det += f"<br><span style='color:{C['error']}'>⚠ {error}</span>"
            caja["detalle"].setText(det)
            nombre = "el servidor" if clave == "control" else PLATAFORMAS[clave]["nombre"]
            caja["conectar"].setText("Cambiar credenciales" if conectado else f"Conectar {nombre}")
            caja["conectar"].setObjectName("secundario" if conectado else "primario")
            caja["conectar"].style().unpolish(caja["conectar"])
            caja["conectar"].style().polish(caja["conectar"])
            caja["info"].setVisible(conectado and clave != "control")
            caja["quitar"].setVisible(conectado)
        try:
            self.codigo.setText(texto_config_programa(self.v.cfg))
        except ValueError as e:
            self.codigo.setText(f"⚠ {e}")


# ============================================================ ajustes

class PaginaAjustes(Pagina):
    titulo = "Ajustes"
    subtitulo = "Apariencia, tamaño, privacidad, control automático y más."
    icono = "⚙️"

    def __init__(self, v):
        super().__init__(v)
        cfg = v.cfg
        cont = QWidget(objectName="pagina")
        c = QVBoxLayout(cont)
        c.setContentsMargins(0, 0, 8, ESP_LG)
        c.setSpacing(ESP_MD)
        self.lay.addWidget(_desplazable(cont))

        # ---- apariencia
        temas = QGridLayout()
        temas.setSpacing(12)
        self.tarjetas_tema: dict[str, TarjetaTema] = {}
        for i, (clave, t) in enumerate(TEMAS.items()):
            tt = TarjetaTema(clave, t)
            tt.clic.connect(self.v.cambiar_tema)
            tt.elegir(clave == cfg.get("tema"))
            self.tarjetas_tema[clave] = tt
            temas.addWidget(tt, i // 3, i % 3)
        temas.setColumnStretch(3, 1)
        self.escala = QComboBox()
        for texto, valor in ESCALAS:
            self.escala.addItem(texto, valor)
        self.escala.setCurrentIndex(max(0, self.escala.findData(cfg.get("escala", 1.0))))
        self.escala.currentIndexChanged.connect(self._escala)
        self.reiniciar = boton("Reiniciar para aplicar", "primario")
        self.reiniciar.setVisible(False)
        self.reiniciar.clicked.connect(self.v.reiniciar)
        self.densidad = QComboBox()
        for clave, alto in DENSIDADES.items():
            self.densidad.addItem(f"{clave.capitalize()}  ({alto} px)", clave)
        self.densidad.setCurrentIndex(max(0, self.densidad.findData(cfg.get("densidad", "normal"))))
        self.densidad.currentIndexChanged.connect(lambda: self._guardar("densidad", self.densidad.currentData()))
        self.animar = Interruptor("Animaciones")
        self.animar.setChecked(cfg.get("animaciones", True))
        self.animar.toggled.connect(lambda v: self._guardar("animaciones", v))
        self.velocidad = QComboBox()
        for texto, valor in VELOCIDADES:
            self.velocidad.addItem(texto, valor)
        self.velocidad.setCurrentIndex(max(0, self.velocidad.findData(cfg.get("velocidad", 1.0))))
        self.velocidad.currentIndexChanged.connect(lambda: self._guardar("velocidad", self.velocidad.currentData()))
        f = self._form()
        f.addRow("Tamaño de la interfaz", fila(self.escala, self.reiniciar, None))
        f.addRow("Altura de las filas", fila(self.densidad, None))
        f.addRow("Animaciones", fila(self.animar, self.velocidad, None))
        c.addWidget(self._seccion("🎨  Apariencia", "Elige un estilo. El cambio se aplica al instante.", temas, f))

        # ---- privacidad
        self.privado = Interruptor("Modo privado (ocultar datos en la interfaz)")
        self.privado.setChecked(cfg.get("privacidad", False))
        self.privado.toggled.connect(lambda val: self.v.fijar_privacidad(val))
        self.ocultar = {}
        f = self._form()
        f.addRow("", self.privado)
        for que, texto, ejemplo in (("nombres", "Ocultar nombres", "Juan Pérez → J••• P••••"),
                                    ("correos", "Ocultar correos", "juan@gmail.com → j•••@g••••.com"),
                                    ("claves", "Ocultar claves de licencia", "ABCD-…-9F3A → ••••-••••-9F3A")):
            interruptor = Interruptor(texto)
            interruptor.setChecked(cfg.get(f"privacidad_{que}", True))
            interruptor.toggled.connect(lambda val, q=que: self._guardar(f"privacidad_{q}", val, repintar=True))
            self.ocultar[que] = interruptor
            f.addRow("", fila(interruptor, etiqueta(ejemplo, "nota"), None))
        c.addWidget(self._seccion("🙈  Privacidad", "Ideal para grabar la pantalla o compartir capturas. Activa el modo "
                                  "privado y elige qué ocultar: nombres, correos y claves de licencia. También con el "
                                  "botón del ojo arriba (Ctrl+Mayús+P).", f))

        # ---- notificaciones
        self.intervalo = QComboBox()
        for texto, seg in INTERVALOS:
            self.intervalo.addItem(texto, seg)
        self.intervalo.setCurrentIndex(max(0, self.intervalo.findData(cfg.get("intervalo", 30))))
        self.intervalo.currentIndexChanged.connect(lambda: self._guardar("intervalo", self.intervalo.currentData()))
        self.notificar = Interruptor("Notificaciones de escritorio (ventas, reembolsos, activaciones)")
        self.notificar.setChecked(cfg.get("notificaciones", True))
        self.notificar.toggled.connect(lambda val: self._guardar("notificaciones", val))
        self.bandeja = Interruptor("Al cerrar, seguir vigilando desde la bandeja del sistema")
        self.bandeja.setChecked(cfg.get("cerrar_a_bandeja", False))
        self.bandeja.toggled.connect(lambda val: self._guardar("cerrar_a_bandeja", val))
        f = self._form()
        f.addRow("Actualizar cada", fila(self.intervalo, None))
        f.addRow("", self.notificar)
        f.addRow("", self.bandeja)
        c.addWidget(self._seccion("🔔  Notificaciones", "", f))

        # ---- control automático
        self.auto_bloq = Interruptor("Bloquear automáticamente las licencias de compras reembolsadas")
        self.auto_bloq.setChecked(cfg.get("auto_bloquear_reembolsos", True))
        self.auto_bloq.toggled.connect(lambda val: self._guardar("auto_bloquear_reembolsos", val))
        self.auto_react = Interruptor("Reactivarlas si se cancela el reembolso o se gana la disputa")
        self.auto_react.setChecked(cfg.get("auto_reactivar", True))
        self.auto_react.toggled.connect(lambda val: self._guardar("auto_reactivar", val))
        self.auto_aviso = Interruptor("Avisar al cliente en su programa cuando se bloquee o reactive")
        self.auto_aviso.setChecked(cfg.get("avisar_al_bloquear", True))
        self.auto_aviso.toggled.connect(lambda val: self._guardar("avisar_al_bloquear", val))
        f = self._form()
        for w in (self.auto_bloq, self.auto_react, self.auto_aviso):
            f.addRow("", w)
        c.addWidget(self._seccion("🛡️  Control automático de licencias",
                                  "Con el servidor de control, el programa del cliente se cierra solo y pide licencia "
                                  "en cuanto se detecta el reembolso, y se vuelve a abrir si se cancela.", f))

        # ---- tu programa
        self.nombre = QLineEdit(cfg.get("nombre_app", ""))
        self.nombre.editingFinished.connect(lambda: self._guardar("nombre_app", self.nombre.text().strip()
                                                                  or "Mi programa", repintar=True))
        self.wa = QLineEdit(cfg.get("whatsapp_soporte", ""), placeholderText="50255551234")
        self.wa.editingFinished.connect(lambda: self._guardar("whatsapp_soporte", self.wa.text().strip(),
                                                              repintar=True))
        self.correo = QLineEdit(cfg.get("correo_soporte", ""), placeholderText="soporte@tudominio.com")
        self.correo.editingFinished.connect(lambda: self._guardar("correo_soporte", self.correo.text().strip(),
                                                                  repintar=True))
        self.pruebas = Interruptor("Aceptar claves de compras de prueba (apágalo al vender de verdad)")
        self.pruebas.setChecked(cfg.get("aceptar_pruebas", True))
        self.pruebas.toggled.connect(lambda val: self._guardar("aceptar_pruebas", val, repintar=True))
        f = self._form()
        f.addRow("Nombre del programa", self.nombre)
        f.addRow("WhatsApp de soporte", self.wa)
        f.addRow("Correo de soporte", self.correo)
        f.addRow("", self.pruebas)
        c.addWidget(self._seccion("🎬  Tu programa", "Estos datos van en cinema_licencias.json (Conexiones).", f))

        # ---- datos
        abrir = boton("📂  Abrir carpeta de configuración")
        abrir.clicked.connect(self.v.abrir_carpeta_config)
        exportar = boton("⭳  Exportar personas (CSV)")
        exportar.clicked.connect(lambda: self.v.exportar_csv("personas"))
        exportar_l = boton("⭳  Exportar licencias (CSV)")
        exportar_l.clicked.connect(lambda: self.v.exportar_csv("licencias"))
        registro = boton("📄  Ver registro")
        registro.clicked.connect(self.v.abrir_registro)
        c.addWidget(self._seccion("🗂️  Datos", "Tus credenciales y notas se guardan solo en esta computadora.",
                                  fila(abrir, exportar, exportar_l, registro, None)))

        # ---- acerca de
        logo = QLabel()
        logo.setPixmap(logo_cinema(22, C["titulo"]))
        from PySide6 import __version__ as version_pyside
        creado = etiqueta(f"Creado por <b>{MARCA}</b>", "valorFuerte")
        creado.setTextFormat(Qt.TextFormat.RichText)
        info = etiqueta(f"{APP_TITULO} {VERSION}  ·  SDK cinema_licencias  ·  PySide6 {version_pyside}  ·  "
                        "Windows, macOS y Linux", "tenue", ajustar=True)
        icono = QLabel()
        icono.setPixmap(ui.icono_app().pixmap(64, 64))
        textos = QVBoxLayout()
        textos.setSpacing(6)
        textos.addWidget(logo)
        textos.addWidget(creado)
        textos.addWidget(info)
        c.addWidget(self._seccion("ℹ️  Acerca de", "", fila(icono, textos, None, espacio=ESP_MD)))
        c.addStretch()

    @staticmethod
    def _form() -> QFormLayout:
        f = QFormLayout()
        f.setSpacing(12)
        f.setHorizontalSpacing(ESP_LG)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return f

    @staticmethod
    def _seccion(titulo: str, texto: str, *contenido) -> QFrame:
        piezas = [etiqueta(titulo, "tituloTarjeta")]
        if texto:
            piezas.append(etiqueta(texto, "nota", ajustar=True))
        return tarjeta(*piezas, *contenido, margen=20, espacio=ESP_SM + 4)

    def _guardar(self, clave: str, valor, repintar: bool = False):
        self.v.cfg[clave] = valor
        self.v.aplicar_preferencias()
        if repintar:
            self.v.pintar(forzar=True)

    def _escala(self):
        valor = self.escala.currentData()
        self.v.cfg["escala"] = valor
        self.v.guardar()
        self.reiniciar.setVisible(abs(valor - self.v.escala_inicial) > 0.001)
        if self.reiniciar.isVisible():
            fundido(self.reiniciar, 0.0, 1.0, 300)

    def marcar_tema(self, nombre: str):
        for clave, t in self.tarjetas_tema.items():
            t.elegir(clave == nombre)


PAGINAS = (PaginaInicio, PaginaPersonas, PaginaLicencias, PaginaEquipos, PaginaVentas, PaginaUso, PaginaAvisos,
           PaginaActividad, PaginaConexiones, PaginaAjustes)
