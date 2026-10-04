# Sistema de licencias con Lemon Squeezy — Resolve Creator Subtitles

```
licencias/
├── Administrador de Licencias.exe   ← TU panel listo para usar (solo para ti, no lo distribuyas)
├── administrador/
│   ├── administrador_licencias.py   ← TU panel (solo para ti, usa tu API key)
│   ├── icono.ico
│   ├── administrador.spec           ← receta de PyInstaller (exe sin partes de Qt que no se usan)
│   └── CONSTRUIR_EXE.bat            ← vuelve a crear el .exe (doble clic)
├── programa/
│   ├── licencia_cliente.py          ← va DENTRO de tu programa (no lleva API key)
│   └── ejemplo_integracion.py       ← ejemplo de cómo conectarlo en main()
└── pruebas/
    ├── simulador_lemonsqueezy.py    ← Lemon Squeezy falso para probar sin comprar
    └── test_licencias.py            ← pruebas automáticas
```

## Cómo funciona

1. El cliente abre tu programa → aparece **"Activa Resolve Creator Subtitles"** con el botón
   **Comprar licencia** (abre tu página de pago de Lemon Squeezy).
2. Paga → **Lemon Squeezy genera la clave y se la manda por correo** (también la ves en tu panel).
3. El cliente pega la clave → **Activar**. El programa llama a la API de Lemon Squeezy:
   - **Activar** (`/v1/licenses/activate`): registra ese equipo y ocupa un "asiento" de la licencia.
   - **Validar** (`/v1/licenses/validate`): en cada arranque comprueba si sigue activa, vencida,
     bloqueada o si quitaste el equipo.
   - **Desactivar** (`/v1/licenses/deactivate`): desde *Ayuda → Mi licencia → Desactivar en este equipo*
     el cliente libera el asiento para instalar en otra computadora.
4. En tu Administrador salta el aviso *"Nueva venta"* y luego *"Activación: Ana — PC-ANA"*.

Si alguien pasa su clave a otra persona y ya se usaron todos los equipos permitidos, le sale
*"Esta licencia ya está activada en el máximo de equipos permitidos"*.

## Paso 1 — Preparar el producto en Lemon Squeezy (una sola vez)

1. Entra a **https://app.lemonsqueezy.com** → **Store → Products → New product** (o edita el tuyo).
2. En la variante, activa **"Generate license keys"** y elige:
   - **Activation limit**: cuántas computadoras por compra (recomendado: 1).
   - **License length**: *Unlimited* (permanente) o la duración que quieras.
3. Publica el producto. Mientras tu tienda esté en **Test mode** puedes hacer compras de prueba
   con la tarjeta `4242 4242 4242 4242`.

## Paso 2 — Abrir el Administrador

1. Abre `Administrador de Licencias.exe`. Si cambias el código, recompílalo con doble clic en
   `administrador\CONSTRUIR_EXE.bat` (crea `administrador\dist\Administrador de Licencias.exe`).
2. La primera vez pide tu **API key** (Lemon Squeezy → **Settings → API**) → **Conectar** →
   elige **Tienda** y **Producto** → **Guardar**.
3. En esa misma ventana aparece **"Datos para tu programa"** → **Copiar**. Ejemplo:
   ```python
   TIENDA_ID = 123456
   PRODUCTOS_ID = (654321,)
   URL_COMPRA = "https://tutienda.lemonsqueezy.com/buy/..."
   ```

La API key solo se guarda en tu PC (`%APPDATA%\RCS-Administrador\config_lemonsqueezy.json`).
El panel se actualiza solo cada 30 segundos.

> Windows puede mostrar "Windows protegió su PC" porque el .exe no está firmado:
> **Más información → Ejecutar de todas formas**.

## Paso 3 — Conectar tu programa

1. Copia `programa/licencia_cliente.py` junto a tu script principal.
2. Pega los "Datos para tu programa" en la sección **CONFIGURACIÓN** del inicio del archivo
   (y si quieres, `WHATSAPP_VENDEDOR = "502XXXXXXXX"` para el botón de ayuda).
3. En `main()`, justo después de crear `QApplication` y antes de mostrar tu ventana:
   ```python
   from licencia_cliente import exigir_licencia, mostrar_mi_licencia
   if not exigir_licencia():
       sys.exit(0)
   ```
4. Añade un menú **Ayuda → Mi licencia** para que el cliente pueda desactivar su equipo
   (mira `ejemplo_integracion.py`):
   ```python
   accion.triggered.connect(lambda: mostrar_mi_licencia(ventana) and app.quit())
   ```
5. Recompila tu programa e instalador como siempre.

## Qué puedes hacer desde el panel

| Acción | Efecto |
|---|---|
| **Nuevo enlace de compra** | Crea un enlace de pago para un cliente: precio normal, **precio especial** o **gratis** (cupón 100 % de un solo uso, para regalar o dar licencias a mano). Lo envías por WhatsApp o correo; al completarlo, Lemon Squeezy le genera la clave. |
| **Copiar clave / Enviar por WhatsApp / correo** | Reenvía la clave al cliente. |
| **Editar** | Cambia los equipos permitidos (o ilimitados) y la fecha de vencimiento (+30 días, +1 año, fecha exacta o nunca). |
| **Bloquear / Desbloquear** | Pausa la licencia. Al desbloquear vuelve a funcionar sola, sin reescribir la clave. |
| **Quitar equipo** | Desactiva esa PC; la clave queda libre para activarse en otra (cambio de PC o formateo). |
| Pestaña **Ventas** | Pedidos, totales, reembolsos y recibos. |
| Pestaña **Actividad** | Ventas, activaciones y equipos desactivados, con notificación en la bandeja. |

Los reembolsos se hacen desde la web de Lemon Squeezy; después revisa en el panel que esa
licencia quede bloqueada (si no, pulsa **Bloquear**). La API de Lemon Squeezy no permite crear
claves sueltas: por eso las licencias "a mano" se dan con un enlace **gratis**.

## Bueno saber

- **Sin internet:** el programa funciona hasta **7 días** desde la última verificación
  (`DIAS_SIN_INTERNET`). Para activar o desactivar sí necesita internet.
- **Claves de prueba:** `ACEPTAR_CLAVES_DE_PRUEBA = True` deja usar claves de compras en *Test mode*.
  Cámbialo a `False` cuando empieces a vender de verdad.
- **Seguridad:**
  - El programa del cliente **no lleva tu API key**; solo usa la API pública de licencias.
  - `TIENDA_ID` / `PRODUCTOS_ID` impiden que funcionen claves de otras tiendas de Lemon Squeezy.
  - Python se puede descompilar: compila tu programa con **Nuitka** para que sea mucho más difícil
    quitar la verificación.
  - Si tu API key se compartió en algún chat o documento, **bórrala y crea otra** en
    Settings → API, y pega la nueva en ⚙ Configuración.

## Probar sin internet

```
pip install pyside6
python -m unittest discover -s licencias/pruebas -v
```

Las pruebas levantan `simulador_lemonsqueezy.py` (un Lemon Squeezy falso en tu PC) y comprueban
activar, validar, desactivar, límite de equipos, bloqueo, vencimiento, modo sin conexión,
claves de otra tienda, enlaces de compra y el panel completo.
