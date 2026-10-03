"""Servidor falso de Lemon Squeezy para probar sin internet ni compras reales.

Imita los endpoints que usan licencia_cliente.py y administrador_licencias.py:
  - API de licencias: POST /v1/licenses/activate | validate | deactivate (sin API key)
  - API principal (JSON:API con Bearer): users/me, stores, products, variants, license-keys,
    license-key-instances, orders, checkouts, discounts
"""
from __future__ import annotations

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

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        ruta = url.path.removeprefix("/v1/")
        if not self._autorizado():
            return
        with DATOS.lock:
            if ruta == "users/me":
                return self._responder(200, {"data": {"type": "users", "id": "1", "attributes": {
                    "name": "Alejandro", "email": "vendedor@example.com"}}})
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
        ruta = urllib.parse.urlparse(self.path).path.removeprefix("/v1/")
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
