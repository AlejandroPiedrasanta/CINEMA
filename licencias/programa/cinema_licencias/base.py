"""Cinema Productions · cinema_licencias — piezas básicas (sin interfaz).

Resultado de cada operación, mensajes en español, identificador del equipo y peticiones HTTP.
Solo usa la biblioteca estándar de Python.

Creado por Cinema Productions.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

__author__ = "Cinema Productions"

VERSION_SDK = "5.0.0"
AGENTE = f"CinemaLicencias/{VERSION_SDK}"

# Códigos con los que la licencia deja de funcionar y queda "suspendida" (si el vendedor la
# desbloquea o se cancela el reembolso, vuelve a funcionar sola con la misma clave).
SUSPENSION = {"invalida", "bloqueada", "vencida", "reembolsada", "revocada", "desactivada", "otra_tienda", "en_uso"}

MENSAJES = {
    "activa": "Licencia activa.",
    "reactivada": "¡Tu licencia volvió a estar activa!",
    "sin_licencia": "Programa sin activar.",
    "invalida": "La clave no es válida. Revísala (te llegó por correo al comprar).",
    "bloqueada": "Tu licencia fue bloqueada. Contacta al vendedor.",
    "vencida": "Tu licencia venció. Renuévala para seguir usando el programa.",
    "en_uso": ("Esta licencia ya está activada en el máximo de equipos permitidos. Desactívala en la otra "
               "computadora o contacta al vendedor."),
    "desactivada": "Este equipo fue desactivado. Vuelve a activar tu licencia.",
    "reembolsada": "La compra de esta licencia fue reembolsada: la licencia ya no es válida.",
    "revocada": "El vendedor retiró esta licencia. Si crees que es un error, contáctalo.",
    "otra_tienda": "Esta clave no es de este programa.",
    "sin_conexion": "No hay conexión a internet.",
    "error": "No se pudo verificar la licencia.",
}

# Estado que el vendedor fija desde el Administrador (servidor de control) → código de la licencia
ESTADO_SERVIDOR = {"suspendida": "bloqueada", "bloqueada": "bloqueada", "reembolsada": "reembolsada",
                   "revocada": "revocada"}


@dataclass
class Resultado:
    """Respuesta de comprobar(), activar() o desactivar().

    ok       → True si el programa puede funcionar.
    codigo   → activa | reactivada | sin_conexion_ok | sin_licencia | invalida | bloqueada | vencida |
               en_uso | desactivada | reembolsada | revocada | otra_tienda | sin_conexion | error
    mensaje  → texto en español para mostrar al cliente.
    datos    → licencia guardada (cliente, correo, tienda, expira_ts…).
    avisos   → avisos del vendedor que llegaron con esta comprobación.
    """
    ok: bool
    codigo: str
    mensaje: str = ""
    datos: dict = field(default_factory=dict)
    avisos: list = field(default_factory=list)

    def __post_init__(self):
        if not self.mensaje:
            self.mensaje = MENSAJES.get(self.codigo, "")

    def a_dict(self) -> dict:
        datos = {k: v for k, v in self.datos.items() if k not in ("firma",)}
        if datos.get("clave"):
            datos["clave"] = ocultar_clave(datos["clave"])
        return {"ok": self.ok, "codigo": self.codigo, "mensaje": self.mensaje, "datos": datos,
                "avisos": self.avisos}


class SinConexion(Exception):
    """El servidor no respondió (sin internet, caído o con demasiadas peticiones)."""


# ---------------------------------------------------------------- utilidades

def iso_a_ts(iso) -> float | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def fecha_texto(ts: float | None) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else ""


def ocultar_clave(clave: str) -> str:
    clave = clave or ""
    return f"••••-{clave[-8:]}" if len(clave) > 8 else "••••"


def hash_licencia(clave: str) -> str:
    """Huella de la clave para el servidor de control: el servidor nunca recibe la clave real.
    El Administrador calcula la misma huella para saber de quién es cada equipo."""
    return hashlib.sha256(f"cinema:{(clave or '').strip().upper()}".encode()).hexdigest()


def es_uuid(clave: str) -> bool:
    """Formato de las claves de Lemon Squeezy: 8-4-4-4-12 caracteres hexadecimales."""
    return bool(re.fullmatch(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}",
                             (clave or "").strip()))


def es_clave_gumroad(clave: str) -> bool:
    """Las claves de Gumroad son 4 bloques de 8 caracteres: 85DB562A-C11D4B06-A2335A6B-8C079166."""
    return bool(re.fullmatch(r"[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{8}){3}", (clave or "").strip()))


def nombre_sistema() -> str:
    try:
        if sys.platform == "win32":
            v = sys.getwindowsversion()
            return f"Windows {'11' if v.build >= 22000 else '10' if v.major >= 10 else v.major} ({v.build})"
        if sys.platform == "darwin":
            return f"macOS {platform.mac_ver()[0]}"
        return f"{platform.system()} {platform.release()}"
    except Exception:  # noqa: BLE001
        return platform.system() or "Desconocido"


def carpeta_datos() -> Path:
    """Carpeta de datos del usuario en cada sistema."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


# ---------------------------------------------------------------- equipo

def _id_bruto_equipo() -> str:
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, "MachineGuid")[0]
    if sys.platform == "darwin":
        import subprocess
        salida = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                                capture_output=True, text=True).stdout
        for linea in salida.splitlines():
            if "IOPlatformUUID" in linea:
                return linea.split('"')[-2]
    for ruta in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        if os.path.exists(ruta):
            return Path(ruta).read_text().strip()
    raise RuntimeError("No se pudo obtener el identificador del equipo")


def id_equipo(prefijo: str = "CP") -> str:
    """ID corto y estable del equipo, p. ej. 3F2A-91BC-04DE-77A1 (no revela nada de la computadora)."""
    h = hashlib.sha256(f"{prefijo}:{_id_bruto_equipo()}".encode()).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


# ---------------------------------------------------------------- HTTP

def peticion(metodo: str, url: str, datos=None, formato: str = "form", cabeceras: dict | None = None,
             timeout: float = 10) -> tuple[int, object]:
    """Hace la petición y devuelve (código HTTP, JSON). También devuelve las respuestas 4xx (la tienda
    contesta así cuando la clave no sirve). Lanza SinConexion si no hay respuesta, si el servidor
    falla (5xx) o si pide esperar (429)."""
    cab = {"Accept": "application/json", "User-Agent": AGENTE, **(cabeceras or {})}
    cuerpo = None
    if datos is not None and metodo != "GET":
        if formato == "json":
            cuerpo = json.dumps(datos).encode()
            cab.setdefault("Content-Type", "application/json")
        else:
            cuerpo = urllib.parse.urlencode(datos).encode()
            cab.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif datos:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(datos)
    req = urllib.request.Request(url, data=cuerpo, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            texto = r.read()
            codigo = r.status
    except urllib.error.HTTPError as e:
        if e.code >= 500 or e.code == 429:
            raise SinConexion(f"El servidor de licencias no respondió bien ({e.code}).") from e
        codigo, texto = e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise SinConexion(MENSAJES["sin_conexion"]) from e
    try:
        return codigo, (json.loads(texto) if texto and texto.strip() else {})
    except ValueError:
        if 200 <= codigo < 300:
            return codigo, {}
        raise SinConexion(f"El servidor de licencias respondió algo inesperado ({codigo}).") from None
