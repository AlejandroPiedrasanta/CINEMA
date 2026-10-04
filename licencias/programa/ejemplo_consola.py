"""Cinema Productions · ejemplo: licencias en un programa SIN ventanas (consola, servicio, otro framework).

    python ejemplo_consola.py                 → comprueba la licencia
    python ejemplo_consola.py CLAVE           → activa la clave en este equipo

Para programas que no están hechos en Python: llama a `python -m cinema_licencias --json estado`
(o al .exe que crees con PyInstaller) y lee el código de salida: 0 = válida, 1 = no válida.

Creado por Cinema Productions.
"""
import sys
import time
from pathlib import Path

from cinema_licencias import Licencias

LICENCIAS = Licencias.desde_json(Path(__file__).with_name("cinema_licencias.json"))


def al_cambiar(resultado):
    if not resultado.ok:
        print(f"\n✖ {resultado.mensaje} — el programa se cerrará.")
        raise SystemExit(1)
    print(f"\n✔ {resultado.mensaje}")


def al_aviso(aviso):
    print(f"\n📣 {aviso.get('titulo')}: {aviso.get('mensaje')}")


def main():
    r = LICENCIAS.activar(sys.argv[1]) if len(sys.argv) > 1 else LICENCIAS.comprobar()
    print(("✔ " if r.ok else "✖ ") + r.mensaje)
    if not r.ok:
        sys.exit(1)
    # revisa la licencia en segundo plano y envía el tiempo de uso mientras el programa trabaja
    LICENCIAS.iniciar_vigilancia(al_cambiar=al_cambiar, al_aviso=al_aviso)
    print("Trabajando… (Ctrl+C para salir)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
