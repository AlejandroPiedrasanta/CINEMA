"""Cinema Productions · pruebas del sistema de licencias contra el simulador (sin internet).

Lemon Squeezy, Hotmart, Gumroad, Polar y el servidor de control (Supabase) son falsos: ver simulador.py.

    pip install -r licencias/requirements.txt
    python -m unittest discover -s licencias/pruebas -v

Creado por Cinema Productions.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="licencias-pruebas-")
os.environ["APPDATA"] = _TMP          # configuración y licencias van a una carpeta temporal
os.environ["XDG_CONFIG_HOME"] = _TMP

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ / "programa"), str(RAIZ / "administrador"), str(Path(__file__).parent)]

import administrador_licencias as adm  # noqa: E402
import cinema_licencias  # noqa: E402
import cinema_licencias.base as sdk_base  # noqa: E402
import cinema_licencias.licencias as sdk_licencias  # noqa: E402
import control  # noqa: E402
import interfaz  # noqa: E402
import licencia_cliente as cli  # noqa: E402
import modelo  # noqa: E402
import paginas  # noqa: E402
import plataformas as plat  # noqa: E402
import simulador as sim  # noqa: E402
from cinema_licencias import Configuracion, Licencias, Resultado, hash_licencia, tiendas  # noqa: E402
from PySide6.QtCore import QDate, Qt  # noqa: E402

SERVIDOR = sim.iniciar()
RAIZ_SIM = f"http://127.0.0.1:{SERVIDOR.server_address[1]}"
BASE = RAIZ_SIM + "/v1/"
APAGADO = "http://127.0.0.1:9"
CFG_LS = {"api_key": sim.API_KEY, "tienda_id": sim.TIENDA, "tienda_nombre": "Mi Tienda",
          "producto_id": sim.PRODUCTO, "moneda": "USD"}
CFG_HM = {"client_id": sim.HM_ID, "client_secret": sim.HM_SECRETO}
CFG_GR = {"token": sim.GR_TOKEN, "producto_id": sim.GR_PRODUCTO}
CFG_PO = {"token": sim.PO_TOKEN, "organizacion_id": sim.PO_ORG, "beneficio_id": sim.PO_BENEFICIO}
CFG_SV = {"url": RAIZ_SIM, "clave_secreta": sim.SB_SECRETA, "clave_publica": sim.SB_PUBLICA}


def esperar_hilos():
    """Espera a los envíos en segundo plano (eventos y avisos leídos) del SDK."""
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon and t.name.startswith("Thread"):
            t.join(2)


def cerrar(ventana):
    try:
        ventana._salir = True
        ventana.close()
    except RuntimeError:      # ya se borró (por ejemplo, al cambiar de tema)
        pass


class Base(unittest.TestCase):
    def setUp(self):
        sim.DATOS.__init__()
        self.carpeta = Path(tempfile.mkdtemp(dir=_TMP))
        self.parches = [
            mock.patch.object(tiendas, "LS_API", BASE + "licenses/"),
            mock.patch.object(tiendas, "GUMROAD_API", RAIZ_SIM + "/v2/licenses/"),
            mock.patch.object(tiendas, "POLAR_API", {False: RAIZ_SIM + "/polar", True: RAIZ_SIM + "/polar"}),
            mock.patch.object(sdk_base, "_id_bruto_equipo", lambda: "equipo-de-pruebas-1"),
            mock.patch.object(cli, "TIENDA_ID", sim.TIENDA),
            mock.patch.object(cli, "PRODUCTOS_ID", (sim.PRODUCTO,)),
            mock.patch.object(cli, "GUMROAD_PRODUCTO_ID", sim.GR_PRODUCTO),
            mock.patch.object(cli, "_CARPETA", self.carpeta),
            mock.patch.dict(cli._INSTANCIAS, clear=True),
            mock.patch.object(plat, "LS_API", BASE),
            mock.patch.object(plat, "HOTMART_AUTH", RAIZ_SIM + "/security/oauth/token"),
            mock.patch.object(plat, "HOTMART_API", {False: RAIZ_SIM, True: RAIZ_SIM}),
            mock.patch.object(plat, "GUMROAD_API", RAIZ_SIM + "/v2/"),
            mock.patch.object(plat, "POLAR_API", {False: RAIZ_SIM + "/polar", True: RAIZ_SIM + "/polar"}),
            mock.patch.object(modelo, "CARPETA_CONFIG", self.carpeta / "admin"),
            mock.patch.object(modelo, "CARPETA_V4", self.carpeta / "RCS-Administrador"),
        ]
        for p in self.parches:
            p.start()
        self.api = plat.LemonSqueezy(sim.API_KEY)
        self.hm = plat.Hotmart(sim.HM_ID, sim.HM_SECRETO)
        self.gr = plat.Gumroad(sim.GR_TOKEN)
        self.po = plat.Polar(sim.PO_TOKEN, organizacion_id=sim.PO_ORG)
        self.srv = control.ServidorControl(RAIZ_SIM, sim.SB_SECRETA, sim.SB_PUBLICA)

    def tearDown(self):
        esperar_hilos()
        for p in self.parches:
            p.stop()

    def otro_equipo(self, nombre="equipo-de-pruebas-2"):
        carpeta = Path(tempfile.mkdtemp(dir=_TMP))
        parches = [mock.patch.object(sdk_base, "_id_bruto_equipo", lambda: nombre),
                   mock.patch.object(cli, "_CARPETA", carpeta)]
        for p in parches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in parches])

    def sdk(self, **opciones) -> Licencias:
        """Licencias del SDK con todas las tiendas del simulador y el servidor de control."""
        base = dict(app="Resolve Creator Subtitles", version="5.0.0", ls_tienda_id=sim.TIENDA,
                    ls_productos=(sim.PRODUCTO,), gumroad_producto_id=sim.GR_PRODUCTO,
                    polar_organizacion_id=sim.PO_ORG, servidor_url=RAIZ_SIM, servidor_clave=sim.SB_PUBLICA,
                    carpeta=str(Path(tempfile.mkdtemp(dir=_TMP))))
        return Licencias(Configuracion(**(base | opciones)))


# ============================================================ programa (forma v4: licencia_cliente.py)

class ProgramaCliente(Base):
    def test_sin_configurar(self):
        with mock.patch.object(cli, "TIENDA_ID", 0), mock.patch.object(cli, "GUMROAD_PRODUCTO_ID", ""):
            self.assertEqual(cli.comprobar().codigo, "error")
            self.assertEqual(cli.activar("x").codigo, "error")

    def test_sin_licencia_y_clave_invalida(self):
        self.assertEqual(cli.comprobar().codigo, "sin_licencia")
        r = cli.activar("no-existe")
        self.assertEqual((r.ok, r.codigo), (False, "invalida"))

    def test_activar_y_validar(self):
        lic = sim.DATOS.vender(cliente="Ana", correo="ana@example.com")
        r = cli.activar(f"  {lic['key']}  ")
        self.assertTrue(r.ok, r.mensaje)
        self.assertEqual(r.datos["cliente"], "Ana")
        self.assertEqual(sim.DATOS.licencias[lic["id"]]["instances_count"], 1)
        nombre = next(iter(sim.DATOS.instancias.values()))["name"]
        self.assertTrue(nombre.endswith(" · " + cli.obtener_id_equipo()))
        self.assertEqual(cli.comprobar().codigo, "activa")
        self.assertTrue(cli.activar(lic["key"]).ok)       # la misma clave otra vez no gasta otro equipo
        self.assertEqual(sim.DATOS.licencias[lic["id"]]["instances_count"], 1)

    def test_conserva_activaciones_de_la_version_4(self):
        """Un licencia.dat firmado por la versión 4 sigue valiendo (misma carpeta, ID de equipo y firma)."""
        import hashlib
        import hmac
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        datos = json.loads((self.carpeta / "licencia.dat").read_text())["datos"]
        equipo = hashlib.sha256(b"RCS:equipo-de-pruebas-1").hexdigest()[:16].upper()
        self.assertEqual(datos["equipo"], "-".join(equipo[i:i + 4] for i in range(0, 16, 4)))
        v4 = {k: v for k, v in datos.items() if k not in ("tienda", "estado", "activada", "motivo", "codigo")}
        llave = hashlib.sha256(b"rcs-licencia-lemonsqueezy-v1" + datos["equipo"].encode()).digest()
        firma = hmac.new(llave, json.dumps(v4, sort_keys=True).encode(), "sha256").hexdigest()
        (self.carpeta / "licencia.dat").write_text(json.dumps({"datos": v4, "firma": firma}))
        cli._INSTANCIAS.clear()
        self.assertEqual(cli.comprobar().codigo, "activa")
        self.assertEqual(cli.licencia_guardada()["tienda"], "lemonsqueezy")

    def test_limite_de_equipos(self):
        lic = sim.DATOS.vender(limite=1)
        self.assertTrue(cli.activar(lic["key"]).ok)
        self.otro_equipo()
        self.assertEqual(cli.activar(lic["key"]).codigo, "en_uso")

    def test_bloqueo_vencimiento_y_sin_internet(self):
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        self.api.editar_licencia(lic["id"], {"disabled": True})
        self.assertEqual(cli.comprobar().codigo, "bloqueada")
        with mock.patch.object(tiendas, "LS_API", APAGADO + "/v1/licenses/"):
            self.assertFalse(cli.comprobar().ok, "tras un bloqueo no debe quedar el modo sin conexión")
        self.api.editar_licencia(lic["id"], {"disabled": False})
        r = cli.comprobar()
        self.assertEqual((r.ok, r.codigo), (True, "reactivada"), "al desbloquearla vuelve sola y lo avisa")
        self.api.editar_licencia(lic["id"], {"expires_at": "2020-01-01T00:00:00.000000Z"})
        r = cli.comprobar()
        self.assertEqual(r.codigo, "vencida")
        self.assertIn("01/01/2020", r.mensaje)

    def test_modo_sin_conexion(self):
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        with mock.patch.object(tiendas, "LS_API", APAGADO + "/v1/licenses/"):
            r = cli.comprobar()
            self.assertEqual((r.ok, r.codigo), (True, "sin_conexion_ok"))
            dentro_de_8_dias = time.time() + 8 * 86400
            with mock.patch.object(sdk_licencias.time, "time", lambda: dentro_de_8_dias):
                self.assertEqual(cli.comprobar().codigo, "sin_conexion")

    def test_equipo_quitado_por_el_vendedor(self):
        lic = sim.DATOS.vender()
        self.assertTrue(cli.activar(lic["key"]).ok)
        ins = next(iter(sim.DATOS.instancias.values()))
        self.api.quitar_equipo(lic["key"], ins["identifier"])
        r = cli.comprobar()
        self.assertEqual(r.codigo, "desactivada", r.mensaje)
        self.assertEqual(r.datos.get("clave"), lic["key"])     # la ventana la muestra ya escrita
        self.assertTrue(cli.activar(lic["key"]).ok)            # y se puede volver a activar

    def test_desactivar_para_cambiar_de_pc(self):
        lic = sim.DATOS.vender(limite=1)
        self.assertTrue(cli.activar(lic["key"]).ok)
        self.assertTrue(cli.desactivar().ok)
        self.assertIsNone(cli.licencia_guardada())
        self.assertEqual(sim.DATOS.licencias[lic["id"]]["instances_count"], 0)
        self.otro_equipo()
        self.assertTrue(cli.activar(lic["key"]).ok)

    def test_clave_de_otra_tienda_o_producto(self):
        ajena = sim.DATOS.vender(tienda=999)
        self.assertEqual(cli.activar(ajena["key"]).codigo, "otra_tienda")
        self.assertEqual(sim.DATOS.licencias[ajena["id"]]["instances_count"], 0, "debe devolver el equipo")
        self.assertEqual(cli.activar(sim.DATOS.vender(producto=555)["key"]).codigo, "otra_tienda")

    def test_claves_de_prueba(self):
        lic = sim.DATOS.vender(test_mode=True)
        with mock.patch.object(cli, "ACEPTAR_CLAVES_DE_PRUEBA", False):
            self.assertEqual(cli.activar(lic["key"]).codigo, "otra_tienda")
            self.assertTrue(cli.activar(sim.DATOS.vender(test_mode=False)["key"]).ok)

    def test_archivo_local_manipulado(self):
        self.assertTrue(cli.activar(sim.DATOS.vender()["key"]).ok)
        archivo = self.carpeta / "licencia.dat"
        archivo.write_text(archivo.read_text().replace('"ultima_ok": ', '"ultima_ok": 9'))
        self.assertIsNone(cli.licencia_guardada())


class GumroadCliente(Base):
    def test_activar_validar_y_limite(self):
        venta = sim.DATOS.vender_gumroad(cliente="Mateo Ríos", correo="mateo@x.com")
        clave = venta["license_key"]
        self.assertTrue(cli.parece_clave_gumroad(clave))
        r = cli.activar(clave)
        self.assertTrue(r.ok, r.mensaje)
        self.assertEqual((r.datos["tienda"], r.datos["cliente"], r.datos["usados"]), ("gumroad", "Mateo Ríos", 1))
        self.assertTrue(cli.comprobar().ok)
        self.assertTrue(cli.activar(clave).ok)
        self.assertEqual(sim.DATOS.gumroad_claves[clave]["uses"], 1, "validar no gasta usos")
        self.otro_equipo()
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
        sim.DATOS.gumroad_claves[clave]["venta"]["refunded"] = False      # se canceló el reembolso
        self.assertEqual(cli.comprobar().codigo, "reactivada")
        self.assertEqual(cli.activar("AAAAAAAA-BBBBBBBB-CCCCCCCC-DDDDDDDD").codigo, "invalida")

    def test_desactivar_y_sin_internet(self):
        clave = sim.DATOS.vender_gumroad()["license_key"]
        self.assertTrue(cli.activar(clave).ok)
        with mock.patch.object(tiendas, "GUMROAD_API", APAGADO + "/v2/licenses/"):
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
            self.assertEqual(cli.activar(otra).codigo, "invalida")


# ============================================================ SDK cinema_licencias

class Configuraciones(unittest.TestCase):
    def test_json_y_formato_plano(self):
        datos = {"app": "X", "lemonsqueezy": {"tienda_id": "5", "productos": ["7"]},
                 "polar": {"organizacion_id": "org", "sandbox": True},
                 "servidor": {"url": "https://a.supabase.co", "clave_publica": "sb_publishable_1"},
                 "opciones": {"dias_sin_internet": 3}, "whatsapp": "502"}
        cfg = Configuracion.desde_dict(datos)
        self.assertEqual((cfg.ls_tienda_id, cfg.ls_productos, cfg.polar_sandbox, cfg.dias_sin_internet, cfg.whatsapp),
                         (5, (7,), True, 3, "502"))
        self.assertEqual(cfg.tiendas(), ["lemonsqueezy", "polar"])
        self.assertEqual(Configuracion.desde_dict(cfg.a_dict()), cfg, "ida y vuelta por JSON")
        ruta = Path(tempfile.mkdtemp(dir=_TMP)) / "cinema_licencias.json"
        cfg.guardar_json(ruta)
        self.assertEqual(Licencias.desde_json(ruta).cfg.ls_tienda_id, 5)
        self.assertEqual(Configuracion.desde_json(RAIZ / "programa" / "cinema_licencias.json").app,
                         "Resolve Creator Subtitles")

    def test_nunca_claves_secretas_en_el_programa(self):
        import base64

        def jwt(rol: str) -> str:
            cuerpo = base64.urlsafe_b64encode(json.dumps({"role": rol}).encode()).decode().rstrip("=")
            return f"eyJhbGciOiJIUzI1NiJ9.{cuerpo}.x"

        for mala in ({"servidor_clave": "sb_secret_abc"}, {"servidor_clave": jwt("service_role")},
                     {"polar_organizacion_id": "polar_oat_123"}):
            with self.assertRaises(ValueError):
                Configuracion.desde_dict(mala)
        with self.assertRaises(ValueError):
            Licencias(ls_tienda_id=1, servidor_clave="sb_secret_abc")
        Configuracion.desde_dict({"servidor_clave": jwt("anon")})       # la anon antigua sí se permite

    def test_ayudas(self):
        self.assertTrue(sdk_base.es_uuid("38B1460A-5104-4067-A91D-77B872934D51"))
        self.assertFalse(sdk_base.es_uuid("CINEMA-38B1460A-5104-4067-A91D-77B872934D51"))
        self.assertTrue(sdk_base.es_clave_gumroad("85DB562A-C11D4B06-A2335A6B-8C079166"))
        self.assertEqual(hash_licencia(" abc "), hash_licencia("ABC"))
        self.assertEqual(len(hash_licencia("x")), 64)
        self.assertEqual(sdk_base.ocultar_clave("1234567890ABCDEF"), "••••-90ABCDEF")
        self.assertEqual(Resultado(True, "activa", datos={"clave": "123456789012"}).a_dict()["datos"]["clave"],
                         "••••-56789012")
        self.assertEqual(Resultado(False, "reembolsada").mensaje, sdk_base.MENSAJES["reembolsada"])


class PolarCliente(Base):
    def test_activar_validar_y_desactivar(self):
        k = sim.DATOS.vender_polar(cliente="Valeria", correo="val@x.com", limite=1)
        lic = self.sdk(ls_tienda_id=0, polar_beneficio_id=sim.PO_BENEFICIO)
        r = lic.activar(k["key"])
        self.assertTrue(r.ok, r.mensaje)
        self.assertEqual((r.datos["tienda"], r.datos["cliente"], r.datos["limite"]), ("polar", "Valeria", 1))
        act = sim.DATOS.polar_activaciones[r.datos["instancia"]]
        self.assertTrue(act["label"].endswith(lic.equipo_id()))
        self.assertEqual(act["meta"]["app"], "Resolve Creator Subtitles")
        self.assertEqual(lic.comprobar().codigo, "activa")
        self.assertEqual(sim.DATOS.polar_claves[k["id"]]["validations"], 1)
        self.otro_equipo()
        self.assertEqual(self.sdk(ls_tienda_id=0).activar(k["key"]).codigo, "en_uso")
        self.assertTrue(lic.desactivar().ok)
        self.assertEqual(sim.DATOS.polar_activaciones, {})

    def test_reembolso_revoca_y_equipo_quitado(self):
        k = sim.DATOS.vender_polar()
        lic = self.sdk()
        self.assertTrue(lic.activar(k["key"]).ok)
        sim.DATOS.reembolsar_polar(k["key"])
        self.assertEqual(lic.comprobar().codigo, "revocada")
        sim.DATOS.reembolsar_polar(k["key"], False)
        self.assertEqual(lic.comprobar().codigo, "reactivada")
        sim.DATOS.polar_activaciones.clear()                       # el vendedor quitó el equipo
        self.assertEqual(lic.comprobar().codigo, "desactivada")
        self.assertTrue(lic.activar(k["key"]).ok)

    def test_claves_sin_activaciones_y_de_otro_beneficio(self):
        sin = sim.DATOS.vender_polar(con_activaciones=False)
        lic = self.sdk(ls_tienda_id=0)
        self.assertTrue(lic.activar(sin["key"]).ok)
        self.assertIsNone(lic.guardada()["instancia"])
        self.assertTrue(lic.comprobar().ok)
        otra = sim.DATOS.vender_polar()
        sim.DATOS.polar_claves[otra["id"]]["benefit_id"] = "otro-beneficio"
        lic2 = self.sdk(ls_tienda_id=0, polar_beneficio_id=sim.PO_BENEFICIO)
        self.assertEqual(lic2.activar(otra["key"]).codigo, "otra_tienda")
        self.assertEqual(sim.DATOS.polar_activaciones, {}, "devuelve la activación")

    def test_elige_la_tienda_por_el_formato(self):
        ls = sim.DATOS.vender()
        po = sim.DATOS.vender_polar()
        gr = sim.DATOS.vender_gumroad()["license_key"]
        uuid_polar = sim.DATOS.vender_polar(prefijo="")
        clave_uuid = uuid_polar["key"].lstrip("-")
        sim.DATOS.polar_claves[uuid_polar["id"]]["key"] = clave_uuid
        self.assertEqual(self.sdk().activar(ls["key"]).datos["tienda"], "lemonsqueezy")
        self.assertEqual(self.sdk().activar(po["key"]).datos["tienda"], "polar")
        self.assertEqual(self.sdk().activar(gr).datos["tienda"], "gumroad")
        # una clave UUID que no existe en Lemon Squeezy se prueba también en Polar
        self.assertEqual(self.sdk().activar(clave_uuid).datos["tienda"], "polar")


class ServidorDeControl(Base):
    def test_estado_del_servidor_y_reactivacion(self):
        k = sim.DATOS.vender_polar()
        lic = self.sdk()
        self.assertTrue(lic.activar(k["key"]).ok)
        h = hash_licencia(k["key"])
        self.srv.fijar_estado(h, "reembolsada", "Tu compra se reembolsó el 03/10.")
        r = lic.comprobar()
        self.assertEqual((r.ok, r.codigo, r.mensaje), (False, "reembolsada", "Tu compra se reembolsó el 03/10."))
        with mock.patch.object(tiendas, "POLAR_API", {False: APAGADO, True: APAGADO}):
            self.assertFalse(lic.comprobar().ok, "suspendida: sin modo sin conexión")
        self.srv.fijar_estado(h, "activa")
        self.assertEqual(lic.comprobar().codigo, "reactivada")
        self.srv.fijar_estado(h, "revocada", "Retirada")
        self.otro_equipo()
        self.assertEqual(self.sdk().activar(k["key"]).codigo, "revocada", "tampoco se activa en otro equipo")

    def test_el_servidor_solo_quita_nunca_da(self):
        k = sim.DATOS.vender_polar()
        lic = self.sdk()
        self.assertTrue(lic.activar(k["key"]).ok)
        self.srv.fijar_estado(hash_licencia(k["key"]), "activa")
        sim.DATOS.reembolsar_polar(k["key"])
        self.assertEqual(lic.comprobar().codigo, "revocada")
        self.srv.fijar_estado(hash_licencia(k["key"]), "reembolsada", "Reembolsada el 04/10")
        r = lic.comprobar()
        self.assertEqual((r.codigo, r.mensaje), ("reembolsada", "Reembolsada el 04/10"), "el motivo exacto")

    def test_avisos_tiempo_de_uso_y_privacidad(self):
        lic_ls = sim.DATOS.vender()
        lic = self.sdk()
        self.assertTrue(lic.activar(lic_ls["key"]).ok)
        h = hash_licencia(lic_ls["key"])
        self.srv.enviar_aviso([h], "remocion", "Será removida", "Paga antes del 20", "2026-10-20T23:59:59+00:00")
        self.srv.enviar_aviso([None], "info", "Nueva versión", "5.1")
        avisos = lic.comprobar().avisos
        self.assertEqual([a["titulo"] for a in avisos], ["Será removida", "Nueva versión"])
        vistos = []
        vig = cinema_licencias.Vigilante(lic, al_aviso=vistos.append)
        vig._procesar_avisos(avisos)
        vig._procesar_avisos(avisos)
        self.assertEqual(len(vistos), 2, "cada aviso se muestra una sola vez")
        esperar_hilos()
        self.assertEqual(lic.comprobar().avisos, [], "quedaron marcados como leídos")
        self.assertEqual(lic.servidor.latido(lic.guardada(), "ses-1", 99999, inicio=True)["estado"], "activa")
        equipo = sim.DATOS.sb["equipos"][(h, lic.equipo_id())]
        self.assertEqual(equipo["segundos_uso"], 3600, "un latido no suma más de una hora")
        enviado = json.dumps({k: str(v) for k, v in sim.DATOS.sb.items()})
        self.assertNotIn(lic_ls["key"], enviado, "la clave real nunca llega al servidor")
        self.assertNotIn("Juan", enviado, "ni el nombre del cliente")
        self.assertEqual({e["tipo"] for e in sim.DATOS.sb["eventos"]}, {"activacion"})

    def test_vigilante_detecta_cambios(self):
        k = sim.DATOS.vender_polar()
        lic = self.sdk()
        self.assertTrue(lic.activar(k["key"]).ok)
        cambios = []
        vig = cinema_licencias.Vigilante(lic, al_cambiar=cambios.append)
        vig.reiniciar(True)
        vig.revisar_ahora()
        self.assertEqual(cambios, [])
        self.srv.fijar_estado(hash_licencia(k["key"]), "suspendida", "Bloqueada por el vendedor")
        vig._latido()                                   # el latido ve el bloqueo y pide revisar ya
        self.assertTrue(vig._ahora.is_set())
        vig.revisar_ahora()
        self.assertEqual([(c.ok, c.codigo) for c in cambios], [(False, "bloqueada")])
        self.srv.fijar_estado(hash_licencia(k["key"]), "activa")
        vig.revisar_ahora()
        self.assertEqual(cambios[-1].codigo, "reactivada")
        esperar_hilos()
        tipos = [e["tipo"] for e in sim.DATOS.sb["eventos"]]
        self.assertIn("licencia_perdida", tipos)
        self.assertIn("reactivada", tipos)
        vig.detener()
        self.assertTrue(any(s["cerrada"] for s in sim.DATOS.sb["sesiones"].values()))

    def test_uso_pendiente_sin_conexion(self):
        lic = self.sdk()
        self.assertTrue(lic.activar(sim.DATOS.vender()["key"]).ok)
        vig = cinema_licencias.Vigilante(lic, latido_min=1)
        with mock.patch.object(lic.servidor, "url", APAGADO):
            vig._marca -= 50
            vig._latido(fin=True)
        self.assertGreaterEqual(json.loads((lic.carpeta / "uso_pendiente.json").read_text())["segundos"], 50)
        cinema_licencias.Vigilante(lic, latido_min=1)._latido(inicio=True)
        equipo = next(iter(sim.DATOS.sb["equipos"].values()))
        self.assertGreaterEqual(equipo["segundos_uso"], 50, "se envía en la siguiente sesión")

    def test_linea_de_comandos(self):
        lic_ls = sim.DATOS.vender()
        carpeta = Path(tempfile.mkdtemp(dir=_TMP))
        ruta = carpeta / "cinema_licencias.json"
        cfg = Configuracion(app="RCS", ls_tienda_id=sim.TIENDA, carpeta=str(carpeta / "datos"))
        ruta.write_text(json.dumps(cfg.a_dict() | {"carpeta": cfg.carpeta}))
        from cinema_licencias.__main__ import main as cli_main
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(cli_main(["--config", str(ruta), "estado"]), 1)
            self.assertEqual(cli_main(["--config", str(ruta), "--json", "activar", lic_ls["key"]]), 0)
            self.assertEqual(cli_main(["--config", str(ruta), "estado"]), 0)
            self.assertEqual(cli_main(["--config", str(ruta), "--json", "equipo"]), 0)
        texto = salida.getvalue()
        self.assertIn('"codigo": "activa"', texto)
        self.assertNotIn(lic_ls["key"], texto, "el JSON no imprime la clave completa")
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(cli_main(["--config", str(carpeta / "no.json"), "estado"]), 2)


# ============================================================ APIs del Administrador

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
        self.assertEqual((r["ventas_validas"], r["compradores"], r["reembolsos"], r["claves"]), (24, 23, 1, 24))
        v = next(x for x in self.gr.ventas(max_edad=0) if x["cliente"] == "R")
        self.assertEqual((v["estado"], v["valida"], v["total"], v["total_txt"]), ("Reembolsada", False, 25.0, "$25"))


class LemonSqueezyApi(Base):
    def test_api_key_incorrecta(self):
        with self.assertRaises(plat.ErrorApi) as e:
            plat.LemonSqueezy("mala").conectar()
        self.assertIn("API key", str(e.exception))

    def test_conectar_resumen_y_datos(self):
        lic = sim.DATOS.vender()
        sim.DATOS.vender(tienda=999)
        r = self.api.conectar()
        self.assertEqual((r["usuario"]["name"], r["tiendas"][0]["id"]), ("Alejandro", sim.TIENDA))
        self.assertEqual((r["tienda"]["licencias"], r["tienda"]["ventas"]), (1, 1))
        self.assertTrue(cli.activar(lic["key"]).ok)
        d = self.api.datos(sim.TIENDA, sim.PRODUCTO)
        self.assertEqual([l["id"] for l in d["licencias"]], [lic["id"]])
        self.assertEqual(len(d["instancias"]), 1)
        self.assertEqual((d["ventas"][0]["estado"], d["ventas"][0]["total"]), ("Pagada", 19.0))

    def test_paginacion_y_edicion(self):
        for _ in range(230):
            sim.DATOS.vender()
        self.assertEqual(len(self.api.datos(sim.TIENDA)["licencias"]), 230)
        lic = next(iter(sim.DATOS.licencias))
        self.assertIsNone(self.api.editar_licencia(lic, {"activation_limit": None})["activation_limit"])
        self.assertEqual(self.api.editar_licencia(lic, {"disabled": True})["status"], "disabled")

    def test_enlaces_de_compra(self):
        venta = {"variante_id": sim.VARIANTE, "cliente": "Luis", "correo": "luis@example.com",
                 "telefono": "50255551234", "precio": "normal", "centavos": 0, "expira": None}
        self.assertTrue(self.api.crear_enlace(sim.TIENDA, venta).startswith("https://"))
        self.assertEqual(sim.DATOS.checkouts[-1]["data"]["attributes"]["checkout_data"],
                         {"name": "Luis", "email": "luis@example.com"})
        self.api.crear_enlace(sim.TIENDA, venta | {"precio": "especial", "centavos": 1250})
        self.assertEqual(sim.DATOS.checkouts[-1]["data"]["attributes"]["custom_price"], 1250)
        self.api.crear_enlace(sim.TIENDA, venta | {"precio": "gratis", "correo": "", "cliente": ""})
        cupon = sim.DATOS.descuentos[-1]["data"]
        self.assertEqual((cupon["attributes"]["amount"], cupon["attributes"]["max_redemptions"]), (100, 1))


class HotmartApi(Base):
    def test_credenciales_incorrectas(self):
        with self.assertRaises(plat.ErrorApi) as e:
            plat.Hotmart(sim.HM_ID, "otro").conectar()
        self.assertIn("rechazó las credenciales", str(e.exception))

    def test_ventas_resumen_y_cache(self):
        sim.DATOS.vender_hotmart(cliente="Lucía", correo="lucia@x.com")
        sim.DATOS.vender_hotmart(cliente="Lucía", correo="LUCIA@x.com", estado="COMPLETE")
        sim.DATOS.vender_hotmart(cliente="Pedro", correo="pedro@x.com", estado="REFUNDED")
        sim.DATOS.vender_hotmart(cliente="Rita", correo="rita@x.com", estado="CHARGEBACK")
        for i in range(60):   # más de una página (max_results=50)
            sim.DATOS.vender_hotmart(cliente=f"C{i}", correo=f"c{i}@x.com")
        r = self.hm.conectar()
        self.assertEqual((r["ventas_validas"], r["compradores"], r["reembolsos"]), (62, 61, 2))
        self.assertEqual(sim.DATOS.hotmart_tokens, 1)
        sim.DATOS.vender_hotmart(correo="nueva@x.com")
        self.assertEqual(len(self.hm.ventas(max_edad=60)), 64, "dentro de 60 s usa la copia guardada")
        sim.DATOS.hotmart_rechaza_fechas = True
        self.assertEqual(len(self.hm.ventas(max_edad=0)), 65, "si Hotmart no acepta fechas, reintenta sin ellas")


class PolarApi(Base):
    def test_token_incorrecto(self):
        with self.assertRaises(plat.ErrorApi) as e:
            plat.Polar("polar_oat_malo").conectar()
        self.assertIn("token de Polar", str(e.exception))

    def test_conectar_datos_y_acciones(self):
        a = sim.DATOS.vender_polar(cliente="Valeria", correo="val@x.com")
        sim.DATOS.vender_polar(cliente="Camila", correo="cam@x.com", reembolsada=True)
        r = self.po.conectar()
        self.assertEqual((r["organizacion"]["id"], r["claves"], r["ventas_validas"], r["reembolsos"]),
                         (sim.PO_ORG, 2, 1, 1))
        self.assertEqual(r["beneficios"][0]["id"], sim.PO_BENEFICIO)
        self.assertEqual(sim.DATOS.polar_versiones, {plat.POLAR_VERSION})
        lic = self.sdk(ls_tienda_id=0)
        self.assertTrue(lic.activar(a["key"]).ok)
        d = self.po.datos(sim.PO_ORG, beneficio=sim.PO_BENEFICIO)
        self.assertEqual(len(d["claves"]), 2)
        self.assertEqual(len(d["detalles"][a["id"]]["activations"]), 1)
        self.po.editar_licencia(a["id"], {"status": "disabled", "limit_activations": 3})
        self.assertEqual(lic.comprobar().codigo, "revocada")
        self.po.editar_licencia(a["id"], {"status": "granted"})
        self.assertTrue(lic.comprobar().ok)
        act = lic.guardada()["instancia"]
        self.po.quitar_equipo(sim.PO_ORG, a["key"], act, a["id"])
        self.po.quitar_equipo(sim.PO_ORG, a["key"], act, a["id"])    # dos veces no falla
        self.assertEqual(lic.comprobar().codigo, "desactivada")


class ServidorControlApi(Base):
    def test_probar_y_errores(self):
        self.assertEqual(self.srv.probar()["equipos"], 0)
        with self.assertRaises(plat.ErrorApi) as e:
            control.ServidorControl(RAIZ_SIM, sim.SB_PUBLICA).probar()
        self.assertIn("PUBLICABLE", str(e.exception))
        with self.assertRaises(plat.ErrorApi) as e:
            control.ServidorControl(RAIZ_SIM, "sb_secret_mala").probar()
        self.assertIn("no es válida", str(e.exception))

    def test_avisos_estados_y_datos(self):
        filas = self.srv.enviar_aviso(["a" * 64, "b" * 64], "remocion", "T", "M", "2026-10-20T00:00:00Z")
        self.assertEqual(len(filas), 2)
        self.srv.borrar_aviso(filas[0]["id"])
        self.srv.fijar_estado("a" * 64, "revocada", "x")
        self.srv.fijar_estado("a" * 64, "activa")
        with self.assertRaises(plat.ErrorApi):
            self.srv.fijar_estado("a" * 64, "inventado")
        d = self.srv.datos()
        self.assertEqual(([a["licencia"] for a in d["avisos"]], d["estados"][0]["estado"]), (["b" * 64], "activa"))
        self.assertEqual(self.srv.limpiar(), {"sesiones": 0, "eventos": 0})


# ============================================================ modelo y configuración del Administrador

class Modelo(Base):
    def cargar(self, clientes: dict, plataformas: dict) -> dict:
        return modelo.construir_modelo(modelo.cargar_todo(clientes, {"plataformas": plataformas}))

    def test_personas_en_varias_plataformas(self):
        lic = sim.DATOS.vender(cliente="Ana", correo="ana@x.com")
        sim.DATOS.vender_hotmart(cliente="Ana López", correo="ANA@x.com")
        sim.DATOS.vender_hotmart(cliente="Pedro", correo="pedro@x.com", estado="REFUNDED")
        sim.DATOS.vender_polar(cliente="Ana", correo="ana@x.com")
        self.assertTrue(cli.activar(lic["key"]).ok)
        m = self.cargar({"lemonsqueezy": self.api, "hotmart": self.hm, "polar": self.po},
                        {"lemonsqueezy": CFG_LS, "hotmart": CFG_HM, "polar": CFG_PO})
        personas = {p["clave"]: p for p in m["personas"]}
        self.assertEqual(personas["ana@x.com"]["plataformas"], {"lemonsqueezy", "hotmart", "polar"})
        self.assertEqual(personas["ana@x.com"]["compras"], 3)
        self.assertEqual(personas["pedro@x.com"]["estado"], "Reembolsada")
        self.assertEqual(m["ventas_30"], 3)

    def test_reembolsos_por_licencia(self):
        ls = sim.DATOS.vender(cliente="Ana", correo="ana@x.com")
        sim.DATOS.ventas[sim.DATOS.licencias[ls["id"]]["order_id"]]["status"] = "refunded"
        gr = sim.DATOS.vender_gumroad(cliente="Bea", correo="bea@x.com", reembolsada=True)
        po = sim.DATOS.vender_polar(cliente="Cami", correo="cam@x.com", reembolsada=True)
        ok = sim.DATOS.vender_polar(cliente="Dani", correo="dani@x.com")
        m = self.cargar({"lemonsqueezy": self.api, "gumroad": self.gr, "polar": self.po},
                        {"lemonsqueezy": CFG_LS, "gumroad": CFG_GR, "polar": CFG_PO})
        por_clave = {l["key"]: l for l in m["licencias"]}
        for clave in (ls["key"], gr["license_key"], po["key"]):
            self.assertTrue(por_clave[clave]["reembolsada"], clave)
        self.assertFalse(por_clave[ok["key"]]["reembolsada"])
        self.assertTrue(por_clave[ok["key"]]["compra_valida"])
        self.assertEqual(por_clave[po["key"]]["status"], "revoked")

    def test_telemetria_en_el_modelo(self):
        k = sim.DATOS.vender_polar(cliente="Vale", correo="vale@x.com")
        lic = self.sdk()
        self.assertTrue(lic.activar(k["key"]).ok)
        lic.servidor.latido(lic.guardada(), "s1", 1800, inicio=True)
        self.srv.enviar_aviso([hash_licencia(k["key"])], "info", "Hola", "")
        esperar_hilos()
        m = self.cargar({"polar": self.po, "control": self.srv}, {"polar": CFG_PO})
        licencia = next(l for l in m["licencias"] if l["key"] == k["key"])
        self.assertEqual((licencia["uso_seg"], licencia["en_linea"], licencia["equipos_tel"]), (1800, True, 1))
        persona = m["persona_por_clave"]["vale@x.com"]
        self.assertEqual((persona["uso_seg"], persona["en_linea"]), (1800, True))
        self.assertEqual((m["activos_hoy"], m["en_linea"], m["horas_30"]), (1, 1, 0.5))
        self.assertEqual(m["avisos"][0]["persona"], "Vale")
        self.assertEqual(len(m["instancias"]), 1, "las activaciones de Polar son equipos")
        self.assertEqual(m["eventos_srv"][0]["persona"], "Vale")

    def test_error_en_una_plataforma_no_bloquea_las_demas(self):
        sim.DATOS.vender()
        res = modelo.cargar_todo({"lemonsqueezy": self.api, "hotmart": plat.Hotmart("x", "y"),
                                  "control": control.ServidorControl(APAGADO, "sb_secret_x")},
                                 {"plataformas": {"lemonsqueezy": CFG_LS, "hotmart": {}}})
        self.assertIn("error", res["hotmart"])
        self.assertIn("error", res["control"])
        self.assertEqual(len(res["lemonsqueezy"]["licencias"]), 1)

    def test_migra_configuracion_de_versiones_anteriores(self):
        modelo.CARPETA_V4.mkdir(parents=True, exist_ok=True)
        (modelo.CARPETA_V4 / "config_lemonsqueezy.json").write_text(json.dumps({"api_key": "k", "tienda_id": 5,
                                                                                  "nombre_app": "X"}))
        cfg = modelo.cargar_config()
        self.assertEqual((cfg["plataformas"]["lemonsqueezy"]["tienda_id"], cfg["nombre_app"]), (5, "X"))
        (modelo.CARPETA_V4 / "config.json").write_text(json.dumps({"version": 3, "nombre_app": "Y",
                                                                   "plataformas": {"gumroad": CFG_GR}}))
        cfg = modelo.cargar_config()
        self.assertEqual((cfg["nombre_app"], cfg["plataformas"]["gumroad"]["token"], cfg["tema"], cfg["version"]),
                         ("Y", sim.GR_TOKEN, "cinema", 5))
        self.assertIn("polar", cfg["plataformas"])
        modelo.guardar_config(cfg)
        self.assertTrue(modelo.archivo_config().exists())
        self.assertEqual(modelo.MARCA, "Cinema Productions")

    def test_datos_para_el_programa_sin_secretos(self):
        cfg = modelo.config_base()
        cfg["plataformas"] |= {"lemonsqueezy": CFG_LS | {"url_compra": "https://x/buy"}, "gumroad": CFG_GR,
                               "polar": CFG_PO | {"url_compra": "https://buy.polar.sh/x"}}
        cfg["servidor"] = CFG_SV
        texto = modelo.texto_config_programa(cfg)
        for secreto in (sim.API_KEY, sim.GR_TOKEN, sim.PO_TOKEN, sim.SB_SECRETA):
            self.assertNotIn(secreto, texto)
        prog = Configuracion.desde_dict(json.loads(texto))
        self.assertEqual((prog.ls_tienda_id, prog.ls_productos, prog.gumroad_producto_id, prog.polar_organizacion_id,
                          prog.servidor_clave), (sim.TIENDA, (sim.PRODUCTO,), sim.GR_PRODUCTO, sim.PO_ORG,
                                                 sim.SB_PUBLICA))
        cfg["servidor"] = CFG_SV | {"clave_publica": sim.SB_SECRETA}
        with self.assertRaises(ValueError):
            modelo.config_programa(cfg)
        espacio = {}
        exec(modelo.datos_para_programa(CFG_LS, CFG_GR, CFG_PO, CFG_SV), espacio)
        self.assertEqual((espacio["TIENDA_ID"], espacio["GUMROAD_PRODUCTO_ID"], espacio["POLAR_ORGANIZACION_ID"],
                          espacio["SERVIDOR_CLAVE_PUBLICA"]), (sim.TIENDA, sim.GR_PRODUCTO, sim.PO_ORG, sim.SB_PUBLICA))

    def test_privacidad_y_formatos(self):
        with mock.patch.dict(interfaz.PRIVACIDAD, {"activa": True, "claves": True}):
            self.assertEqual(interfaz.priv_nombre("Juan Pérez"), "J••• P••••")
            self.assertEqual(interfaz.priv_correo("juan@gmail.com"), "j•••@g••••.com")
            self.assertEqual(interfaz.priv_nombre("ana@x.com"), interfaz.priv_correo("ana@x.com"))
            self.assertEqual(interfaz.priv_clave("ABCD-1234"), "••••-••••-1234")
        self.assertEqual(interfaz.priv_nombre("Juan Pérez"), "Juan Pérez")
        self.assertEqual((modelo.duracion(3725), modelo.duracion(0), modelo.duracion(45)), ("1 h 2 min", "—", "45 s"))


# ============================================================ ventanas

class Ventanas(Base):
    @classmethod
    def setUpClass(cls):
        cls.app = adm.preparar_aplicacion([])

    def esperar(self, condicion, segundos=10):
        fin = time.time() + segundos
        while time.time() < fin:
            self.app.processEvents()
            if condicion():
                return True
            time.sleep(0.02)
        self.fail("tiempo de espera agotado")

    def ventana(self, plataformas: dict, servidor: dict | None = None, **ajustes):
        cfg = modelo.config_base() | ajustes
        cfg["plataformas"] |= plataformas
        cfg["servidor"] = servidor or {}
        modelo.guardar_config(cfg)
        v = adm.Ventana()
        self.addCleanup(cerrar, v)
        return v

    def test_sin_conexion_muestra_bienvenida(self):
        v = self.ventana({})
        self.app.processEvents()
        self.assertEqual(v.paginas[paginas.P_INICIO].pila.currentIndex(), 0)
        self.assertTrue(v.paginas[paginas.P_LICENCIAS].sin_ls.isVisibleTo(v.paginas[paginas.P_LICENCIAS]))
        self.assertTrue(v.paginas[paginas.P_USO].vacio_srv.isVisibleTo(v.paginas[paginas.P_USO]))
        self.assertTrue(v.windowFlags() & Qt.WindowType.FramelessWindowHint, "ventana sin marco")
        self.assertEqual(set(v.barra.botones), {"min", "max", "cerrar"})

    def test_panel_completo(self):
        lic = sim.DATOS.vender(cliente="Ana", correo="ana@x.com")
        self.assertTrue(cli.activar(lic["key"]).ok)
        sim.DATOS.vender_hotmart(cliente="Lu", correo="lu@x.com")
        v = self.ventana({"lemonsqueezy": CFG_LS, "hotmart": CFG_HM})
        personas, licencias = v.paginas[paginas.P_PERSONAS], v.paginas[paginas.P_LICENCIAS]
        equipos, ventas = v.paginas[paginas.P_EQUIPOS], v.paginas[paginas.P_VENTAS]
        self.esperar(lambda: licencias.t.rowCount() == 1 and ventas.t.rowCount() == 2)
        self.esperar(lambda: v.paginas[paginas.P_INICIO].k_personas.valor.text() == "2")
        self.assertEqual((personas.t.rowCount(), equipos.t.rowCount()), (2, 1))
        v.buscar.setText("lu@x")
        self.assertEqual(personas.t.rowCount(), 1)
        v.buscar.clear()
        sim.DATOS.vender_hotmart(cliente="Beto", correo="beto@x.com")
        v.clientes["hotmart"]._cache = None
        v.refrescar()
        self.esperar(lambda: ventas.t.rowCount() == 3)
        self.assertIn("●", v.nav.botones[paginas.P_ACTIVIDAD].text())
        v.ir_a(paginas.P_LICENCIAS)
        licencias.t.selectRow(0)
        self.esperar(lambda: licencias.panel.maximumWidth() == licencias.panel.ancho)
        with mock.patch.object(adm, "preguntar", return_value=True):
            v.quitar_equipo(v.modelo["lic_por_id"][lic["id"]], v.modelo["instancias"][0])
        self.esperar(lambda: equipos.t.rowCount() == 0)
        self.assertTrue(any(e["tipo"] == "desactivacion" for e in v.eventos()))
        with mock.patch.object(adm, "preguntar", return_value=True):
            v.alternar_bloqueo(v.modelo["lic_por_id"][lic["id"]])
        self.esperar(lambda: sim.DATOS.licencias[lic["id"]]["disabled"])
        self.esperar(lambda: licencias.b_bloquear.text() == "Desbloquear")

    def test_control_automatico_de_reembolsos(self):
        po = sim.DATOS.vender_polar(cliente="Cami", correo="cam@x.com")
        gr = sim.DATOS.vender_gumroad(cliente="Bea", correo="bea@x.com")
        prog = self.sdk()
        self.assertTrue(prog.activar(po["key"]).ok)
        v = self.ventana({"gumroad": CFG_GR, "polar": CFG_PO}, CFG_SV)
        self.esperar(lambda: len(v.modelo["licencias"]) == 2)
        # reembolsos en las dos tiendas → se bloquean solas y el servidor avisa al programa
        sim.DATOS.reembolsar_polar(po["key"])
        sim.DATOS.gumroad_claves[gr["license_key"]]["venta"]["refunded"] = True
        v.clientes["gumroad"]._cache = None
        v.clientes["polar"]._cache_ventas = None
        v.refrescar()
        self.esperar(lambda: len(v.cfg["auto_bloqueadas"]) == 2, 15)
        self.assertTrue(sim.DATOS.gumroad_claves[gr["license_key"]]["disabled"])
        self.assertEqual(sim.DATOS.sb["estados"][hash_licencia(po["key"])]["estado"], "reembolsada")
        self.assertEqual(prog.comprobar().codigo, "reembolsada")
        # se cancela el reembolso de Polar → se reactiva y el cliente recibe un aviso
        sim.DATOS.reembolsar_polar(po["key"], False)
        v.clientes["polar"]._cache_ventas = None
        self.esperar(lambda: not v.cargando and not v._automatico, 10)
        v.refrescar()
        self.esperar(lambda: len(v.cfg["auto_bloqueadas"]) == 1, 15)
        self.assertEqual(sim.DATOS.sb["estados"][hash_licencia(po["key"])]["estado"], "activa")
        r = prog.comprobar()
        self.assertEqual(r.codigo, "reactivada")
        self.assertEqual([a["tipo"] for a in r.avisos], ["reactivada"])
        self.assertTrue(any(e["tipo"] == "auto" for e in v.eventos()))

    def test_avisos_y_bloqueo_programado(self):
        ls = sim.DATOS.vender(cliente="Ana", correo="ana@x.com")
        prog = self.sdk()
        self.assertTrue(prog.activar(ls["key"]).ok)
        v = self.ventana({"lemonsqueezy": CFG_LS}, CFG_SV)
        self.esperar(lambda: v.modelo["licencias"] and v.modelo["control"])

        def responder(dialogo):
            dialogo.tipo.setCurrentIndex(dialogo.tipo.findData("remocion"))
            dialogo.fecha.setDate(QDate(2020, 1, 1))
            dialogo.bloquear.setChecked(True)
            return adm.DialogoAviso.DialogCode.Accepted

        with mock.patch.object(adm.DialogoAviso, "exec", responder):
            v.nuevo_aviso(persona="ana@x.com")
        self.esperar(lambda: sim.DATOS.sb["avisos"], 10)
        self.assertTrue(prog.comprobar().avisos[0]["titulo"].startswith("Tu licencia de "))
        self.esperar(lambda: sim.DATOS.licencias[ls["id"]]["disabled"], 15)     # la fecha límite ya pasó
        self.esperar(lambda: not v.cfg["remociones"], 5)
        self.assertEqual(prog.comprobar().codigo, "revocada")

    def test_ficha_privacidad_y_temas(self):
        po = sim.DATOS.vender_polar(cliente="Valeria Soto", correo="val@x.com")
        prog = self.sdk()
        self.assertTrue(prog.activar(po["key"]).ok)
        prog.servidor.latido(prog.guardada(), "s", 600, inicio=True)
        v = self.ventana({"polar": CFG_PO}, CFG_SV)
        self.esperar(lambda: v.modelo["licencias"] and v.modelo["control"])
        ficha = adm.DialogoPersona(v, "val@x.com")
        self.assertIn("Valeria", ficha.windowTitle())
        ficha.notas.setPlainText("Cliente fiel")
        ficha.etiquetas.setText("vip, soporte")
        ficha._guardar_notas()
        self.assertEqual((modelo.cargar_config()["etiquetas"]["val@x.com"], v.cfg["notas"]["val@x.com"]),
                         (["vip", "soporte"], "Cliente fiel"))
        v.buscar.setText("soporte")
        self.assertEqual(v.paginas[paginas.P_PERSONAS].t.rowCount(), 1, "se busca también por etiquetas")
        v.buscar.clear()
        v.boton_ojo.setChecked(True)
        self.assertTrue(v.cfg["privacidad"])
        self.assertEqual(v.paginas[paginas.P_PERSONAS].t.item(0, 1).text(), "v••@x••.com")
        v.fijar_privacidad(False)
        self.assertFalse(v.boton_ojo.isChecked())
        v.cambiar_tema("claro")
        nueva = adm._VENTANAS[0]
        self.addCleanup(cerrar, nueva)
        self.assertIsNot(nueva, v)
        self.assertEqual((interfaz.C["clave"], modelo.cargar_config()["tema"]), ("claro", "claro"))
        self.assertEqual(len(nueva.modelo["licencias"]), 1, "conserva los datos sin volver a descargar")
        nueva.plegar_lateral(True, animar=False)
        self.assertEqual(nueva.lateral.width(), adm.ANCHO_PLEGADO)
        nueva.cambiar_tema("cinema")
        self.addCleanup(cerrar, adm._VENTANAS[0])
        self.assertEqual(interfaz.C["clave"], "cinema")

    def test_conectar_polar_y_servidor(self):
        sim.DATOS.vender_polar()
        v = self.ventana({})
        d = adm.DialogoConectar(v, "polar")
        from PySide6.QtTest import QTest
        d.show()
        d.token_po.setText("polar_oat_malo")
        QTest.keyClick(d.token_po, Qt.Key.Key_Return)      # Enter conecta y no vuelve atrás
        self.assertEqual(d.pila.currentIndex(), 1)
        self.esperar(lambda: "token de Polar" in d.error.text())
        d.token_po.setText(sim.PO_TOKEN)
        d.conectar()
        self.esperar(lambda: d.resultado is not None)
        clave, datos, resumen, cliente = d.resultado
        r = adm.DialogoResumen(clave, cliente, resumen, datos, v, v.cfg)
        self.assertIn(sim.PO_ORG, r.codigo.text())
        r.guardar()
        self.assertEqual((r.datos["beneficio_id"], r.datos["url_compra"]),
                         (sim.PO_BENEFICIO, "https://buy.polar.sh/polar_cl_prueba"))
        v._guardar_conexion(clave, r.datos)
        self.assertIn("polar", v.clientes)
        s = adm.DialogoServidor(v)
        s.url.setText(RAIZ_SIM)
        s.publica.setText(sim.SB_SECRETA)
        s.secreta.setText(sim.SB_SECRETA)
        s.conectar()
        self.assertIn("PUBLICABLE", s.error.text())
        s.publica.setText(sim.SB_PUBLICA)
        s.conectar()
        self.esperar(lambda: s.datos)
        v._guardar_conexion("control", s.datos)
        self.assertIn("control", v.clientes)
        self.assertEqual(modelo.config_programa(v.cfg)["servidor"]["clave_publica"], sim.SB_PUBLICA)
        with mock.patch.object(adm, "preguntar", return_value=True):
            v.desconectar_servidor()
        self.assertNotIn("control", v.clientes)

    def test_componentes(self):
        interruptor = interfaz.Interruptor("Animaciones")
        interruptor.setChecked(True)
        self.assertEqual(interruptor._pos, 1.0)
        contador = interfaz.ContadorAnimado()
        contador.fijar(42)
        self.esperar(lambda: contador.text() == "42", 3)
        v = self.ventana({})
        b = interfaz.Bienvenida("Administrador", "v5")
        b.mostrar()
        self.assertEqual(b._intro, 1.0, "el logo termina de aparecer antes de armar la ventana")
        b.terminar(v)
        self.esperar(lambda: v.isVisible() and not b.isVisible(), 4)
        e = adm.DialogoEditar({"activation_limit": 2, "expires_at": None, "user_name": "Ana", "plataforma": "polar"})
        self.assertEqual(e.datos(), {"activation_limit": 2, "expires_at": None})
        e._sumar(30)
        self.assertIsNotNone(e.datos()["expires_at"])
        venta = adm.DialogoVenta(self.api.variantes(sim.TIENDA), "USD", previo={"cliente": "Lu", "precio": "gratis"})
        self.assertEqual(venta.datos()["precio"], "gratis")
        tarjeta = interfaz.TarjetaTema("oro", modelo.TEMAS["oro"])
        tarjeta.elegir(True)
        self.assertTrue(tarjeta.property("elegido"))

    def test_ventanas_del_programa(self):
        from cinema_licencias.qt import DialogoActivacion, DialogoAviso, DialogoLicenciaPerdida, DialogoMiLicencia
        from cinema_licencias.ventanas import Mensaje
        prog = self.sdk(ls_url_compra="https://x", polar_url_compra="https://y", whatsapp="502")
        d = DialogoActivacion(prog, Resultado(False, "reembolsada", "Reembolsada"))
        self.assertTrue(d.banda.isVisibleTo(d))
        self.assertTrue(d.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertEqual(set(d.barra.botones), {"min", "max", "cerrar"})
        d.txt.setText("no-existe")
        d.activar()
        self.esperar(lambda: not d._trabajando and "no es válida" in d.msg.text())
        k = sim.DATOS.vender_polar()
        d.txt.setText(k["key"])
        d.activar()
        self.esperar(lambda: d.result() == 1, 8)
        self.assertTrue(DialogoMiLicencia(prog).btn_desactivar.isEnabled())
        DialogoAviso(prog, {"id": 1, "tipo": "remocion", "titulo": "T", "mensaje": "M", "fecha_limite": "2026-10-20"})
        perdida = DialogoLicenciaPerdida(prog, Resultado(False, "reembolsada"), 1)
        perdida.show()
        self.esperar(lambda: not perdida.isVisible(), 4)
        # un diálogo abierto no impide cerrar el programa (Qt 6 pregunta a cada ventana al salir)
        m = Mensaje(None, "Hola", "texto")
        m.show()
        self.app.processEvents()
        m.close()
        self.esperar(lambda: not m.isVisible(), 2)


if __name__ == "__main__":
    unittest.main()
