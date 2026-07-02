# PRD — Cinema Productions: Gestión de Reservas de Eventos

## Problema Original
Crear un programa para gestionar reserva de eventos. Un cliente da un anticipo para una fecha. Búsqueda por mes/año en el calendario. Configuración de base de datos dinámica. Recordatorios (Email/WhatsApp). Paquete instalable/portable local. Notificaciones de sistema (Windows) y gráficos de barras en calendario/dashboard.

## Usuario Objetivo
Empresas de producción de eventos (ej. Cinema Productions) que gestionan reservas, pagos anticipados y comunicación con clientes.

---

## Arquitectura
- **Frontend**: React + TailwindCSS + Framer Motion + Shadcn UI
- **Backend**: FastAPI (Python)
- **Base de Datos**: MongoDB (Motor async)
- **Contexto Global**: SettingsContext.jsx (tema, idioma, apariencia, etc.)

### Estructura de archivos clave:
```
/app/
├── backend/
│   ├── server.py             # FastAPI principal (web)
│   └── standalone_app.py     # FastAPI embebido en el ZIP (app local de escritorio)
├── frontend/src/
│   ├── components/
│   │   └── Layout.jsx     # Sidebar (Dashboard, Reservaciones, Calendario, Socios, Base de Datos, Apariencia, Ajustes)
│   ├── context/
│   │   └── SettingsContext.jsx   # Estado global de apariencia + 6 nuevos estados
│   ├── pages/
│   │   ├── Dashboard.jsx
│   │   ├── Reservations.jsx
│   │   ├── CalendarView.jsx
│   │   ├── Socios.jsx
│   │   ├── DatabasePage.jsx
│   │   ├── AppearancePage.jsx   ← (9 secciones de apariencia)
│   │   └── Settings.jsx         ← Solo: idioma, moneda, notif, negocio, escritorio, publicar
│   ├── App.js             # Router con /apariencia route + pageTransition dinámico
│   └── index.css          # Variables CSS dinámicas + nuevos data attributes
```

---

## Funcionalidades Implementadas ✅

### Core
- Gestión de reservas (CRUD) con anticipo, balance, fecha de evento
- Calendario mensual con filtros y visualización
- Dashboard con estadísticas y gráficos
- Gestión de Socios (equipo)

### Apariencia (AppearancePage.jsx — 9 secciones)
- **Paleta de Colores**: 6 temas de acento + color hex personalizado + presets de diseño (Glass Aurora, Crystal, Minimal) + saturación
- **Tipografía e Iconos**: 8 familias de fuente + 3 tamaños de texto + tamaño de iconos
- **Animaciones y Movimiento**: Toggle de animaciones + velocidad (lento/normal/rápido/instante) + transición de páginas (fade/slide/zoom/ninguna) + efecto hover
- **Formas y Bordes**: 3 estilos de borde + 5 estilos de tarjeta + 3 estilos de botón + 4 sombras
- **Fondo y Colores**: Modo oscuro + intensidad de fondo + intensidad del vidrio/blur + gradiente personalizado + imagen de fondo URL
- **Interfaz y Espacio**: Densidad del contenido + estilo de barra lateral + barra lateral compacta + ancho del contenido + scrollbar + formato de fecha
- **Tipos de Evento**: Personalizar icono y color de cada tipo
- **Diseño de PDF**: 3 temas + exportar PDF
- **Logo y Marca**: Logo sidebar + logo PDF separado

### Notificaciones Multi-canal (Settings.jsx)
- Email vía Resend
- Telegram Bot
- ntfy.sh
- Web Push (browser notifications)
- WhatsApp link automático

### Base de Datos (DatabasePage.jsx)
- JSON Backup/Restore
- Auto-backup a PC local
- CSV/Excel Import/Export
- Limpieza de base de datos
- Cambio dinámico de MongoDB URL

### Ajustes (Settings.jsx — solo no-apariencia)
- Idioma (ES/EN)
- Moneda (Q/$/€/₡)
- Config de negocio
- App de escritorio (descarga)
- Publicar en línea (guía de despliegue)

### Reservaciones (Reservations.jsx)
- Listado ordenado de fecha más cercana a más lejana
- Máximo 8 filas visibles con botón "Mostrar más (N restantes)"
- Filtro por Tipo de Evento, Estado, Paquete (Básico/Intermedio/Completo)
- Filtro por rango de fechas (Desde/Hasta) mediante botón "Más filtros"
- Botón "Limpiar" para resetear todos los filtros

### Calendario (CalendarView.jsx)
- Pastillas muestran siempre el Tipo de Evento (no el nombre del cliente)

### Dashboard (Dashboard.jsx)
- "Próximas Reservas" muestra eventos del mes actual ordenados de fecha más cercana a más lejana
- 5 estilos visuales: Línea, Línea Paquete, Tarjeta, Compacto, Banda

---

## Schema DB Principal

### `app_settings` (MongoDB)
Contiene claves de apariencia + configuración de negocio:
- `theme, preset, animations, radius, pdfTheme`
- `darkMode, fontScale, bgIntensity, sidebarCompact, dateFormat`
- `fontFamily, cardStyle, animSpeed, shadowDepth, pageWidth, btnCorner, scrollbar`
- `customBgEnabled, bgColor1, bgColor2, customAccent, saturation, hoverEffect`
- `glassBlur, layoutDensity, pageTransition, iconSize, sidebarStyle, bgImage` (NUEVOS)
- `eventConfigs, logoUrl, pdfLogoUrl, logoSize, usePdfLogo, useCustomPdfLogo`
- Notificaciones, config negocio, etc.

---

## Rutas API clave
- `GET/POST /api/settings`
- `GET/POST /api/reservations`
- `GET/POST /api/socios`
- `GET /api/db/stats`, `POST /api/db/switch`, `POST /api/db/reset`
- `GET /api/db/export-json`, `POST /api/db/restore`
- `GET /api/db/export-csv`, `POST /api/db/import-csv`
- `GET /api/db/export-xlsx`
- `POST /api/reminders/send-test`

---

## Integraciones de Terceros
- **Resend** — Emails de recordatorio (requiere API key del usuario)
- **Telegram Bot API** — Notificaciones Telegram (requiere token + chat ID)
- **ntfy.sh** — Push notifications (requiere topic name)

---

## Roadmap / Backlog

### P1 — Próximos
- WhatsApp automático vía Twilio

### P2 — Futuro
- Portal para clientes con link único
- Integración de pagos online Stripe/Wompi
- Función de "Temas guardados" en Apariencia

---

## Changelog (resumido)
- 2025: MVP inicial — Reservas, Calendario, Dashboard, Socios
- 2025: Notificaciones multi-canal (Resend, Telegram, ntfy, Web Push)
- 2025: Base de datos avanzada (backup, restore, import, export)
- 2025: 13+ opciones de apariencia en Settings.jsx
- 2026-04-15: **Migración a AppearancePage.jsx** + 6 nuevas funciones
- 2026: **Limpieza de Settings.jsx** — Eliminadas secciones redundantes
- 2026: **Títulos del Sitio** en Apariencia
- 2026: **Campos de Formulario** en Apariencia — Toggles para activar/desactivar campos
- 2026-04-20: **3 mejoras formulario/dashboard**
- 2026-04-16: **Fix real_income=0 en app local**
- 2026-04-21: **Fix Bug Crítico Backup/Restore**
- 2026-04-21: **Limpieza y unificación de Base de Datos**; Socios drag-and-drop
- 2026-04-21: **Widgets configurables del Dashboard**
- 2026-04-21: **Dashboard Próximas Reservas mejorado**
- 2026-04-22: **5 estilos visuales Dashboard** + campo Paquete (Básico/Intermedio/Completo)
- 2026-04-22: **Socios: Panel asignar evento** con toggle Pendiente↔Pagado
- 2026-04-22: **Reservaciones mejoradas**: paginación 8+mostrar más, filtros extra (paquete, rango fechas), orden fecha más cercana. **Calendario**: pastillas siempre muestran tipo de evento.
- 2026-07-02: **Base de Datos mejorada**: (1) Sección "Actualizaciones guardadas" — lista de versiones almacenadas en la DB con versión, canal, tamaño, fecha y botón eliminar. (2) 3 modos de conexión: URL completa | Por IP/campos (host+puerto+user+pass+db auto-genera la URL) | NAS/Red local (igual con UI específica para NAS). (3) 4 opciones toggle: auto-probar antes de conectar, notificar al cambiar, mostrar URL completa, comprimir respaldos.
