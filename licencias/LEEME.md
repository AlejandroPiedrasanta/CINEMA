# Sistema de licencias — Resolve Creator Subtitles (v3)

```
licencias/
├── Administrador de Licencias.exe   ← TU panel listo para Windows (solo para ti, no lo distribuyas)
├── requirements.txt                 ← librerías (PySide6 6.11 y PyInstaller 6.22, las más recientes)
├── administrador/
│   ├── administrador_licencias.py   ← ventana principal del panel
│   ├── interfaz.py                  ← diseño, colores y animaciones
│   ├── plataformas.py               ← conexión con Lemon Squeezy y Hotmart
│   ├── administrador.spec           ← receta para crear el ejecutable
│   ├── CONSTRUIR_EXE.bat            ← vuelve a crear el .exe en Windows (doble clic)
│   ├── INICIAR_MAC_LINUX.sh         ← abre (o construye) el panel en macOS y Linux
│   └── icono.ico
├── programa/
│   ├── licencia_cliente.py          ← va DENTRO de tu programa (no lleva ninguna clave secreta)
│   └── ejemplo_integracion.py       ← ejemplo de cómo conectarlo en main()
└── pruebas/
    ├── simulador.py                 ← Lemon Squeezy y Hotmart falsos para probar sin comprar
    └── test_licencias.py            ← 30 pruebas automáticas
```

## Qué hay de nuevo en la versión 3

- **Interfaz nueva** con menú lateral: *Inicio, Personas, Licencias, Equipos, Ventas, Actividad y Conexiones*.
- **Varias plataformas**: conecta **Lemon Squeezy**, **Hotmart** o las dos a la vez.
- **Conectar es guiado**: eliges la plataforma, pegas tus datos y aparece una ventana con
  **toda la información de la cuenta** (plataforma, cuenta, tienda, productos, licencias, ventas,
  compradores, ingresos, modo prueba/real) antes de guardar.
- **¿Cuántas personas tienen tu programa?** En *Inicio* y en *Personas* se cuentan los compradores
  únicos de todas tus plataformas (si alguien compró en las dos, cuenta una sola vez).
- **Animaciones**: páginas que entran deslizándose, números que suben, gráfico que crece, panel de
  detalle que se abre de lado, avisos flotantes y sacudida cuando un dato está mal.
  Se pueden apagar en *Conexiones → Ajustes*.
- **Multiplataforma**: `.exe` para Windows; en macOS y Linux se abre con `INICIAR_MAC_LINUX.sh`.

## Cómo funciona la licencia

1. El cliente abre tu programa → ventana **"Activa Resolve Creator Subtitles"** con el botón
   **Comprar licencia** (tu página de pago de Lemon Squeezy).
2. Paga → **Lemon Squeezy genera la clave y se la manda por correo**.
3. Pega la clave → **Activar**. El programa usa la API de licencias de Lemon Squeezy:
   - **Activar**: registra ese equipo y ocupa un "asiento" de la licencia.
   - **Validar**: en cada arranque (¿activa, vencida, bloqueada o le quitaste el equipo?).
   - **Desactivar**: *Ayuda → Mi licencia → Desactivar en este equipo* libera el asiento para otra PC.
4. En el Administrador te salta el aviso *"Nueva venta"* y luego *"Activación"*.

**¿Y si vendes en Hotmart?** Hotmart no crea claves de licencia. Cuando alguien te compre en
Hotmart, búscalo en *Personas* o *Ventas* y pulsa **🎁 Dar licencia**: se crea un enlace gratis de
Lemon Squeezy (cupón 100 %, un solo uso) con su nombre y correo, y se lo envías por WhatsApp o
correo. Al abrirlo recibe su clave. (Para esto necesitas tener conectado también Lemon Squeezy.)

## Paso 1 — Preparar tu producto

**Lemon Squeezy** (https://app.lemonsqueezy.com) → *Store → Products*: en la variante activa
**"Generate license keys"**, elige el **límite de equipos** (recomendado: 1) y la duración.
En *Test mode* puedes hacer compras de prueba con la tarjeta `4242 4242 4242 4242`.

**Hotmart** (opcional): no necesita nada especial en el producto.

## Paso 2 — Abrir el Administrador y conectar

- **Windows:** abre `Administrador de Licencias.exe` (requiere Windows 10 versión 1903 o más nueva,
  o Windows 11). Si Windows muestra "Windows protegió su PC": *Más información → Ejecutar de todas formas*.
- **macOS / Linux:** en una terminal, `bash administrador/INICIAR_MAC_LINUX.sh`
  (la primera vez instala lo necesario; necesitas Python 3.10 o más nuevo).

En la pantalla de bienvenida pulsa **Conectar Lemon Squeezy** o **Conectar Hotmart**:

| Plataforma | Qué pegar | Dónde se consigue |
|---|---|---|
| Lemon Squeezy | **API key** | app.lemonsqueezy.com → *Settings → API* → **+** |
| Hotmart | **Client ID** y **Client Secret** (el *Basic* se calcula solo) | Hotmart → *Herramientas → Credenciales Hotmart* → crear credencial *API Hotmart*. Marca **Sandbox** si son credenciales de pruebas. |

Al conectar se abre la ventana con toda la información de esa cuenta. Elige la **tienda** y el
**producto a vigilar** y pulsa **Guardar y continuar**. Las credenciales solo se guardan en tu
computadora (`RCS-Administrador/config.json` dentro de AppData en Windows o `~/.config` en macOS/Linux).

## Paso 3 — Conectar tu programa

1. Copia `programa/licencia_cliente.py` junto a tu script principal.
2. En *Conexiones → Datos para tu programa* pulsa **Copiar** y pega esas líneas en la sección
   **CONFIGURACIÓN** de `licencia_cliente.py` (y si quieres, `WHATSAPP_VENDEDOR = "502XXXXXXXX"`):
   ```python
   TIENDA_ID = 123456
   PRODUCTOS_ID = (654321,)
   URL_COMPRA = "https://tutienda.lemonsqueezy.com/buy/..."
   ```
3. En `main()`, después de crear `QApplication` y antes de mostrar tu ventana:
   ```python
   from licencia_cliente import exigir_licencia, mostrar_mi_licencia
   if not exigir_licencia():
       sys.exit(0)
   ```
4. Añade **Ayuda → Mi licencia** para que el cliente pueda liberar su equipo (ver `ejemplo_integracion.py`).
5. Recompila tu programa e instalador como siempre.

## Qué puedes hacer en el panel

| Página | Para qué sirve |
|---|---|
| **Inicio** | Personas con el programa, licencias activas, equipos, ventas e ingresos de 30 días, gráfico de ventas por plataforma y actividad reciente. |
| **Personas** | Cada comprador una sola vez, en todas tus plataformas: si tiene el programa, compras, licencia y equipos. Copiar correo, WhatsApp, ver licencia o **🎁 Dar licencia**. |
| **Licencias** | Clic en una licencia → panel de detalle: copiar/enviar la clave, **Editar** (equipos permitidos y vencimiento), **Bloquear/Desbloquear** y **Quitar** equipos. Filtros por estado. **＋ Nuevo enlace de compra** (precio normal, especial o gratis). |
| **Equipos** | Computadoras donde se activó el programa; quitar un equipo libera el asiento. |
| **Ventas** | Ventas de Lemon Squeezy y Hotmart juntas, con reembolsos y contracargos. |
| **Actividad** | Ventas, reembolsos, activaciones y equipos desactivados, con aviso en pantalla. |
| **Conexiones** | Estado de cada plataforma (ver información, cambiar credenciales, desconectar), datos para tu programa y ajustes (nombre del programa, cada cuánto actualizar, animaciones). |

## Bueno saber

- **Sin internet:** tu programa funciona hasta **7 días** desde la última verificación (`DIAS_SIN_INTERNET`).
- **Claves de prueba:** `ACEPTAR_CLAVES_DE_PRUEBA = True` deja usar claves de compras en *Test mode*.
  Cámbialo a `False` cuando vendas de verdad.
- **Seguridad:**
  - Tu programa **no lleva ninguna clave secreta**; solo usa la API pública de licencias.
  - `TIENDA_ID` / `PRODUCTOS_ID` impiden que funcionen claves de otras tiendas.
  - Compila tu programa con **Nuitka** para que sea más difícil quitar la verificación.
  - Si una API key o credencial se compartió en un chat o documento, **bórrala y crea otra**.
- **Si algo falla en el panel:** revisa `registro.log` en la misma carpeta que `config.json`.

## Probar sin internet

```
pip install -r licencias/requirements.txt
python -m unittest discover -s licencias/pruebas -v
```

Las pruebas levantan `simulador.py` (Lemon Squeezy y Hotmart falsos) y comprueban activar, validar,
desactivar, límite de equipos, bloqueo, vencimiento, modo sin conexión, claves de otra tienda,
enlaces de compra, ventas y reembolsos de Hotmart, el conteo de personas y las ventanas del panel.
