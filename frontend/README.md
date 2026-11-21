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
│                       HistorialAsignaciones, AsignarConductor y BotonRealizado
├── pantallas/          Login, Panel, Vehiculos, FichaVehiculo, Personal, FichaPersona, Taller, EstadoSistema
└── util/formato.ts     Fechas, km y números en español
```

## Pantallas

| URL | Pantalla |
|---|---|
| `/login` | Inicio de sesión |
| `/panel` | Panel de flota (inicio): contadores por estado que filtran la tabla, alertas (documentación y preventivos) y aptitud de cada vehículo |
| `/vehiculos` | Listado con búsqueda y filtros por centro, tipo, estado e incluir bajas |
| `/vehiculos/:id` | Ficha: aptitud para salir, conductor/a habitual y pestañas de datos, documentación (semáforo), asignaciones (historial, asignar y finalizar), mantenimiento (planes preventivos y su situación) y km (con formulario de lectura) |
| `/personal` | Listado del personal con semáforo de documentación y filtros por puesto, centro y documentación |
| `/personal/:id` | Ficha: aviso de documentación y pestañas de datos, documentación y vehículos asignados |
| `/taller` | Previsión de preventivos por urgencia, con filtros y "Registrar realizado" (gerente y taller) |
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
