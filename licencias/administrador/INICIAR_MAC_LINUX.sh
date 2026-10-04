#!/usr/bin/env bash
# Abre el Administrador de Licencias en macOS o Linux (la primera vez instala lo necesario).
#   bash INICIAR_MAC_LINUX.sh            → abre el panel
#   bash INICIAR_MAC_LINUX.sh construir  → crea la app en dist/ (.app en macOS)
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Preparando el entorno (solo la primera vez)…"
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade --quiet -r ../requirements.txt
if [ "$1" = "construir" ]; then
  python -m PyInstaller --noconfirm --clean administrador.spec
  echo "LISTO: $(pwd)/dist"
else
  python administrador_licencias.py
fi
