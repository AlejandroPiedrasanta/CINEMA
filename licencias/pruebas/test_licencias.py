"""Pruebas del sistema de licencias contra el simulador de Lemon Squeezy (no usa internet).

    pip install pyside6
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
import licencia_cliente as cli  # noqa: E402
import simulador_lemonsqueezy as sim  # noqa: E402

SERVIDOR = sim.iniciar()
BASE = f"http://127.0.0.1:{SERVIDOR.server_address[1]}/v1/"


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
            mock.patch.object(adm, "API_BASE", BASE),
        ]
        for p in self.parches:
            p.start()
        self.api = adm.Api(sim.API_KEY)

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
        with mock.patch.object(cli, "TIENDA_ID", 0):
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
        r = cli.comprobar()
        self.assertEqual(r.codigo, "bloqueada", r.mensaje)
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
        r = cli.activar(ajena["key"])
        self.assertEqual(r.codigo, "otra_tienda")
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


class Administrador(Base):
    def test_api_key_incorrecta(self):
        with self.assertRaises(adm.ErrorApi) as e:
            adm.Api("mala").conectar()
        self.assertIn("API key", str(e.exception))

    def test_conectar_y_leer_todo(self):
        r = self.api.conectar()
        self.assertEqual(r["usuario"]["name"], "Alejandro")
        self.assertEqual(r["tiendas"][0]["id"], sim.TIENDA)
        lic = sim.DATOS.vender()
        sim.DATOS.vender(tienda=999)
        self.assertTrue(cli.activar(lic["key"]).ok)
        todo = self.api.todo(sim.TIENDA, sim.PRODUCTO)
        self.assertEqual([l["id"] for l in todo["licencias"]], [lic["id"]])
        self.assertEqual(todo["licencias"][0]["status"], "active")
        self.assertEqual(len(todo["instancias"]), 1)
        self.assertEqual(len(todo["ventas"]), 1)

    def test_paginacion(self):
        for _ in range(230):
            sim.DATOS.vender()
        self.assertEqual(len(self.api.todo(sim.TIENDA)["licencias"]), 230)

    def test_editar_licencia(self):
        lic = sim.DATOS.vender()
        r = self.api.editar_licencia(lic["id"], {"activation_limit": None, "expires_at": None})
        self.assertIsNone(r["activation_limit"])
        self.assertEqual(self.api.editar_licencia(lic["id"], {"disabled": True})["status"], "disabled")

    def test_enlaces_de_compra(self):
        venta = {"variante_id": sim.VARIANTE, "cliente": "Luis", "correo": "luis@example.com",
                 "telefono": "50255551234", "precio": "normal", "centavos": 0, "expira": None}
        url = self.api.crear_enlace(sim.TIENDA, venta)
        self.assertTrue(url.startswith("https://"))
        atributos = sim.DATOS.checkouts[-1]["data"]["attributes"]
        self.assertEqual(atributos["checkout_data"], {"name": "Luis", "email": "luis@example.com"})
        self.assertNotIn("custom_price", atributos)

        self.api.crear_enlace(sim.TIENDA, venta | {"precio": "especial", "centavos": 1250})
        self.assertEqual(sim.DATOS.checkouts[-1]["data"]["attributes"]["custom_price"], 1250)

        self.api.crear_enlace(sim.TIENDA, venta | {"precio": "gratis", "correo": "", "cliente": ""})
        cupon = sim.DATOS.descuentos[-1]["data"]
        self.assertEqual(cupon["attributes"]["amount"], 100)
        self.assertEqual(cupon["attributes"]["max_redemptions"], 1)
        self.assertEqual(cupon["relationships"]["variants"]["data"][0]["id"], str(sim.VARIANTE))
        self.assertEqual(sim.DATOS.checkouts[-1]["data"]["attributes"]["checkout_data"],
                         {"discount_code": cupon["attributes"]["code"]})

    def test_variantes(self):
        v = self.api.variantes(sim.TIENDA)
        self.assertEqual(v[0]["producto"], "Resolve Creator Subtitles")

    def test_datos_para_programa(self):
        texto = adm.datos_para_programa({"tienda_id": 5, "producto_id": 7, "url_compra": "https://x/buy/1"})
        espacio = {}
        exec(texto, espacio)
        self.assertEqual((espacio["TIENDA_ID"], espacio["PRODUCTOS_ID"], espacio["URL_COMPRA"]),
                         (5, (7,), "https://x/buy/1"))


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

    def test_panel_completo(self):
        lic = sim.DATOS.vender(cliente="Ana")
        self.assertTrue(cli.activar(lic["key"]).ok)
        adm.guardar_config(adm.cargar_config() | {"api_key": sim.API_KEY, "tienda_id": sim.TIENDA,
                                                  "tienda_nombre": "Mi Tienda", "producto_id": sim.PRODUCTO})
        v = adm.Ventana()
        self.esperar(lambda: v.tl.rowCount() == 1)
        self.assertEqual(v.te.rowCount(), 1)
        self.assertEqual(v.tv.rowCount(), 1)
        self.assertEqual(v.ta.rowCount(), 2)   # venta + activación
        self.assertEqual(v.t_act.valor.text(), "1")

        # Una venta nueva llega como notificación
        sim.DATOS.vender(cliente="Beto")
        v.refrescar()
        self.esperar(lambda: v.tl.rowCount() == 2)
        self.assertIn("●", v.tabs.tabText(v.TAB_ACTIVIDAD))

        # Quitar el equipo desde el panel → aparece "Equipo desactivado"
        v.te.selectRow(0)
        with mock.patch.object(v, "confirmar", return_value=True):
            v.quitar_equipo_seleccionado()
        self.esperar(lambda: v.te.rowCount() == 0)
        self.assertTrue(any(e["tipo"] == "desactivacion" for e in v.eventos()))
        self.assertEqual(cli.comprobar().codigo, "desactivada")

        # Bloquear desde el panel
        v.tabs.setCurrentIndex(0)
        fila = next(r for r in range(v.tl.rowCount()) if v.tl.item(r, 0).text() == "Ana")
        v.tl.selectRow(fila)
        with mock.patch.object(v, "confirmar", return_value=True):
            v.alternar_bloqueo()
        self.esperar(lambda: sim.DATOS.licencias[lic["id"]]["disabled"])
        self.esperar(lambda: v.b_bloq.text() == "Desbloquear")
        v.close()

    def test_dialogos(self):
        cfg = adm.cargar_config() | {"api_key": sim.API_KEY, "tienda_id": sim.TIENDA, "producto_id": sim.PRODUCTO}
        d = adm.DialogoConfig(cfg)
        self.esperar(lambda: d.producto.count() == 2 and "✔" in d.estado.text())
        self.assertIn(f"TIENDA_ID = {sim.TIENDA}", d.datos.toPlainText())
        self.assertIn(f"PRODUCTOS_ID = ({sim.PRODUCTO},)", d.datos.toPlainText())
        self.assertIn("buy/abc", d.datos.toPlainText())

        e = adm.DialogoEditar({"activation_limit": 2, "expires_at": None, "user_name": "Ana"})
        self.assertEqual(e.datos(), {"activation_limit": 2, "expires_at": None})
        e._sumar(30)
        self.assertIsNotNone(e.datos()["expires_at"])

        venta = adm.DialogoVenta(self.api.variantes(sim.TIENDA), "USD")
        venta.precio.setCurrentIndex(1)
        venta.monto.setValue(12.5)
        self.assertEqual(venta.datos()["centavos"], 1250)
        adm.DialogoEnlace("https://x", venta.datos(), "App")

        self.assertIsNotNone(cli._DialogoActivacion(cli.Resultado(False, "sin_licencia", "")))
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        self.assertIsNotNone(cli._DialogoMiLicencia())


if __name__ == "__main__":
    unittest.main()
