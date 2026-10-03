"""Licencias con Lemon Squeezy — este archivo va DENTRO de tu programa.

Uso en el arranque (después de crear QApplication y ANTES de mostrar la ventana principal):

    from licencia_cliente import exigir_licencia
    if not exigir_licencia():
        sys.exit(0)

El programa habla con la API pública de licencias de Lemon Squeezy:
  - activar:    la primera vez que el cliente escribe su clave (ocupa un equipo de la licencia)
  - validar:    en cada arranque (¿sigue activa, vencida, bloqueada, desactivada?)
  - desactivar: cuando el cliente quiere pasar la licencia a otra computadora

Esa API NO necesita tu API key: nunca la pongas en este archivo ni en tu programa.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ======================= CONFIGURACIÓN =======================
# Copia estos valores desde el Administrador: ⚙ Configuración → "Datos para tu programa".
TIENDA_ID = 0                      # ID de tu tienda en Lemon Squeezy (obligatorio)
PRODUCTOS_ID: tuple[int, ...] = ()  # IDs de producto aceptados, p. ej. (123456,). Vacío = cualquiera de tu tienda
URL_COMPRA = ""                    # enlace de compra, p. ej. "https://tutienda.lemonsqueezy.com/buy/..."
WHATSAPP_VENDEDOR = ""             # opcional, para soporte: número con código de país, p. ej. "50255551234"
NOMBRE_APP = "Resolve Creator Subtitles"
VERSION_APP = "4.1.0"
DIAS_SIN_INTERNET = 7              # días que funciona sin conexión tras la última verificación
ACEPTAR_CLAVES_DE_PRUEBA = True    # claves de compras en "Test mode". Pon False cuando vendas de verdad
# =============================================================

_API = "https://api.lemonsqueezy.com/v1/licenses/"
_CARPETA = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "ResolveCreatorSubtitles"
_ARCHIVO = _CARPETA / "licencia.dat"
_SAL = b"rcs-licencia-lemonsqueezy-v1"


# ---------------------------------------------------------------- equipo

def _id_bruto_equipo() -> str:
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, "MachineGuid")[0]
    if sys.platform == "darwin":
        import subprocess
        salida = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                                capture_output=True, text=True).stdout
        for linea in salida.splitlines():
            if "IOPlatformUUID" in linea:
                return linea.split('"')[-2]
    for ruta in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        if os.path.exists(ruta):
            return Path(ruta).read_text().strip()
    raise RuntimeError("No se pudo obtener el identificador del equipo")


def obtener_id_equipo() -> str:
    """ID corto y estable del equipo, p. ej. 3F2A-91BC-04DE-77A1."""
    h = hashlib.sha256(f"RCS:{_id_bruto_equipo()}".encode()).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def nombre_instancia() -> str:
    """Nombre con el que el equipo aparece en Lemon Squeezy y en el Administrador."""
    return f"{platform.node() or 'Equipo'} · {obtener_id_equipo()}"[:100]


# ---------------------------------------------------------------- servidor

class SinConexion(Exception):
    pass


def _llamar(accion: str, datos: dict) -> dict:
    """POST a la API de licencias. Devuelve la respuesta JSON también cuando Lemon Squeezy
    contesta con un error de la licencia (400/404/422); lanza SinConexion si no hay respuesta."""
    req = urllib.request.Request(
        _API + accion,
        data=urllib.parse.urlencode(datos).encode(),
        headers={"Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": f"{NOMBRE_APP.replace(' ', '')}/{VERSION_APP}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            respuesta = json.loads(r.read() or b"{}")
            return respuesta if isinstance(respuesta, dict) else {}
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500 and e.code != 429:
            try:
                respuesta = json.loads(e.read())
                if isinstance(respuesta, dict):
                    return respuesta | {"_http": e.code}
            except ValueError:
                pass
        raise SinConexion(f"El servidor de licencias no respondió bien ({e.code}).") from e
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise SinConexion("No hay conexión a internet.") from e


def _es_nuestra(r: dict) -> bool:
    """Evita que funcionen claves de OTRAS tiendas de Lemon Squeezy (todas usan la misma API)."""
    meta = r.get("meta") or {}
    if int(meta.get("store_id") or 0) != int(TIENDA_ID):
        return False
    if PRODUCTOS_ID and int(meta.get("product_id") or 0) not in {int(p) for p in PRODUCTOS_ID}:
        return False
    if not ACEPTAR_CLAVES_DE_PRUEBA and (r.get("license_key") or {}).get("test_mode"):
        return False
    return True


def _fecha(iso: str | None) -> str:
    ts = _iso_a_ts(iso)
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else ""


def _traducir(r: dict) -> tuple[str, str]:
    """Convierte la respuesta de error de Lemon Squeezy en (codigo, mensaje en español)."""
    lic = r.get("license_key") or {}
    error = str(r.get("error") or "").lower()
    estado = lic.get("status")
    if estado == "disabled" or "disabled" in error:
        return "bloqueada", "Tu licencia fue bloqueada. Contacta al vendedor."
    if estado == "expired" or "expired" in error:
        cuando = _fecha(lic.get("expires_at"))
        return "vencida", (f"Tu licencia venció el {cuando}." if cuando else "Tu licencia venció.") + \
            " Renuévala para seguir usando el programa."
    if "activation limit" in error:
        return "en_uso", ("Esta licencia ya está activada en el máximo de equipos permitidos. "
                          "Desactívala en la otra computadora o contacta al vendedor.")
    if "instance" in error:
        return "desactivada", "Este equipo fue desactivado. Vuelve a activar tu licencia."
    if "not found" in error or r.get("_http") == 404:
        return "invalida", "La clave no es válida. Revísala (te llegó por correo al comprar)."
    return "error", str(r.get("error") or "No se pudo verificar la licencia.")


def _datos_respuesta(r: dict) -> dict:
    lic, meta = r.get("license_key") or {}, r.get("meta") or {}
    return {"cliente": meta.get("customer_name") or "", "correo": meta.get("customer_email") or "",
            "producto": meta.get("product_name") or "", "expira_ts": _iso_a_ts(lic.get("expires_at")),
            "limite": lic.get("activation_limit"), "usados": lic.get("activation_usage")}


def _iso_a_ts(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# ---------------------------------------------------------------- estado local

def _firma(datos: dict) -> str:
    texto = json.dumps(datos, sort_keys=True).encode()
    return hmac.new(hashlib.sha256(_SAL + obtener_id_equipo().encode()).digest(), texto, "sha256").hexdigest()


def _leer_local() -> dict | None:
    try:
        contenido = json.loads(_ARCHIVO.read_text(encoding="utf-8"))
        datos, firma = contenido["datos"], contenido["firma"]
        if (hmac.compare_digest(firma, _firma(datos)) and datos.get("equipo") == obtener_id_equipo()
                and datos.get("clave") and datos.get("instancia")):
            return datos
    except Exception:
        pass
    return None


def _guardar_local(datos: dict) -> None:
    _CARPETA.mkdir(parents=True, exist_ok=True)
    _ARCHIVO.write_text(json.dumps({"datos": datos, "firma": _firma(datos)}), encoding="utf-8")


def _borrar_local() -> None:
    try:
        _ARCHIVO.unlink()
    except FileNotFoundError:
        pass


def licencia_guardada() -> dict | None:
    """Datos de la licencia activada en este equipo (cliente, correo, expira_ts…) o None."""
    return _leer_local()


# ---------------------------------------------------------------- lógica

@dataclass
class Resultado:
    ok: bool
    codigo: str
    mensaje: str
    datos: dict = field(default_factory=dict)


def _sin_configurar() -> Resultado | None:
    if not TIENDA_ID:
        return Resultado(False, "error", "Falta configurar TIENDA_ID en licencia_cliente.py.")
    return None


def comprobar() -> Resultado:
    """Valida la licencia guardada contra Lemon Squeezy (se llama en cada arranque)."""
    if error := _sin_configurar():
        return error
    local = _leer_local()
    if not local:
        return Resultado(False, "sin_licencia", "Programa sin activar.")
    try:
        r = _llamar("validate", {"license_key": local["clave"], "instance_id": local["instancia"]})
    except SinConexion as e:
        transcurrido = time.time() - local.get("ultima_ok", 0)
        expira = local.get("expira_ts")
        if 0 <= transcurrido < DIAS_SIN_INTERNET * 86400 and (not expira or time.time() < expira):
            return Resultado(True, "sin_conexion_ok", "Modo sin conexión.", local)
        return Resultado(False, "sin_conexion", f"{e} Conéctate para verificar tu licencia.", local)

    if r.get("valid") and _es_nuestra(r):
        datos = local | _datos_respuesta(r) | {"ultima_ok": time.time()}
        _guardar_local(datos)
        return Resultado(True, "activa", "Licencia activa.", datos)

    codigo, mensaje = _traducir(r) if not r.get("valid") else ("otra_tienda", f"Esta clave no es de {NOMBRE_APP}.")
    # Bloqueada, vencida, desactivada…: se conserva la clave (si la desbloqueas o renuevas vuelve a
    # funcionar sola) pero se anula el modo sin conexión.
    _guardar_local(local | {"ultima_ok": 0})
    return Resultado(False, codigo, mensaje, local)


def activar(clave: str) -> Resultado:
    """Activa la clave en este equipo (ocupa uno de los equipos permitidos de la licencia)."""
    if error := _sin_configurar():
        return error
    clave = clave.strip()
    if not clave:
        return Resultado(False, "error", "Escribe tu clave de licencia.")

    local = _leer_local()
    if local and local["clave"] == clave:
        # Ya estaba activada aquí: solo se valida, para no gastar otro equipo de la licencia.
        r = comprobar()
        if r.ok or r.codigo != "desactivada":
            return r

    try:
        r = _llamar("activate", {"license_key": clave, "instance_name": nombre_instancia()})
    except SinConexion as e:
        return Resultado(False, "sin_conexion", f"{e} Se necesita internet para activar.")
    if not r.get("activated"):
        return Resultado(False, *_traducir(r))

    instancia = (r.get("instance") or {}).get("id")
    if not _es_nuestra(r) or not instancia:
        if instancia:   # devolver el equipo que se acaba de ocupar en esa otra licencia
            try:
                _llamar("deactivate", {"license_key": clave, "instance_id": instancia})
            except SinConexion:
                pass
        return Resultado(False, "otra_tienda", f"Esta clave no es de {NOMBRE_APP}.")

    datos = {"clave": clave, "instancia": instancia, "equipo": obtener_id_equipo(),
             **_datos_respuesta(r), "ultima_ok": time.time()}
    _guardar_local(datos)
    return Resultado(True, "activa", "Licencia activada.", datos)


def desactivar() -> Resultado:
    """Libera este equipo para que el cliente pueda activar la licencia en otra computadora."""
    local = _leer_local()
    if not local:
        _borrar_local()
        return Resultado(True, "sin_licencia", "Este equipo no tenía una licencia activada.")
    try:
        r = _llamar("deactivate", {"license_key": local["clave"], "instance_id": local["instancia"]})
    except SinConexion as e:
        return Resultado(False, "sin_conexion", f"{e} Se necesita internet para desactivar.")
    if r.get("deactivated") or _traducir(r)[0] in ("desactivada", "invalida"):
        _borrar_local()
        return Resultado(True, "desactivada",
                         "Licencia desactivada en este equipo. Ya puedes activarla en otra computadora.")
    return Resultado(False, *_traducir(r))


def enlace_whatsapp() -> str:
    texto = (f"Hola, necesito ayuda con mi licencia de {NOMBRE_APP}.\n"
             f"Mi ID de equipo: {obtener_id_equipo()}\n"
             f"Nombre del equipo: {platform.node()}")
    return f"https://wa.me/{WHATSAPP_VENDEDOR}?text={urllib.parse.quote(texto)}"


# ---------------------------------------------------------------- ventanas (PySide6)

def exigir_licencia(parent=None) -> bool:
    """Comprueba la licencia; si no es válida muestra la ventana de activación.
    Devuelve True si el programa puede continuar."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        r = comprobar()
    finally:
        QGuiApplication.restoreOverrideCursor()
    if r.ok:
        return True
    return _DialogoActivacion(r, parent).exec() == 1


def mostrar_mi_licencia(parent=None) -> bool:
    """Ventana "Mi licencia" (para un menú Ayuda → Licencia). Permite desactivar este equipo.
    Devuelve True si el cliente desactivó la licencia: en ese caso cierra tu programa."""
    from PySide6.QtWidgets import QDialog
    return _DialogoMiLicencia(parent).exec() == QDialog.DialogCode.Accepted


def _en_segundo_plano(funcion, al_terminar):
    """Ejecuta funcion() fuera del hilo de la ventana y llama al_terminar(resultado) al acabar."""
    from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

    class _Senales(QObject):
        listo = Signal(object)

    class _Trabajo(QRunnable):
        def __init__(self):
            super().__init__()
            self.senales = _Senales()

        def run(self):
            self.senales.listo.emit(funcion())

    trabajo = _Trabajo()
    trabajo.senales.listo.connect(al_terminar)
    QThreadPool.globalInstance().start(trabajo)
    return trabajo   # hay que guardar la referencia mientras trabaja


def _mono(puntos, negrita=False):
    from PySide6.QtGui import QFont
    f = QFont("Consolas", puntos)
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setBold(negrita)
    return f


def _DialogoActivacion(resultado: Resultado, parent=None):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

    class Dialogo(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle(f"Activar {NOMBRE_APP}")
            self.setMinimumWidth(500)
            self.setStyleSheet(_QSS)

            titulo = QLabel(f"Activa {NOMBRE_APP}", objectName="titulo")
            sub = QLabel("Para usar el programa necesitas una clave de licencia.", objectName="sub")
            sub.setWordWrap(True)

            btn_comprar = QPushButton("Comprar licencia", objectName="comprar")
            btn_comprar.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_COMPRA)))
            btn_comprar.setVisible(bool(URL_COMPRA))

            self.txt = QLineEdit(placeholderText="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
            self.txt.setFont(_mono(12))
            self.txt.setText((resultado.datos or {}).get("clave", ""))
            self.txt.returnPressed.connect(self.activar)

            self.msg = QLabel(objectName="msg")
            self.msg.setWordWrap(True)
            if resultado.codigo != "sin_licencia":
                self.mostrar(resultado.mensaje, error=True)

            btn_ayuda = QPushButton("Ayuda por WhatsApp", objectName="whatsapp")
            btn_ayuda.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(enlace_whatsapp())))
            btn_ayuda.setVisible(bool(WHATSAPP_VENDEDOR))
            self.btn_activar = QPushButton("Activar", objectName="primario")
            self.btn_activar.clicked.connect(self.activar)
            btn_salir = QPushButton("Salir", objectName="secundario")
            btn_salir.clicked.connect(self.reject)
            botones = QHBoxLayout()
            botones.addWidget(btn_ayuda)
            botones.addStretch()
            botones.addWidget(btn_salir)
            botones.addWidget(self.btn_activar)

            lay = QVBoxLayout(self)
            lay.setContentsMargins(28, 24, 28, 24)
            lay.setSpacing(12)
            lay.addWidget(titulo)
            lay.addWidget(sub)
            if URL_COMPRA:
                lay.addWidget(QLabel("1. Compra tu licencia (te llega la clave por correo):", objectName="paso"))
                lay.addWidget(btn_comprar)
                lay.addSpacing(6)
            lay.addWidget(QLabel(("2. " if URL_COMPRA else "") + "Escribe tu clave de licencia:",
                                 objectName="paso"))
            lay.addWidget(self.txt)
            lay.addWidget(self.msg)
            lay.addLayout(botones)

        def mostrar(self, texto, error=False):
            self.msg.setText(texto)
            self.msg.setProperty("error", error)
            self.msg.style().unpolish(self.msg)
            self.msg.style().polish(self.msg)

        def activar(self):
            clave = self.txt.text().strip()
            if not clave:
                self.mostrar("Escribe tu clave de licencia.", error=True)
                return
            self.btn_activar.setEnabled(False)
            self.btn_activar.setText("Activando…")
            self.mostrar("Verificando con el servidor…")
            self._trabajo = _en_segundo_plano(lambda: activar(clave), self.terminado)

        def terminado(self, r: Resultado):
            self.btn_activar.setEnabled(True)
            self.btn_activar.setText("Activar")
            if r.ok:
                self.accept()
            else:
                self.mostrar(r.mensaje, error=True)

    return Dialogo()


def _DialogoMiLicencia(parent=None):
    from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QMessageBox,
                                   QPushButton, QVBoxLayout)

    class Dialogo(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle("Mi licencia")
            self.setMinimumWidth(460)
            self.setStyleSheet(_QSS)
            datos = _leer_local() or {}

            titulo = QLabel(NOMBRE_APP, objectName="titulo")
            clave = datos.get("clave", "")
            expira = datos.get("expira_ts")
            limite, usados = datos.get("limite"), datos.get("usados")
            form = QFormLayout()
            form.setSpacing(8)
            form.addRow("Licencia de:", QLabel(datos.get("cliente") or "—"))
            form.addRow("Correo:", QLabel(datos.get("correo") or "—"))
            etiqueta_clave = QLabel(f"••••-{clave[-12:]}" if clave else "—")
            etiqueta_clave.setFont(_mono(11))
            form.addRow("Clave:", etiqueta_clave)
            form.addRow("Vence:", QLabel(datetime.fromtimestamp(expira).strftime("%d/%m/%Y") if expira else "Nunca"))
            if usados is not None:
                form.addRow("Equipos:", QLabel(f"{usados} de {limite if limite else 'ilimitados'}"))
            form.addRow("Este equipo:", QLabel(nombre_instancia()))

            self.msg = QLabel(objectName="msg")
            self.msg.setWordWrap(True)
            self.btn_desactivar = QPushButton("Desactivar en este equipo", objectName="secundario")
            self.btn_desactivar.setToolTip("Libera esta computadora para activar la licencia en otra.")
            self.btn_desactivar.setEnabled(bool(clave))
            self.btn_desactivar.clicked.connect(self.desactivar)
            cerrar = QPushButton("Cerrar", objectName="primario")
            cerrar.clicked.connect(self.reject)
            botones = QHBoxLayout()
            botones.addWidget(self.btn_desactivar)
            botones.addStretch()
            botones.addWidget(cerrar)

            lay = QVBoxLayout(self)
            lay.setContentsMargins(28, 24, 28, 24)
            lay.setSpacing(12)
            lay.addWidget(titulo)
            lay.addLayout(form)
            lay.addWidget(self.msg)
            lay.addLayout(botones)

        def desactivar(self):
            caja = QMessageBox(QMessageBox.Icon.Question, "Desactivar licencia",
                               "¿Desactivar la licencia en esta computadora?\n\n"
                               "El programa se cerrará y podrás activar tu clave en otra computadora.",
                               parent=self)
            si = caja.addButton("Sí, desactivar", QMessageBox.ButtonRole.AcceptRole)
            caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            caja.exec()
            if caja.clickedButton() is not si:
                return
            self.btn_desactivar.setEnabled(False)
            self.msg.setText("Desactivando…")
            self._trabajo = _en_segundo_plano(desactivar, self.terminado)

        def terminado(self, r: Resultado):
            if r.ok:
                QMessageBox.information(self, "Licencia desactivada", r.mensaje)
                self.accept()
            else:
                self.btn_desactivar.setEnabled(True)
                self.msg.setText(r.mensaje)
                self.msg.setProperty("error", True)
                self.msg.style().unpolish(self.msg)
                self.msg.style().polish(self.msg)

    return Dialogo()


_QSS = """
QDialog { background: #15171c; }
QLabel { color: #d8dbe2; font-size: 13px; background: transparent; }
QLabel#titulo { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#sub { color: #9aa1ad; }
QLabel#paso { color: #c3c8d2; font-weight: 600; margin-top: 4px; }
QLabel#msg { color: #9aa1ad; min-height: 18px; }
QLabel#msg[error="true"] { color: #ff7a7a; }
QLineEdit { background: #1e2129; color: #fff; border: 1px solid #343946; border-radius: 8px; padding: 10px; }
QLineEdit:focus { border-color: #7047eb; }
QPushButton { border-radius: 8px; padding: 9px 18px; font-size: 13px; font-weight: 600; }
QPushButton#primario { background: #4c8dff; color: white; border: none; }
QPushButton#primario:hover { background: #6aa0ff; }
QPushButton#primario:disabled { background: #34405a; color: #8a92a0; }
QPushButton#secundario { background: #262a33; color: #d8dbe2; border: 1px solid #343946; }
QPushButton#secundario:hover { background: #2f3440; }
QPushButton#secundario:disabled { color: #5b6270; }
QPushButton#comprar { background: #7047eb; color: white; border: none; padding: 11px; }
QPushButton#comprar:hover { background: #8563f0; }
QPushButton#whatsapp { background: transparent; color: #3ddc84; border: none; padding: 9px 4px; }
QPushButton#whatsapp:hover { color: #6be8a3; }
"""
