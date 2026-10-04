"""Pruebas del sistema de licencias contra el simulador de Lemon Squeezy, Hotmart y Gumroad (sin internet).

    pip install -r licencias/requirements.txt
    python -m unittest discover -s licencias/pruebas -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="licencias-pruebas-")
os.environ["APPDATA"] = _TMP   # configuración y licencia.dat van a una carpeta temporal

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ / "programa"), str(RAIZ / "administrador"), str(Path(__file__).parent)]

import administrador_licencias as adm  # noqa: E402
import interfaz  # noqa: E402
import licencia_cliente as cli  # noqa: E402
import plataformas as plat  # noqa: E402
import simulador as sim  # noqa: E402

SERVIDOR = sim.iniciar()
RAIZ_SIM = f"http://127.0.0.1:{SERVIDOR.server_address[1]}"
BASE = RAIZ_SIM + "/v1/"
CFG_LS = {"api_key": sim.API_KEY, "tienda_id": sim.TIENDA, "tienda_nombre": "Mi Tienda",
          "producto_id": sim.PRODUCTO, "moneda": "USD"}
CFG_HM = {"client_id": sim.HM_ID, "client_secret": sim.HM_SECRETO}
CFG_GR = {"token": sim.GR_TOKEN, "producto_id": sim.GR_PRODUCTO}


class Base(unittest.TestCase):
    def setUp(self):
        sim.DATOS.__init__()
        self.carpeta = Path(tempfile.mkdtemp(dir=_TMP))
        self.parches = [
            mock.patch.object(cli, "_API", BASE + "licenses/"),
            mock.patch.object(cli, "TIENDA_ID", sim.TIENDA),
            mock.patch.object(cli, "PRODUCTOS_ID", (sim.PRODUCTO,)),
            mock.patch.object(cli, "_CARPETA", self.carpeta),
            mock.patch.object(cli, "_ARCHIVO", self.carpeta / "licencia.dat"),
            mock.patch.object(cli, "_id_bruto_equipo", lambda: "equipo-de-pruebas-1"),
            mock.patch.object(plat, "LS_API", BASE),
            mock.patch.object(plat, "HOTMART_AUTH", RAIZ_SIM + "/security/oauth/token"),
            mock.patch.object(plat, "HOTMART_API", {False: RAIZ_SIM, True: RAIZ_SIM}),
            mock.patch.object(plat, "GUMROAD_API", RAIZ_SIM + "/v2/"),
            mock.patch.object(cli, "_GUMROAD_API", RAIZ_SIM + "/v2/licenses/"),
            mock.patch.object(cli, "GUMROAD_PRODUCTO_ID", sim.GR_PRODUCTO),
            mock.patch.object(adm, "CARPETA_CONFIG", self.carpeta / "admin"),
            mock.patch.object(adm, "ARCHIVO_CONFIG", self.carpeta / "admin" / "config.json"),
            mock.patch.object(adm, "ARCHIVO_CONFIG_V2", self.carpeta / "admin" / "config_lemonsqueezy.json"),
        ]
        for p in self.parches:
            p.start()
        self.api = plat.LemonSqueezy(sim.API_KEY)
        self.hm = plat.Hotmart(sim.HM_ID, sim.HM_SECRETO)
        self.gr = plat.Gumroad(sim.GR_TOKEN)

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def otro_equipo(self, nombre="equipo-de-pruebas-2"):
        carpeta = Path(tempfile.mkdtemp(dir=_TMP))
        return [mock.patch.object(cli, "_id_bruto_equipo", lambda: nombre),
                mock.patch.object(cli, "_CARPETA", carpeta),
                mock.patch.object(cli, "_ARCHIVO", carpeta / "licencia.dat")]


class ProgramaCliente(Base):
    def test_sin_configurar(self):
        with mock.patch.object(cli, "TIENDA_ID", 0), mock.patch.object(cli, "GUMROAD_PRODUCTO_ID", ""):
            self.assertEqual(cli.comprobar().codigo, "error")
            self.assertEqual(cli.activar("x").codigo, "error")

    def test_sin_licencia_y_clave_invalida(self):
        self.assertEqual(cli.comprobar().codigo, "sin_licencia")
        r = cli.activar("no-existe")
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, "invalida")

    def test_activar_y_validar(self):
        lic = sim.DATOS.vender(cliente="Ana", correo="ana@example.com")
        r = cli.activar(f"  {lic['key']}  ")
        self.assertTrue(r.ok, r.mensaje)
        self.assertEqual(r.datos["cliente"], "Ana")
        self.assertEqual(sim.DATOS.licencias[lic["id"]]["instances_count"], 1)
        nombre = next(iter(sim.DATOS.instancias.values()))["name"]
        self.assertTrue(nombre.endswith(" · " + cli.obtener_id_equipo()))
        r = cli.comprobar()
        self.assertTrue(r.ok, r.mensaje)
        self.assertEqual(r.codigo, "activa")
        # Volver a escribir la misma clave no gasta otro equipo.
        self.assertTrue(cli.activar(lic["key"]).ok)
        self.assertEqual(sim.DATOS.licencias[lic["id"]]["instances_count"], 1)

    def test_limite_de_equipos(self):
        lic = sim.DATOS.vender(limite=1)
        self.assertTrue(cli.activar(lic["key"]).ok)
        parches = self.otro_equipo()
        for p in parches:
            p.start()
        try:
            r = cli.activar(lic["key"])
            self.assertEqual(r.codigo, "en_uso", r.mensaje)
        finally:
            for p in parches:
                p.stop()

    def test_bloqueo_vencimiento_y_sin_internet(self):
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        self.api.editar_licencia(lic["id"], {"disabled": True})
        self.assertEqual(cli.comprobar().codigo, "bloqueada")
        with mock.patch.object(cli, "_API", "http://127.0.0.1:9/v1/licenses/"):
            self.assertFalse(cli.comprobar().ok, "tras un bloqueo no debe quedar el modo sin conexión")
        self.api.editar_licencia(lic["id"], {"disabled": False})
        self.assertTrue(cli.comprobar().ok)
        self.api.editar_licencia(lic["id"], {"expires_at": "2020-01-01T00:00:00.000000Z"})
        r = cli.comprobar()
        self.assertEqual(r.codigo, "vencida")
        self.assertIn("01/01/2020", r.mensaje)

    def test_modo_sin_conexion(self):
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        with mock.patch.object(cli, "_API", "http://127.0.0.1:9/v1/licenses/"):
            r = cli.comprobar()
            self.assertTrue(r.ok)
            self.assertEqual(r.codigo, "sin_conexion_ok")
            dentro_de_8_dias = time.time() + 8 * 86400
            with mock.patch.object(cli.time, "time", lambda: dentro_de_8_dias):
                self.assertEqual(cli.comprobar().codigo, "sin_conexion")

    def test_equipo_quitado_por_el_vendedor(self):
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        ins = next(iter(sim.DATOS.instancias.values()))
        self.api.quitar_equipo(lic["key"], ins["identifier"])
        r = cli.comprobar()
        self.assertEqual(r.codigo, "desactivada", r.mensaje)
        self.assertEqual(r.datos.get("clave"), lic["key"])   # la ventana la muestra ya escrita
        self.assertTrue(cli.activar(lic["key"]).ok)          # y se puede volver a activar

    def test_desactivar_para_cambiar_de_pc(self):
        lic = sim.DATOS.vender(limite=1)
        self.assertTrue(cli.activar(lic["key"]).ok)
        r = cli.desactivar()
        self.assertTrue(r.ok, r.mensaje)
        self.assertIsNone(cli.licencia_guardada())
        self.assertEqual(sim.DATOS.licencias[lic["id"]]["instances_count"], 0)
        self.assertEqual(cli.comprobar().codigo, "sin_licencia")
        parches = self.otro_equipo()
        for p in parches:
            p.start()
        try:
            self.assertTrue(cli.activar(lic["key"]).ok)
        finally:
            for p in parches:
                p.stop()

    def test_clave_de_otra_tienda_o_producto(self):
        ajena = sim.DATOS.vender(tienda=999)
        self.assertEqual(cli.activar(ajena["key"]).codigo, "otra_tienda")
        self.assertEqual(sim.DATOS.licencias[ajena["id"]]["instances_count"], 0, "debe devolver el equipo")
        otro_producto = sim.DATOS.vender(producto=555)
        self.assertEqual(cli.activar(otro_producto["key"]).codigo, "otra_tienda")

    def test_claves_de_prueba(self):
        lic = sim.DATOS.vender(test_mode=True)
        with mock.patch.object(cli, "ACEPTAR_CLAVES_DE_PRUEBA", False):
            self.assertEqual(cli.activar(lic["key"]).codigo, "otra_tienda")
        real = sim.DATOS.vender(test_mode=False)
        with mock.patch.object(cli, "ACEPTAR_CLAVES_DE_PRUEBA", False):
            self.assertTrue(cli.activar(real["key"]).ok)

    def test_archivo_local_manipulado(self):
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        texto = cli._ARCHIVO.read_text(encoding="utf-8").replace('"ultima_ok": ', '"ultima_ok": 9')
        cli._ARCHIVO.write_text(texto, encoding="utf-8")
        self.assertIsNone(cli.licencia_guardada())


class GumroadCliente(Base):
    def en_otro_equipo(self):
        parches = self.otro_equipo()
        for p in parches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in parches])

    def test_activar_validar_y_limite(self):
        venta = sim.DATOS.vender_gumroad(cliente="Mateo Ríos", correo="mateo@x.com")
        clave = venta["license_key"]
        self.assertTrue(cli.parece_clave_gumroad(clave))
        r = cli.activar(clave)
        self.assertTrue(r.ok, r.mensaje)
        self.assertEqual((r.datos["plataforma"], r.datos["cliente"], r.datos["usados"]), ("gumroad", "Mateo Ríos", 1))
        self.assertTrue(cli.comprobar().ok)
        self.assertTrue(cli.activar(clave).ok)                       # otra vez en el mismo equipo
        self.assertEqual(sim.DATOS.gumroad_claves[clave]["uses"], 1, "validar no gasta usos")
        self.en_otro_equipo()
        self.assertEqual(cli.activar(clave).codigo, "en_uso")
        self.assertEqual(self.gr.liberar_uso(sim.GR_PRODUCTO, clave), 0)   # el vendedor libera un uso
        self.assertTrue(cli.activar(clave).ok)

    def test_bloqueo_reembolso_e_invalida(self):
        clave = sim.DATOS.vender_gumroad()["license_key"]
        self.assertTrue(cli.activar(clave).ok)
        self.gr.bloquear(sim.GR_PRODUCTO, clave)
        self.assertEqual(cli.comprobar().codigo, "bloqueada")
        self.assertTrue(self.gr.licencia(sim.GR_PRODUCTO, clave)["bloqueada"])
        self.gr.bloquear(sim.GR_PRODUCTO, clave, False)
        self.assertTrue(cli.comprobar().ok)
        sim.DATOS.gumroad_claves[clave]["venta"]["refunded"] = True
        self.assertEqual(cli.comprobar().codigo, "reembolsada")
        self.assertEqual(cli.activar("AAAAAAAA-BBBBBBBB-CCCCCCCC-DDDDDDDD").codigo, "invalida")

    def test_desactivar_y_sin_internet(self):
        clave = sim.DATOS.vender_gumroad()["license_key"]
        self.assertTrue(cli.activar(clave).ok)
        with mock.patch.object(cli, "_GUMROAD_API", "http://127.0.0.1:9/v2/licenses/"):
            self.assertEqual(cli.comprobar().codigo, "sin_conexion_ok")
        r = cli.desactivar()
        self.assertTrue(r.ok)
        self.assertIn("libere un uso", r.mensaje)
        self.assertIsNone(cli.licencia_guardada())

    def test_solo_gumroad_y_compras_de_prueba(self):
        with mock.patch.object(cli, "TIENDA_ID", 0):
            self.assertEqual(cli.activar("38b1460a-5104-4067-a91d-77b872934d51").codigo, "invalida")
            prueba = sim.DATOS.vender_gumroad(test=True)["license_key"]
            with mock.patch.object(cli, "ACEPTAR_CLAVES_DE_PRUEBA", False):
                self.assertEqual(cli.activar(prueba).codigo, "otra_tienda")
            otra = sim.DATOS.vender_gumroad(producto="otro")["license_key"]
            self.assertEqual(cli.activar(otra).codigo, "invalida")      # la clave es de otro producto


class GumroadApi(Base):
    def test_token_incorrecto(self):
        with self.assertRaises(plat.ErrorApi) as e:
            plat.Gumroad("malo").conectar()
        self.assertIn("access token", str(e.exception))

    def test_conectar_ventas_y_paginacion(self):
        for i in range(23):
            sim.DATOS.vender_gumroad(cliente=f"C{i}", correo=f"c{i}@x.com")
        sim.DATOS.vender_gumroad(cliente="R", correo="r@x.com", reembolsada=True)
        sim.DATOS.vender_gumroad(cliente="C0", correo="C0@x.com", con_clave=False)
        r = self.gr.conectar()
        self.assertEqual(r["usuario"]["name"], "Alejandro")
        self.assertEqual(r["productos"][0]["id"], sim.GR_PRODUCTO)
        self.assertEqual((r["ventas_validas"], r["compradores"], r["reembolsos"], r["claves"]), (24, 23, 1, 24))
        v = next(x for x in self.gr.ventas(max_edad=0) if x["cliente"] == "R")
        self.assertEqual((v["estado"], v["valida"], v["total"], v["total_txt"]), ("Reembolsada", False, 25.0, "$25"))


class LemonSqueezyApi(Base):
    def test_api_key_incorrecta(self):
        with self.assertRaises(plat.ErrorApi) as e:
            plat.LemonSqueezy("mala").conectar()
        self.assertIn("API key", str(e.exception))

    def test_conectar_resumen(self):
        sim.DATOS.vender()
        r = self.api.conectar()
        self.assertEqual(r["usuario"]["name"], "Alejandro")
        self.assertEqual(r["tiendas"][0]["id"], sim.TIENDA)
        self.assertEqual(r["tienda"]["licencias"], 1)
        self.assertEqual(r["tienda"]["ventas"], 1)
        self.assertEqual(r["tienda"]["variantes"][0]["producto"], "Resolve Creator Subtitles")

    def test_datos(self):
        lic = sim.DATOS.vender()
        sim.DATOS.vender(tienda=999)
        self.assertTrue(cli.activar(lic["key"]).ok)
        d = self.api.datos(sim.TIENDA, sim.PRODUCTO)
        self.assertEqual([l["id"] for l in d["licencias"]], [lic["id"]])
        self.assertEqual(d["licencias"][0]["status"], "active")
        self.assertEqual(len(d["instancias"]), 1)
        v = d["ventas"][0]
        self.assertEqual((v["plataforma"], v["estado"], v["valida"], v["total"]), ("lemonsqueezy", "Pagada", True, 19.0))

    def test_paginacion(self):
        for _ in range(230):
            sim.DATOS.vender()
        self.assertEqual(len(self.api.datos(sim.TIENDA)["licencias"]), 230)

    def test_editar_licencia(self):
        lic = sim.DATOS.vender()
        r = self.api.editar_licencia(lic["id"], {"activation_limit": None, "expires_at": None})
        self.assertIsNone(r["activation_limit"])
        self.assertEqual(self.api.editar_licencia(lic["id"], {"disabled": True})["status"], "disabled")

    def test_enlaces_de_compra(self):
        venta = {"variante_id": sim.VARIANTE, "cliente": "Luis", "correo": "luis@example.com",
                 "telefono": "50255551234", "precio": "normal", "centavos": 0, "expira": None}
        self.assertTrue(self.api.crear_enlace(sim.TIENDA, venta).startswith("https://"))
        atributos = sim.DATOS.checkouts[-1]["data"]["attributes"]
        self.assertEqual(atributos["checkout_data"], {"name": "Luis", "email": "luis@example.com"})
        self.assertNotIn("custom_price", atributos)
        self.api.crear_enlace(sim.TIENDA, venta | {"precio": "especial", "centavos": 1250})
        self.assertEqual(sim.DATOS.checkouts[-1]["data"]["attributes"]["custom_price"], 1250)
        self.api.crear_enlace(sim.TIENDA, venta | {"precio": "gratis", "correo": "", "cliente": ""})
        cupon = sim.DATOS.descuentos[-1]["data"]
        self.assertEqual((cupon["attributes"]["amount"], cupon["attributes"]["max_redemptions"]), (100, 1))
        self.assertEqual(cupon["relationships"]["variants"]["data"][0]["id"], str(sim.VARIANTE))
        self.assertEqual(sim.DATOS.checkouts[-1]["data"]["attributes"]["checkout_data"],
                         {"discount_code": cupon["attributes"]["code"]})

    def test_datos_para_programa(self):
        espacio = {}
        exec(adm.datos_para_programa({"tienda_id": 5, "producto_id": 7, "url_compra": "https://x/buy/1"}), espacio)
        self.assertEqual((espacio["TIENDA_ID"], espacio["PRODUCTOS_ID"], espacio["URL_COMPRA"]),
                         (5, (7,), "https://x/buy/1"))


class HotmartApi(Base):
    def test_credenciales_incorrectas(self):
        with self.assertRaises(plat.ErrorApi) as e:
            plat.Hotmart(sim.HM_ID, "otro").conectar()
        self.assertIn("rechazó las credenciales", str(e.exception))

    def test_basic_manual_o_calculado(self):
        import base64
        basic = base64.b64encode(f"{sim.HM_ID}:{sim.HM_SECRETO}".encode()).decode()
        for valor in ("", basic, "Basic " + basic):
            self.assertEqual(plat.Hotmart(sim.HM_ID, sim.HM_SECRETO, valor).token()["access_token"], sim.HM_TOKEN)

    def test_ventas_y_resumen(self):
        sim.DATOS.vender_hotmart(cliente="Lucía", correo="lucia@x.com")
        sim.DATOS.vender_hotmart(cliente="Lucía", correo="LUCIA@x.com", estado="COMPLETE")
        sim.DATOS.vender_hotmart(cliente="Pedro", correo="pedro@x.com", estado="REFUNDED")
        sim.DATOS.vender_hotmart(cliente="Rita", correo="rita@x.com", estado="CHARGEBACK")
        sim.DATOS.vender_hotmart(cliente="Otro", correo="otro@x.com", estado="WAITING_PAYMENT")
        for i in range(60):   # más de una página (max_results=50)
            sim.DATOS.vender_hotmart(cliente=f"C{i}", correo=f"c{i}@x.com")
        r = self.hm.conectar()
        self.assertEqual(r["entorno"], "Producción")
        self.assertEqual(r["productos"][0]["id"], sim.HM_PRODUCTO)
        self.assertEqual(r["ventas_validas"], 62)
        self.assertEqual(r["compradores"], 61)          # Lucía compró dos veces
        self.assertEqual(r["reembolsos"], 2)
        self.assertAlmostEqual(r["ingresos"]["BRL"], 62 * 297.0)
        v = next(x for x in self.hm.ventas(max_edad=0) if x["cliente"] == "Pedro")
        self.assertEqual((v["estado"], v["valida"], v["plataforma"]), ("Reembolsada", False, "hotmart"))

    def test_token_se_reutiliza_y_cache(self):
        sim.DATOS.vender_hotmart()
        self.hm.ventas(max_edad=0)
        self.hm.ventas(max_edad=0)
        self.assertEqual(sim.DATOS.hotmart_tokens, 1)
        sim.DATOS.vender_hotmart(correo="nueva@x.com")
        self.assertEqual(len(self.hm.ventas(max_edad=60)), 1, "dentro de 60 s usa la copia guardada")
        self.assertEqual(len(self.hm.ventas(max_edad=0)), 2)

    def test_filtro_producto_y_sin_fechas(self):
        sim.DATOS.vender_hotmart(producto=sim.HM_PRODUCTO)
        sim.DATOS.vender_hotmart(producto=9999, correo="b@x.com")
        self.assertEqual(len(self.hm.ventas(sim.HM_PRODUCTO, max_edad=0)), 1)
        sim.DATOS.hotmart_rechaza_fechas = True
        self.assertEqual(len(self.hm.ventas(max_edad=0)), 2, "si Hotmart no acepta fechas, reintenta sin ellas")


class Modelo(Base):
    def test_personas_en_varias_plataformas(self):
        lic = sim.DATOS.vender(cliente="Ana", correo="ana@x.com")
        sim.DATOS.vender_hotmart(cliente="Ana López", correo="ANA@x.com")
        sim.DATOS.vender_hotmart(cliente="Pedro", correo="pedro@x.com", estado="REFUNDED")
        sim.DATOS.vender_hotmart(cliente="Lu", correo="lu@x.com")
        self.assertTrue(cli.activar(lic["key"]).ok)
        res = adm.cargar_todo({"lemonsqueezy": self.api, "hotmart": self.hm},
                              {"plataformas": {"lemonsqueezy": CFG_LS, "hotmart": CFG_HM}})
        m = adm.construir_modelo(res)
        personas = {p["clave"]: p for p in m["personas"]}
        self.assertEqual(sum(p["tiene"] for p in m["personas"]), 2)        # Ana y Lu
        self.assertEqual(personas["ana@x.com"]["plataformas"], {"lemonsqueezy", "hotmart"})
        self.assertEqual(personas["ana@x.com"]["equipos"], 1)
        self.assertEqual(personas["pedro@x.com"]["estado"], "Reembolsada")
        self.assertEqual(m["ventas_30"], 3)
        self.assertEqual(sum(m["serie"]["hotmart"]), 2)

    def test_licencias_de_gumroad_en_el_modelo(self):
        a = sim.DATOS.vender_gumroad(cliente="Ana", correo="ana@x.com")
        b = sim.DATOS.vender_gumroad(cliente="Bea", correo="bea@x.com", reembolsada=True)
        lic_ls = sim.DATOS.vender(cliente="Ana", correo="ANA@x.com")
        res = adm.cargar_todo({"lemonsqueezy": self.api, "gumroad": self.gr},
                              {"plataformas": {"lemonsqueezy": CFG_LS, "gumroad": CFG_GR | {"bloqueadas": [a["license_key"]]}}})
        m = adm.construir_modelo(res)
        por_clave = {l["key"]: l for l in m["licencias"]}
        self.assertEqual(por_clave[a["license_key"]]["status"], "disabled")
        self.assertEqual(por_clave[b["license_key"]]["status"], "refunded")
        self.assertEqual(por_clave[lic_ls["key"]]["plataforma"], "lemonsqueezy")
        ana = next(p for p in m["personas"] if p["clave"] == "ana@x.com")
        self.assertEqual(ana["plataformas"], {"lemonsqueezy", "gumroad"})
        texto = adm.datos_para_programa(CFG_LS, CFG_GR | {"url_compra": "https://x.gumroad.com/l/rcs"})
        espacio = {}
        exec(texto, espacio)
        self.assertEqual((espacio["GUMROAD_PRODUCTO_ID"], espacio["URL_COMPRA_GUMROAD"]),
                         (sim.GR_PRODUCTO, "https://x.gumroad.com/l/rcs"))

    def test_error_en_una_plataforma_no_bloquea_la_otra(self):
        sim.DATOS.vender()
        res = adm.cargar_todo({"lemonsqueezy": self.api, "hotmart": plat.Hotmart("x", "y")},
                              {"plataformas": {"lemonsqueezy": CFG_LS, "hotmart": {}}})
        self.assertIn("error", res["hotmart"])
        self.assertEqual(len(res["lemonsqueezy"]["licencias"]), 1)

    def test_migra_configuracion_v2(self):
        import json
        adm.CARPETA_CONFIG.mkdir(parents=True, exist_ok=True)
        adm.ARCHIVO_CONFIG_V2.write_text(json.dumps({"api_key": "k", "tienda_id": 5, "nombre_app": "X"}))
        cfg = adm.cargar_config()
        self.assertEqual(cfg["plataformas"]["lemonsqueezy"]["tienda_id"], 5)
        self.assertEqual(cfg["nombre_app"], "X")


class Ventanas(Base):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def esperar(self, condicion, segundos=10):
        fin = time.time() + segundos
        while time.time() < fin:
            self.app.processEvents()
            if condicion():
                return True
            time.sleep(0.02)
        self.fail("tiempo de espera agotado")

    def ventana(self, plataformas: dict):
        cfg = adm.config_base()
        cfg["plataformas"] |= plataformas
        adm.guardar_config(cfg)
        return adm.Ventana()

    def test_sin_conexion_muestra_bienvenida(self):
        v = self.ventana({})
        self.app.processEvents()
        self.assertEqual(v.paginas[0].pila.currentIndex(), 0)
        self.assertTrue(v.paginas[2].sin_ls.isVisibleTo(v.paginas[2]))
        v.close()

    def test_panel_completo(self):
        lic = sim.DATOS.vender(cliente="Ana", correo="ana@x.com")
        self.assertTrue(cli.activar(lic["key"]).ok)
        sim.DATOS.vender_hotmart(cliente="Lu", correo="lu@x.com")
        v = self.ventana({"lemonsqueezy": CFG_LS, "hotmart": CFG_HM})
        personas, licencias, equipos, ventas = v.paginas[1], v.paginas[2], v.paginas[3], v.paginas[4]
        self.esperar(lambda: licencias.t.rowCount() == 1 and ventas.t.rowCount() == 2)
        self.assertEqual(v.paginas[0].pila.currentIndex(), 1)
        self.esperar(lambda: v.paginas[0].k_personas.valor.text() == "2")
        self.assertEqual(personas.t.rowCount(), 2)
        self.assertEqual(equipos.t.rowCount(), 1)
        self.assertEqual(v.paginas[5].t.rowCount(), 3)   # 2 ventas + 1 activación

        # búsqueda global
        v.buscar.setText("lu@x")
        self.assertEqual(personas.t.rowCount(), 1)
        v.buscar.clear()

        # una venta nueva en Hotmart llega como aviso
        sim.DATOS.vender_hotmart(cliente="Beto", correo="beto@x.com")
        v.clientes["hotmart"]._cache = None
        v.refrescar()
        self.esperar(lambda: ventas.t.rowCount() == 3)
        self.assertIn("●", v.nav.botones[5].text())

        # panel de detalle de la licencia y quitar el equipo
        v.ir_a(2)
        licencias.t.selectRow(0)
        self.esperar(lambda: licencias.panel.maximumWidth() == licencias.panel.ancho)
        with mock.patch.object(adm, "confirmar", return_value=True):
            v.quitar_equipo(v.modelo["lic_por_id"][lic["id"]], v.modelo["instancias"][0])
        self.esperar(lambda: equipos.t.rowCount() == 0)
        self.assertTrue(any(e["tipo"] == "desactivacion" for e in v.eventos()))
        self.assertEqual(cli.comprobar().codigo, "desactivada")

        # bloquear
        with mock.patch.object(adm, "confirmar", return_value=True):
            v.alternar_bloqueo(v.modelo["lic_por_id"][lic["id"]])
        self.esperar(lambda: sim.DATOS.licencias[lic["id"]]["disabled"])
        self.esperar(lambda: licencias.b_bloquear.text() == "Desbloquear")
        v.close()

    def test_conectar_y_ventana_de_informacion(self):
        sim.DATOS.vender()
        v = self.ventana({})
        conectar = adm.DialogoConectar(v)
        conectar._elegir("lemonsqueezy")
        conectar._mostrar_formulario("lemonsqueezy")
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        conectar.show()
        conectar.api_key.setText("mala")
        QTest.keyClick(conectar.api_key, Qt.Key.Key_Return)      # Enter conecta y no vuelve atrás
        self.assertEqual(conectar.pila.currentIndex(), 1)
        self.esperar(lambda: "API key" in conectar.error.text())
        conectar.api_key.setText(sim.API_KEY)
        conectar.conectar()
        self.esperar(lambda: conectar.resultado is not None)
        clave, datos, resumen, cliente = conectar.resultado
        r = adm.DialogoResumen(clave, cliente, resumen, datos, v)
        self.assertEqual(r.modo.text(), "MODO PRUEBA")
        self.assertIn(f"TIENDA_ID = {sim.TIENDA}", r.codigo.text())
        self.assertIn(f"PRODUCTOS_ID = ({sim.PRODUCTO},)", r.codigo.text())
        r.guardar()
        v._guardar_conexion(clave, r.datos)
        self.assertIn("lemonsqueezy", v.clientes)
        self.assertEqual(adm.cargar_config()["plataformas"]["lemonsqueezy"]["tienda_id"], sim.TIENDA)

        sim.DATOS.vender_hotmart()
        hm = adm.DialogoConectar(v, "hotmart")
        hm.client_id.setText(sim.HM_ID)
        hm.client_secret.setText(sim.HM_SECRETO)
        hm.conectar()
        self.esperar(lambda: hm.resultado is not None)
        plataforma, datos_hm, resumen_hm, cliente_hm = hm.resultado
        r2 = adm.DialogoResumen(plataforma, cliente_hm, resumen_hm, datos_hm, v)
        self.assertEqual(r2.modo.text(), "PRODUCCIÓN")
        r2.guardar()
        v._guardar_conexion("hotmart", r2.datos)
        self.assertEqual(set(v.clientes), {"lemonsqueezy", "hotmart"})
        with mock.patch.object(adm, "confirmar", return_value=True):
            v.desconectar("hotmart")
        self.assertEqual(set(v.clientes), {"lemonsqueezy"})
        v.close()

    def test_gumroad_en_el_panel(self):
        a = sim.DATOS.vender_gumroad(cliente="Ana", correo="ana@x.com")
        v = self.ventana({"gumroad": CFG_GR})
        licencias = v.paginas[2]
        self.esperar(lambda: licencias.t.rowCount() == 1)
        self.assertFalse(licencias.nuevo.isVisibleTo(licencias), "sin Lemon Squeezy no hay enlaces de compra")
        v.ir_a(2)
        licencias.t.selectRow(0)
        self.esperar(lambda: licencias.lbl_usos is not None and licencias.lbl_usos.text() == "0")
        with mock.patch.object(adm, "confirmar", return_value=True):
            v.bloquear_gumroad(v.modelo["licencias"][0])
        self.esperar(lambda: sim.DATOS.gumroad_claves[a["license_key"]]["disabled"])
        self.esperar(lambda: v.modelo["licencias"][0]["status"] == "disabled")
        self.assertEqual(adm.cargar_config()["plataformas"]["gumroad"]["bloqueadas"], [a["license_key"]])
        sim.DATOS.gumroad_claves[a["license_key"]]["uses"] = 2
        with mock.patch.object(adm, "confirmar", return_value=True):
            v.liberar_uso_gumroad(v.modelo["licencias"][0])
        self.esperar(lambda: sim.DATOS.gumroad_claves[a["license_key"]]["uses"] == 1)
        v.close()

    def test_conectar_gumroad(self):
        sim.DATOS.vender_gumroad()
        v = self.ventana({})
        d = adm.DialogoConectar(v, "gumroad")
        d.token_gr.setText(sim.GR_TOKEN)
        d.conectar()
        self.esperar(lambda: d.resultado is not None)
        plataforma, datos, resumen, cliente = d.resultado
        r = adm.DialogoResumen(plataforma, cliente, resumen, datos, v)
        self.assertIn(f'GUMROAD_PRODUCTO_ID = "{sim.GR_PRODUCTO}"', r.codigo.text())
        r.guardar()
        v._guardar_conexion(plataforma, r.datos)
        guardado = adm.cargar_config()["plataformas"]["gumroad"]
        self.assertEqual((guardado["producto_id"], guardado["url_compra"]),
                         (sim.GR_PRODUCTO, "https://alejandro.gumroad.com/l/rcs"))
        v.close()

    def test_componentes_animados(self):
        interruptor = interfaz.Interruptor("Animaciones")
        interruptor.setChecked(True)
        self.assertEqual(interruptor._pos, 1.0)               # oculto: se mueve sin animar
        marca = interfaz.MarcaExito()
        marca.show()
        self.esperar(lambda: marca._p == 1.0, 3)
        v = self.ventana({})
        b = interfaz.Bienvenida("Administrador", "v4")
        b.mostrar()
        self.assertEqual(b._intro, 1.0, "el logo termina de aparecer antes de armar la ventana")
        b.terminar(v)
        self.esperar(lambda: v.isVisible() and not b.isVisible(), 4)
        interfaz.entrada_escalonada([v.btn_refrescar])
        v.close()

    def test_dialogos_y_animaciones(self):
        e = adm.DialogoEditar({"activation_limit": 2, "expires_at": None, "user_name": "Ana"})
        self.assertEqual(e.datos(), {"activation_limit": 2, "expires_at": None})
        e._sumar(30)
        self.assertIsNotNone(e.datos()["expires_at"])
        venta = adm.DialogoVenta(self.api.variantes(sim.TIENDA), "USD", previo={"cliente": "Lu", "precio": "gratis"})
        self.assertEqual(venta.datos()["precio"], "gratis")
        venta.precio.setCurrentIndex(1)
        venta.monto.setValue(12.5)
        self.assertEqual(venta.datos()["centavos"], 1250)
        adm.DialogoEnlace("https://x", venta.datos(), "App")
        contador = interfaz.ContadorAnimado()
        contador.fijar(42)
        self.esperar(lambda: contador.text() == "42", 3)
        with mock.patch.dict(interfaz.ANIMACIONES, {"activas": False}):
            contador.fijar(7)
            self.assertEqual(contador.text(), "7")
        self.assertIsNotNone(cli._DialogoActivacion(cli.Resultado(False, "sin_licencia", "")))
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        self.assertIsNotNone(cli._DialogoMiLicencia())


if __name__ == "__main__":
    unittest.main()
