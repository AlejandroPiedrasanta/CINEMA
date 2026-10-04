"""Cinema Productions · cinema_licencias — tiendas: Lemon Squeezy, Gumroad y Polar.

Cada tienda sabe activar una clave en este equipo, validarla y desactivarla usando la API PÚBLICA
de licencias de la plataforma (ninguna necesita tus claves secretas).

  - Lemon Squeezy: activa ocupando un "equipo" de la licencia (instancia).
  - Gumroad: verifica la clave y suma un "uso" (no registra equipos).
  - Polar: activa ocupando una "activación" del beneficio de claves de licencia.

Creado por Cinema Productions.
"""
from __future__ import annotations

import time

from .base import MENSAJES, Resultado, SinConexion, es_clave_gumroad, es_uuid, fecha_texto, iso_a_ts, peticion
from .config import Configuracion

__author__ = "Cinema Productions"

LS_API = "https://api.lemonsqueezy.com/v1/licenses/"
GUMROAD_API = "https://api.gumroad.com/v2/licenses/"
POLAR_API = {False: "https://api.polar.sh", True: "https://sandbox-api.polar.sh"}


class Tienda:
    clave = ""
    nombre = ""

    def __init__(self, cfg: Configuracion):
        self.cfg = cfg

    def configurada(self) -> bool:
        return False

    def prioridad(self, clave: str) -> int:
        """Qué tan probable es que la clave sea de esta tienda (0 = no intentarlo)."""
        return 1

    def url_compra(self) -> str:
        return ""

    def otra(self) -> Resultado:
        return Resultado(False, "otra_tienda", f"Esta clave no es de {self.cfg.app}.")

    def activar(self, clave: str, nombre_equipo: str, meta: dict) -> Resultado:
        raise NotImplementedError

    def validar(self, local: dict) -> Resultado:
        raise NotImplementedError

    def desactivar(self, local: dict) -> Resultado:
        raise NotImplementedError


# ============================================================ Lemon Squeezy

class TiendaLemonSqueezy(Tienda):
    clave = "lemonsqueezy"
    nombre = "Lemon Squeezy"

    def configurada(self) -> bool:
        return bool(self.cfg.ls_tienda_id)

    def prioridad(self, clave: str) -> int:
        return 3 if es_uuid(clave) else 1

    def url_compra(self) -> str:
        return self.cfg.ls_url_compra

    @staticmethod
    def _llamar(accion: str, datos: dict) -> dict:
        codigo, r = peticion("POST", LS_API + accion, datos, "form")
        r = r if isinstance(r, dict) else {}
        return r | {"_http": codigo}

    def _es_nuestra(self, r: dict) -> bool:
        """Evita que funcionen claves de OTRAS tiendas de Lemon Squeezy (todas usan la misma API)."""
        meta = r.get("meta") or {}
        if int(meta.get("store_id") or 0) != int(self.cfg.ls_tienda_id):
            return False
        if self.cfg.ls_productos and int(meta.get("product_id") or 0) not in {int(p) for p in self.cfg.ls_productos}:
            return False
        if not self.cfg.aceptar_pruebas and (r.get("license_key") or {}).get("test_mode"):
            return False
        return True

    @staticmethod
    def _traducir(r: dict) -> Resultado:
        lic = r.get("license_key") or {}
        error = str(r.get("error") or "").lower()
        estado = lic.get("status")
        if estado == "disabled" or "disabled" in error:
            return Resultado(False, "bloqueada")
        if estado == "expired" or "expired" in error:
            cuando = fecha_texto(iso_a_ts(lic.get("expires_at")))
            return Resultado(False, "vencida", (f"Tu licencia venció el {cuando}." if cuando else "Tu licencia venció.")
                             + " Renuévala para seguir usando el programa.")
        if "activation limit" in error:
            return Resultado(False, "en_uso")
        if "instance" in error:
            return Resultado(False, "desactivada")
        if "not found" in error or r.get("_http") == 404:
            return Resultado(False, "invalida")
        return Resultado(False, "error", str(r.get("error") or MENSAJES["error"]))

    @staticmethod
    def _datos(r: dict) -> dict:
        lic, meta = r.get("license_key") or {}, r.get("meta") or {}
        return {"cliente": meta.get("customer_name") or "", "correo": meta.get("customer_email") or "",
                "producto": meta.get("product_name") or "", "expira_ts": iso_a_ts(lic.get("expires_at")),
                "limite": lic.get("activation_limit"), "usados": lic.get("activation_usage")}

    def activar(self, clave: str, nombre_equipo: str, meta: dict) -> Resultado:
        r = self._llamar("activate", {"license_key": clave, "instance_name": nombre_equipo})
        if not r.get("activated"):
            return self._traducir(r)
        instancia = (r.get("instance") or {}).get("id")
        if not self._es_nuestra(r) or not instancia:
            if instancia:   # devolver el equipo que se acaba de ocupar en esa otra licencia
                try:
                    self._llamar("deactivate", {"license_key": clave, "instance_id": instancia})
                except SinConexion:
                    pass
            return self.otra()
        return Resultado(True, "activa", "Licencia activada.", self._datos(r) | {"instancia": instancia})

    def validar(self, local: dict) -> Resultado:
        r = self._llamar("validate", {"license_key": local["clave"], "instance_id": local.get("instancia") or ""})
        if r.get("valid") and self._es_nuestra(r):
            return Resultado(True, "activa", datos=self._datos(r))
        return self._traducir(r) if not r.get("valid") else self.otra()

    def desactivar(self, local: dict) -> Resultado:
        r = self._llamar("deactivate", {"license_key": local["clave"], "instance_id": local.get("instancia") or ""})
        if r.get("deactivated") or self._traducir(r).codigo in ("desactivada", "invalida"):
            return Resultado(True, "desactivada",
                             "Licencia desactivada en este equipo. Ya puedes activarla en otra computadora.")
        return self._traducir(r)


# ============================================================ Gumroad

class TiendaGumroad(Tienda):
    clave = "gumroad"
    nombre = "Gumroad"

    def configurada(self) -> bool:
        return bool(self.cfg.gumroad_producto_id)

    def prioridad(self, clave: str) -> int:
        return 5 if es_clave_gumroad(clave) else 0

    def url_compra(self) -> str:
        return self.cfg.gumroad_url_compra

    def _verificar(self, clave: str, sumar_uso: bool = False) -> dict:
        codigo, r = peticion("POST", GUMROAD_API + "verify",
                             {"product_id": self.cfg.gumroad_producto_id, "license_key": clave,
                              "increment_uses_count": "true" if sumar_uso else "false"}, "form")
        r = r if isinstance(r, dict) else {}
        return r | {"_http": codigo}

    def _fallo(self, r: dict) -> Resultado | None:
        """None si la clave es válida; si no, el resultado con el motivo."""
        if not r.get("success"):
            mensaje = str(r.get("message") or "")
            if "disabled" in mensaje.lower():
                return Resultado(False, "bloqueada")
            if r.get("_http") == 404 or "not exist" in mensaje.lower():
                return Resultado(False, "invalida")
            return Resultado(False, "error", mensaje or MENSAJES["error"])
        compra = r.get("purchase") or {}
        if compra.get("refunded") or compra.get("chargebacked") or compra.get("chargedback"):
            return Resultado(False, "reembolsada")
        if compra.get("disputed") and not compra.get("dispute_won"):
            return Resultado(False, "bloqueada", "La compra de esta licencia está en disputa. Contacta al vendedor.")
        if compra.get("subscription_ended_at") or compra.get("subscription_failed_at") \
                or compra.get("subscription_cancelled_at"):
            return Resultado(False, "vencida", "Tu suscripción terminó. Renuévala para seguir usando el programa.")
        if not self.cfg.aceptar_pruebas and compra.get("test"):
            return Resultado(False, "otra_tienda", "Esta clave es de una compra de prueba.")
        if compra.get("product_id") and str(compra["product_id"]) != str(self.cfg.gumroad_producto_id):
            return self.otra()
        return None

    def _datos(self, r: dict) -> dict:
        compra = r.get("purchase") or {}
        return {"cliente": compra.get("full_name") or compra.get("email") or "", "correo": compra.get("email") or "",
                "producto": compra.get("product_name") or "", "expira_ts": None,
                "limite": self.cfg.gumroad_max_equipos or None, "usados": r.get("uses")}

    def activar(self, clave: str, nombre_equipo: str, meta: dict) -> Resultado:
        r = self._verificar(clave)
        if fallo := self._fallo(r):
            return fallo
        if self.cfg.gumroad_max_equipos and (r.get("uses") or 0) >= self.cfg.gumroad_max_equipos:
            return Resultado(False, "en_uso", "Esta licencia ya se activó en el máximo de equipos permitidos. "
                                              "Pide al vendedor que libere un uso de tu clave.")
        r = self._verificar(clave, sumar_uso=True)
        if fallo := self._fallo(r):
            return fallo
        return Resultado(True, "activa", "Licencia activada.", self._datos(r) | {"instancia": None})

    def validar(self, local: dict) -> Resultado:
        r = self._verificar(local["clave"])
        return self._fallo(r) or Resultado(True, "activa", datos=self._datos(r))

    def desactivar(self, local: dict) -> Resultado:
        return Resultado(True, "desactivada", "Licencia quitada de este equipo. Para activarla en otra computadora, "
                                              "pide al vendedor que libere un uso de tu clave.")


# ============================================================ Polar

class TiendaPolar(Tienda):
    clave = "polar"
    nombre = "Polar"

    def configurada(self) -> bool:
        return bool(self.cfg.polar_organizacion_id)

    def prioridad(self, clave: str) -> int:
        if es_clave_gumroad(clave):
            return 0
        return 2 if es_uuid(clave) else 4    # las de Polar suelen llevar un prefijo propio

    def url_compra(self) -> str:
        return self.cfg.polar_url_compra

    def _post(self, accion: str, cuerpo: dict) -> tuple[int, dict]:
        url = f"{POLAR_API[bool(self.cfg.polar_sandbox)]}/v1/customer-portal/license-keys/{accion}"
        codigo, r = peticion("POST", url, cuerpo, "json")
        return codigo, (r if isinstance(r, dict) else {})

    def _base(self, clave: str) -> dict:
        return {"key": clave, "organization_id": self.cfg.polar_organizacion_id}

    def _validar(self, clave: str, activacion: str | None = None) -> tuple[int, dict]:
        cuerpo = self._base(clave)
        if activacion:
            cuerpo["activation_id"] = activacion
        if self.cfg.polar_beneficio_id:
            cuerpo["benefit_id"] = self.cfg.polar_beneficio_id
        return self._post("validate", cuerpo)

    def _datos(self, lk: dict) -> dict:
        cliente = lk.get("customer") or {}
        return {"cliente": cliente.get("name") or cliente.get("email") or "", "correo": cliente.get("email") or "",
                "producto": "", "expira_ts": iso_a_ts(lk.get("expires_at")), "limite": lk.get("limit_activations"),
                "usados": None, "polar_id": lk.get("id")}

    def _vencida(self, lk: dict) -> bool:
        ts = iso_a_ts(lk.get("expires_at"))
        return bool(ts and ts < time.time())

    def activar(self, clave: str, nombre_equipo: str, meta: dict) -> Resultado:
        codigo, r = self._post("activate", self._base(clave) | {"label": nombre_equipo[:100],
                                                                 "meta": {k: str(v)[:500] for k, v in meta.items()}})
        if codigo in (200, 201):
            lk = r.get("license_key") or {}
            if self.cfg.polar_beneficio_id and lk.get("benefit_id") != self.cfg.polar_beneficio_id:
                self._post("deactivate", self._base(clave) | {"activation_id": r.get("id")})
                return self.otra()
            return Resultado(True, "activa", "Licencia activada.", self._datos(lk) | {"instancia": r.get("id")})
        if codigo == 403:
            # Sin permiso para activar: o se llenó el límite de equipos, o la clave no usa activaciones,
            # o fue revocada/bloqueada/venció. La validación (sin activar) dice cuál es.
            vcodigo, v = self._validar(clave)
            if vcodigo == 200:
                if v.get("limit_activations"):
                    return Resultado(False, "en_uso")
                return Resultado(True, "activa", "Licencia activada.", self._datos(v) | {"instancia": None})
            return Resultado(False, "revocada", "Esta licencia ya no es válida: fue revocada (por ejemplo, por un "
                                                "reembolso), bloqueada o venció. Contacta al vendedor.")
        if codigo in (404, 422):
            return Resultado(False, "invalida")
        return Resultado(False, "error", str(r.get("detail") or MENSAJES["error"]))

    def validar(self, local: dict) -> Resultado:
        activacion = local.get("instancia")
        codigo, r = self._validar(local["clave"], activacion)
        if codigo == 200:
            if self._vencida(r):
                return Resultado(False, "vencida")
            return Resultado(True, "activa", datos=self._datos(r))
        if codigo == 404:
            if activacion:      # ¿la clave sigue bien y solo se quitó este equipo?
                codigo2, r2 = self._validar(local["clave"])
                if codigo2 == 200:
                    return Resultado(False, "desactivada")
            if local.get("expira_ts") and local["expira_ts"] < time.time():
                return Resultado(False, "vencida")
            return Resultado(False, "revocada", "Esta licencia ya no es válida: fue revocada (por ejemplo, por un "
                                                "reembolso) o bloqueada por el vendedor.")
        if codigo == 422:
            return Resultado(False, "invalida")
        return Resultado(False, "error", str(r.get("detail") or MENSAJES["error"]))

    def desactivar(self, local: dict) -> Resultado:
        if local.get("instancia"):
            codigo, r = self._post("deactivate", self._base(local["clave"]) | {"activation_id": local["instancia"]})
            if codigo not in (200, 204, 404):
                return Resultado(False, "error", str(r.get("detail") or MENSAJES["error"]))
        return Resultado(True, "desactivada",
                         "Licencia desactivada en este equipo. Ya puedes activarla en otra computadora.")


TIENDAS = (TiendaLemonSqueezy, TiendaGumroad, TiendaPolar)
NOMBRES = {t.clave: t.nombre for t in TIENDAS}
