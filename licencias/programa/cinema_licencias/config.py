"""Cinema Productions · cinema_licencias — configuración de tu programa.

Se puede escribir en código (Configuracion(...)) o en un archivo cinema_licencias.json que crea el
Administrador de Licencias (Conexiones → Datos para tu programa → Guardar archivo). Solo lleva datos
PÚBLICOS: IDs de tienda/producto y la clave publicable del servidor. Nunca una API key secreta.

Creado por Cinema Productions.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

__author__ = "Cinema Productions"

@dataclass(frozen=True)
class Configuracion:
    # --- tu programa
    app: str = "Mi programa"
    version: str = "1.0.0"
    # --- Lemon Squeezy (0 si no lo usas)
    ls_tienda_id: int = 0
    ls_productos: tuple = ()              # IDs de producto aceptados; vacío = cualquiera de tu tienda
    ls_url_compra: str = ""
    # --- Gumroad ("" si no lo usas)
    gumroad_producto_id: str = ""
    gumroad_max_equipos: int = 1          # computadoras por clave (0 = sin límite)
    gumroad_url_compra: str = ""
    # --- Polar ("" si no lo usas)
    polar_organizacion_id: str = ""
    polar_beneficio_id: str = ""          # opcional: acepta solo las claves de ese beneficio
    polar_url_compra: str = ""
    polar_sandbox: bool = False
    # --- servidor de control (Supabase): avisos, bloqueos y tiempo de uso. Opcional.
    servidor_url: str = ""                # https://xxxx.supabase.co
    servidor_clave: str = ""              # clave PUBLICABLE (sb_publishable_… o anon). Nunca la secreta.
    telemetria: bool = True               # enviar tiempo de uso y equipo (sin datos personales)
    enviar_nombre_equipo: bool = True     # el nombre de la PC ayuda a reconocer el equipo en el panel
    # --- soporte
    whatsapp: str = ""                    # número con código de país, p. ej. "50255551234"
    correo_soporte: str = ""
    # --- comportamiento
    dias_sin_internet: int = 7            # días que funciona sin conexión tras la última verificación
    aceptar_pruebas: bool = True          # claves de compras de prueba. Pon False al vender de verdad
    revisar_cada_min: int = 30            # cada cuánto se revisa la licencia mientras el programa está abierto
    latido_cada_min: int = 5              # cada cuánto se envía el tiempo de uso al servidor
    segundos_antes_de_cerrar: int = 12    # cuenta regresiva antes de cerrar el programa si se pierde la licencia
    carpeta: str = ""                     # dónde se guarda la licencia (por defecto en la carpeta del usuario)
    sal: str = "cinema-productions-licencias-v1"
    prefijo_equipo: str = "CP"
    # --- apariencia de las ventanas
    marca: bool = True                    # pie "Licencias · Cinema Productions" en las ventanas
    tema: str = "oscuro"                  # "oscuro" | "claro"
    color_acento: str = "#e50914"

    # ------------------------------------------------------------ lectura y escritura
    @classmethod
    def desde_dict(cls, d: dict) -> "Configuracion":
        """Acepta el formato del archivo JSON (con secciones) o los nombres de campo directos."""
        d = dict(d or {})
        plano: dict = {}
        ls, gr, po = d.pop("lemonsqueezy", None) or {}, d.pop("gumroad", None) or {}, d.pop("polar", None) or {}
        sv, so, op = d.pop("servidor", None) or {}, d.pop("soporte", None) or {}, d.pop("opciones", None) or {}
        ap = d.pop("apariencia", None) or {}
        plano |= {"ls_tienda_id": ls.get("tienda_id"), "ls_productos": ls.get("productos"),
                  "ls_url_compra": ls.get("url_compra")}
        plano |= {"gumroad_producto_id": gr.get("producto_id"), "gumroad_max_equipos": gr.get("max_equipos"),
                  "gumroad_url_compra": gr.get("url_compra")}
        plano |= {"polar_organizacion_id": po.get("organizacion_id"), "polar_beneficio_id": po.get("beneficio_id"),
                  "polar_url_compra": po.get("url_compra"), "polar_sandbox": po.get("sandbox")}
        plano |= {"servidor_url": sv.get("url"), "servidor_clave": sv.get("clave_publica")}
        plano |= {"whatsapp": so.get("whatsapp"), "correo_soporte": so.get("correo")}
        plano |= {k: v for k, v in (op | ap).items()}
        plano |= d
        nombres = {f.name for f in fields(cls)}
        limpio = {k: v for k, v in plano.items() if k in nombres and v is not None}
        if "ls_productos" in limpio:
            limpio["ls_productos"] = tuple(int(p) for p in (limpio["ls_productos"] or ()))
        for k in ("ls_tienda_id", "gumroad_max_equipos", "dias_sin_internet", "revisar_cada_min",
                  "latido_cada_min", "segundos_antes_de_cerrar"):
            if k in limpio:
                limpio[k] = int(limpio[k] or 0)
        cfg = cls(**limpio)
        cfg.verificar_sin_secretos()
        return cfg

    @classmethod
    def desde_json(cls, ruta: str | Path) -> "Configuracion":
        return cls.desde_dict(json.loads(Path(ruta).read_text(encoding="utf-8")))

    def con(self, **cambios) -> "Configuracion":
        return replace(self, **cambios)

    def a_dict(self) -> dict:
        """Formato con secciones (el mismo del archivo cinema_licencias.json)."""
        c = asdict(self)
        return {
            "app": c["app"], "version": c["version"],
            "lemonsqueezy": {"tienda_id": c["ls_tienda_id"], "productos": list(c["ls_productos"]),
                             "url_compra": c["ls_url_compra"]},
            "gumroad": {"producto_id": c["gumroad_producto_id"], "max_equipos": c["gumroad_max_equipos"],
                        "url_compra": c["gumroad_url_compra"]},
            "polar": {"organizacion_id": c["polar_organizacion_id"], "beneficio_id": c["polar_beneficio_id"],
                      "url_compra": c["polar_url_compra"], "sandbox": c["polar_sandbox"]},
            "servidor": {"url": c["servidor_url"], "clave_publica": c["servidor_clave"]},
            "soporte": {"whatsapp": c["whatsapp"], "correo": c["correo_soporte"]},
            "opciones": {k: c[k] for k in ("dias_sin_internet", "aceptar_pruebas", "revisar_cada_min",
                                           "latido_cada_min", "segundos_antes_de_cerrar", "telemetria",
                                           "enviar_nombre_equipo")},
            "apariencia": {k: c[k] for k in ("marca", "tema", "color_acento")},
        }

    def guardar_json(self, ruta: str | Path) -> None:
        Path(ruta).write_text(json.dumps(self.a_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def verificar_sin_secretos(self) -> None:
        """Evita el error más grave: meter una clave secreta dentro del programa que reciben los clientes."""
        clave = self.servidor_clave or ""
        if clave.startswith("sb_secret_") or "service_role" in _rol_jwt(clave):
            raise ValueError("servidor_clave debe ser la clave PUBLICABLE de Supabase (sb_publishable_… o anon), "
                             "nunca la secreta (sb_secret_… o service_role).")
        for nombre in ("ls_url_compra", "gumroad_url_compra", "polar_url_compra", "polar_organizacion_id",
                       "gumroad_producto_id"):
            valor = str(getattr(self, nombre) or "")
            if valor.startswith(("polar_oat_", "sb_secret_")) or valor.startswith("eyJ0eXAiOiJKV1Qi"):
                raise ValueError(f"{nombre} parece una clave secreta. Tu programa no debe llevar claves secretas.")

    # ------------------------------------------------------------ ayudas
    def tiendas(self) -> list[str]:
        t = []
        if self.ls_tienda_id:
            t.append("lemonsqueezy")
        if self.gumroad_producto_id:
            t.append("gumroad")
        if self.polar_organizacion_id:
            t.append("polar")
        return t


def _rol_jwt(clave: str) -> str:
    """Lee el 'role' de una clave JWT antigua de Supabase (anon o service_role) sin verificarla."""
    import base64
    partes = clave.split(".")
    if len(partes) != 3:
        return ""
    try:
        relleno = partes[1] + "=" * (-len(partes[1]) % 4)
        return str(json.loads(base64.urlsafe_b64decode(relleno)).get("role") or "")
    except Exception:  # noqa: BLE001
        return ""
