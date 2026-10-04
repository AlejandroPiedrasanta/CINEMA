"""Conexión con las plataformas de venta: Lemon Squeezy, Hotmart y Gumroad.

Sin dependencias externas (solo urllib), para que el Administrador funcione igual en
Windows, macOS y Linux. Todas las llamadas son bloqueantes: la interfaz las ejecuta en
segundo plano.
"""
from __future__ import annotations

import base64
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

AGENTE = "RCS-Administrador/4.0"
LS_API = "https://api.lemonsqueezy.com/v1/"
HOTMART_AUTH = "https://api-sec-vlc.hotmart.com/security/oauth/token"
HOTMART_API = {False: "https://developers.hotmart.com", True: "https://sandbox.hotmart.com"}
HOTMART_DESDE_MS = 1420070400000          # 01/01/2015: para traer todo el historial de ventas
GUMROAD_API = "https://api.gumroad.com/v2/"

PLATAFORMAS = {
    "lemonsqueezy": {"nombre": "Lemon Squeezy", "icono": "🍋", "color": "#facc15",
                     "descripcion": "Licencias, equipos activados y ventas.",
                     "ayuda_url": "https://app.lemonsqueezy.com/settings/api"},
    "hotmart": {"nombre": "Hotmart", "icono": "🔥", "color": "#f97316",
                "descripcion": "Ventas y compradores de tu producto.",
                "ayuda_url": "https://app.hotmart.com"},
    "gumroad": {"nombre": "Gumroad", "icono": "🛍️", "color": "#ff90e8",
                "descripcion": "Ventas, compradores y claves de licencia.",
                "ayuda_url": "https://app.gumroad.com/settings/advanced"},
}

ESTADOS_LICENCIA = {"active": "Activa", "inactive": "Sin activar", "expired": "Vencida", "disabled": "Bloqueada",
                    "refunded": "Reembolsada"}
ESTADOS_LS = {"paid": "Pagada", "refunded": "Reembolsada", "partial_refund": "Reembolso parcial",
              "pending": "Pendiente", "failed": "Fallida"}
ESTADOS_HOTMART = {
    "APPROVED": "Aprobada", "COMPLETE": "Completada", "REFUNDED": "Reembolsada", "CHARGEBACK": "Contracargo",
    "PARTIALLY_REFUNDED": "Reembolso parcial", "CANCELLED": "Cancelada", "EXPIRED": "Expirada",
    "WAITING_PAYMENT": "Esperando pago", "PRINTED_BILLET": "Boleto emitido", "BLOCKED": "Bloqueada",
    "PROTESTED": "En disputa", "UNDER_ANALISYS": "En análisis", "PRE_ORDER": "Preventa",
    "STARTED": "Iniciada", "NO_FUNDS": "Sin fondos", "OVERDUE": "Vencida",
    "PROCESSING_TRANSACTION": "Procesando",
}
HOTMART_VALIDAS = {"APPROVED", "COMPLETE", "PARTIALLY_REFUNDED"}


# ============================================================ HTTP

class ErrorApi(Exception):
    def __init__(self, mensaje: str, codigo: int = 0, cuerpo=None):
        super().__init__(mensaje)
        self.codigo, self.cuerpo = codigo, cuerpo


def _http(metodo: str, url: str, cabeceras: dict, cuerpo: bytes | None = None, timeout: float = 25):
    req = urllib.request.Request(url, data=cuerpo, method=metodo, headers={"User-Agent": AGENTE, **cabeceras})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            texto = r.read()
    except urllib.error.HTTPError as e:
        try:
            datos = json.loads(e.read() or b"null")
        except ValueError:
            datos = None
        raise ErrorApi(f"Error {e.code}", e.code, datos) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErrorApi("Sin conexión. Revisa tu internet.") from e
    try:
        return json.loads(texto) if texto.strip() else None
    except ValueError as e:
        raise ErrorApi("La plataforma respondió algo inesperado. Inténtalo de nuevo.") from e


def _detalle(cuerpo) -> str:
    if not isinstance(cuerpo, dict):
        return ""
    errores = cuerpo.get("errors")
    if isinstance(errores, list) and errores:
        return str(errores[0].get("detail") or errores[0].get("title") or "")
    return str(cuerpo.get("error_description") or cuerpo.get("message") or cuerpo.get("error") or "")


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ms_a_iso(ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def dinero(valor: float | None, moneda: str) -> str:
    if valor is None:
        return "—"
    return f"{valor:,.2f} {moneda}".strip()


# ============================================================ Lemon Squeezy

def plano(objeto: dict) -> dict:
    """Recurso JSON:API → diccionario simple con 'id' + atributos."""
    id_ = str(objeto["id"])
    return {"id": int(id_) if id_.isdigit() else id_, **(objeto.get("attributes") or {})}


class LemonSqueezy:
    clave = "lemonsqueezy"

    def __init__(self, api_key: str):
        self.api_key = api_key.strip()

    def _req(self, metodo: str, ruta: str, consulta: dict | None = None, cuerpo=None):
        url = LS_API + ruta + ("?" + urllib.parse.urlencode(consulta) if consulta else "")
        try:
            return _http(metodo, url, {"Accept": "application/vnd.api+json",
                                       "Content-Type": "application/vnd.api+json",
                                       "Authorization": f"Bearer {self.api_key}"},
                         json.dumps(cuerpo).encode() if cuerpo is not None else None)
        except ErrorApi as e:
            raise self._traducir(e) from e

    @staticmethod
    def _traducir(e: ErrorApi) -> ErrorApi:
        detalle = _detalle(e.cuerpo)
        mensajes = {
            0: str(e),
            401: "La API key de Lemon Squeezy no es válida o venció. Crea una nueva en Settings → API.",
            403: f"Lemon Squeezy no permitió la acción. {detalle}",
            404: f"No se encontró en Lemon Squeezy. {detalle}",
            429: "Demasiadas peticiones a Lemon Squeezy. Espera un minuto.",
        }
        return ErrorApi(mensajes.get(e.codigo, f"Error de Lemon Squeezy ({e.codigo}). {detalle}").strip(),
                        e.codigo, e.cuerpo)

    def _todas(self, ruta: str, filtros: dict | None = None, max_paginas: int = 50) -> list[dict]:
        resultado, pagina = [], 1
        while True:
            consulta = {f"filter[{k}]": v for k, v in (filtros or {}).items() if v}
            consulta |= {"page[number]": pagina, "page[size]": 100}
            r = self._req("GET", ruta, consulta) or {}
            resultado += [plano(o) for o in r.get("data") or []]
            ultima = int(((r.get("meta") or {}).get("page") or {}).get("lastPage") or 1)
            if pagina >= ultima or pagina >= max_paginas:
                return resultado
            pagina += 1

    def _contar(self, ruta: str, filtros: dict) -> int:
        consulta = {f"filter[{k}]": v for k, v in filtros.items() if v} | {"page[size]": 1}
        r = self._req("GET", ruta, consulta) or {}
        return int(((r.get("meta") or {}).get("page") or {}).get("total") or len(r.get("data") or []))

    # --- cuenta
    def usuario(self) -> dict:
        r = self._req("GET", "users/me") or {}
        return plano(r["data"]) | {"modo_prueba": (r.get("meta") or {}).get("test_mode")}

    def tiendas(self) -> list[dict]:
        return self._todas("stores")

    def productos(self, tienda_id: int) -> list[dict]:
        return self._todas("products", {"store_id": tienda_id})

    def variantes(self, tienda_id: int, producto_id: int = 0, productos: list[dict] | None = None) -> list[dict]:
        productos_por_id = {p["id"]: p for p in (productos if productos is not None else self.productos(tienda_id))}
        if producto_id:
            variantes = self._todas("variants", {"product_id": producto_id})
        else:
            variantes = [v for v in self._todas("variants") if v.get("product_id") in productos_por_id]
        for v in variantes:
            v["producto"] = (productos_por_id.get(v.get("product_id")) or {}).get("name", "")
        return variantes

    def conectar(self) -> dict:
        """Prueba la API key y reúne todo lo que se muestra en la ventana de 'Conectado'."""
        usuario = self.usuario()
        tiendas = self.tiendas()
        resumen = {"plataforma": self.clave, "usuario": usuario, "tiendas": tiendas}
        if tiendas:
            resumen["tienda"] = self.detalle_tienda(tiendas[0]["id"])
        return resumen

    def detalle_tienda(self, tienda_id: int) -> dict:
        productos = self.productos(tienda_id)
        variantes = self.variantes(tienda_id, productos=productos)
        return {"id": tienda_id, "productos": productos, "variantes": variantes,
                "licencias": self._contar("license-keys", {"store_id": tienda_id}),
                "ventas": self._contar("orders", {"store_id": tienda_id})}

    # --- lectura
    def datos(self, tienda_id: int, producto_id: int = 0) -> dict:
        licencias = self._todas("license-keys", {"store_id": tienda_id, "product_id": producto_id})
        ids = {l["id"] for l in licencias}
        instancias = [i for i in self._todas("license-key-instances") if i.get("license_key_id") in ids]
        pedidos = self._todas("orders", {"store_id": tienda_id})
        if producto_id:
            pedidos = [p for p in pedidos if (p.get("first_order_item") or {}).get("product_id") == producto_id]
        return {"licencias": licencias, "instancias": instancias, "ventas": [venta_ls(p) for p in pedidos]}

    # --- licencias
    def editar_licencia(self, id_: int, atributos: dict) -> dict:
        cuerpo = {"data": {"type": "license-keys", "id": str(id_), "attributes": atributos}}
        return plano(self._req("PATCH", f"license-keys/{id_}", cuerpo=cuerpo)["data"])

    def quitar_equipo(self, clave: str, instancia: str):
        """Desactiva un equipo con la API de licencias (la misma que usa el programa del cliente)."""
        try:
            r = _http("POST", LS_API + "licenses/deactivate",
                      {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                      urllib.parse.urlencode({"license_key": clave, "instance_id": instancia}).encode()) or {}
        except ErrorApi as e:
            if e.codigo == 404:   # el equipo ya estaba desactivado
                return
            raise ErrorApi(_detalle(e.cuerpo) or str(e), e.codigo) from e
        if not r.get("deactivated"):
            raise ErrorApi(r.get("error") or "Lemon Squeezy no desactivó el equipo.")

    # --- enlaces de compra
    def crear_cupon_gratis(self, tienda_id: int, variante_id: int) -> str:
        codigo = "REGALO" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        cuerpo = {"data": {
            "type": "discounts",
            "attributes": {"name": f"Licencia de regalo {codigo}", "code": codigo, "amount": 100,
                           "amount_type": "percent", "duration": "once", "is_limited_to_products": True,
                           "is_limited_redemptions": True, "max_redemptions": 1},
            "relationships": {"store": {"data": {"type": "stores", "id": str(tienda_id)}},
                              "variants": {"data": [{"type": "variants", "id": str(variante_id)}]}}}}
        self._req("POST", "discounts", cuerpo=cuerpo)
        return codigo

    def crear_enlace(self, tienda_id: int, venta: dict) -> str:
        """Crea un checkout y devuelve su URL. Al pagar, Lemon Squeezy genera la clave de licencia
        y se la envía al cliente por correo."""
        datos = {k: v for k, v in (("name", venta["cliente"]), ("email", venta["correo"])) if v}
        if venta["precio"] == "gratis":
            datos["discount_code"] = self.crear_cupon_gratis(tienda_id, venta["variante_id"])
        atributos = {"product_options": {"enabled_variants": [venta["variante_id"]]},
                     "checkout_data": datos or None,
                     "custom_price": venta["centavos"] if venta["precio"] == "especial" else None,
                     "expires_at": venta["expira"]}
        cuerpo = {"data": {
            "type": "checkouts",
            "attributes": {k: v for k, v in atributos.items() if v is not None},
            "relationships": {"store": {"data": {"type": "stores", "id": str(tienda_id)}},
                              "variant": {"data": {"type": "variants", "id": str(venta["variante_id"])}}}}}
        return self._req("POST", "checkouts", cuerpo=cuerpo)["data"]["attributes"]["url"]


def venta_ls(p: dict) -> dict:
    item = p.get("first_order_item") or {}
    producto = item.get("product_name") or ""
    if item.get("variant_name") and item["variant_name"] != "Default":
        producto = f"{producto} — {item['variant_name']}"
    total = p.get("total")
    return {
        "plataforma": "lemonsqueezy", "id": f"ls-{p['id']}", "referencia": f"#{p.get('order_number')}",
        "fecha": p.get("created_at"), "cliente": p.get("user_name") or "", "correo": p.get("user_email") or "",
        "producto": producto, "total": total / 100 if isinstance(total, (int, float)) else None,
        "moneda": p.get("currency") or "", "total_txt": p.get("total_formatted") or "",
        "estado": ESTADOS_LS.get(p.get("status"), p.get("status_formatted") or "—"),
        "valida": p.get("status") in ("paid", "partial_refund"),
        "reembolso": p.get("refunded_at"), "recibo": (p.get("urls") or {}).get("receipt") or "",
        "prueba": bool(p.get("test_mode")),
    }


# ============================================================ Hotmart

class Hotmart:
    clave = "hotmart"

    def __init__(self, client_id: str, client_secret: str, basic: str = "", sandbox: bool = False):
        self.client_id, self.client_secret = client_id.strip(), client_secret.strip()
        self.basic, self.sandbox = basic.strip(), bool(sandbox)
        self._token, self._vence = "", 0.0
        self._lock = threading.Lock()
        self._cache: tuple[float, tuple, list] | None = None

    def _cabecera_basic(self) -> str:
        if self.basic:
            return self.basic if self.basic.lower().startswith("basic ") else f"Basic {self.basic}"
        return "Basic " + base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

    def token(self) -> dict:
        """Pide un token de acceso (OAuth client credentials). Lo guarda hasta 5 min antes de vencer."""
        with self._lock:
            if self._token and time.time() < self._vence - 300:
                return {"access_token": self._token, "expires_in": int(self._vence - time.time())}
            consulta = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": self.client_id,
                                               "client_secret": self.client_secret})
            try:
                r = _http("POST", f"{HOTMART_AUTH}?{consulta}",
                          {"Authorization": self._cabecera_basic(), "Content-Type": "application/json"}) or {}
            except ErrorApi as e:
                if e.codigo in (400, 401, 403):
                    raise ErrorApi("Hotmart rechazó las credenciales. Revisa el Client ID y el Client Secret "
                                   "(y que sean de producción o de sandbox según elegiste).", e.codigo) from e
                raise ErrorApi(f"No se pudo conectar con Hotmart. {_detalle(e.cuerpo) or e}".strip(), e.codigo) from e
            if not r.get("access_token"):
                raise ErrorApi("Hotmart no devolvió un token de acceso.")
            self._token = r["access_token"]
            self._vence = time.time() + float(r.get("expires_in") or 3600)
            return r

    def _get(self, ruta: str, consulta: dict | None = None, reintento: bool = True):
        url = HOTMART_API[self.sandbox] + ruta + ("?" + urllib.parse.urlencode(consulta) if consulta else "")
        try:
            return _http("GET", url, {"Authorization": f"Bearer {self.token()['access_token']}",
                                      "Content-Type": "application/json"}) or {}
        except ErrorApi as e:
            if e.codigo == 401 and reintento:
                with self._lock:
                    self._token = ""
                return self._get(ruta, consulta, reintento=False)
            mensajes = {401: "Hotmart rechazó el acceso. Vuelve a conectar tus credenciales.",
                        403: "Tus credenciales de Hotmart no tienen permiso para ver esto.",
                        429: "Demasiadas peticiones a Hotmart. Espera un minuto."}
            raise ErrorApi(mensajes.get(e.codigo, f"Error de Hotmart ({e.codigo}). {_detalle(e.cuerpo)}").strip()
                           if e.codigo else str(e), e.codigo, e.cuerpo) from e

    def _paginas(self, ruta: str, consulta: dict, max_paginas: int = 40) -> list[dict]:
        items, token = [], None
        for _ in range(max_paginas):
            r = self._get(ruta, consulta | ({"page_token": token} if token else {}))
            items += r.get("items") or []
            token = (r.get("page_info") or {}).get("next_page_token")
            if not token:
                break
        return items

    def productos(self) -> list[dict]:
        return self._paginas("/products/api/v1/products", {"max_results": 50})

    def _historial(self, consulta: dict) -> list[dict]:
        con_fechas = consulta | {"start_date": HOTMART_DESDE_MS, "end_date": int(time.time() * 1000)}
        try:
            return self._paginas("/payments/api/v1/sales/history", con_fechas)
        except ErrorApi as e:
            if e.codigo != 400:
                raise
            return self._paginas("/payments/api/v1/sales/history", consulta)   # sin rango de fechas

    def ventas(self, producto_id: int = 0, max_edad: float = 60) -> list[dict]:
        """Historial de ventas normalizado (aprobadas, completas, reembolsos y contracargos).
        Se guarda max_edad segundos para no gastar el límite de peticiones de Hotmart."""
        clave = (producto_id,)
        if self._cache and self._cache[1] == clave and time.time() - self._cache[0] < max_edad:
            return self._cache[2]
        base = {"max_results": 50} | ({"product_id": producto_id} if producto_id else {})
        vistas, ventas = set(), []
        for estado in (None, "REFUNDED", "CHARGEBACK"):
            for item in self._historial(base | ({"transaction_status": estado} if estado else {})):
                v = venta_hotmart(item)
                if v["id"] not in vistas:
                    vistas.add(v["id"])
                    ventas.append(v)
        self._cache = (time.time(), clave, ventas)
        return ventas

    def conectar(self, producto_id: int = 0) -> dict:
        """Prueba las credenciales y reúne todo lo que se muestra en la ventana de 'Conectado'."""
        token = self.token()
        productos = self.productos()
        ventas = self.ventas(producto_id, max_edad=0)
        return {"plataforma": self.clave, "entorno": "Sandbox (pruebas)" if self.sandbox else "Producción",
                "token_horas": round(int(token.get("expires_in") or 0) / 3600, 1),
                "productos": productos, **resumen_ventas(ventas)}


def venta_hotmart(item: dict) -> dict:
    compra, comprador = item.get("purchase") or {}, item.get("buyer") or {}
    precio = compra.get("price") or {}
    estado = str(compra.get("status") or "")
    valor = precio.get("value")
    return {
        "plataforma": "hotmart",
        "id": f"hm-{compra.get('transaction') or (comprador.get('email') or '') + str(compra.get('order_date'))}",
        "referencia": compra.get("transaction") or "",
        "fecha": ms_a_iso(compra.get("approved_date") or compra.get("order_date")),
        "cliente": comprador.get("name") or "", "correo": comprador.get("email") or "",
        "producto": (item.get("product") or {}).get("name") or "",
        "producto_id": (item.get("product") or {}).get("id"),
        "total": float(valor) if isinstance(valor, (int, float)) else None,
        "moneda": precio.get("currency_code") or "",
        "total_txt": dinero(float(valor), precio.get("currency_code") or "") if isinstance(valor, (int, float)) else "—",
        "estado": ESTADOS_HOTMART.get(estado, estado.title() or "—"),
        "valida": estado in HOTMART_VALIDAS,
        "reembolso": ms_a_iso(compra.get("order_date")) if estado in ("REFUNDED", "CHARGEBACK") else None,
        "recibo": "", "prueba": False,
    }


def resumen_ventas(ventas: list[dict]) -> dict:
    validas = [v for v in ventas if v["valida"]]
    ingresos: dict[str, float] = {}
    for v in validas:
        if v["total"] is not None:
            ingresos[v["moneda"]] = ingresos.get(v["moneda"], 0) + v["total"]
    return {"ventas_validas": len(validas),
            "compradores": len({(v["correo"] or v["cliente"]).lower() for v in validas}),
            "reembolsos": sum(1 for v in ventas if not v["valida"] and v["estado"] in
                              ("Reembolsada", "Contracargo", "En disputa")),
            "ingresos": ingresos}


# ============================================================ Gumroad

class Gumroad:
    clave = "gumroad"

    def __init__(self, token: str):
        self.token = token.strip()
        self._cache: tuple[float, tuple, list] | None = None

    def _req(self, metodo: str, ruta: str, datos: dict | None = None, publico: bool = False):
        datos = {k: v for k, v in (datos or {}).items() if v not in (None, "")}
        if not publico:
            datos["access_token"] = self.token
        url, cuerpo = GUMROAD_API + ruta, None
        cabeceras = {"Accept": "application/json"}
        if not publico:
            cabeceras["Authorization"] = f"Bearer {self.token}"
        if metodo == "GET":
            url += "?" + urllib.parse.urlencode(datos)
        else:
            cuerpo = urllib.parse.urlencode(datos).encode()
            cabeceras["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            r = _http(metodo, url, cabeceras, cuerpo) or {}
        except ErrorApi as e:
            detalle = _detalle(e.cuerpo)
            mensajes = {0: str(e),
                        401: "El access token de Gumroad no es válido. Genera uno nuevo en Settings → Advanced.",
                        403: "El access token de Gumroad no tiene permiso para esto.",
                        404: detalle or "No se encontró en Gumroad.",
                        429: "Demasiadas peticiones a Gumroad. Espera un minuto."}
            raise ErrorApi(mensajes.get(e.codigo, f"Error de Gumroad ({e.codigo}). {detalle}").strip(),
                           e.codigo, e.cuerpo) from e
        if isinstance(r, dict) and r.get("success") is False:
            raise ErrorApi(r.get("message") or "Gumroad rechazó la petición.", 0, r)
        return r

    def usuario(self) -> dict:
        return self._req("GET", "user").get("user") or {}

    def productos(self) -> list[dict]:
        return self._req("GET", "products").get("products") or []

    def ventas(self, producto_id: str = "", max_edad: float = 60) -> list[dict]:
        """Todas las ventas (con su clave de licencia, si el producto genera claves)."""
        clave = (producto_id,)
        if self._cache and self._cache[1] == clave and time.time() - self._cache[0] < max_edad:
            return self._cache[2]
        ventas, pagina = [], None
        for _ in range(200):
            r = self._req("GET", "sales", {"product_id": producto_id, "page_key": pagina})
            ventas += [venta_gumroad(v) for v in r.get("sales") or []]
            pagina = r.get("next_page_key")
            if not pagina:
                break
        self._cache = (time.time(), clave, ventas)
        return ventas

    def conectar(self, producto_id: str = "") -> dict:
        """Prueba el token y reúne lo que se muestra en la ventana de 'Conectado'."""
        usuario = self.usuario()
        productos = self.productos()
        ventas = self.ventas(producto_id, max_edad=0)
        return {"plataforma": self.clave, "usuario": usuario, "productos": productos,
                "claves": sum(1 for v in ventas if v.get("clave_licencia")), **resumen_ventas(ventas)}

    # --- licencias
    def licencia(self, producto_id: str, clave: str) -> dict:
        """Estado de una clave sin gastar un uso: {'usos', 'compra', 'bloqueada'}."""
        try:
            r = self._req("POST", "licenses/verify", {"product_id": producto_id, "license_key": clave,
                                                      "increment_uses_count": "false"}, publico=True)
        except ErrorApi as e:
            if "disabled" in str(e).lower() or "deshabilit" in str(e).lower():
                return {"usos": None, "compra": {}, "bloqueada": True}
            raise
        return {"usos": r.get("uses"), "compra": r.get("purchase") or {}, "bloqueada": False}

    def bloquear(self, producto_id: str, clave: str, bloquear: bool = True):
        self._req("PUT", "licenses/disable" if bloquear else "licenses/enable",
                  {"product_id": producto_id, "license_key": clave})

    def liberar_uso(self, producto_id: str, clave: str) -> int | None:
        """Resta un uso a la clave: el cliente podrá activarla en otra computadora."""
        return self._req("PUT", "licenses/decrement_uses_count",
                         {"product_id": producto_id, "license_key": clave}).get("uses")


def venta_gumroad(v: dict) -> dict:
    reembolsada, contracargo = bool(v.get("refunded")), bool(v.get("chargedback") or v.get("chargebacked"))
    disputa = bool(v.get("disputed")) and not v.get("dispute_won")
    estado = ("Contracargo" if contracargo else "Reembolsada" if reembolsada else "En disputa" if disputa
              else "Reembolso parcial" if v.get("partially_refunded") else "Pagada")
    centavos = v.get("price")
    return {
        "plataforma": "gumroad", "id": f"gr-{v.get('id')}", "referencia": f"#{v.get('order_id') or ''}".rstrip("#"),
        "fecha": v.get("created_at"), "cliente": v.get("full_name") or "",
        "correo": v.get("email") or v.get("purchase_email") or "",
        "producto": v.get("product_name") or "", "producto_id": v.get("product_id"),
        "total": centavos / 100 if isinstance(centavos, (int, float)) else None,
        "moneda": v.get("currency_symbol") or "",
        "total_txt": v.get("formatted_total_price") or v.get("formatted_display_price") or "—",
        "estado": estado, "valida": not (reembolsada or contracargo or disputa),
        "reembolso": v.get("created_at") if (reembolsada or contracargo) else None,
        "recibo": "", "prueba": bool(v.get("test")), "clave_licencia": v.get("license_key") or "",
    }


def crear_cliente(plataforma: str, cfg: dict):
    """Cliente de API a partir de la configuración guardada de una plataforma (o None)."""
    if plataforma == "lemonsqueezy" and cfg.get("api_key"):
        return LemonSqueezy(cfg["api_key"])
    if plataforma == "hotmart" and cfg.get("client_id") and cfg.get("client_secret"):
        return Hotmart(cfg["client_id"], cfg["client_secret"], cfg.get("basic", ""), cfg.get("sandbox", False))
    if plataforma == "gumroad" and cfg.get("token"):
        return Gumroad(cfg["token"])
    return None
