# Administrador de Licencias v5 — Cinema Productions

Sistema completo para vender tu programa con licencias: un **panel de escritorio** para ver y
controlar a tus compradores, y un **kit (API de programa) `cinema_licencias`** para meter
licencias en cualquier programa de Python en 3 líneas.

Funciona con **Lemon Squeezy, Gumroad, Polar.sh y Hotmart** (ventas). Opcionalmente, con un
**servidor de control gratuito en Supabase** para avisos, bloqueos y tiempo de uso.

*Creado por Cinema Productions.*

## Qué hay de nuevo en la versión 5

- **Marca Cinema Productions** en el panel, el instalador, las carpetas, los comandos y el kit.
- **Ventanas sin el marco de Windows**: botones de minimizar, maximizar y cerrar dibujados a mano,
  en todas las ventanas y diálogos. Se arrastran por la barra y se redimensionan por los bordes.
- **Pestaña Ajustes**: tamaño de la interfaz (80 %–200 %), estilos (Cinema, Violeta, Medianoche,
  Grafito, Oro, Claro), velocidad de las animaciones y modo privado. Abajo: *Creado por Cinema Productions*.
- **Modo privado** (botón 👁 o *Ajustes → Privacidad*): elige ocultar **nombres, correos y claves de licencia** en todo el panel, ideal para
  grabar pantalla o hacer capturas.
- **Polar.sh** conectado a la API (claves de licencia, activaciones, pedidos y reembolsos).
- **Más control sobre los compradores**: ficha de cada persona con compras, licencias, equipos,
  **tiempo de uso**, última vez que abrió el programa, versión y sistema.
- **Avisos y alertas**: envía un aviso a una licencia (informativo, advertencia o bloqueo). Si le
  quitas la licencia, el cliente ve el aviso y el programa le pide licencia; si la vuelves a
  activar, se reactiva sola.
- **Reembolsos automáticos**: si una compra se reembolsa, el programa del cliente muestra un aviso
  con cuenta atrás, **se cierra y pide licencia**. Si el reembolso se cancela, se reactiva.
- **Más animaciones**: transiciones entre páginas, aurora en el inicio, tarjetas que se elevan,
  cambio de tema con fundido, notificaciones deslizantes.

## Paso 1 — Instalar el Administrador

**Windows 10/11 (64 bits):** doble clic en **`Instalar Administrador de Licencias 5.0.0.exe`** →
*Siguiente* → *Instalar* → *Terminar*. Si tenías la versión 4, se reemplaza sola (tus credenciales
se migran). Queda en *Inicio → Cinema Productions*.

> El instalador no está firmado; si Windows muestra "Windows protegió su PC":
> **Más información → Ejecutar de todas formas**.

El componente **"Kit para tu programa"** copia `cinema_licencias/`, ejemplos, el SQL del servidor y
este LEEME a la carpeta de instalación.

**macOS / Linux:** `bash administrador/INICIAR_MAC_LINUX.sh` (Python 3.10 o más nuevo).

## Paso 2 — Conectar tus plataformas

En **Inicio** pulsa **Conectar** en la plataforma que uses (puedes conectar todas):

| Plataforma | Qué pegar | Dónde se consigue |
|---|---|---|
| Lemon Squeezy | **API key** | app.lemonsqueezy.com → *Settings → API* → **+** |
| Gumroad | **Access token** | *Settings → Advanced → Applications* → crea una app (Redirect URI `http://127.0.0.1`) → **Generate access token** |
| Polar.sh | **Organization Access Token** (`polar_oat_…`) | polar.sh → tu organización → *Settings → Developers → New token* (permisos de lectura/escritura de licencias, clientes, pedidos y beneficios). Marca **Sandbox** si es de pruebas. |
| Hotmart | **Client ID** y **Client Secret** | *Herramientas → Credenciales Hotmart* |

Al conectar aparece una ventana con la información de la cuenta. Elige el producto (en Polar, el
**beneficio de License Keys**) y pulsa **Guardar y continuar**. Las credenciales solo se guardan
en tu computadora (`%APPDATA%\Cinema Productions\Administrador de Licencias`).

## Paso 3 — Servidor de control (opcional, recomendado)

Necesario para **avisos, bloqueos manuales, tiempo de uso y reactivación automática**.

1. Crea un proyecto gratis en **supabase.com**.
2. *SQL Editor* → pega el contenido de `servidor/supabase_cinema.sql` → **Run**.
3. En el Administrador: **Inicio → Conectar el servidor de control** y pega la **URL** del proyecto
   y la **clave secreta** (`sb_secret_…`, solo para el Administrador) y la **clave publicable**
   (`sb_publishable_…`, la que va en tu programa).

El programa del cliente solo puede **leer su propio estado y enviar su tiempo de uso**; nunca
puede darse una licencia. Las claves se guardan como hash (`sha256`), no en texto.

## Paso 4 — Meter licencias en tu programa (API de programa)

1. En **Conexiones → Datos para tu programa** pulsa **Guardar archivo** → `cinema_licencias.json`.
   (El Administrador nunca escribe claves secretas en ese archivo.)
2. Copia la carpeta `programa/cinema_licencias/` y el `.json` junto a tu script.
3. Agrega 3 líneas:

```python
from cinema_licencias import Licencias
LICENCIAS = Licencias.desde_json("cinema_licencias.json")

app = QApplication(sys.argv)
if not LICENCIAS.exigir():      # sin licencia → ventana de activación (y botones de compra)
    sys.exit(0)
LICENCIAS.vigilar(ventana)      # avisos, bloqueos y reembolsos en vivo + tiempo de uso
```

Menú **Ayuda → Mi licencia**: `LICENCIAS.mostrar_mi_licencia(ventana)`.
Ejemplos completos: `programa/ejemplo_integracion.py` (PySide6) y `programa/ejemplo_consola.py`
(sin interfaz, usa `comprobar()` / `activar()` y devuelve `Resultado`).

**Desde la terminal** (útil para scripts o programas en otros lenguajes):

```
python -m cinema_licencias estado  --config cinema_licencias.json --json
python -m cinema_licencias activar CLAVE
python -m cinema_licencias desactivar
python -m cinema_licencias equipo
```

Código de salida: `0` licencia válida, `1` sin licencia, `2` error.

¿Ya usabas `licencia_cliente.py` de la v4? Sigue funcionando igual (ahora por dentro usa
`cinema_licencias`), así que tus clientes no tienen que activar de nuevo.

El programa reconoce la tienda por el formato de la clave: Gumroad (4 bloques de 8), Lemon
Squeezy (UUID) y Polar (con prefijo o UUID).

## Qué puedes hacer en el panel

| Página | Para qué sirve |
|---|---|
| **Inicio** | Personas, licencias activas, equipos, ventas e ingresos, uso de hoy, gráfico por plataforma. |
| **Personas** | Cada comprador una vez en todas las plataformas; ficha con tiempo de uso, equipos y avisos. |
| **Licencias** | Bloquear, desbloquear, editar límites, quitar equipos, enviar avisos. |
| **Equipos** | Computadoras activadas, sistema, versión y última conexión. |
| **Uso** | Tiempo de uso por persona y por día (telemetría del servidor de control). |
| **Ventas** | Ventas, reembolsos, contracargos y disputas de todas las plataformas. |
| **Avisos** | Avisos enviados, leídos o pendientes; bloqueo/reactivación. |
| **Actividad** | Ventas, reembolsos, activaciones; notificación en pantalla al llegar algo nuevo. |
| **Conexiones** | Estado de cada plataforma y del servidor; datos para tu programa. |
| **Ajustes** | Tamaño, estilo, animaciones, modo privado. *Creado por Cinema Productions.* |

**Privacidad de tus clientes:** la telemetría solo envía tiempo de uso, versión, sistema y
(opcional) el nombre del equipo. Puedes apagarla con `"telemetria": false` o
`"enviar_nombre_equipo": false` en `cinema_licencias.json`. Avisa en tus términos de uso.

## Volver a crear el instalador o el .exe

- **Instalador:** instala NSIS (`winget install NSIS.NSIS`) y ejecuta
  `instalador\CONSTRUIR_INSTALADOR.bat`.
- **.exe portátil:** `administrador\CONSTRUIR_EXE.bat`.
- **Banners e icono:** `pip install pillow` y `python instalador\crear_imagenes.py`.

## Bueno saber

- **Sin internet:** el programa funciona hasta **7 días** (`dias_sin_internet`).
- **Claves de prueba:** `"aceptar_pruebas": true` acepta compras de prueba. Ponlo en `false`
  cuando vendas de verdad.
- **Seguridad:** tu programa **no lleva ninguna clave secreta**. Si una API key o token se
  compartió en un chat o en un archivo, **bórrala y crea otra** en la plataforma.
- **Registro de errores del panel:** `registro.log` en
  `%APPDATA%\Cinema Productions\Administrador de Licencias`.

## Probar sin internet

```
pip install -r requirements.txt
python -m unittest discover -s pruebas -v
```

56 pruebas con simuladores de Lemon Squeezy, Gumroad, Polar, Hotmart y Supabase.

---
© Cinema Productions
