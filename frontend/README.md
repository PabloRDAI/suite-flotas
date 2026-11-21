# Frontend

Aplicación web con **React + TypeScript** y **Vite**.

## Estructura

```
frontend/
├── public/            Archivos que se sirven tal cual (favicon)
├── src/
│   ├── main.tsx       Punto de entrada: monta <App /> en index.html
│   ├── App.tsx        Pantalla principal (estado del sistema)
│   ├── api.ts         Llamadas a la API del backend
│   ├── App.css        Estilos de la pantalla
│   └── index.css      Estilos globales y colores (modo claro/oscuro)
├── index.html         Única página HTML; React pinta dentro de <div id="root">
├── vite.config.ts     Configuración de Vite (incluye el proxy /api -> backend)
└── package.json       Dependencias y scripts
```

## Puesta en marcha

Requisitos: Node.js 20+ y el backend arrancado en http://127.0.0.1:8000
(ver [`backend/README.md`](../backend/README.md)).

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

El frontend llama a rutas que empiezan por `/api` (p. ej. `/api/salud`). En desarrollo,
el proxy de Vite las reenvía a FastAPI quitando el prefijo (`/api/salud` → `http://127.0.0.1:8000/salud`).
Así navegador y API comparten origen y no hace falta configurar CORS.
