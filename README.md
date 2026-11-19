# Suite Flotas

Suite de gestión para operadores de transporte (viajeros y mercancías) con flotas pequeñas
(5-150 vehículos): **flota, personal y mantenimiento (GMAO básico)**.

> Proyecto personal. **Solo datos ficticios.**

## Qué resuelve

- Ver en una pantalla el estado de toda la flota (operativo, en taller, inmovilizado, de baja).
- Controlar el personal y los vencimientos de su documentación (permisos, CAP, tarjeta de tacógrafo…).
- Gestionar el mantenimiento: preventivos por km o por tiempo, averías y órdenes de trabajo con coste.

La especificación completa está en [`docs/especificacion.md`](docs/especificacion.md).

## Stack

| Parte | Tecnología |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy · Alembic · pytest |
| Frontend | React · TypeScript · Vite |
| Base de datos | PostgreSQL (en Docker) |
| CI | GitHub Actions |

## Estructura

```
suite-flotas/
├── backend/            API REST y motor de reglas (FastAPI)
├── frontend/           Aplicación web (React + TypeScript)
├── docs/               Especificación, decisiones (ADR) y capturas
├── docker-compose.yml  PostgreSQL para desarrollo
├── .env.example        Variables de entorno de ejemplo
└── LICENSE             Licencia MIT
```

## Puesta en marcha (desarrollo)

Requisitos: [Git](https://git-scm.com/), [Docker Desktop](https://www.docker.com/products/docker-desktop/),
Python 3.12+ y Node.js 20+.

```bash
# 1. Variables de entorno
cp .env.example .env

# 2. Base de datos
docker compose up -d
docker compose ps        # el servicio "db" debe aparecer como "healthy"
```

Las instrucciones del backend y del frontend se añadirán en las fases siguientes.

## Plan de entrega

| Fase | Contenido | Estado |
|---|---|---|
| F0 Andamiaje | Repositorio, Docker con PostgreSQL, FastAPI, React e integración continua | 🚧 En curso |
| F1 Flota | Multiempresa, roles, vehículos, km, vencimientos, panel de flota | ⏳ |
| F2 Personal | Personas, vencimientos personales, asignaciones | ⏳ |
| F3 GMAO | Planes preventivos, averías, órdenes de trabajo, costes | ⏳ |
| F4 Pulido | Importar/exportar Excel, despliegue de la demo | ⏳ |

## Licencia

[MIT](LICENSE)
