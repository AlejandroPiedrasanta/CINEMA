"""Cinema Productions · Administrador de Licencias — configuración y modelo de datos.

Junta lo que llega de cada plataforma (Lemon Squeezy, Hotmart, Gumroad, Polar) y del servidor de
control (tiempo de uso, equipos, avisos) en un solo modelo: personas, licencias, equipos, ventas.

Creado por Cinema Productions.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from temas import TEMAS, TEMA_POR_DEFECTO  # noqa: F401  (también prepara la ruta del SDK)
from cinema_licencias.base import carpeta_datos, hash_licencia
from cinema_licencias.config import Configuracion
from control import ServidorControl
from plataformas import (ESTADOS_LICENCIA, PLATAFORMAS, Gumroad, Hotmart, LemonSqueezy, Polar, instancias_polar,
                         licencia_polar)

__author__ = "Cinema Productions"

APP_TITULO = "Administrador de Licencias"
MARCA = "Cinema Productions"
VERSION = "5.0"
CARPETA_CONFIG = carpeta_datos() / "Cinema Productions" / "Administrador de Licencias"
CARPETA_V4 = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "RCS-Administrador"
INTERVALOS = [("15 segundos", 15), ("30 segundos", 30), ("1 minuto", 60), ("5 minutos", 300)]
ESCALAS = [("80 %", 0.8), ("90 %", 0.9), ("100 %", 1.0), ("110 %", 1.1), ("125 %", 1.25), ("150 %", 1.5),
           ("175 %", 1.75), ("200 %", 2.0)]
VELOCIDADES = [("Rápidas", 0.6), ("Normales", 1.0), ("Suaves", 1.4)]
EN_LINEA_MIN = 12           # minutos desde el último latido para considerar un equipo "en línea"
REEMBOLSOS = ("Reembolsada", "Contracargo", "En disputa")
PLATAFORMAS_LICENCIA = ("lemonsqueezy", "gumroad", "polar")


# ============================================================ configuración

def archivo_config() -> Path:
    return CARPETA_CONFIG / "config.json"


def config_base() -> dict:
    return {
        "version": 5, "nombre_app": "Resolve Creator Subtitles", "intervalo": 30,
        # apariencia
        "tema": TEMA_POR_DEFECTO, "escala": 1.0, "densidad": "normal", "animaciones": True, "velocidad": 1.0,
        "nav_plegada": False,
        # privacidad y notificaciones
        "privacidad": False, "privacidad_claves": False, "notificaciones": True, "bandeja": True,
        "cerrar_a_bandeja": False,
        # control automático de licencias
        "auto_bloquear_reembolsos": True, "auto_reactivar": True, "avisar_al_bloquear": True,
        # tu programa
        "whatsapp_soporte": "", "correo_soporte": "", "aceptar_pruebas": True, "gumroad_max_equipos": 1,
        # datos guardados
        "telefonos": {}, "notas": {}, "etiquetas": {}, "auto_bloqueadas": {}, "remociones": {},
        "servidor": {}, "plataformas": {k: {} for k in PLATAFORMAS},
    }


def cargar_config() -> dict:
    cfg = config_base()
    guardado = None
    for ruta in (archivo_config(), CARPETA_V4 / "config.json"):     # la versión 4 guardaba en RCS-Administrador
        try:
            guardado = json.loads(ruta.read_text(encoding="utf-8"))
            break
        except Exception:  # noqa: BLE001
            continue
    if guardado is None:
        try:   # versión 2 (solo Lemon Squeezy)
            v2 = json.loads((CARPETA_V4 / "config_lemonsqueezy.json").read_text(encoding="utf-8"))
            if v2.get("api_key"):
                cfg["plataformas"]["lemonsqueezy"] = {k: v2.get(k) for k in (
                    "api_key", "tienda_id", "tienda_nombre", "tienda_url", "moneda", "producto_id",
                    "producto_nombre", "url_compra")}
            cfg["nombre_app"] = v2.get("nombre_app") or cfg["nombre_app"]
            cfg["telefonos"] = v2.get("telefonos") or {}
        except Exception:  # noqa: BLE001
            pass
        return cfg
    for k, v in guardado.items():
        if k == "plataformas":
            for p, datos in (v or {}).items():
                cfg["plataformas"][p] = datos or {}
        else:
            cfg[k] = v
    if cfg.get("tema") not in TEMAS:
        cfg["tema"] = TEMA_POR_DEFECTO
    cfg["version"] = 5
    return cfg


def guardar_config(cfg: dict) -> None:
    CARPETA_CONFIG.mkdir(parents=True, exist_ok=True)
    archivo_config().write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# ============================================================ datos para tu programa

def config_programa(cfg: dict) -> dict:
    """Contenido de cinema_licencias.json (solo datos PÚBLICOS: nunca API keys ni tokens)."""
    pl = cfg["plataformas"]
    ls, gr, po = pl.get("lemonsqueezy") or {}, pl.get("gumroad") or {}, pl.get("polar") or {}
    sv = cfg.get("servidor") or {}
    tema = TEMAS.get(cfg.get("tema"), TEMAS[TEMA_POR_DEFECTO])
    datos = {
        "app": cfg.get("nombre_app") or "Mi programa", "version": "1.0.0",
        "lemonsqueezy": {"tienda_id": int(ls.get("tienda_id") or 0) if ls.get("api_key") else 0,
                         "productos": [ls["producto_id"]] if ls.get("api_key") and ls.get("producto_id") else [],
                         "url_compra": (ls.get("url_compra") or ls.get("tienda_url") or "") if ls.get("api_key") else ""},
        "gumroad": {"producto_id": (gr.get("producto_id") or "") if gr.get("token") else "",
                    "max_equipos": int(cfg.get("gumroad_max_equipos", 1) or 0),
                    "url_compra": (gr.get("url_compra") or "") if gr.get("token") else ""},
        "polar": {"organizacion_id": (po.get("organizacion_id") or "") if po.get("token") else "",
                  "beneficio_id": (po.get("beneficio_id") or "") if po.get("token") else "",
                  "url_compra": (po.get("url_compra") or "") if po.get("token") else "",
                  "sandbox": bool(po.get("sandbox"))},
        "servidor": {"url": sv.get("url") or "", "clave_publica": sv.get("clave_publica") or ""},
        "soporte": {"whatsapp": cfg.get("whatsapp_soporte") or "", "correo": cfg.get("correo_soporte") or ""},
        "opciones": {"dias_sin_internet": 7, "aceptar_pruebas": bool(cfg.get("aceptar_pruebas", True)),
                     "revisar_cada_min": 30, "latido_cada_min": 5, "segundos_antes_de_cerrar": 12,
                     "telemetria": True, "enviar_nombre_equipo": True},
        "apariencia": {"marca": True, "tema": "oscuro" if tema["oscuro"] else "claro",
                       "color_acento": tema["acento"]},
    }
    Configuracion.desde_dict(datos)          # valida: lanza ValueError si se coló una clave secreta
    return datos


def texto_config_programa(cfg: dict) -> str:
    return json.dumps(config_programa(cfg), indent=2, ensure_ascii=False)


def datos_para_programa(ls: dict, gr: dict | None = None, po: dict | None = None, sv: dict | None = None) -> str:
    """Líneas para la sección CONFIGURACIÓN de licencia_cliente.py (forma de la versión 4)."""
    productos = f"({ls['producto_id']},)" if ls.get("producto_id") else "()"
    url = ls.get("url_compra") or ls.get("tienda_url") or ""
    texto = (f"TIENDA_ID = {ls.get('tienda_id') or 0}\n"
             f"PRODUCTOS_ID = {productos}\n"
             f"URL_COMPRA = \"{url}\"")
    if gr and gr.get("token"):
        texto += (f"\nGUMROAD_PRODUCTO_ID = \"{gr.get('producto_id') or ''}\"\n"
                  f"URL_COMPRA_GUMROAD = \"{gr.get('url_compra') or ''}\"")
    if po and po.get("token"):
        texto += (f"\nPOLAR_ORGANIZACION_ID = \"{po.get('organizacion_id') or ''}\"\n"
                  f"POLAR_BENEFICIO_ID = \"{po.get('beneficio_id') or ''}\"\n"
                  f"URL_COMPRA_POLAR = \"{po.get('url_compra') or ''}\"")
        if po.get("sandbox"):
            texto += "\nPOLAR_SANDBOX = True"
    if sv and sv.get("url") and sv.get("clave_publica"):
        texto += (f"\nSERVIDOR_URL = \"{sv['url']}\"\n"
                  f"SERVIDOR_CLAVE_PUBLICA = \"{sv['clave_publica']}\"")
    return texto


# ============================================================ utilidades

def a_fecha(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        f = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (f if f.tzinfo else f.replace(tzinfo=timezone.utc)).astimezone()
    except ValueError:
        return None


def fmt_fecha(iso: str | None, hora=True) -> str:
    f = a_fecha(iso)
    return f.strftime("%d/%m/%Y %H:%M" if hora else "%d/%m/%Y") if f else "—"


def hace(iso: str | None) -> str:
    f = a_fecha(iso)
    if not f:
        return "—"
    s = int((datetime.now(timezone.utc) - f).total_seconds())
    if s < 60:
        return "hace un momento"
    if s < 3600:
        return f"hace {s // 60} min"
    if s < 86400:
        return f"hace {s // 3600} h"
    if s < 86400 * 30:
        return f"hace {s // 86400} días"
    return fmt_fecha(iso, hora=False)


def duracion(segundos: float | int | None) -> str:
    """3725 → '1 h 2 min'."""
    s = int(segundos or 0)
    if s <= 0:
        return "—"
    if s < 60:
        return f"{s} s"
    h, m = divmod(s // 60, 60)
    if h >= 100:
        return f"{h:,} h"
    return f"{h} h {m} min" if h else f"{m} min"


def solo_digitos(tel: str) -> str:
    return re.sub(r"\D", "", tel or "")


def partir_instancia(nombre: str) -> tuple[str, str]:
    """'PC-JUAN · 3F2A-91BC-04DE-77A1' → ('PC-JUAN', '3F2A-91BC-04DE-77A1')."""
    pc, _, equipo = (nombre or "").partition(" · ")
    return pc, equipo


def estado_licencia(lic: dict) -> str:
    if lic.get("estado_srv") in ("suspendida", "revocada", "reembolsada") and lic.get("status") in ("active",
                                                                                                       "inactive"):
        return {"suspendida": "Suspendida", "revocada": "Retirada", "reembolsada": "Reembolsada"}[lic["estado_srv"]]
    return ESTADOS_LICENCIA.get(lic.get("status"), lic.get("status_formatted") or "—")


def nombre_plataforma(clave: str) -> str:
    p = PLATAFORMAS.get(clave) or {}
    return f"{p.get('icono', '')} {p.get('nombre', clave)}".strip()


def _ok(r) -> dict:
    return r if isinstance(r, dict) and "error" not in r else {}


# ============================================================ carga y modelo

def cargar_todo(clientes: dict, cfg: dict) -> dict:
    """Se ejecuta en segundo plano: trae los datos de cada plataforma conectada y del servidor de control.
    Un error en una plataforma no impide ver las demás."""
    resultado = {}
    for clave, cliente in clientes.items():
        pc = cfg["plataformas"].get(clave) or {}
        try:
            if isinstance(cliente, LemonSqueezy):
                resultado[clave] = cliente.datos(pc.get("tienda_id"), pc.get("producto_id") or 0)
            elif isinstance(cliente, Hotmart):
                resultado[clave] = {"ventas": cliente.ventas(pc.get("producto_id") or 0)}
            elif isinstance(cliente, Gumroad):
                resultado[clave] = {"ventas": cliente.ventas(pc.get("producto_id") or ""),
                                    "bloqueadas": sorted(pc.get("bloqueadas") or [])}
            elif isinstance(cliente, Polar):
                resultado[clave] = cliente.datos(pc.get("organizacion_id") or "", pc.get("producto_id") or "",
                                                 pc.get("beneficio_id") or "")
            elif isinstance(cliente, ServidorControl):
                resultado[clave] = cliente.datos()
        except Exception as e:  # noqa: BLE001
            resultado[clave] = {"error": str(e)}
    return resultado


def construir_modelo(resultados: dict) -> dict:
    ls, hm, gr = (_ok(resultados.get(k)) for k in ("lemonsqueezy", "hotmart", "gumroad"))
    po, tel = _ok(resultados.get("polar")), _ok(resultados.get("control"))

    # ---- licencias de las tres plataformas que generan claves
    licencias = [l | {"plataforma": "lemonsqueezy"} for l in ls.get("licencias") or []]
    bloqueadas = set(gr.get("bloqueadas") or [])
    for v in gr.get("ventas") or []:         # cada venta de Gumroad con clave es una licencia
        clave = v.get("clave_licencia")
        if not clave:
            continue
        estado = "disabled" if clave in bloqueadas else ("active" if v["valida"] else "refunded")
        licencias.append({"id": f"lic-{v['id']}", "plataforma": "gumroad", "key": clave, "status": estado,
                          "disabled": clave in bloqueadas, "user_name": v["cliente"], "user_email": v["correo"],
                          "created_at": v["fecha"], "expires_at": None, "test_mode": v["prueba"],
                          "producto_id": v.get("producto_id"), "venta_id": v["id"]})
    instancias_po = []
    detalles = po.get("detalles") or {}
    for k in po.get("claves") or []:
        licencias.append(licencia_polar(k, detalles.get(k["id"]), po.get("sandbox", False)))
        instancias_po += instancias_polar(k, detalles.get(k["id"]))
    licencias.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    instancias = sorted([i | {"plataforma": "lemonsqueezy"} for i in ls.get("instancias") or []] + instancias_po,
                        key=lambda x: x.get("created_at") or "", reverse=True)
    ventas = sorted((ls.get("ventas") or []) + (hm.get("ventas") or []) + (gr.get("ventas") or [])
                    + (po.get("ventas") or []), key=lambda v: v["fecha"] or "", reverse=True)
    venta_por_pedido = {v["id"]: v for v in ventas}
    por_licencia: dict = {}
    for i in instancias:
        por_licencia.setdefault(i["license_key_id"], []).append(i)

    # ---- compra de cada licencia: ¿se reembolsó?
    polar_por_cliente: dict = {}
    for v in ventas:
        if v["plataforma"] == "polar" and v.get("cliente_id"):
            polar_por_cliente.setdefault(v["cliente_id"], []).append(v)
    for lic in licencias:
        if lic["plataforma"] == "lemonsqueezy":
            compras = [venta_por_pedido[f"ls-{lic.get('order_id')}"]] if f"ls-{lic.get('order_id')}" in venta_por_pedido \
                else []
        elif lic["plataforma"] == "gumroad":
            compras = [venta_por_pedido[lic["venta_id"]]] if lic.get("venta_id") in venta_por_pedido else []
        else:
            compras = polar_por_cliente.get(lic.get("cliente_id")) or []
        lic["compras"] = [c["id"] for c in compras]
        lic["compra_valida"] = any(c["valida"] for c in compras)
        lic["reembolsada"] = bool(compras) and not lic["compra_valida"] and any(c["estado"] in REEMBOLSOS
                                                                                for c in compras)
        lic["hash"] = hash_licencia(lic["key"]) if lic.get("key") else ""
    lic_por_hash = {l["hash"]: l for l in licencias if l["hash"]}

    # ---- servidor de control: equipos, tiempo de uso, estados y avisos
    ahora = datetime.now(timezone.utc)
    estados_srv = {e["licencia"]: e for e in tel.get("estados") or []}
    equipos_tel, tel_por_hash = [], {}
    for e in tel.get("equipos") or []:
        lic = lic_por_hash.get(e.get("licencia"))
        ultima = a_fecha(e.get("ultima_vez"))
        fila = dict(e, lic_id=lic["id"] if lic else None,
                    en_linea=bool(ultima and (ahora - ultima).total_seconds() < EN_LINEA_MIN * 60))
        equipos_tel.append(fila)
        tel_por_hash.setdefault(e.get("licencia"), []).append(fila)
    for lic in licencias:
        eqs = tel_por_hash.get(lic["hash"], [])
        lic["uso_seg"] = sum(int(e.get("segundos_uso") or 0) for e in eqs)
        lic["ultima_vez"] = max((e.get("ultima_vez") or "" for e in eqs), default="") or None
        lic["en_linea"] = any(e["en_linea"] for e in eqs)
        lic["equipos_tel"] = len(eqs)
        srv = estados_srv.get(lic["hash"]) or {}
        lic["estado_srv"] = srv.get("estado") or "activa"
        lic["motivo_srv"] = srv.get("motivo") or ""

    # ---- personas (una por correo en todas las plataformas)
    personas: dict = {}

    def persona(nombre: str, correo: str) -> dict:
        clave = (correo or "").strip().lower() or "nombre:" + (nombre or "?").strip().lower()
        p = personas.setdefault(clave, {"clave": clave, "nombre": nombre, "correo": correo, "plataformas": set(),
                                        "compras": 0, "reembolsos": 0, "gastado": {}, "licencias": [], "equipos": 0,
                                        "ventas": [], "ultima": None, "primera": None, "uso_seg": 0,
                                        "ultima_vez": None, "en_linea": False, "equipos_tel": 0})
        p["nombre"] = p["nombre"] or nombre
        p["correo"] = p["correo"] or correo
        return p

    for v in ventas:
        p = persona(v["cliente"], v["correo"])
        p["plataformas"].add(v["plataforma"])
        p["ventas"].append(v["id"])
        if v["valida"]:
            p["compras"] += 1
            if v["total"] is not None:
                p["gastado"][v["moneda"]] = p["gastado"].get(v["moneda"], 0) + v["total"]
        elif v["estado"] in ("Reembolsada", "Contracargo"):
            p["reembolsos"] += 1
        p["ultima"] = max(p["ultima"] or "", v["fecha"] or "") or None
        p["primera"] = min(p["primera"] or "9", v["fecha"] or "9") if v["fecha"] else p["primera"]
    for lic in licencias:
        p = persona(lic.get("user_name") or "", lic.get("user_email") or "")
        p["plataformas"].add(lic["plataforma"])
        p["licencias"].append(lic)
        p["equipos"] += len(por_licencia.get(lic["id"], []))
        p["uso_seg"] += lic["uso_seg"]
        p["equipos_tel"] += lic["equipos_tel"]
        p["en_linea"] = p["en_linea"] or lic["en_linea"]
        if lic["ultima_vez"]:
            p["ultima_vez"] = max(p["ultima_vez"] or "", lic["ultima_vez"])
        lic["persona"] = p["clave"]
    for p in personas.values():
        activa = any(l.get("status") in ("active", "inactive") and l.get("estado_srv") == "activa"
                     for l in p["licencias"])
        p["tiene"] = (p["compras"] > 0 and not any(l.get("estado_srv") != "activa" for l in p["licencias"])) or activa
        if p["tiene"]:
            p["estado"] = "Con el programa"
        elif p["reembolsos"]:
            p["estado"] = "Reembolsada"
        elif p["licencias"]:
            p["estado"] = estado_licencia(p["licencias"][0])
        else:
            p["estado"] = "Sin compra válida"
    lista = sorted(personas.values(), key=lambda p: p["ultima"] or p["ultima_vez"] or "", reverse=True)

    # ---- ventas e ingresos de los últimos 30 días, por plataforma
    hoy = datetime.now().astimezone().date()
    dias = [hoy - timedelta(days=29 - i) for i in range(30)]
    serie = {k: [0.0] * 30 for k in PLATAFORMAS if resultados.get(k) and "error" not in resultados[k]}
    ingresos: dict[str, float] = {}
    for v in ventas:
        f = a_fecha(v["fecha"])
        if not f or not v["valida"]:
            continue
        d = (f.date() - dias[0]).days
        if 0 <= d < 30 and v["plataforma"] in serie:
            serie[v["plataforma"]][d] += 1
            if v["total"] is not None:
                ingresos[v["moneda"]] = ingresos.get(v["moneda"], 0) + v["total"]

    # ---- uso por día (servidor de control)
    activos_dia = [set() for _ in range(30)]
    horas_dia = [0.0] * 30
    for u in tel.get("uso") or []:
        try:
            d = (datetime.fromisoformat(str(u["dia"])).date() - dias[0]).days
        except (KeyError, ValueError):
            continue
        if 0 <= d < 30:
            activos_dia[d].add(u.get("licencia"))
            horas_dia[d] += int(u.get("segundos") or 0) / 3600
    activos_7 = set().union(*activos_dia[-7:]) if activos_dia else set()

    # ---- avisos enviados (con cuántos equipos los leyeron)
    leidos: dict = {}
    for l in tel.get("leidos") or []:
        leidos.setdefault(l.get("aviso"), set()).add((l.get("licencia"), l.get("equipo")))
    avisos = []
    for a in tel.get("avisos") or []:
        lic = lic_por_hash.get(a.get("licencia")) if a.get("licencia") else None
        avisos.append(a | {"leidos": len(leidos.get(a.get("id"), ())), "lic_id": lic["id"] if lic else None,
                           "persona": (lic.get("user_name") or lic.get("user_email")) if lic else ""})

    eventos_srv = []
    for e in tel.get("eventos") or []:
        lic = lic_por_hash.get(e.get("licencia"))
        eventos_srv.append(e | {"lic_id": lic["id"] if lic else None,
                                "persona": (lic.get("user_name") or lic.get("user_email") or "") if lic else ""})

    return {
        "licencias": licencias, "instancias": instancias, "ventas": ventas, "personas": lista,
        "por_licencia": por_licencia, "lic_por_id": {l["id"]: l for l in licencias}, "lic_por_hash": lic_por_hash,
        "persona_por_clave": {p["clave"]: p for p in lista},
        "venta_por_pedido": venta_por_pedido,
        "dias": [d.strftime("%d/%m") for d in dias], "serie": serie, "ingresos_30": ingresos,
        "ventas_30": int(sum(sum(s) for s in serie.values())),
        "control": bool(tel), "equipos_tel": equipos_tel, "avisos": avisos, "eventos_srv": eventos_srv,
        "activos_dia": [len(s) for s in activos_dia], "horas_dia": [round(h, 2) for h in horas_dia],
        "activos_hoy": len(activos_dia[-1]) if activos_dia else 0, "activos_7": len(activos_7),
        "en_linea": sum(1 for e in equipos_tel if e["en_linea"]), "horas_30": round(sum(horas_dia), 1),
        "estados_srv": estados_srv,
    }
