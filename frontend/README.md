# Frontend

Aplicación web con **React + TypeScript** y **Vite**, componentes de **Mantine**, navegación con
**React Router** y datos con **TanStack Query** (decisión en
[`docs/adr/0001`](../docs/adr/0001-libreria-de-componentes-frontend.md)).

## Estructura

```
frontend/src/
├── main.tsx            Arranque: proveedores (Mantine, TanStack Query, Router, sesión)
├── App.tsx             Rutas: qué pantalla corresponde a cada URL (carga diferida)
├── api/
│   ├── cliente.ts      Cliente HTTP: token, errores (ErrorApi) y sesión caducada (401)
│   ├── consultas.ts    Hooks de datos (useVehiculos, useVehiculo, useRegistrarLectura…)
│   ├── tipos.ts        Tipos de lo que devuelve la API (reflejo de backend/app/schemas.py)
│   └── salud.ts        Comprobación pública de /salud
├── auth/
│   ├── contexto.ts     Contexto de sesión y hook useSesion()
│   ├── permisos.ts     Qué botones ve cada rol (reflejo de los permisos de la API)
│   └── sesion.tsx      ProveedorSesion (login/logout) y RequiereSesion (rutas protegidas)
├── componentes/        Layout, indicadores (semáforo, estado), carga/error, Documentacion,
│                       HistorialAsignaciones, AsignarConductor, BotonRealizado, BotonCrearOTPlan
│                       IndicadoresMantenimiento (cifras, barra de reparto y tabla de costes)
│                       BotonExportar (descarga el Excel de un listado con sus filtros)
│                       y BotonImportar (plantilla, subida y tabla de errores por fila)
├── pantallas/          Inicio (según el rol), Login, Panel, Vehiculos, FichaVehiculo, Personal, FichaPersona,
│                       Taller, OrdenTrabajo, Recambios, Averias, ComunicarAveria, EstadoSistema
└── util/formato.ts     Fechas, km y números en español
```

## Pantallas

Vehículos, Personal, Averías, Recambios, el tablero y la previsión del Taller y la tabla de costes del
Panel tienen un botón **Exportar a Excel** que descarga lo que se ve, con los filtros aplicados (GEN-06).
Vehículos y Personal tienen además **Importar** (gerente y tráfico, GEN-05): descarga de la plantilla,
subida del Excel o CSV y, si hay errores, la lista de filas con su motivo (no se importa nada a medias).

| URL | Pantalla |
|---|---|
| `/login` | Inicio de sesión |
| `/` | Inicio según el rol: el conductor va a comunicar avería; el resto, al panel |
| `/panel` | Panel de flota (inicio): contadores por estado que filtran la tabla, alertas (documentación y preventivos), aptitud de cada vehículo e indicadores de mantenimiento de los últimos 6 meses (coste, €/km, averías, días parado, reparto preventivo/correctivo y tabla por vehículo, MAN-08) |
| `/vehiculos` | Listado con búsqueda y filtros por centro, tipo, estado e incluir bajas |
| `/vehiculos/:id` | Ficha: aptitud para salir, conductor/a habitual y pestañas de datos, documentación (semáforo), asignaciones (historial, asignar y finalizar), mantenimiento (planes preventivos, "Crear OT" e historial de OT con costes, MAN-07) y km (con formulario de lectura) |
| `/personal` | Listado del personal con semáforo de documentación y filtros por puesto, centro y documentación |
| `/personal/:id` | Ficha: aviso de documentación y pestañas de datos, documentación y vehículos asignados |
| `/taller` | Tablero de OT por estado (abiertas, en curso, cerradas en 30 días) con "Nueva OT", y previsión de preventivos con "Crear OT" y "Registrar realizado" |
| `/ordenes-trabajo/:id` | Orden de trabajo: datos, acciones según el estado (iniciar, cerrar con km y fecha, cancelar) y líneas de coste; al elegir un recambio del catálogo se rellenan su descripción y su precio |
| `/recambios` | Catálogo de recambios con búsqueda; alta, edición y baja para gerente y taller (MAN-09) |
| `/averias/nueva` | Comunicar avería, pensada para el móvil: vehículo preseleccionado, gravedad con botones grandes, foto con la cámara |
| `/averias` | Averías abiertas o todas, con foto, "Crear OT" / "Ver OT" y "Resolver sin OT" (gerente y taller) |
| `/sistema` | Estado de la API y la base de datos |

## Puesta en marcha

Requisitos: Node.js 20+ y el backend arrancado en http://127.0.0.1:8000
(ver [`backend/README.md`](../backend/README.md)). Para tener datos, crea la empresa demo
(`python -m app.scripts.demo` en `backend/`) y entra con `trafico@demo.example.com` / `demostracion`.

```powershell
cd frontend
npm install        # solo la primera vez (o cuando cambie package.json)
npm run dev        # arranca en http://localhost:5173
```

## Scripts

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo con recarga instantánea |
| `npm run lint` | Revisa el código con oxlint |
| `npm run build` | Comprueba los tipos (TypeScript) y genera la versión optimizada en `dist/` |
| `npm run preview` | Sirve la versión de `dist/` para probarla |

## Cómo habla con el backend

El frontend llama a rutas que empiezan por `/api` (p. ej. `/api/vehiculos`). En desarrollo,
el proxy de Vite las reenvía a FastAPI quitando el prefijo. El token de sesión se guarda en
`localStorage` y se envía en la cabecera `Authorization: Bearer …`; si la API responde 401,
la sesión se cierra y se vuelve al login.

## Accesibilidad y móvil

- Los estados y semáforos llevan siempre **icono y texto**, no solo color.
- En pantallas estrechas el menú se recoge (botón ☰) y las tablas se desplazan en horizontal.
- El modo oscuro sigue la preferencia del sistema operativo.
