"""Servidor falso de Lemon Squeezy y Hotmart para probar sin internet ni compras reales.

Imita los endpoints que usan licencia_cliente.py y el Administrador:
  - API de licencias: POST /v1/licenses/activate | validate | deactivate (sin API key)
  - API principal (JSON:API con Bearer): users/me, stores, products, variants, license-keys,
    license-key-instances, orders, checkouts, discounts
  - Hotmart: POST /security/oauth/token, GET /payments/api/v1/sales/history, GET /products/api/v1/products
  - Gumroad: GET /v2/user | products | sales, POST /v2/licenses/verify,
    PUT /v2/licenses/enable | disable | decrement_uses_count
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

    def _form(self) -> dict:
        return {k: v[0] for k, v in urllib.parse.parse_qs(self._cuerpo().decode()).items()}

    def do_PUT(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.startswith("/v2/"):
            with DATOS.lock:
                return self._gumroad("PUT", url.path[4:], self._form())
        self._responder(404, {"errors": [{"status": "404", "title": "Not Found"}]})

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
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
        if not self._autorizado():
            return
        ruta = urllib.parse.urlparse(self.path).path.removeprefix("/v1/")
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
    print("Simulador en http://127.0.0.1:8765  (Ctrl+C para salir)")
    threading.Event().wait()
