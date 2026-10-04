"""Cinema Productions · cinema_licencias desde la línea de comandos.

Sirve para probar la configuración y para usar las licencias desde programas que NO están hechos en
Python (C#, C++, Node, Electron, AutoHotkey…): se llama al comando y se lee el código de salida o el
JSON que imprime con --json.

    python -m cinema_licencias estado
    python -m cinema_licencias activar 38B1460A-5104-4067-A91D-77B872934D51
    python -m cinema_licencias desactivar
    python -m cinema_licencias equipo
    python -m cinema_licencias ventana        (abre la ventana de activación; necesita PySide6)
    python -m cinema_licencias --config ruta/cinema_licencias.json --json estado

Códigos de salida: 0 = licencia válida · 1 = no válida · 2 = error de uso.

Creado por Cinema Productions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import Licencias, Resultado, VERSION_SDK

__author__ = "Cinema Productions"


def _buscar_config(ruta: str | None) -> Path | None:
    if ruta:
        return Path(ruta)
    for candidata in (Path.cwd() / "cinema_licencias.json", Path(sys.argv[0]).resolve().parent / "cinema_licencias.json"):
        if candidata.exists():
            return candidata
    return None


def _imprimir(r: Resultado, como_json: bool) -> int:
    if como_json:
        print(json.dumps(r.a_dict(), ensure_ascii=False, indent=2))
    else:
        marca = "✔" if r.ok else "✖"
        print(f"{marca} {r.mensaje}  [{r.codigo}]")
        d = r.datos or {}
        for etiqueta, clave in (("Cliente", "cliente"), ("Correo", "correo"), ("Tienda", "tienda")):
            if d.get(clave):
                print(f"   {etiqueta}: {d[clave]}")
        for a in r.avisos:
            print(f"   Aviso: {a.get('titulo')} — {a.get('mensaje')}")
    return 0 if r.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cinema_licencias",
                                     description="Licencias de Cinema Productions (Lemon Squeezy, Gumroad y Polar).")
    parser.add_argument("--config", help="ruta de cinema_licencias.json (por defecto, la carpeta actual)")
    parser.add_argument("--json", action="store_true", help="imprime el resultado en JSON")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("estado", help="comprueba la licencia de este equipo")
    act = sub.add_parser("activar", help="activa una clave en este equipo")
    act.add_argument("clave")
    sub.add_parser("desactivar", help="libera este equipo")
    sub.add_parser("equipo", help="muestra el ID de este equipo")
    sub.add_parser("ventana", help="abre la ventana de activación (PySide6)")
    sub.add_parser("version", help="versión del SDK")
    args = parser.parse_args(argv)

    if args.comando == "version":
        print(f"cinema_licencias {VERSION_SDK} — Cinema Productions")
        return 0
    ruta = _buscar_config(args.config)
    if not ruta or not ruta.exists():
        print("No se encontró cinema_licencias.json. Créalo desde el Administrador (Conexiones → Datos para tu "
              "programa → Guardar archivo) o indica la ruta con --config.", file=sys.stderr)
        return 2
    lic = Licencias.desde_json(ruta)
    if args.comando == "equipo":
        if args.json:
            print(json.dumps({"equipo": lic.equipo_id(), "nombre": lic.nombre_equipo()}, ensure_ascii=False))
        else:
            print(lic.nombre_equipo())
        return 0
    if args.comando == "ventana":
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName(lic.cfg.app)
        return 0 if lic.exigir() else 1
    if args.comando == "estado":
        return _imprimir(lic.comprobar(), args.json)
    if args.comando == "activar":
        return _imprimir(lic.activar(args.clave), args.json)
    if args.comando == "desactivar":
        return _imprimir(lic.desactivar(), args.json)
    return 2


if __name__ == "__main__":
    sys.exit(main())
