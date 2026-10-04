"""Cinema Productions · cinema_licencias — servidor de control y vigilancia de la licencia.

El servidor de control (Supabase, opcional) permite al vendedor, desde el Administrador:
  - ver cuánto tiempo usan el programa sus clientes y en qué equipos,
  - enviar avisos a una licencia o a todas (por ejemplo, "tu licencia será removida el 15/10"),
  - bloquear, marcar como reembolsada o reactivar una licencia aunque la tienda no lo sepa.

El programa solo usa la clave PUBLICABLE y dos funciones del servidor (cinema_latido y
cinema_aviso_leido). Nunca envía la clave de licencia: envía su huella (hash_licencia).

El Vigilante revisa la licencia cada cierto tiempo mientras el programa está abierto y avisa cuando
deja de ser válida (reembolso, bloqueo…) o cuando vuelve a serlo.

Creado por Cinema Productions.
"""
from __future__ import annotations

import json
import threading
import time
import uuid

from .base import AGENTE, SinConexion, hash_licencia, nombre_sistema, peticion

__author__ = "Cinema Productions"


class ClienteServidor:
    def __init__(self, licencias):
        self.lic = licencias
        cfg = licencias.cfg
        self.url = cfg.servidor_url.rstrip("/")
        self.clave = cfg.servidor_clave

    def _cabeceras(self) -> dict:
        cab = {"apikey": self.clave}
        if self.clave.startswith("eyJ"):     # clave anon antigua (JWT)
            cab["Authorization"] = f"Bearer {self.clave}"
        return cab

    def _rpc(self, funcion: str, p: dict, timeout: float = 8) -> dict | None:
        try:
            codigo, r = peticion("POST", f"{self.url}/rest/v1/rpc/{funcion}", {"p": p}, "json", self._cabeceras(),
                                 timeout=timeout)
        except SinConexion:
            return None
        return r if codigo == 200 and isinstance(r, dict) else ({} if codigo == 204 else None)

    def _base(self, clave: str) -> dict:
        cfg = self.lic.cfg
        datos = {"app": cfg.app, "version": cfg.version, "licencia": hash_licencia(clave),
                 "equipo": self.lic.equipo_id(), "so": nombre_sistema(), "sdk": AGENTE}
        if cfg.enviar_nombre_equipo:
            datos["nombre_equipo"] = self.lic.nombre_pc()
        return datos

    def latido(self, local: dict, sesion: str | None = None, segundos: int = 0, inicio: bool = False,
               fin: bool = False, evento: str | None = None, detalle: str = "", timeout: float = 8) -> dict | None:
        """Envía el uso y devuelve {'estado', 'motivo', 'avisos'} o None si el servidor no respondió."""
        if not local or not local.get("clave"):
            return None
        p = self._base(local["clave"]) | {"tienda": local.get("tienda") or "", "sesion": sesion,
                                          "segundos": int(segundos) if self.lic.cfg.telemetria else 0,
                                          "inicio": inicio, "fin": fin, "evento": evento, "detalle": detalle[:300]}
        return self._rpc("cinema_latido", p, timeout)

    def estado(self, local: dict) -> dict | None:
        return self.latido(local)

    def estado_clave(self, clave: str) -> dict | None:
        return self.latido({"clave": clave})

    def evento(self, local: dict, tipo: str, detalle: str = "") -> None:
        """Registra un evento (activación, desactivación…) sin hacer esperar al programa."""
        threading.Thread(target=self.latido, args=(dict(local),), kwargs={"evento": tipo, "detalle": detalle},
                         daemon=True).start()

    def aviso_leido(self, local: dict, aviso_id) -> None:
        if local and local.get("clave"):
            self._rpc("cinema_aviso_leido", self._base(local["clave"]) | {"aviso": aviso_id})


class Vigilante(threading.Thread):
    """Revisa la licencia mientras el programa está abierto (en segundo plano).

    al_cambiar(resultado) → la licencia dejó de valer (reembolso, bloqueo, vencida…) o volvió a valer.
    al_aviso(aviso)       → llegó un aviso del vendedor: {'id', 'tipo', 'titulo', 'mensaje', 'fecha_limite'}.
    Las funciones se llaman desde el hilo del vigilante (con Qt usa licencias.vigilar(), que ya las
    pasa a la ventana).
    """

    def __init__(self, licencias, al_cambiar=None, al_aviso=None, revisar_min: float | None = None,
                 latido_min: float | None = None, revisar_al_iniciar: bool = False):
        super().__init__(daemon=True, name="cinema-licencias")
        self.lic = licencias
        self.al_cambiar, self.al_aviso = al_cambiar, al_aviso
        self.revisar_s = max(15.0, (revisar_min or licencias.cfg.revisar_cada_min) * 60)
        self.latido_s = max(15.0, (latido_min or licencias.cfg.latido_cada_min) * 60)
        self.revisar_al_iniciar = revisar_al_iniciar
        self.sesion = str(uuid.uuid4())
        self._parar = threading.Event()
        self._ahora = threading.Event()
        self._ultimo_ok: bool | None = None
        self._marca = time.monotonic()
        self._pendiente = self._leer_pendiente()
        self._vistos = self._leer_vistos()
        self._detenido = False

    # ---------------------------------------------------------------- archivos pequeños
    def _ruta(self, nombre: str):
        return self.lic.carpeta / nombre

    def _leer_vistos(self) -> set:
        try:
            return set(json.loads(self._ruta("avisos_vistos.json").read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            return set()

    def _guardar_vistos(self):
        try:
            self.lic.carpeta.mkdir(parents=True, exist_ok=True)
            self._ruta("avisos_vistos.json").write_text(json.dumps(sorted(self._vistos)[-500:]), encoding="utf-8")
        except OSError:
            pass

    def _leer_pendiente(self) -> int:
        try:
            return int(json.loads(self._ruta("uso_pendiente.json").read_text(encoding="utf-8")).get("segundos", 0))
        except Exception:  # noqa: BLE001
            return 0

    def _guardar_pendiente(self, segundos: int):
        try:
            self.lic.carpeta.mkdir(parents=True, exist_ok=True)
            self._ruta("uso_pendiente.json").write_text(json.dumps({"segundos": int(segundos)}), encoding="utf-8")
        except OSError:
            pass

    # ---------------------------------------------------------------- ciclo
    def run(self):
        self._latido(inicio=True)
        if self.revisar_al_iniciar:
            self.revisar_ahora()
        siguiente_revision = time.monotonic() + self.revisar_s
        siguiente_latido = time.monotonic() + self.latido_s
        while not self._parar.is_set():
            espera = max(1.0, min(siguiente_revision, siguiente_latido) - time.monotonic())
            self._ahora.wait(espera)
            if self._parar.is_set():
                break
            pedido = self._ahora.is_set()
            self._ahora.clear()
            ahora = time.monotonic()
            if ahora >= siguiente_latido:
                self._latido()
                siguiente_latido = ahora + self.latido_s
            if pedido or ahora >= siguiente_revision:
                self.revisar_ahora()
                siguiente_revision = time.monotonic() + self.revisar_s

    def revisar_pronto(self):
        """Pide una revisión inmediata (sin esperar al siguiente turno)."""
        self._ahora.set()

    def reiniciar(self, ok: bool = True):
        """Después de volver a activar la licencia desde la ventana."""
        self._ultimo_ok = ok

    def revisar_ahora(self):
        try:
            r = self.lic.comprobar()
        except Exception:  # noqa: BLE001
            return None
        self._procesar_avisos(r.avisos)
        cambio = (self._ultimo_ok is None and not r.ok) or (self._ultimo_ok is not None and r.ok != self._ultimo_ok) \
            or r.codigo == "reactivada"
        anterior, self._ultimo_ok = self._ultimo_ok, r.ok
        if cambio:
            if not r.ok and self.lic.servidor and anterior is not False:
                self.lic.servidor.evento(self.lic.guardada() or {}, "licencia_perdida", r.codigo)
            elif r.codigo == "reactivada" and self.lic.servidor:
                self.lic.servidor.evento(self.lic.guardada() or {}, "reactivada", "")
            if self.al_cambiar:
                self.al_cambiar(r)
        return r

    def _segundos(self) -> int:
        ahora = time.monotonic()
        transcurrido, self._marca = ahora - self._marca, ahora
        # si la computadora estuvo suspendida no se cuenta todo ese tiempo
        return int(min(transcurrido, self.latido_s * 2))

    def _latido(self, inicio: bool = False, fin: bool = False):
        servidor = self.lic.servidor
        segundos = (0 if inicio else self._segundos()) + self._pendiente
        local = self.lic.guardada()
        if not servidor or not local:
            self._pendiente = 0
            return
        r = servidor.latido(local, self.sesion, segundos, inicio=inicio, fin=fin, timeout=4 if fin else 8)
        if r is None:
            self._pendiente = min(segundos, 7 * 86400)
            if fin:
                self._guardar_pendiente(self._pendiente)
            return
        self._pendiente = 0
        if inicio or fin:
            self._guardar_pendiente(0)
        if r.get("estado") not in (None, "", "activa") and self._ultimo_ok is not False and not fin:
            self.revisar_pronto()      # el vendedor la bloqueó/retiró: revisar ya
        self._procesar_avisos(r.get("avisos") or [])

    def _procesar_avisos(self, avisos: list):
        nuevos = [a for a in avisos or [] if isinstance(a, dict) and str(a.get("id")) not in self._vistos]
        if not nuevos:
            return
        for a in nuevos:
            self._vistos.add(str(a.get("id")))
        self._guardar_vistos()
        local = self.lic.guardada() or {}
        for a in nuevos:
            if self.lic.servidor:
                threading.Thread(target=self.lic.servidor.aviso_leido, args=(local, a.get("id")), daemon=True).start()
            if self.al_aviso:
                try:
                    self.al_aviso(a)
                except Exception:  # noqa: BLE001
                    pass

    def detener(self):
        """Envía el último tiempo de uso y termina (se llama al cerrar el programa)."""
        if self._detenido:
            return
        self._detenido = True
        self._parar.set()
        self._ahora.set()
        self._latido(fin=True)
