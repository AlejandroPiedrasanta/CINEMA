"""Cinema Productions · ejemplo: licencias en un programa con PySide6 (3 líneas).

1. Copia la carpeta cinema_licencias/ junto a tu script principal.
2. Copia también cinema_licencias.json (lo crea el Administrador: Conexiones → Datos para tu programa →
   Guardar archivo).
3. Agrega las líneas marcadas con ★.

Creado por Cinema Productions.
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from cinema_licencias import Licencias                                              # ★

LICENCIAS = Licencias.desde_json(Path(__file__).with_name("cinema_licencias.json"))  # ★


def main():
    app = QApplication(sys.argv)
    if not LICENCIAS.exigir():          # ★ sin licencia válida → ventana de activación; si sale, se cierra
        sys.exit(0)

    ventana = QMainWindow()             # aquí va la ventana de tu programa
    ventana.setCentralWidget(QLabel("Programa principal funcionando ✔"))
    ventana.resize(480, 240)

    # Menú Ayuda → Mi licencia (el cliente puede desactivar este equipo para usar otro)
    accion = ventana.menuBar().addMenu("Ayuda").addAction("Mi licencia…")
    accion.triggered.connect(lambda: LICENCIAS.mostrar_mi_licencia(ventana) and app.quit())

    ventana.show()
    # ★ Mientras está abierto: muestra tus avisos, envía el tiempo de uso y, si la compra se reembolsa o
    #   bloqueas la licencia, avisa, cierra el programa y pide una licencia (si la reactivas, vuelve solo).
    LICENCIAS.vigilar(ventana)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
