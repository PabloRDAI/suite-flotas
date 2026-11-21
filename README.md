# Suite Flotas

[![CI](https://github.com/PabloRDAI/suite-flotas/actions/workflows/ci.yml/badge.svg)](https://github.com/PabloRDAI/suite-flotas/actions/workflows/ci.yml)

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
├── .github/workflows/  Integración continua (GitHub Actions)
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

Después, en dos terminales:

1. **API:** sigue [`backend/README.md`](backend/README.md) → http://127.0.0.1:8000/salud
2. **Web:** sigue [`frontend/README.md`](frontend/README.md) → http://localhost:5173

Para tener datos con los que probar, crea la empresa de demostración (todo ficticio):

```bash
cd backend
python -m app.scripts.demo     # usuarios admin|trafico|taller|conductor@demo.example.com, contraseña "demostracion"
```

## Integración continua

En cada `push` a `main`, GitHub Actions ([`ci.yml`](.github/workflows/ci.yml)) ejecuta los tests del
backend contra un PostgreSQL temporal, y el linter y la compilación del frontend.

## Plan de entrega

| Fase | Contenido | Estado |
|---|---|---|
| F0 Andamiaje | Repositorio, Docker con PostgreSQL, FastAPI, React e integración continua | ✅ Hecha |
| F1 Flota | Multiempresa, roles, vehículos, km, vencimientos, panel de flota | ✅ Hecha |
| F2 Personal | Personas, vencimientos personales, asignaciones | ⏳ |
| F3 GMAO | Planes preventivos, averías, órdenes de trabajo, costes | ⏳ |
| F4 Pulido | Importar/exportar Excel, despliegue de la demo | ⏳ |

## Licencia

[MIT](LICENSE)
