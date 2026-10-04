"""Cinema Productions · servidor falso de Lemon Squeezy, Hotmart, Gumroad, Polar y Supabase para probar sin
internet ni compras reales.

Imita los endpoints que usan licencia_cliente.py y el Administrador:
  - API de licencias: POST /v1/licenses/activate | validate | deactivate (sin API key)
  - API principal (JSON:API con Bearer): users/me, stores, products, variants, license-keys,
    license-key-instances, orders, checkouts, discounts
  - Hotmart: POST /security/oauth/token, GET /payments/api/v1/sales/history, GET /products/api/v1/products
  - Gumroad: GET /v2/user | products | sales, POST /v2/licenses/verify,
    PUT /v2/licenses/enable | disable | decrement_uses_count
  - Polar: organizations, products, benefits, checkout-links, orders, license-keys (Bearer + Polar-Version)
    y la API pública /v1/customer-portal/license-keys/activate | validate | deactivate
  - Supabase (servidor de control): /rest/v1/rpc/cinema_latido | cinema_aviso_leido y las tablas cinema_*
    (con la clave secreta), con la misma lógica que servidor/supabase_cinema.sql

Creado por Cinema Productions.
"""
from __future__ import annotations

import base64
import json
import threading
import urllib.parse
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY = "clave-de-prueba"
TIENDA = 111
PRODUCTO = 222
VARIANTE = 333
HM_ID, HM_SECRETO = "hotmart-id", "hotmart-secreto"
HM_PRODUCTO = 4444
HM_TOKEN = "token-hotmart-de-prueba"
GR_TOKEN = "token-gumroad-de-prueba"
GR_PRODUCTO = "gr-prod-ABC=="
PO_TOKEN = "polar_oat_de_prueba"
PO_ORG = "11111111-2222-4333-8444-555555555555"
PO_PRODUCTO = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
PO_BENEFICIO = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff"
SB_PUBLICA = "sb_publishable_de_prueba"
SB_SECRETA = "sb_secret_de_prueba"


def ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


class Datos:
    def __init__(self):
        self.lock = threading.Lock()
        self.licencias: dict[int, dict] = {}
        self.instancias: dict[int, dict] = {}
        self.ventas: dict[int, dict] = {}
        self.checkouts: list[dict] = []
        self.descuentos: list[dict] = []
        self.hotmart: list[dict] = []
        self.hotmart_rechaza_fechas = False
        self.hotmart_tokens = 0
        self.gumroad: list[dict] = []
        self.gumroad_claves: dict[str, dict] = {}
        self.polar_claves: dict[str, dict] = {}
        self.polar_activaciones: dict[str, dict] = {}
        self.polar_ordenes: list[dict] = []
        self.polar_versiones: set = set()
        self.sb = {"equipos": {}, "sesiones": {}, "uso": {}, "estados": {}, "avisos": [], "leidos": set(),
                   "eventos": [], "aviso_id": 0}
        self._id = 1000

    def nuevo_id(self) -> int:
        self._id += 1
        return self._id

    def vender(self, cliente="Juan Pérez", correo="juan@example.com", limite=1, expira=None,
               tienda=TIENDA, producto=PRODUCTO, test_mode=True) -> dict:
        orden = self.nuevo_id()
        self.ventas[orden] = {
            "store_id": tienda, "customer_id": 1, "identifier": str(uuid.uuid4()), "order_number": orden,
            "user_name": cliente, "user_email": correo, "currency": "USD", "status": "paid",
            "status_formatted": "Paid", "total": 1900, "total_formatted": "$19.00", "refunded": False,
            "refunded_at": None, "refunded_amount_formatted": "$0.00", "test_mode": test_mode,
            "first_order_item": {"product_id": producto, "variant_id": VARIANTE,
                                 "product_name": "Resolve Creator Subtitles", "variant_name": "Default"},
            "urls": {"receipt": f"https://app.lemonsqueezy.com/my-orders/{orden}"},
            "created_at": ahora(), "updated_at": ahora()}
        id_ = self.nuevo_id()
        clave = str(uuid.uuid4()).upper()
        self.licencias[id_] = {
            "store_id": tienda, "customer_id": 1, "order_id": orden, "order_item_id": 1, "product_id": producto,
            "user_name": cliente, "user_email": correo, "key": clave, "key_short": "XXXX-" + clave[-12:],
            "activation_limit": limite, "instances_count": 0, "disabled": False, "status": "inactive",
            "status_formatted": "Inactive", "expires_at": expira, "created_at": ahora(), "updated_at": ahora(),
            "test_mode": test_mode}
        return {"id": id_, **self.licencias[id_]}

    def vender_hotmart(self, cliente="Lucía Gómez", correo="lucia@example.com", estado="APPROVED",
                       producto=HM_PRODUCTO, valor=297.0, moneda="BRL", dias_atras=0) -> dict:
        ms = int((datetime.now(timezone.utc).timestamp() - dias_atras * 86400) * 1000)
        item = {"product": {"id": producto, "name": "Resolve Creator Subtitles"},
                "buyer": {"name": cliente, "email": correo, "ucode": str(uuid.uuid4())},
                "producer": {"name": "Alejandro", "ucode": "x"},
                "purchase": {"transaction": f"HP{self.nuevo_id()}{len(self.hotmart)}", "order_date": ms,
                             "approved_date": ms, "status": estado, "is_subscription": False,
                             "price": {"value": valor, "currency_code": moneda},
                             "payment": {"method": "CREDIT_CARD", "installments_number": 1}}}
        self.hotmart.append(item)
        return item

    def vender_gumroad(self, cliente="Mateo Ríos", correo="mateo@example.com", producto=GR_PRODUCTO,
                       reembolsada=False, con_clave=True, test=False) -> dict:
        n = self.nuevo_id()
        clave = "-".join(uuid.uuid4().hex[:8].upper() for _ in range(4)) if con_clave else None
        venta = {"id": f"S{n}==", "email": cliente.split()[0].lower() + "@x.com" if not correo else correo,
                 "seller_id": "vendedor", "created_at": ahora(), "product_name": "Resolve Creator Subtitles",
                 "product_id": producto, "price": 2500, "formatted_display_price": "$25",
                 "formatted_total_price": "$25", "currency_symbol": "$", "full_name": cliente, "order_id": n,
                 "refunded": reembolsada, "partially_refunded": False, "chargedback": False, "disputed": False,
                 "dispute_won": False, "test": test, "license_key": clave}
        self.gumroad.append(venta)
        if clave:
            self.gumroad_claves[clave] = {"uses": 0, "disabled": False, "venta": venta}
        return venta

    def vender_polar(self, cliente="Valeria Soto", correo="valeria@example.com", limite=2, reembolsada=False,
                     prefijo="CINEMA", con_activaciones=True) -> dict:
        cliente_id = str(uuid.uuid4())
        orden = {"id": str(uuid.uuid4()), "created_at": ahora(), "modified_at": ahora(),
                 "status": "refunded" if reembolsada else "paid", "paid": True, "total_amount": 2900,
                 "currency": "usd", "billing_reason": "purchase", "customer_id": cliente_id,
                 "product_id": PO_PRODUCTO, "invoice_number": f"POL-{len(self.polar_ordenes) + 1:04d}",
                 "customer": {"id": cliente_id, "email": correo, "name": cliente},
                 "product": {"id": PO_PRODUCTO, "name": "Resolve Creator Subtitles"}, "description": "RCS"}
        self.polar_ordenes.append(orden)
        id_ = str(uuid.uuid4())
        self.polar_claves[id_] = {
            "id": id_, "created_at": ahora(), "modified_at": None, "organization_id": PO_ORG,
            "customer_id": cliente_id, "customer": {"id": cliente_id, "email": correo, "name": cliente},
            "benefit_id": PO_BENEFICIO, "key": f"{prefijo}-{str(uuid.uuid4()).upper()}", "display_key": "****",
            "status": "revoked" if reembolsada else "granted",
            "limit_activations": limite if con_activaciones else None, "usage": 0, "limit_usage": None,
            "validations": 0, "last_validated_at": None, "expires_at": None}
        return self.polar_claves[id_]

    def reembolsar_polar(self, clave: str, reembolsar: bool = True):
        lic = next(l for l in self.polar_claves.values() if l["key"] == clave)
        lic["status"] = "revoked" if reembolsar else "granted"
        for o in self.polar_ordenes:
            if o["customer_id"] == lic["customer_id"]:
                o["status"] = "refunded" if reembolsar else "paid"

    def polar_por_clave(self, clave: str):
        return next((l for l in self.polar_claves.values() if l["key"] == clave), None)

    def por_clave(self, clave: str):
        return next(((i, l) for i, l in self.licencias.items() if l["key"] == clave), (None, None))

    def estado(self, lic: dict) -> str:
        if lic["disabled"]:
            return "disabled"
        if lic["expires_at"] and lic["expires_at"] < ahora():
            return "expired"
        return "active" if lic["instances_count"] else "inactive"


DATOS = Datos()


def _licencia_publica(id_: int, lic: dict) -> dict:
    return {"id": id_, "status": DATOS.estado(lic), "key": lic["key"],
            "activation_limit": lic["activation_limit"], "activation_usage": lic["instances_count"],
            "created_at": lic["created_at"], "expires_at": lic["expires_at"], "test_mode": lic["test_mode"]}


def _meta(lic: dict) -> dict:
    return {"store_id": lic["store_id"], "order_id": lic["order_id"], "order_item_id": 1,
            "product_id": lic["product_id"], "product_name": "Resolve Creator Subtitles", "variant_id": VARIANTE,
            "variant_name": "Default", "customer_id": 1, "customer_name": lic["user_name"],
            "customer_email": lic["user_email"]}


def _polar_lic(lic: dict) -> dict:
    return {k: v for k, v in lic.items()}


def _polar_activaciones(id_: str) -> list[dict]:
    return [a for a in DATOS.polar_activaciones.values() if a["license_key_id"] == id_]


def _pagina(items: list, q: dict) -> dict:
    limite = int((q.get("limit") or ["10"])[0])
    pagina = int((q.get("page") or ["1"])[0])
    maximo = max(1, -(-len(items) // limite))
    return {"items": items[(pagina - 1) * limite: pagina * limite],
            "pagination": {"total_count": len(items), "max_page": maximo}}


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _responder(self, codigo: int, cuerpo):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _cuerpo(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    # ------------------------------------------------------------ API de licencias
    def _licencias(self, accion: str):
        if self.headers.get("Accept") != "application/json":
            return self._responder(400, {"error": "Accept header must be application/json"})
        p = {k: v[0] for k, v in urllib.parse.parse_qs(self._cuerpo().decode()).items()}
        clave = p.get("license_key", "")
        with DATOS.lock:
            id_, lic = DATOS.por_clave(clave)
            campo = {"activate": "activated", "validate": "valid", "deactivate": "deactivated"}[accion]
            if not lic:
                return self._responder(404, {campo: False, "error": "license_key not found.",
                                             "license_key": None, "meta": None})
            base = {"license_key": _licencia_publica(id_, lic), "meta": _meta(lic)}
            instancia = next((i for i in DATOS.instancias.values()
                              if i["license_key_id"] == id_ and i["identifier"] == p.get("instance_id")), None)
            estado = DATOS.estado(lic)

            if accion == "activate":
                if estado == "disabled":
                    return self._responder(400, {campo: False, "error": "This license key is disabled.", **base})
                if estado == "expired":
                    return self._responder(400, {campo: False, "error": "This license key has expired.", **base})
                if lic["activation_limit"] and lic["instances_count"] >= lic["activation_limit"]:
                    return self._responder(400, {campo: False, **base,
                                                 "error": "This license key has reached the activation limit."})
                iid = DATOS.nuevo_id()
                DATOS.instancias[iid] = {"license_key_id": id_, "identifier": str(uuid.uuid4()),
                                         "name": p.get("instance_name", ""), "created_at": ahora(),
                                         "updated_at": ahora()}
                lic["instances_count"] += 1
                ins = DATOS.instancias[iid]
                return self._responder(200, {campo: True, "error": None,
                                             "license_key": _licencia_publica(id_, lic), "meta": _meta(lic),
                                             "instance": {"id": ins["identifier"], "name": ins["name"],
                                                          "created_at": ins["created_at"]}})
            if accion == "validate":
                if p.get("instance_id") and not instancia:
                    return self._responder(404, {campo: False, "error": "license_key instance not found.",
                                                 **base, "instance": None})
                if estado in ("disabled", "expired"):
                    return self._responder(400, {campo: False, "error": f"This license key is {estado}.",
                                                 **base, "instance": None})
                return self._responder(200, {campo: True, "error": None, **base,
                                             "instance": instancia and {"id": instancia["identifier"],
                                                                        "name": instancia["name"],
                                                                        "created_at": instancia["created_at"]}})
            # deactivate
            if not instancia:
                return self._responder(404, {campo: False, "error": "license_key instance not found.", **base})
            DATOS.instancias = {k: v for k, v in DATOS.instancias.items() if v is not instancia}
            lic["instances_count"] -= 1
            return self._responder(200, {campo: True, "error": None, "license_key": _licencia_publica(id_, lic),
                                         "meta": _meta(lic)})

    # ------------------------------------------------------------ API principal
    def _autorizado(self) -> bool:
        if self.headers.get("Authorization") != f"Bearer {API_KEY}":
            self._responder(401, {"errors": [{"status": "401", "title": "Unauthenticated."}]})
            return False
        return True

    def _lista(self, tipo: str, objetos: list[tuple[int, dict]], q: dict):
        filtros = {k[7:-1]: v[0] for k, v in q.items() if k.startswith("filter[")}
        for campo, valor in filtros.items():
            objetos = [(i, o) for i, o in objetos if str(o.get(campo)) == valor]
        tam = int(q.get("page[size]", ["10"])[0])
        num = int(q.get("page[number]", ["1"])[0])
        ultima = max(1, -(-len(objetos) // tam))
        pagina = objetos[(num - 1) * tam: num * tam]
        self._responder(200, {"meta": {"page": {"currentPage": num, "from": 1, "lastPage": ultima,
                                                "perPage": tam, "to": len(pagina), "total": len(objetos)}},
                              "data": [{"type": tipo, "id": str(i), "attributes": o} for i, o in pagina]})

    # ------------------------------------------------------------ Hotmart
    def _hotmart_token(self, q: dict):
        basic = "Basic " + base64.b64encode(f"{HM_ID}:{HM_SECRETO}".encode()).decode()
        if (self.headers.get("Authorization") != basic or q.get("client_id", [""])[0] != HM_ID
                or q.get("client_secret", [""])[0] != HM_SECRETO
                or q.get("grant_type", [""])[0] != "client_credentials"):
            return self._responder(401, {"error": "invalid_client", "error_description": "Bad credentials"})
        DATOS.hotmart_tokens += 1
        self._responder(200, {"access_token": HM_TOKEN, "token_type": "bearer", "expires_in": 86400,
                              "scope": "read write", "jti": "x"})

    def _hotmart_get(self, ruta: str, q: dict):
        if self.headers.get("Authorization") != f"Bearer {HM_TOKEN}":
            return self._responder(401, {"error": "invalid_token"})
        uno = {k: v[0] for k, v in q.items()}
        if ruta == "/products/api/v1/products":
            return self._responder(200, {"items": [{"id": HM_PRODUCTO, "name": "Resolve Creator Subtitles",
                                                    "ucode": "abc", "status": "ACTIVE", "format": "SOFTWARE"}],
                                         "page_info": {"total_results": 1, "results_per_page": 50}})
        if ruta != "/payments/api/v1/sales/history":
            return self._responder(404, {"message": "not found"})
        if DATOS.hotmart_rechaza_fechas and "start_date" in uno:
            return self._responder(400, {"error": "invalid_parameter", "message": "start_date"})
        estado = uno.get("transaction_status")
        items = [i for i in DATOS.hotmart if (i["purchase"]["status"] == estado if estado
                                              else i["purchase"]["status"] in ("APPROVED", "COMPLETE"))]
        if "product_id" in uno:
            items = [i for i in items if str(i["product"]["id"]) == uno["product_id"]]
        tam = int(uno.get("max_results", 10))
        desde = int(uno.get("page_token", 0))
        pagina = items[desde:desde + tam]
        siguiente = str(desde + tam) if desde + tam < len(items) else None
        self._responder(200, {"items": pagina, "page_info": {"total_results": len(items), "results_per_page": tam,
                                                             **({"next_page_token": siguiente} if siguiente else {})}})

    # ------------------------------------------------------------ Gumroad
    def _gumroad(self, metodo: str, ruta: str, p: dict):
        if ruta != "licenses/verify":
            if p.get("access_token") != GR_TOKEN or self.headers.get("Authorization") != f"Bearer {GR_TOKEN}":
                return self._responder(401, {"success": False, "message": "The access token is invalid"})
        if metodo == "GET" and ruta == "user":
            return self._responder(200, {"success": True, "user": {"name": "Alejandro", "email": "vendedor@example.com",
                                                                     "user_id": "u1", "url": "https://alejandro.gumroad.com"}})
        if metodo == "GET" and ruta == "products":
            return self._responder(200, {"success": True, "products": [{
                "id": GR_PRODUCTO, "name": "Resolve Creator Subtitles", "price": 2500, "currency": "usd",
                "formatted_price": "$25", "short_url": "https://alejandro.gumroad.com/l/rcs", "published": True,
                "sales_count": str(len(DATOS.gumroad))}]})
        if metodo == "GET" and ruta == "sales":
            ventas = [v for v in DATOS.gumroad if not p.get("product_id") or v["product_id"] == p["product_id"]]
            desde = int(p.get("page_key") or 0)
            pagina = ventas[desde:desde + 10]
            siguiente = str(desde + 10) if desde + 10 < len(ventas) else None
            return self._responder(200, {"success": True, "sales": pagina, "next_page_key": siguiente,
                                         "next_page_url": f"/v2/sales?page_key={siguiente}" if siguiente else None})
        if ruta.startswith("licenses/"):
            lic = DATOS.gumroad_claves.get(p.get("license_key", ""))
            if not lic or lic["venta"]["product_id"] != p.get("product_id"):
                return self._responder(404, {"success": False,
                                             "message": "That license does not exist for the provided product."})
            accion = ruta.split("/")[1]
            if accion == "verify":
                if lic["disabled"]:
                    return self._responder(200, {"success": False, "message": "This license key has been disabled."})
                if p.get("increment_uses_count", "true") != "false":
                    lic["uses"] += 1
            elif accion in ("disable", "enable"):
                lic["disabled"] = accion == "disable"
            elif accion == "decrement_uses_count":
                lic["uses"] = max(0, lic["uses"] - 1)
            v = lic["venta"]
            compra = {"product_id": v["product_id"], "product_name": v["product_name"], "email": v["email"],
                      "full_name": v["full_name"], "license_key": v["license_key"], "refunded": v["refunded"],
                      "chargebacked": v["chargedback"], "disputed": v["disputed"], "dispute_won": False,
                      "test": v["test"], "subscription_ended_at": None, "subscription_failed_at": None}
            return self._responder(200, {"success": True, "uses": lic["uses"], "purchase": compra})
        self._responder(404, {"success": False, "message": "Not found"})

    # ------------------------------------------------------------ Polar
    def _json(self) -> dict:
        try:
            return json.loads(self._cuerpo() or b"{}")
        except ValueError:
            return {}

    def _polar_publico(self, accion: str):
        c = self._json()
        lic = DATOS.polar_por_clave(c.get("key", ""))
        no_hay = {"error": "ResourceNotFound", "detail": "License key not found."}
        if not lic or c.get("organization_id") != PO_ORG:
            return self._responder(404, no_hay)
        vencida = lic["expires_at"] and lic["expires_at"] < ahora()
        if accion == "validate":
            if lic["status"] != "granted" or vencida:
                return self._responder(404, no_hay)
            if c.get("benefit_id") and c["benefit_id"] != lic["benefit_id"]:
                return self._responder(404, no_hay)
            if c.get("activation_id"):
                act = DATOS.polar_activaciones.get(c["activation_id"])
                if not act or act["license_key_id"] != lic["id"]:
                    return self._responder(404, {"error": "ResourceNotFound", "detail": "Activation not found."})
            lic["validations"] += 1
            lic["last_validated_at"] = ahora()
            return self._responder(200, _polar_lic(lic) | {"status": "granted"})
        if accion == "activate":
            if lic["status"] != "granted" or vencida:
                return self._responder(403, {"error": "NotPermitted", "detail": "License key is not granted."})
            if lic["limit_activations"] is None:
                return self._responder(403, {"error": "NotPermitted",
                                             "detail": "License key does not support activations."})
            if len(_polar_activaciones(lic["id"])) >= lic["limit_activations"]:
                return self._responder(403, {"error": "NotPermitted", "detail": "Activation limit reached."})
            act = {"id": str(uuid.uuid4()), "license_key_id": lic["id"], "label": c.get("label", ""),
                   "meta": c.get("meta") or {}, "created_at": ahora(), "modified_at": None}
            DATOS.polar_activaciones[act["id"]] = act
            return self._responder(200, act | {"license_key": _polar_lic(lic) | {"status": "granted"}})
        if accion == "deactivate":
            act = DATOS.polar_activaciones.get(c.get("activation_id", ""))
            if not act or act["license_key_id"] != lic["id"]:
                return self._responder(404, {"error": "ResourceNotFound", "detail": "Activation not found."})
            del DATOS.polar_activaciones[act["id"]]
            self.send_response(204)
            self.end_headers()
            return None
        return self._responder(404, no_hay)

    def _polar(self, metodo: str, ruta: str, q: dict):
        if self.headers.get("Authorization") != f"Bearer {PO_TOKEN}":
            return self._responder(401, {"error": "Unauthorized", "detail": "Invalid token"})
        DATOS.polar_versiones.add(self.headers.get("Polar-Version"))
        uno = {k: v[0] for k, v in q.items()}
        if metodo == "GET" and ruta == "organizations/":
            return self._responder(200, _pagina([{"id": PO_ORG, "name": "Cinema Productions", "slug": "cinema"}], q))
        if metodo == "GET" and ruta == "products/":
            return self._responder(200, _pagina([{"id": PO_PRODUCTO, "name": "Resolve Creator Subtitles",
                                                  "organization_id": PO_ORG, "is_archived": False}], q))
        if metodo == "GET" and ruta == "benefits/":
            return self._responder(200, _pagina([{"id": PO_BENEFICIO, "type": "license_keys",
                                                  "description": "Licencia de RCS",
                                                  "properties": {"prefix": "CINEMA", "activations": {"limit": 2}}}],
                                                q))
        if metodo == "GET" and ruta == "checkout-links/":
            return self._responder(200, _pagina([{"id": "cl1", "url": "https://buy.polar.sh/polar_cl_prueba",
                                                  "products": [{"id": PO_PRODUCTO}]}], q))
        if metodo == "GET" and ruta == "orders/":
            ordenes = [o for o in DATOS.polar_ordenes if not uno.get("product_id")
                       or o["product_id"] == uno["product_id"]]
            return self._responder(200, _pagina(list(reversed(ordenes)), q))
        if metodo == "GET" and ruta == "license-keys/":
            claves = [_polar_lic(l) for l in DATOS.polar_claves.values()
                      if not uno.get("benefit_id") or l["benefit_id"] == uno["benefit_id"]]
            return self._responder(200, _pagina(claves, q))
        if ruta.startswith("license-keys/") and ruta.count("/") == 1 and ruta != "license-keys/deactivate":
            lic = DATOS.polar_claves.get(ruta.split("/")[1])
            if not lic:
                return self._responder(404, {"error": "ResourceNotFound", "detail": "Not found"})
            if metodo == "PATCH":
                cambios = self._json()
                for k in ("status", "limit_activations", "expires_at", "usage"):
                    if k in cambios:
                        lic[k] = cambios[k]
                lic["modified_at"] = ahora()
                return self._responder(200, _polar_lic(lic))
            return self._responder(200, _polar_lic(lic) | {"activations": _polar_activaciones(lic["id"])})
        if metodo == "POST" and ruta == "license-keys/deactivate":
            c = self._json()
            act = DATOS.polar_activaciones.get(c.get("activation_id", ""))
            if not act:
                return self._responder(404, {"error": "ResourceNotFound", "detail": "Not found"})
            del DATOS.polar_activaciones[act["id"]]
            self.send_response(204)
            self.end_headers()
            return None
        return self._responder(404, {"error": "ResourceNotFound", "detail": "Not found"})

    # ------------------------------------------------------------ Supabase (servidor de control)
    def _sb_clave(self) -> str:
        return self.headers.get("apikey") or ""

    def _sb_rpc(self, funcion: str):
        clave = self._sb_clave()
        if clave not in (SB_PUBLICA, SB_SECRETA):
            return self._responder(401, {"message": "Invalid API key"})
        p = (self._json() or {}).get("p") or {}
        sb = DATOS.sb
        if funcion == "cinema_limpiar":
            if clave != SB_SECRETA:
                return self._responder(401, {"code": "42501", "message": "permission denied for function"})
            return self._responder(200, {"sesiones": 0, "eventos": 0})
        lic, equipo = str(p.get("licencia") or "").lower(), str(p.get("equipo") or "")[:40]
        if funcion == "cinema_aviso_leido":
            aviso = next((a for a in sb["avisos"] if str(a["id"]) == str(p.get("aviso"))), None)
            if aviso and equipo and (aviso["licencia"] in (None, lic)):
                sb["leidos"].add((aviso["id"], lic, equipo, ahora()))
            return self._responder(200, {})
        if funcion != "cinema_latido":
            return self._responder(404, {"code": "PGRST202", "message": "Could not find the function"})
        if len(lic) != 64 or not equipo:
            return self._responder(400, {"code": "22023", "message": "datos incompletos"})
        seg = max(0, min(int(p.get("segundos") or 0), 3600))
        e = sb["equipos"].setdefault((lic, equipo), {"licencia": lic, "equipo": equipo, "primera_vez": ahora(),
                                                     "segundos_uso": 0, "sesiones": 0})
        e.update({k2: p[k1] for k1, k2 in (("app", "app"), ("nombre_equipo", "nombre_equipo"), ("so", "so"),
                                          ("version", "version_app"), ("tienda", "tienda"), ("sdk", "sdk"))
                  if p.get(k1)})
        e["ultima_vez"] = ahora()
        e["segundos_uso"] += seg
        e["sesiones"] += 1 if p.get("inicio") else 0
        if p.get("sesion"):
            ses = sb["sesiones"].setdefault(p["sesion"], {"id": p["sesion"], "licencia": lic, "equipo": equipo,
                                                         "inicio": ahora(), "segundos": 0, "cerrada": False})
            ses["segundos"] += seg
            ses["ultima"] = ahora()
            ses["cerrada"] = ses["cerrada"] or bool(p.get("fin"))
        if seg:
            dia = ahora()[:10]
            sb["uso"][(lic, equipo, dia)] = sb["uso"].get((lic, equipo, dia), 0) + seg
        if p.get("evento"):
            sb["eventos"].append({"id": len(sb["eventos"]) + 1, "licencia": lic, "equipo": equipo,
                                  "tipo": p["evento"], "detalle": p.get("detalle") or "", "creado": ahora()})
        estado = sb["estados"].get(lic) or {}
        leidos = {(a, l, eq) for a, l, eq, _ in sb["leidos"]}
        avisos = [{k: a[k] for k in ("id", "tipo", "titulo", "mensaje", "fecha_limite", "creado")}
                  for a in sb["avisos"] if a["licencia"] in (None, lic)
                  and (a.get("app") in (None, p.get("app"))) and (a["id"], lic, equipo) not in leidos]
        return self._responder(200, {"estado": estado.get("estado") or "activa", "motivo": estado.get("motivo"),
                                     "avisos": avisos})

    def _sb_tabla(self, metodo: str, tabla: str, q: dict):
        if self._sb_clave() != SB_SECRETA:
            return self._responder(401, {"code": "42501", "message": f"permission denied for table {tabla}"})
        sb, uno = DATOS.sb, {k: v[0] for k, v in q.items()}
        filas = {
            "cinema_equipos": lambda: list(sb["equipos"].values()),
            "cinema_uso_diario": lambda: [{"licencia": l, "equipo": e, "dia": d, "segundos": s}
                                          for (l, e, d), s in sb["uso"].items()],
            "cinema_estados": lambda: list(sb["estados"].values()),
            "cinema_avisos": lambda: list(sb["avisos"]),
            "cinema_avisos_leidos": lambda: [{"aviso": a, "licencia": l, "equipo": e, "leido": f}
                                             for a, l, e, f in sb["leidos"]],
            "cinema_eventos": lambda: list(sb["eventos"]),
            "cinema_sesiones": lambda: list(sb["sesiones"].values()),
        }
        if tabla not in filas:
            return self._responder(404, {"code": "PGRST205", "message": f"Could not find the table 'public.{tabla}'"})
        if metodo == "GET":
            datos = filas[tabla]()
            for campo, filtro in uno.items():
                if campo in ("select", "order", "limit", "offset"):
                    continue
                op, _, valor = filtro.partition(".")
                datos = [d for d in datos if (str(d.get(campo)) == valor if op == "eq" else
                                              str(d.get(campo)) >= valor if op == "gte" else True)]
            if "order" in uno:
                campo, _, sentido = uno["order"].partition(".")
                datos.sort(key=lambda d: str(d.get(campo) or ""), reverse=sentido == "desc")
            inicio = int(uno.get("offset") or 0)
            return self._responder(200, datos[inicio:inicio + int(uno.get("limit") or 1000)])
        if metodo == "POST" and tabla == "cinema_avisos":
            nuevas = self._json()
            nuevas = nuevas if isinstance(nuevas, list) else [nuevas]
            creadas = []
            for n in nuevas:
                sb["aviso_id"] += 1
                creadas.append({"id": sb["aviso_id"], "licencia": n.get("licencia"), "app": n.get("app"),
                                "tipo": n.get("tipo", "info"), "titulo": n["titulo"], "mensaje": n.get("mensaje", ""),
                                "fecha_limite": n.get("fecha_limite"), "creado": ahora(), "expira": None})
            sb["avisos"] += creadas
            return self._responder(201, creadas)
        if metodo == "POST" and tabla == "cinema_estados":
            n = self._json()
            sb["estados"][n["licencia"]] = {"licencia": n["licencia"], "estado": n["estado"],
                                            "motivo": n.get("motivo"), "actualizado": ahora()}
            self.send_response(201)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if metodo == "DELETE" and tabla == "cinema_avisos":
            id_ = uno.get("id", "").partition(".")[2]
            sb["avisos"] = [a for a in sb["avisos"] if str(a["id"]) != id_]
            sb["leidos"] = {x for x in sb["leidos"] if str(x[0]) != id_}
            self.send_response(204)
            self.end_headers()
            return None
        return self._responder(405, {"message": "not allowed"})

    def _form(self) -> dict:
        return {k: v[0] for k, v in urllib.parse.parse_qs(self._cuerpo().decode()).items()}

    def do_PUT(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.startswith("/v2/"):
            with DATOS.lock:
                return self._gumroad("PUT", url.path[4:], self._form())
        self._responder(404, {"errors": [{"status": "404", "title": "Not Found"}]})

    def do_DELETE(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.startswith("/rest/v1/"):
            with DATOS.lock:
                return self._sb_tabla("DELETE", url.path[9:], urllib.parse.parse_qs(url.query))
        self._responder(404, {"message": "Not Found"})

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path.startswith("/rest/v1/"):
            with DATOS.lock:
                return self._sb_tabla("GET", url.path[9:], q)
        if url.path.startswith("/polar/v1/"):
            with DATOS.lock:
                return self._polar("GET", url.path[10:], q)
        if url.path.startswith("/v2/"):
            with DATOS.lock:
                return self._gumroad("GET", url.path[4:], {k: v[0] for k, v in q.items()})
        if url.path.startswith(("/payments/", "/products/api/")):
            with DATOS.lock:
                return self._hotmart_get(url.path, q)
        ruta = url.path.removeprefix("/v1/")
        if not self._autorizado():
            return
        with DATOS.lock:
            if ruta == "users/me":
                return self._responder(200, {"meta": {"test_mode": True}, "data": {"type": "users", "id": "1",
                                             "attributes": {"name": "Alejandro", "email": "vendedor@example.com"}}})
            if ruta == "stores":
                return self._lista("stores", [(TIENDA, {"name": "Mi Tienda", "url": "https://mitienda.lemonsqueezy.com",
                                                        "currency": "USD"})], q)
            if ruta == "products":
                return self._lista("products", [(PRODUCTO, {"store_id": TIENDA, "name": "Resolve Creator Subtitles",
                                                            "buy_now_url": "https://mitienda.lemonsqueezy.com/buy/abc"})], q)
            if ruta == "variants":
                return self._lista("variants", [(VARIANTE, {"product_id": PRODUCTO, "name": "Default", "price": 1900,
                                                            "has_license_keys": True})], q)
            if ruta == "license-keys":
                lics = [(i, l | {"status": DATOS.estado(l)}) for i, l in DATOS.licencias.items()]
                return self._lista("license-keys", lics, q)
            if ruta == "license-key-instances":
                return self._lista("license-key-instances", list(DATOS.instancias.items()), q)
            if ruta == "orders":
                return self._lista("orders", list(DATOS.ventas.items()), q)
        self._responder(404, {"errors": [{"status": "404", "title": "Not Found"}]})

    def do_PATCH(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.startswith("/polar/v1/"):
            with DATOS.lock:
                return self._polar("PATCH", url.path[10:], urllib.parse.parse_qs(url.query))
        if not self._autorizado():
            return
        ruta = url.path.removeprefix("/v1/")
        cuerpo = json.loads(self._cuerpo())
        with DATOS.lock:
            if ruta.startswith("license-keys/"):
                id_ = int(ruta.split("/")[1])
                lic = DATOS.licencias.get(id_)
                if not lic or cuerpo["data"]["id"] != str(id_):
                    return self._responder(404, {"errors": [{"status": "404", "title": "Not Found"}]})
                lic.update(cuerpo["data"]["attributes"])
                return self._responder(200, {"data": {"type": "license-keys", "id": str(id_),
                                                      "attributes": lic | {"status": DATOS.estado(lic)}}})
        self._responder(404, {"errors": [{"status": "404", "title": "Not Found"}]})

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.startswith("/rest/v1/rpc/"):
            with DATOS.lock:
                return self._sb_rpc(url.path[13:])
        if url.path.startswith("/rest/v1/"):
            with DATOS.lock:
                return self._sb_tabla("POST", url.path[9:], urllib.parse.parse_qs(url.query))
        if url.path.startswith("/polar/v1/customer-portal/license-keys/"):
            with DATOS.lock:
                return self._polar_publico(url.path.rsplit("/", 1)[1])
        if url.path.startswith("/polar/v1/"):
            with DATOS.lock:
                return self._polar("POST", url.path[10:], urllib.parse.parse_qs(url.query))
        if url.path == "/security/oauth/token":
            return self._hotmart_token(urllib.parse.parse_qs(url.query))
        if url.path.startswith("/v2/"):
            with DATOS.lock:
                return self._gumroad("POST", url.path[4:], self._form())
        ruta = url.path.removeprefix("/v1/")
        if ruta.startswith("licenses/"):
            return self._licencias(ruta.split("/")[1])
        if not self._autorizado():
            return
        cuerpo = json.loads(self._cuerpo())
        with DATOS.lock:
            if ruta == "checkouts":
                DATOS.checkouts.append(cuerpo)
                id_ = str(uuid.uuid4())
                return self._responder(201, {"data": {"type": "checkouts", "id": id_, "attributes": {
                    **cuerpo["data"]["attributes"], "url": f"https://mitienda.lemonsqueezy.com/checkout/custom/{id_}"}}})
            if ruta == "discounts":
                DATOS.descuentos.append(cuerpo)
                return self._responder(201, {"data": {"type": "discounts", "id": "9",
                                                      "attributes": cuerpo["data"]["attributes"]}})
        self._responder(404, {"errors": [{"status": "404", "title": "Not Found"}]})


def iniciar(puerto: int = 0) -> ThreadingHTTPServer:
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


if __name__ == "__main__":
    s = iniciar(8765)
    print(DATOS.vender())
    print(DATOS.vender_polar())
    print("Simulador en http://127.0.0.1:8765  (Ctrl+C para salir)")
    threading.Event().wait()
