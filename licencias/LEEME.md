# Sistema de licencias — Resolve Creator Subtitles (v4)

```
licencias/
├── Instalar Administrador de Licencias 4.0.0.exe   ← INSTALADOR para Windows (solo para ti)
├── requirements.txt                 ← librerías (PySide6 6.11 y PyInstaller 6.22)
├── administrador/
│   ├── administrador_licencias.py   ← ventana principal del panel
│   ├── interfaz.py                  ← diseño, colores y animaciones
│   ├── plataformas.py               ← conexión con Lemon Squeezy, Hotmart y Gumroad
│   ├── administrador.spec           ← receta para crear el ejecutable
│   ├── version_info.txt             ← nombre, versión y empresa que muestra Windows
│   ├── CONSTRUIR_EXE.bat            ← crea un .exe portátil (sin instalar)
│   ├── INICIAR_MAC_LINUX.sh         ← abre (o construye) el panel en macOS y Linux
│   └── icono.ico
├── instalador/
│   ├── instalador.nsi               ← receta del instalador (NSIS)
│   ├── CONSTRUIR_INSTALADOR.bat     ← vuelve a crear el instalador (doble clic)
│   ├── crear_imagenes.py            ← dibuja los banners y el icono
│   └── imagenes/                    ← banners del instalador e icono
├── programa/
│   ├── licencia_cliente.py          ← va DENTRO de tu programa (no lleva ninguna clave secreta)
│   └── ejemplo_integracion.py       ← ejemplo de cómo conectarlo en main()
└── pruebas/
    ├── simulador.py                 ← Lemon Squeezy, Hotmart y Gumroad falsos para probar sin comprar
    └── test_licencias.py            ← 40 pruebas automáticas
```

## Qué hay de nuevo en la versión 4

- **Gumroad**: el panel muestra sus ventas, compradores y **claves de licencia** (bloquear,
  desbloquear y liberar un uso), y tu programa acepta las claves de Gumroad además de las de
  Lemon Squeezy.
- **Instalador completo para Windows** con banners: bienvenida, carpeta, componentes, progreso y
  final. Crea accesos directos en el **menú Inicio** y (opcional) en el **escritorio**, y queda en
  **Configuración → Aplicaciones** con su desinstalador.
- **Más animaciones**: pantalla de carga con el logo, tarjetas que suben una tras otra, gráfico que
  crece en ola, brillo mientras cargan los datos, onda al pulsar botones, tarjetas que se levantan
  al pasar el ratón, fondo de bienvenida con luces en movimiento, palomita animada al conectar,
  interruptores deslizantes y destello cuando llega actividad nueva. Se pueden apagar en
  *Conexiones → Ajustes*.

## Paso 1 — Instalar el Administrador (Windows)

Doble clic en **`Instalar Administrador de Licencias 4.0.0.exe`** → *Siguiente* → *Siguiente* →
*Instalar* → *Terminar*. Requiere Windows 10 (versión 1903 o más nueva) u 11, de 64 bits.

> Como el instalador no está firmado, Windows puede mostrar "Windows protegió su PC":
> **Más información → Ejecutar de todas formas**.

Para desinstalar: *Configuración → Aplicaciones → Administrador de Licencias → Desinstalar*.
Tus credenciales se conservan, salvo que marques **"Borrar también mis credenciales y ajustes"**.

**macOS / Linux:** `bash administrador/INICIAR_MAC_LINUX.sh` (necesitas Python 3.10 o más nuevo).

## Paso 2 — Conectar tus plataformas

En la pantalla de bienvenida pulsa **Conectar** en la plataforma que uses (puedes conectar las tres):

| Plataforma | Qué pegar | Dónde se consigue |
|---|---|---|
| Lemon Squeezy | **API key** | app.lemonsqueezy.com → *Settings → API* → **+** |
| Hotmart | **Client ID** y **Client Secret** | Hotmart → *Herramientas → Credenciales Hotmart* → crear credencial *API Hotmart* (marca **Sandbox** si son de pruebas) |
| Gumroad | **Access token** | Gumroad → *Settings → Advanced → Applications* → crea una aplicación (en *Redirect URI* pon `http://127.0.0.1`) → **Generate access token** |

Al conectar aparece una ventana con toda la información de la cuenta. Elige el **producto** y pulsa
**Guardar y continuar**. Las credenciales solo se guardan en tu computadora.

## Paso 3 — Preparar tus productos

- **Lemon Squeezy**: en la variante activa **"Generate license keys"** y el **límite de equipos**.
- **Gumroad**: en tu producto activa **"Generate a unique license key per sale"**. Cada clave
  cuenta "usos": tu programa suma uno al activarse (máximo `GUMROAD_MAX_EQUIPOS`) y tú puedes
  **liberar un uso** desde el panel cuando un cliente cambie de computadora.
- **Hotmart**: no genera claves. Para dar una licencia a un comprador de Hotmart usa
  **🎁 Dar licencia** (crea un enlace gratis de Lemon Squeezy; requiere Lemon Squeezy conectado).

## Paso 4 — Conectar tu programa

1. Copia `programa/licencia_cliente.py` junto a tu script principal.
2. En *Conexiones → Datos para tu programa* pulsa **Copiar** y pega esas líneas en la sección
   **CONFIGURACIÓN** de `licencia_cliente.py`. Ejemplo:
   ```python
   TIENDA_ID = 123456                      # Lemon Squeezy (0 si no lo usas)
   PRODUCTOS_ID = (654321,)
   URL_COMPRA = "https://tutienda.lemonsqueezy.com/buy/..."
   GUMROAD_PRODUCTO_ID = "AbC123...=="     # Gumroad ("" si no lo usas)
   URL_COMPRA_GUMROAD = "https://tunombre.gumroad.com/l/producto"
   ```
3. En `main()`, después de crear `QApplication` y antes de mostrar tu ventana:
   ```python
   from licencia_cliente import exigir_licencia, mostrar_mi_licencia
   if not exigir_licencia():
       sys.exit(0)
   ```
4. Añade **Ayuda → Mi licencia** (ver `ejemplo_integracion.py`).

La ventana de activación muestra un botón de compra por cada tienda configurada. El programa
reconoce solo la plataforma por el formato de la clave (las de Gumroad son 4 bloques de 8 caracteres).

## Qué puedes hacer en el panel

| Página | Para qué sirve |
|---|---|
| **Inicio** | Personas con el programa, licencias activas, equipos, ventas e ingresos de 30 días, gráfico por plataforma y actividad reciente. |
| **Personas** | Cada comprador una sola vez en las tres plataformas: si tiene el programa, compras, licencia y equipos. |
| **Licencias** | Claves de Lemon Squeezy y Gumroad. Lemon Squeezy: editar equipos/vencimiento, bloquear y quitar equipos. Gumroad: bloquear/desbloquear y liberar un uso. |
| **Equipos** | Computadoras donde se activó el programa (Lemon Squeezy). |
| **Ventas** | Ventas de las tres plataformas, con reembolsos, contracargos y disputas. |
| **Actividad** | Ventas, reembolsos, activaciones y equipos desactivados, con aviso en pantalla. |
| **Conexiones** | Estado de cada plataforma, datos para tu programa y ajustes. |

## Volver a crear el instalador o el .exe

- **Instalador:** instala NSIS (`winget install NSIS.NSIS`) y haz doble clic en
  `instalador\CONSTRUIR_INSTALADOR.bat`.
- **.exe portátil (sin instalar):** doble clic en `administrador\CONSTRUIR_EXE.bat`.
- **Banners e icono:** `pip install pillow` y `python instalador\crear_imagenes.py`.

## Bueno saber

- **Sin internet:** tu programa funciona hasta **7 días** desde la última verificación.
- **Claves de prueba:** `ACEPTAR_CLAVES_DE_PRUEBA = True` acepta compras de prueba. Pon `False`
  cuando vendas de verdad.
- **Seguridad:** tu programa **no lleva ninguna clave secreta**. Si una API key o token se
  compartió en un chat, **bórrala y crea otra**.
- **Si algo falla en el panel:** revisa `registro.log` en `%APPDATA%\RCS-Administrador`.

## Probar sin internet

```
pip install -r licencias/requirements.txt
python -m unittest discover -s licencias/pruebas -v
```
