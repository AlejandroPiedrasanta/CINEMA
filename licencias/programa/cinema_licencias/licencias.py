"""Cinema Productions · cinema_licencias — la clase Licencias (lo único que tu programa necesita).

    from cinema_licencias import Licencias
    lic = Licencias.desde_json("cinema_licencias.json")

    r = lic.comprobar()        # ¿puede funcionar? → Resultado(ok, codigo, mensaje, datos, avisos)
    r = lic.activar(clave)     # activa la clave en este equipo
    r = lic.desactivar()       # libera este equipo

    # Con PySide6:
    if not lic.exigir():       # ventana de activación si hace falta
        sys.exit(0)
    lic.vigilar(ventana)       # avisos del vendedor, cierre automático si hay reembolso o bloqueo

Creado por Cinema Productions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import platform
import re
import threading
import time
import urllib.parse
from pathlib import Path

from .base import MENSAJES, SUSPENSION, ESTADO_SERVIDOR, Resultado, SinConexion, carpeta_datos, id_equipo, \
    nombre_sistema
from .config import Configuracion
from .servidor import ClienteServidor, Vigilante
from .tiendas import TIENDAS

__author__ = "Cinema Productions"


def _slug(texto: str) -> str:
    return re.sub(r"[^\w\- ]", "", texto or "Programa").strip() or "Programa"


class Licencias:
    def __init__(self, config: Configuracion | dict | str | Path | None = None, **opciones):
        if isinstance(config, (str, Path)):
            config = Configuracion.desde_json(config)
        elif isinstance(config, dict):
            config = Configuracion.desde_dict(config)
        elif config is None:
            config = Configuracion()
        if opciones:
            if "ls_productos" in opciones:
                opciones["ls_productos"] = tuple(int(p) for p in opciones["ls_productos"] or ())
            config = config.con(**opciones)
            config.verificar_sin_secretos()
        self.cfg: Configuracion = config
        self.tiendas = {t.clave: t(config) for t in TIENDAS}
        self.servidor = ClienteServidor(self) if config.servidor_url and config.servidor_clave else None
        self._lock = threading.RLock()
        self._equipo: str | None = None
        self.vigilante: Vigilante | None = None

    @classmethod
    def desde_json(cls, ruta: str | Path, **opciones) -> "Licencias":
        return cls(Configuracion.desde_json(ruta), **opciones)

    # ---------------------------------------------------------------- equipo y carpeta
    @property
    def carpeta(self) -> Path:
        if self.cfg.carpeta:
            return Path(self.cfg.carpeta)
        return carpeta_datos() / "Cinema Productions" / _slug(self.cfg.app)

    @property
    def archivo(self) -> Path:
        return self.carpeta / "licencia.dat"

    def equipo_id(self) -> str:
        if not self._equipo:
            self._equipo = id_equipo(self.cfg.prefijo_equipo)
        return self._equipo

    @staticmethod
    def nombre_pc() -> str:
        return platform.node() or "Equipo"

    def nombre_equipo(self) -> str:
        """Nombre con el que el equipo aparece en la tienda y en el Administrador: 'PC-JUAN · 3F2A-…'."""
        return f"{self.nombre_pc()} · {self.equipo_id()}"[:100]

    def _meta(self) -> dict:
        return {"equipo": self.equipo_id(), "so": nombre_sistema(), "app": self.cfg.app,
                "version": self.cfg.version}

    # ---------------------------------------------------------------- licencia guardada
    def _firma(self, datos: dict) -> str:
        texto = json.dumps(datos, sort_keys=True).encode()
        llave = hashlib.sha256(self.cfg.sal.encode() + self.equipo_id().encode()).digest()
        return hmac.new(llave, texto, "sha256").hexdigest()

    def _leer(self) -> dict | None:
        try:
            contenido = json.loads(self.archivo.read_text(encoding="utf-8"))
            datos, firma = contenido["datos"], contenido["firma"]
            if not (hmac.compare_digest(firma, self._firma(datos)) and datos.get("equipo") == self.equipo_id()
                    and datos.get("clave")):
                return None
            datos.setdefault("tienda", datos.get("plataforma") or "lemonsqueezy")   # licencias de la versión 4
            if datos["tienda"] == "lemonsqueezy" and not datos.get("instancia"):
                return None
            return datos
        except Exception:  # noqa: BLE001
            return None

    def _guardar(self, datos: dict) -> None:
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.archivo.write_text(json.dumps({"datos": datos, "firma": self._firma(datos)}), encoding="utf-8")

    def _borrar(self) -> None:
        try:
            self.archivo.unlink()
        except FileNotFoundError:
            pass

    def guardada(self) -> dict | None:
        """La licencia activada en este equipo (cliente, correo, tienda, expira_ts…) o None."""
        return self._leer()

    # ---------------------------------------------------------------- información
    def tiendas_activas(self) -> list:
        return [t for t in self.tiendas.values() if t.configurada()]

    def enlaces_compra(self) -> list[tuple[str, str]]:
        return [(t.nombre, t.url_compra()) for t in self.tiendas_activas() if t.url_compra()]

    def enlace_whatsapp(self) -> str:
        texto = (f"Hola, necesito ayuda con mi licencia de {self.cfg.app}.\n"
                 f"Mi ID de equipo: {self.equipo_id()}\nNombre del equipo: {self.nombre_pc()}")
        numero = re.sub(r"\D", "", self.cfg.whatsapp or "")
        return f"https://wa.me/{numero}?text={urllib.parse.quote(texto)}" if numero else ""

    def enlace_correo(self) -> str:
        if not self.cfg.correo_soporte:
            return ""
        asunto = urllib.parse.quote(f"Licencia de {self.cfg.app}")
        cuerpo = urllib.parse.quote(f"Hola, necesito ayuda con mi licencia.\nID de equipo: {self.equipo_id()}")
        return f"mailto:{self.cfg.correo_soporte}?subject={asunto}&body={cuerpo}"

    # ---------------------------------------------------------------- operaciones
    def _sin_configurar(self) -> Resultado | None:
        if not self.tiendas_activas():
            return Resultado(False, "error", "Falta configurar una tienda (Lemon Squeezy, Gumroad o Polar) en "
                                             "cinema_licencias.json.")
        return None

    def _sin_conexion(self, local: dict, e: Exception) -> Resultado:
        """Sin internet: funciona dias_sin_internet días desde la última verificación correcta."""
        transcurrido = time.time() - (local.get("ultima_ok") or 0)
        expira = local.get("expira_ts")
        if local.get("estado") != "suspendida" and 0 <= transcurrido < self.cfg.dias_sin_internet * 86400 \
                and (not expira or time.time() < expira):
            return Resultado(True, "sin_conexion_ok", "Modo sin conexión.", local)
        return Resultado(False, "sin_conexion", f"{e} Conéctate para verificar tu licencia.", local)

    def _estado_servidor(self, local: dict) -> tuple[Resultado | None, list]:
        """Lo que el vendedor fijó en el servidor de control: solo puede quitar, nunca dar licencias."""
        if not self.servidor:
            return None, []
        r = self.servidor.estado(local)
        if not r:
            return None, []
        avisos = r.get("avisos") or []
        estado = str(r.get("estado") or "activa")
        if estado in ESTADO_SERVIDOR:
            codigo = ESTADO_SERVIDOR[estado]
            return Resultado(False, codigo, r.get("motivo") or MENSAJES[codigo]), avisos
        return None, avisos

    def comprobar(self, consultar_servidor: bool = True) -> Resultado:
        """Valida la licencia guardada (al abrir el programa y cada cierto tiempo)."""
        if error := self._sin_configurar():
            return error
        with self._lock:
            local = self._leer()
            if not local:
                return Resultado(False, "sin_licencia")
            tienda = self.tiendas.get(local["tienda"])
            if not tienda or not tienda.configurada():
                return Resultado(False, "otra_tienda", "La licencia guardada es de una tienda que este programa ya "
                                                       "no acepta. Activa una clave nueva.", local)
            suspendida = local.get("estado") == "suspendida"
            try:
                r = tienda.validar(local)
            except SinConexion as e:
                return self._sin_conexion(local, e)
            avisos: list = []
            if consultar_servidor and (r.ok or r.codigo in SUSPENSION):
                # el servidor puede quitar una licencia válida, y cuando la tienda ya la rechazó da el motivo
                # exacto (por ejemplo "reembolsada" en lugar de "revocada")
                bloqueo, avisos = self._estado_servidor(local)
                r = bloqueo or r
            if r.ok:
                datos = local | r.datos | {"ultima_ok": time.time(), "estado": "activa", "motivo": "", "codigo": ""}
                self._guardar(datos)
                if suspendida:
                    return Resultado(True, "reactivada", datos=datos, avisos=avisos)
                return Resultado(True, "activa", datos=datos, avisos=avisos)
            if r.codigo in SUSPENSION:
                # Se conserva la clave: si el vendedor la desbloquea o se cancela el reembolso, vuelve sola.
                local = local | {"ultima_ok": 0, "estado": "suspendida", "motivo": r.mensaje, "codigo": r.codigo}
                self._guardar(local)
                return Resultado(False, r.codigo, r.mensaje, local, avisos)
            return self._sin_conexion(local, Exception(r.mensaje))     # error raro de la tienda: como sin internet

    def activar(self, clave: str) -> Resultado:
        """Activa la clave en este equipo (ocupa uno de los equipos permitidos de la licencia)."""
        if error := self._sin_configurar():
            return error
        clave = (clave or "").strip()
        if not clave:
            return Resultado(False, "error", "Escribe tu clave de licencia.")
        with self._lock:
            local = self._leer()
            if local and local["clave"].strip().upper() == clave.upper():
                # Ya estaba activada aquí: solo se valida, para no gastar otro equipo de la licencia.
                r = self.comprobar()
                if r.ok or r.codigo not in ("desactivada", "sin_conexion"):
                    return r
            if self.servidor:
                info = self.servidor.estado_clave(clave)
                if info and str(info.get("estado") or "activa") in ESTADO_SERVIDOR:
                    codigo = ESTADO_SERVIDOR[info["estado"]]
                    return Resultado(False, codigo, info.get("motivo") or MENSAJES[codigo])
            candidatas = sorted((t for t in self.tiendas_activas() if t.prioridad(clave) > 0),
                                key=lambda t: -t.prioridad(clave))
            primero: Resultado | None = None
            for tienda in candidatas:
                try:
                    r = tienda.activar(clave, self.nombre_equipo(), self._meta())
                except SinConexion as e:
                    return Resultado(False, "sin_conexion", f"{e} Se necesita internet para activar.")
                if r.ok:
                    datos = {"tienda": tienda.clave, "clave": clave, "equipo": self.equipo_id(), **r.datos,
                             "ultima_ok": time.time(), "estado": "activa", "activada": time.time()}
                    self._guardar(datos)
                    if self.servidor:
                        self.servidor.evento(datos, "activacion", tienda.nombre)
                    return Resultado(True, "activa", "Licencia activada.", datos)
                if r.codigo not in ("invalida", "otra_tienda"):
                    return r
                primero = primero or r
            return primero or Resultado(False, "invalida")

    def desactivar(self) -> Resultado:
        """Libera este equipo para que el cliente pueda activar la licencia en otra computadora."""
        with self._lock:
            local = self._leer()
            if not local:
                self._borrar()
                return Resultado(True, "sin_licencia", "Este equipo no tenía una licencia activada.")
            tienda = self.tiendas.get(local["tienda"])
            try:
                r = tienda.desactivar(local) if tienda else Resultado(True, "desactivada")
            except SinConexion as e:
                return Resultado(False, "sin_conexion", f"{e} Se necesita internet para desactivar.")
            if r.ok:
                if self.servidor:
                    self.servidor.evento(local, "desactivacion", "")
                self._borrar()
            return r

    # ---------------------------------------------------------------- vigilancia
    def iniciar_vigilancia(self, al_cambiar=None, al_aviso=None, **opciones) -> Vigilante:
        """Revisa la licencia en segundo plano mientras el programa está abierto (sin Qt)."""
        if self.vigilante and self.vigilante.is_alive():
            self.vigilante.detener()
        self.vigilante = Vigilante(self, al_cambiar, al_aviso, **opciones)
        self.vigilante.start()
        import atexit
        atexit.register(self.vigilante.detener)
        return self.vigilante

    # ---------------------------------------------------------------- ventanas (PySide6)
    def exigir(self, parent=None) -> bool:
        """Comprueba la licencia; si no es válida muestra la ventana de activación.
        Devuelve True si el programa puede continuar."""
        from .qt import exigir_licencia
        return exigir_licencia(self, parent)

    def mostrar_mi_licencia(self, parent=None) -> bool:
        """Ventana "Mi licencia". Devuelve True si el cliente desactivó la licencia (cierra tu programa)."""
        from .qt import mostrar_mi_licencia
        return mostrar_mi_licencia(self, parent)

    def vigilar(self, ventana=None, **opciones):
        """Vigila la licencia con Qt: muestra los avisos del vendedor y, si la licencia deja de valer
        (reembolso, bloqueo, retirada), avisa, cierra el programa y pide una licencia. Si después vuelve
        a valer (se canceló el reembolso, el vendedor la reactivó) el programa se abre de nuevo."""
        from .qt import VigilanteQt
        return VigilanteQt(self, ventana, **opciones)
