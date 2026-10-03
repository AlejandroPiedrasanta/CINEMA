"""Ejemplo mínimo: así se integra la licencia en el main() de tu programa."""
import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel

from licencia_cliente import exigir_licencia, mostrar_mi_licencia


def main():
    app = QApplication(sys.argv)
    if not exigir_licencia():      # sin licencia válida -> se cierra
        sys.exit(0)

    ventana = QMainWindow()        # aquí va tu SubtitleApp
    ventana.setCentralWidget(QLabel("Programa principal funcionando ✔"))
    ventana.resize(400, 200)

    # Menú Ayuda → Mi licencia (permite al cliente desactivar este equipo para usar otro)
    accion = ventana.menuBar().addMenu("Ayuda").addAction("Mi licencia…")
    accion.triggered.connect(lambda: mostrar_mi_licencia(ventana) and app.quit())

    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
