"""Cinema Productions · Administrador de Licencias — servidor de control (Supabase).

Con la clave SECRETA (que solo vive en tu computadora) el Administrador lee el tiempo de uso, los
equipos y los eventos que envían tus programas, envía avisos a una licencia o a todas, y fija el estado
de una licencia (activa, suspendida, reembolsada o revocada) para que el programa se cierre o se
reactive solo.

Las tablas se crean con servidor/supabase_cinema.sql.

Creado por Cinema Productions.
"""
from __future__ import annotations

import json
import urllib.parse
from datetime import date, timedelta

from plataformas import ErrorApi, _detalle, _http, ahora_iso

__author__ = "Cinema Productions"

ESTADOS_SERVIDOR = {"activa": "Activa", "suspendida": "Suspendida", "reembolsada": "Reembolsada",
                    "revocada": "Retirada"}
TIPOS_AVISO = {"info": "Información", "advertencia": "Advertencia", "remocion": "Será removida",
               "reactivada": "Reactivada", "bloqueo": "Bloqueo"}
PAGINA = 1000          # Supabase devuelve como máximo 1000 filas por petición


class ServidorControl:
    clave = "control"

    def __init__(self, url: str, clave_secreta: str, clave_publica: str = ""):
        self.url = (url or "").strip().rstrip("/")
        self.secreta = (clave_secreta or "").strip()
        self.publica = (clave_publica or "").strip()

    def _req(self, metodo: str, ruta: str, consulta: dict | None = None, cuerpo=None, prefer: str = ""):
        url = f"{self.url}/rest/v1/{ruta}"
        if consulta:
            url += "?" + urllib.parse.urlencode(consulta, safe=",.*():")
        cab = {"apikey": self.secreta, "Accept": "application/json", "Content-Type": "application/json"}
        if self.secreta.startswith("eyJ"):        # clave service_role antigua (JWT)
            cab["Authorization"] = f"Bearer {self.secreta}"
        if prefer:
            cab["Prefer"] = prefer
        try:
            return _http(metodo, url, cab, json.dumps(cuerpo).encode() if cuerpo is not None else None)
        except ErrorApi as e:
            detalle = _detalle(e.cuerpo)
            texto = json.dumps(e.cuerpo) if e.cuerpo else ""
            if "42P01" in texto or "PGRST205" in texto or "PGRST202" in texto or "does not exist" in texto:
                raise ErrorApi("Falta preparar el servidor: ejecuta servidor/supabase_cinema.sql en el SQL Editor de "
                               "Supabase.", e.codigo, e.cuerpo) from e
            mensajes = {0: str(e),
                        401: "La clave secreta del servidor no es válida. Cópiala de Supabase → Project Settings → "
                             "API Keys (sb_secret_…).",
                        403: "La clave del servidor no tiene permiso. Usa la clave SECRETA, no la publicable.",
                        404: "No se encontró el servidor. Revisa la URL del proyecto (https://xxxx.supabase.co)."}
            raise ErrorApi(mensajes.get(e.codigo, f"Error del servidor ({e.codigo}). {detalle}").strip(), e.codigo,
                           e.cuerpo) from e

    def _todas(self, tabla: str, consulta: dict, max_paginas: int = 20) -> list[dict]:
        filas: list[dict] = []
        for n in range(max_paginas):
            r = self._req("GET", tabla, consulta | {"limit": PAGINA, "offset": n * PAGINA}) or []
            filas += r
            if len(r) < PAGINA:
                break
        return filas

    # ---------------------------------------------------------------- lectura
    def probar(self) -> dict:
        """Comprueba la URL, la clave y que las tablas existan."""
        if not self.url.startswith("http"):
            raise ErrorApi("La URL del proyecto debe empezar con https://")
        if self.secreta.startswith("sb_publishable_"):
            raise ErrorApi("Esa es la clave PUBLICABLE. Aquí va la SECRETA (sb_secret_…); la publicable va en tu "
                           "programa.")
        equipos = self._todas("cinema_equipos", {"select": "licencia,equipo,segundos_uso,ultima_vez"})
        avisos = self._req("GET", "cinema_avisos", {"select": "id", "limit": 1000}) or []
        return {"plataforma": self.clave, "url": self.url, "equipos": len(equipos),
                "licencias": len({e["licencia"] for e in equipos}),
                "horas": round(sum(int(e.get("segundos_uso") or 0) for e in equipos) / 3600, 1),
                "avisos": len(avisos)}

    def datos(self, dias: int = 30) -> dict:
        desde = (date.today() - timedelta(days=dias - 1)).isoformat()
        return {
            "equipos": self._todas("cinema_equipos", {"select": "*", "order": "ultima_vez.desc"}),
            "uso": self._todas("cinema_uso_diario", {"select": "*", "dia": f"gte.{desde}"}),
            "estados": self._todas("cinema_estados", {"select": "*"}),
            "avisos": self._req("GET", "cinema_avisos", {"select": "*", "order": "creado.desc", "limit": 500}) or [],
            "leidos": self._todas("cinema_avisos_leidos", {"select": "aviso,licencia,equipo,leido"}),
            "eventos": self._req("GET", "cinema_eventos", {"select": "*", "order": "creado.desc", "limit": 300}) or [],
        }

    # ---------------------------------------------------------------- acciones
    def enviar_aviso(self, licencias: list[str | None], tipo: str, titulo: str, mensaje: str,
                     fecha_limite: str | None = None, app: str | None = None) -> list[dict]:
        """Un aviso por licencia (huella). licencias=[None] lo envía a todas."""
        filas = [{"licencia": l, "app": app or None, "tipo": tipo, "titulo": titulo[:200], "mensaje": mensaje[:4000],
                  "fecha_limite": fecha_limite} for l in (licencias or [None])]
        return self._req("POST", "cinema_avisos", cuerpo=filas, prefer="return=representation") or []

    def borrar_aviso(self, id_) -> None:
        self._req("DELETE", "cinema_avisos", {"id": f"eq.{id_}"})

    def fijar_estado(self, licencia: str, estado: str, motivo: str = "") -> None:
        if estado not in ESTADOS_SERVIDOR:
            raise ErrorApi(f"Estado desconocido: {estado}")
        self._req("POST", "cinema_estados", {"on_conflict": "licencia"},
                  {"licencia": licencia, "estado": estado, "motivo": motivo[:300] or None, "actualizado": ahora_iso()},
                  prefer="resolution=merge-duplicates,return=minimal")

    def limpiar(self) -> dict:
        return self._req("POST", "rpc/cinema_limpiar", cuerpo={}) or {}


def crear_servidor(cfg: dict) -> ServidorControl | None:
    if cfg and cfg.get("url") and cfg.get("clave_secreta"):
        return ServidorControl(cfg["url"], cfg["clave_secreta"], cfg.get("clave_publica", ""))
    return None
