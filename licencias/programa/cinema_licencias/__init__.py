"""cinema_licencias — sistema de licencias de Cinema Productions para cualquier programa.

Funciona con Lemon Squeezy, Gumroad y Polar (y Hotmart a través de licencias de regalo), con un
servidor de control opcional (Supabase) para avisos, bloqueos y tiempo de uso.

Uso mínimo (PySide6):

    from cinema_licencias import Licencias

    licencias = Licencias.desde_json("cinema_licencias.json")   # lo crea el Administrador

    app = QApplication(sys.argv)
    if not licencias.exigir():          # ventana de activación si hace falta
        sys.exit(0)
    ventana = MiVentana()
    ventana.show()
    licencias.vigilar(ventana)          # avisos + cierre automático por reembolso o bloqueo
    sys.exit(app.exec())

Sin interfaz (consola, otro framework o desde otro lenguaje con `python -m cinema_licencias`):

    r = licencias.comprobar()           # Resultado(ok, codigo, mensaje, datos, avisos)
    r = licencias.activar("CLAVE")
    r = licencias.desactivar()

Creado por Cinema Productions.
"""
from .base import VERSION_SDK, Resultado, SinConexion, hash_licencia
from .config import Configuracion
from .licencias import Licencias
from .servidor import Vigilante

__all__ = ["Configuracion", "Licencias", "Resultado", "SinConexion", "Vigilante", "hash_licencia", "VERSION_SDK"]
__version__ = VERSION_SDK
__author__ = "Cinema Productions"
