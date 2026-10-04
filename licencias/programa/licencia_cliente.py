"""Cinema Productions · licencia_cliente.py — forma rápida de poner licencias en tu programa.

Va DENTRO de tu programa junto con la carpeta cinema_licencias/. Es la misma forma de uso de la
versión 4 (los programas que ya lo usaban siguen funcionando igual y conservan su activación), pero
ahora por dentro usa el SDK cinema_licencias: Lemon Squeezy, Gumroad y Polar, avisos del vendedor,
tiempo de uso y cierre automático si la compra se reembolsa.

    from licencia_cliente import exigir_licencia, vigilar, mostrar_mi_licencia
    if not exigir_licencia():          # después de crear QApplication y antes de mostrar la ventana
        sys.exit(0)
    ventana.show()
    vigilar(ventana)                   # avisos + cierre automático por reembolso o bloqueo

¿Programa nuevo? Mejor usa directamente cinema_licencias con el archivo cinema_licencias.json que crea el
Administrador (ver ejemplo_integracion.py).

Creado por Cinema Productions.
"""
from __future__ import annotations

import os
from pathlib import Path

from cinema_licencias import Configuracion, Licencias, Resultado, SinConexion  # noqa: F401  (SinConexion: v4)
from cinema_licencias.base import es_clave_gumroad

__author__ = "Cinema Productions"

# ======================= CONFIGURACIÓN =======================
# Copia estos valores desde el Administrador: Conexiones → "Datos para tu programa".
# Lemon Squeezy (déjalo en 0 si no vendes ahí)
TIENDA_ID = 0                      # ID de tu tienda en Lemon Squeezy
PRODUCTOS_ID: tuple[int, ...] = ()  # IDs de producto aceptados, p. ej. (123456,). Vacío = cualquiera de tu tienda
URL_COMPRA = ""                    # enlace de compra, p. ej. "https://tutienda.lemonsqueezy.com/buy/..."
# Gumroad (déjalo vacío si no vendes ahí)
GUMROAD_PRODUCTO_ID = ""           # "Product ID" de tu producto en Gumroad (aparece en el Administrador)
GUMROAD_MAX_EQUIPOS = 1            # cuántas computadoras puede activar cada clave de Gumroad (0 = sin límite)
URL_COMPRA_GUMROAD = ""            # enlace de compra, p. ej. "https://tunombre.gumroad.com/l/producto"
# Polar (déjalo vacío si no vendes ahí)
POLAR_ORGANIZACION_ID = ""         # ID de tu organización en Polar (aparece en el Administrador)
POLAR_BENEFICIO_ID = ""            # opcional: solo claves de ese beneficio de "License Keys"
URL_COMPRA_POLAR = ""              # enlace de compra de Polar
POLAR_SANDBOX = False              # True mientras pruebas con sandbox.polar.sh
# Servidor de control (Supabase) para avisos, bloqueos y tiempo de uso. Opcional.
SERVIDOR_URL = ""                  # https://xxxx.supabase.co
SERVIDOR_CLAVE_PUBLICA = ""        # clave PUBLICABLE (sb_publishable_…). NUNCA la secreta
# Generales
WHATSAPP_VENDEDOR = ""             # opcional, para soporte: número con código de país, p. ej. "50255551234"
NOMBRE_APP = "Resolve Creator Subtitles"
VERSION_APP = "5.0.0"
DIAS_SIN_INTERNET = 7              # días que funciona sin conexión tras la última verificación
ACEPTAR_CLAVES_DE_PRUEBA = True    # claves de compras en "Test mode". Pon False cuando vendas de verdad
# =============================================================

# Se conserva la carpeta y la firma de la versión 4 para que las activaciones existentes sigan valiendo.
_CARPETA = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "ResolveCreatorSubtitles"
_INSTANCIAS: dict = {}


def configuracion() -> Configuracion:
    return Configuracion(
        app=NOMBRE_APP, version=VERSION_APP,
        ls_tienda_id=int(TIENDA_ID or 0), ls_productos=tuple(int(p) for p in PRODUCTOS_ID), ls_url_compra=URL_COMPRA,
        gumroad_producto_id=GUMROAD_PRODUCTO_ID, gumroad_max_equipos=GUMROAD_MAX_EQUIPOS,
        gumroad_url_compra=URL_COMPRA_GUMROAD,
        polar_organizacion_id=POLAR_ORGANIZACION_ID, polar_beneficio_id=POLAR_BENEFICIO_ID,
        polar_url_compra=URL_COMPRA_POLAR, polar_sandbox=POLAR_SANDBOX,
        servidor_url=SERVIDOR_URL, servidor_clave=SERVIDOR_CLAVE_PUBLICA,
        whatsapp=WHATSAPP_VENDEDOR, dias_sin_internet=DIAS_SIN_INTERNET, aceptar_pruebas=ACEPTAR_CLAVES_DE_PRUEBA,
        carpeta=str(_CARPETA), sal="rcs-licencia-lemonsqueezy-v1", prefijo_equipo="RCS")


def licencias() -> Licencias:
    """El objeto Licencias con la configuración de arriba (se crea una sola vez)."""
    cfg = configuracion()
    if cfg not in _INSTANCIAS:
        cfg.verificar_sin_secretos()
        _INSTANCIAS[cfg] = Licencias(cfg)
    return _INSTANCIAS[cfg]


# ---------------------------------------------------------------- funciones de la versión 4

def obtener_id_equipo() -> str:
    return licencias().equipo_id()


def nombre_instancia() -> str:
    return licencias().nombre_equipo()


def parece_clave_gumroad(clave: str) -> bool:
    return es_clave_gumroad(clave)


def licencia_guardada() -> dict | None:
    return licencias().guardada()


def comprobar() -> Resultado:
    return licencias().comprobar()


def activar(clave: str) -> Resultado:
    return licencias().activar(clave)


def desactivar() -> Resultado:
    return licencias().desactivar()


def enlace_whatsapp() -> str:
    return licencias().enlace_whatsapp()


def exigir_licencia(parent=None) -> bool:
    """Comprueba la licencia; si no es válida muestra la ventana de activación."""
    return licencias().exigir(parent)


def mostrar_mi_licencia(parent=None) -> bool:
    """Ventana "Mi licencia". Devuelve True si el cliente desactivó la licencia (cierra tu programa)."""
    return licencias().mostrar_mi_licencia(parent)


def vigilar(ventana=None, **opciones):
    """Avisos del vendedor y cierre automático si la licencia deja de valer (reembolso, bloqueo…)."""
    return licencias().vigilar(ventana, **opciones)
