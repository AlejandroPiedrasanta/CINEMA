"""Cinema Productions · Administrador de Licencias — temas (colores) y hoja de estilos.

Cada tema define los mismos "tokens" de color. Toda la interfaz los toma de C (el tema activo),
nunca de colores escritos a mano, así que cambiar de tema cambia todo.

Escala de espacios en múltiplos de 4 px y tipografía de la guía de diseño.

Creado por Cinema Productions.
"""
from __future__ import annotations

import sys
from pathlib import Path

__author__ = "Cinema Productions"

# El SDK cinema_licencias (ventanas sin marco, huella de licencias) vive en ../programa
_SDK = Path(__file__).resolve().parent.parent / "programa"
if _SDK.is_dir() and str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from cinema_licencias.ventanas import fijar_paleta, qss_ventanas, tinte  # noqa: E402

# ------------------------------------------------------------ espacios, radios y letra
ESPACIO = 4
ESP_XS, ESP_SM, ESP_MD, ESP_LG, ESP_XL = 4, 8, 16, 24, 32
RADIO_SM, RADIO, RADIO_LG, RADIO_XL = 6, 10, 14, 18
LETRA = ["Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Inter", "Helvetica Neue", "Noto Sans", "DejaVu Sans"]
LETRA_TITULOS = ["Segoe UI Variable Display", "Segoe UI", "SF Pro Display", "Hanken Grotesk", "Inter", "Noto Sans"]
DENSIDADES = {"compacta": 34, "normal": 42, "amplia": 50}

TEMAS: dict[str, dict] = {
    "cinema": {
        "nombre": "Cinema", "descripcion": "Negro y rojo de cine, con detalles dorados.", "oscuro": True,
        "fondo": "#0a0a0c", "panel": "#121215", "panel2": "#19191e", "borde": "#24242b", "borde2": "#33333c",
        "texto": "#ececf1", "suave": "#a1a1aa", "tenue": "#6b6b76", "titulo": "#ffffff",
        "acento": "#e50914", "acento2": "#ff5a36", "sobre_acento": "#ffffff", "oro": "#f5c518",
        "ok": "#22c55e", "aviso": "#f59e0b", "error": "#ff4d6d", "info": "#38bdf8",
        "seleccion": "#2b1216", "hover": "#1c1c22", "activo": "#2a0f13", "heroe1": "#24090d", "heroe2": "#0d0d11",
        "sombra": "#000000",
    },
    "violeta": {
        "nombre": "Violeta", "descripcion": "El estilo clásico del panel: violeta y azul.", "oscuro": True,
        "fondo": "#0d0f14", "panel": "#141823", "panel2": "#1a1f2d", "borde": "#252b3b", "borde2": "#323a50",
        "texto": "#e8ebf3", "suave": "#8d95aa", "tenue": "#5d6579", "titulo": "#ffffff",
        "acento": "#7c5cff", "acento2": "#4f8cff", "sobre_acento": "#ffffff", "oro": "#f5c518",
        "ok": "#22c55e", "aviso": "#f59e0b", "error": "#ef4444", "info": "#38bdf8",
        "seleccion": "#243156", "hover": "#1f2536", "activo": "#1f1a3d", "heroe1": "#1d1840", "heroe2": "#10203a",
        "sombra": "#000000",
    },
    "medianoche": {
        "nombre": "Medianoche", "descripcion": "Azul profundo y cian, tranquilo para la vista.", "oscuro": True,
        "fondo": "#0b121f", "panel": "#111a2b", "panel2": "#162135", "borde": "#1f2b42", "borde2": "#2a3a57",
        "texto": "#e6edf8", "suave": "#94a3b8", "tenue": "#64748b", "titulo": "#ffffff",
        "acento": "#3b82f6", "acento2": "#06b6d4", "sobre_acento": "#ffffff", "oro": "#fbbf24",
        "ok": "#22c55e", "aviso": "#f59e0b", "error": "#f87171", "info": "#22d3ee",
        "seleccion": "#15305a", "hover": "#172338", "activo": "#13294d", "heroe1": "#0f2147", "heroe2": "#0a1a2a",
        "sombra": "#000000",
    },
    "grafito": {
        "nombre": "Grafito", "descripcion": "Gris neutro con acentos esmeralda.", "oscuro": True,
        "fondo": "#111113", "panel": "#18181b", "panel2": "#1f1f23", "borde": "#27272a", "borde2": "#3f3f46",
        "texto": "#f4f4f5", "suave": "#a1a1aa", "tenue": "#71717a", "titulo": "#fafafa",
        "acento": "#10b981", "acento2": "#22d3ee", "sobre_acento": "#04120d", "oro": "#facc15",
        "ok": "#4ade80", "aviso": "#fbbf24", "error": "#f87171", "info": "#38bdf8",
        "seleccion": "#133a30", "hover": "#232327", "activo": "#10302a", "heroe1": "#112620", "heroe2": "#141418",
        "sombra": "#000000",
    },
    "oro": {
        "nombre": "Oro", "descripcion": "Negro con dorado: alfombra roja.", "oscuro": True,
        "fondo": "#0c0a06", "panel": "#15120b", "panel2": "#1c1810", "borde": "#2a2417", "borde2": "#3b3320",
        "texto": "#f3eee2", "suave": "#b5aa8f", "tenue": "#7d7462", "titulo": "#fff8e6",
        "acento": "#f5c518", "acento2": "#ff9f1c", "sobre_acento": "#1a1405", "oro": "#f5c518",
        "ok": "#4ade80", "aviso": "#fb923c", "error": "#f87171", "info": "#67e8f9",
        "seleccion": "#3a3012", "hover": "#211c12", "activo": "#33290d", "heroe1": "#2a2108", "heroe2": "#100d07",
        "sombra": "#000000",
    },
    "claro": {
        "nombre": "Claro", "descripcion": "Fondo blanco para trabajar de día.", "oscuro": False,
        "fondo": "#f5f6fa", "panel": "#ffffff", "panel2": "#f1f3f9", "borde": "#e3e6ef", "borde2": "#cfd4e2",
        "texto": "#1d2433", "suave": "#536079", "tenue": "#8a93a8", "titulo": "#0b1220",
        "acento": "#d10812", "acento2": "#ff5a36", "sobre_acento": "#ffffff", "oro": "#b98900",
        "ok": "#15803d", "aviso": "#b45309", "error": "#dc2626", "info": "#0369a1",
        "seleccion": "#fde2e4", "hover": "#f3f4f8", "activo": "#fdecee", "heroe1": "#fff1f2", "heroe2": "#eef1ff",
        "sombra": "#1e2433",
    },
}
TEMA_POR_DEFECTO = "cinema"

C: dict = dict(TEMAS[TEMA_POR_DEFECTO])     # tema activo (se modifica en el mismo diccionario)
C["clave"] = TEMA_POR_DEFECTO


def aplicar_tema(nombre: str) -> dict:
    """Cambia los colores activos (C) y los de las ventanas sin marco del SDK."""
    nombre = nombre if nombre in TEMAS else TEMA_POR_DEFECTO
    C.clear()
    C.update(TEMAS[nombre])
    C["clave"] = nombre
    fijar_paleta({k: v for k, v in C.items() if isinstance(v, str)})
    return C


def _icono_palomita(color: str) -> str:
    """Dibuja una palomita (✓) para las casillas marcadas y devuelve su ruta (QSS solo acepta archivos)."""
    import tempfile
    ruta = Path(tempfile.gettempdir()) / f"cinema_palomita_{color.strip('#')}.png"
    if not ruta.exists():
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
        pm = QPixmap(36, 36)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(color), 4.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        camino = QPainterPath(QPointF(9, 18.5))
        camino.lineTo(15.5, 25)
        camino.lineTo(27, 11)
        p.drawPath(camino)
        p.end()
        pm.save(str(ruta))
    return ruta.as_posix()


def construir_qss(T: dict | None = None) -> str:
    """Hoja de estilos completa del Administrador a partir de los tokens del tema."""
    T = dict(T or C)
    t = T | {"acento_t": tinte(T["acento"], 0.16), "acento_b": tinte(T["acento"], 0.45),
             "error_t": tinte(T["error"], 0.12), "error_b": tinte(T["error"], 0.4), "error_h": tinte(T["error"], 0.22),
             "ok_t": tinte(T["ok"], 0.14), "ok_b": tinte(T["ok"], 0.45), "wa": "#25d366",
             "wa_t": tinte("#25d366", 0.14), "wa_b": tinte("#25d366", 0.45),
             "letra": ", ".join(f'"{f}"' for f in LETRA), "titulos": ", ".join(f'"{f}"' for f in LETRA_TITULOS),
             "r_sm": RADIO_SM, "r": RADIO, "r_lg": RADIO_LG, "r_xl": RADIO_XL,
             "palomita": _icono_palomita(T["sobre_acento"])}
    return qss_ventanas(T) + """
* { font-family: %(letra)s; font-size: 13px; }
QMainWindow, QDialog { background: %(fondo)s; }
QWidget { color: %(texto)s; }
QWidget#raiz { background: %(fondo)s; border: 1px solid %(borde2)s; }
QWidget#raiz[maximizada="true"] { border: none; }
QWidget#pagina, QStackedWidget, QWidget#vacio { background: transparent; }
QLabel { background: transparent; }
QToolTip { background: %(panel2)s; color: %(texto)s; border: 1px solid %(borde2)s; padding: 6px 8px;
           border-radius: 8px; }

/* ---- barra de título y lateral ---- */
QWidget#barraTitulo[principal="true"] { background: %(panel)s; border-bottom: 1px solid %(borde)s; }
QFrame#lateral { background: %(panel)s; border-right: 1px solid %(borde)s; }
QLabel#marca { font-family: %(titulos)s; font-size: 16px; font-weight: 800; color: %(titulo)s; }
QLabel#marcaSub { color: %(suave)s; font-size: 11px; }
QWidget#nav { background: transparent; }
QPushButton#navBoton { text-align: left; padding: 9px 12px; border: none; border-radius: %(r)spx;
                       color: %(suave)s; font-weight: 600; background: transparent; }
QPushButton#navBoton:hover { background: %(hover)s; color: %(texto)s; }
QPushButton#navBoton:checked { background: %(activo)s; color: %(titulo)s; }
QPushButton#navBoton:focus { outline: none; }
QFrame#navIndicador { background: %(acento)s; border-radius: 2px; }
QLabel#seccionLateral { color: %(tenue)s; font-size: 10px; font-weight: 700; padding: 10px 12px 2px 12px; }
QPushButton#plataformaChip { text-align: left; background: %(panel2)s; border: 1px solid %(borde)s;
                             border-radius: %(r)spx; padding: 7px 10px; color: %(texto)s; font-weight: 600; }
QPushButton#plataformaChip:hover { border-color: %(borde2)s; background: %(hover)s; }
QPushButton#colapsar { background: transparent; border: none; border-radius: 8px; color: %(suave)s;
                       font-size: 16px; padding: 4px 8px; }
QPushButton#colapsar:hover { background: %(hover)s; color: %(titulo)s; }

/* ---- cabecera ---- */
QLabel#tituloPagina { font-family: %(titulos)s; font-size: 24px; font-weight: 800; color: %(titulo)s; }
QLabel#subtitulo { color: %(suave)s; }
QLineEdit#buscar { background: %(panel)s; border: 1px solid %(borde)s; border-radius: %(r)spx; padding: 8px 12px; }
QLineEdit#buscar:hover { border-color: %(borde2)s; }
QLineEdit#buscar:focus { border-color: %(acento)s; }
QLabel#barraEstado { color: %(tenue)s; font-size: 11px; }

/* ---- tarjetas ---- */
QFrame#tarjeta, QFrame#kpi { background: %(panel)s; border: 1px solid %(borde)s; border-radius: %(r_lg)spx; }
QFrame#kpi:hover { border-color: %(borde2)s; }
QLabel#kpiTitulo { color: %(suave)s; font-size: 10px; font-weight: 700; }
QLabel#kpiValor { font-family: %(titulos)s; font-size: 30px; font-weight: 800; }
QLabel#kpiSub { color: %(tenue)s; font-size: 11px; }
QLabel#tituloTarjeta { font-family: %(titulos)s; font-size: 15px; font-weight: 700; color: %(titulo)s; }
QLabel#nota { color: %(suave)s; }
QLabel#tenue { color: %(tenue)s; font-size: 12px; }
QLabel#valorFuerte { color: %(titulo)s; font-size: 14px; font-weight: 600; }
QLabel#codigo { background: %(fondo)s; border: 1px dashed %(borde2)s; border-radius: %(r)spx; padding: 12px;
                color: %(titulo)s; }
QFrame#heroe { border: 1px solid %(borde2)s; border-radius: %(r_xl)spx;
               background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 %(heroe1)s, stop:1 %(heroe2)s); }
QLabel#heroeTitulo { font-family: %(titulos)s; font-size: 26px; font-weight: 800; color: %(titulo)s; }
QFrame#plataforma { background: %(panel)s; border: 1px solid %(borde)s; border-radius: %(r_xl)spx; }
QFrame#plataforma:hover { border-color: %(acento)s; }
QFrame#opcion { background: %(panel)s; border: 2px solid %(borde)s; border-radius: %(r_lg)spx; }
QFrame#opcion:hover { border-color: %(borde2)s; }
QFrame#panelDetalle { background: %(panel)s; border: 1px solid %(borde)s; border-radius: %(r_lg)spx; }
QFrame#separador { background: %(borde)s; max-height: 1px; min-height: 1px; }
QFrame#temaTarjeta { background: %(panel)s; border: 2px solid %(borde)s; border-radius: %(r_lg)spx; }
QFrame#temaTarjeta:hover { border-color: %(borde2)s; }
QFrame#temaTarjeta[elegido="true"] { border-color: %(acento)s; }
QFrame#banda { background: %(error_t)s; border: 1px solid %(error_b)s; border-radius: %(r)spx; }
QFrame#banda[tipo="ok"] { background: %(ok_t)s; border-color: %(ok_b)s; }
QFrame#banda[tipo="info"] { background: %(acento_t)s; border-color: %(acento_b)s; }

/* ---- vacío ---- */
QLabel#vacioIcono { font-size: 44px; }
QLabel#vacioTitulo { font-family: %(titulos)s; font-size: 18px; font-weight: 700; color: %(titulo)s; }
QLabel#vacioTexto { color: %(suave)s; }

/* ---- avisos flotantes ---- */
QFrame#toast { background: %(panel2)s; border: 1px solid %(borde2)s; border-radius: %(r_lg)spx; }
QLabel#toastTitulo { font-weight: 700; color: %(titulo)s; }
QLabel#toastTexto { color: %(suave)s; font-size: 12px; }

/* ---- controles ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit {
    background: %(fondo)s; color: %(texto)s; border: 1px solid %(borde2)s; border-radius: %(r)spx;
    padding: 8px 10px; selection-background-color: %(acento)s; selection-color: %(sobre_acento)s; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover, QPlainTextEdit:hover {
    border-color: %(suave)s; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QPlainTextEdit:focus {
    border-color: %(acento)s; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDateEdit:disabled { color: %(tenue)s;
    background: %(panel2)s; border-color: %(borde)s; }
QLineEdit[error="true"] { border-color: %(error)s; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: %(panel2)s; border: 1px solid %(borde2)s; border-radius: 8px;
                              selection-background-color: %(seleccion)s; selection-color: %(titulo)s;
                              outline: none; padding: 4px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid %(borde2)s;
                       background: %(fondo)s; }
QCheckBox::indicator:hover { border-color: %(acento)s; }
QCheckBox::indicator:checked { background: %(acento)s; border-color: %(acento)s; image: url(%(palomita)s); }
QSlider::groove:horizontal { height: 4px; background: %(borde2)s; border-radius: 2px; }
QSlider::sub-page:horizontal { background: %(acento)s; border-radius: 2px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; background: %(titulo)s;
                             border: 2px solid %(acento)s; }
QPushButton { border-radius: %(r)spx; padding: 8px 16px; font-weight: 600; }
QPushButton:focus { outline: none; }
QPushButton#primario { color: %(sobre_acento)s; border: none;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 %(acento)s, stop:1 %(acento2)s); }
QPushButton#primario:hover { background: %(acento2)s; }
QPushButton#primario:pressed { background: %(acento)s; }
QPushButton#secundario { background: %(panel2)s; color: %(texto)s; border: 1px solid %(borde2)s; }
QPushButton#secundario:hover { background: %(hover)s; border-color: %(suave)s; color: %(titulo)s; }
QPushButton#secundario:pressed { background: %(borde)s; }
QPushButton#peligro { background: %(error_t)s; color: %(error)s; border: 1px solid %(error_b)s; }
QPushButton#peligro:hover { background: %(error_h)s; }
QPushButton#whatsapp { background: %(wa_t)s; color: %(wa)s; border: 1px solid %(wa_b)s; }
QPushButton#whatsapp:hover { background: %(wa_b)s; color: %(titulo)s; }
QPushButton#enlace { background: transparent; border: none; color: %(info)s; padding: 4px 2px; }
QPushButton#enlace:hover { color: %(titulo)s; }
QPushButton#chip { background: transparent; color: %(suave)s; border: 1px solid %(borde2)s; border-radius: 12px;
                   padding: 4px 14px; font-weight: 600; font-size: 12px; }
QPushButton#chip:hover { color: %(texto)s; border-color: %(suave)s; }
QPushButton#chip:checked { background: %(acento_t)s; color: %(titulo)s; border-color: %(acento)s; }
QPushButton:disabled { background: %(panel)s; color: %(tenue)s; border: 1px solid %(borde)s; }

/* ---- tablas ---- */
QTableWidget { background: %(panel)s; alternate-background-color: %(panel2)s; border: 1px solid %(borde)s;
               border-radius: %(r_lg)spx; selection-background-color: %(seleccion)s; selection-color: %(titulo)s;
               gridline-color: transparent; }
QTableWidget::item { padding: 0 10px; border: none; }
QTableWidget::item:hover { background: %(hover)s; }
QTableWidget::item:selected { background: %(seleccion)s; color: %(titulo)s; }
QHeaderView { background: transparent; }
QHeaderView::section { background: %(panel)s; color: %(tenue)s; border: none; border-bottom: 1px solid %(borde)s;
                       padding: 10px; font-weight: 700; font-size: 11px; }
QHeaderView::section:hover { color: %(texto)s; }
QTableCornerButton::section { background: %(panel)s; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
QScrollBar::handle { background: %(borde2)s; border-radius: 4px; min-height: 30px; min-width: 30px; }
QScrollBar::handle:hover { background: %(tenue)s; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { width: 0; height: 0;
                                                                                         background: none; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QMenu { background: %(panel2)s; border: 1px solid %(borde2)s; border-radius: %(r)spx; padding: 6px; }
QMenu::item { padding: 8px 18px; border-radius: 6px; }
QMenu::item:selected { background: %(seleccion)s; color: %(titulo)s; }
QMenu::separator { height: 1px; background: %(borde)s; margin: 4px 8px; }
QCalendarWidget QWidget { alternate-background-color: %(panel2)s; }
QCalendarWidget QAbstractItemView:enabled { background: %(panel)s; selection-background-color: %(acento)s;
                                            selection-color: %(sobre_acento)s; }
""" % t
