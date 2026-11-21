# Backend

API REST con **FastAPI**, **SQLAlchemy** y **Alembic** sobre PostgreSQL, tests con **pytest**.

## Estructura

```
backend/
├── app/
│   ├── config.py      Configuración leída del .env (DATABASE_URL…)
│   ├── db.py          Conexión a PostgreSQL: engine, sesiones, Base y convención de nombres
│   ├── main.py        Aplicación FastAPI y endpoints
│   └── models/        Modelos (tablas): empresa, centro, usuario, tipo_vehiculo, vehiculo
│       └── comun.py   Mixins reutilizables (empresa_id, fechas) y columnas de tipo enum
├── alembic/           Migraciones de la base de datos
│   ├── env.py         Conecta Alembic con app.config y app.db.Base
│   └── versions/      Un archivo por cada cambio del esquema
├── alembic.ini        Configuración de Alembic (sin contraseñas)
├── tests/             Tests con pytest
└── pyproject.toml     Dependencias y configuración de pytest
```

## Puesta en marcha

Requisitos: Python 3.12+ y la base de datos levantada (`docker compose up -d` en la raíz)
con el archivo `.env` creado a partir de `.env.example`.

```powershell
cd backend

# 1. Crear el entorno virtual e instalar dependencias (solo la primera vez)
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 2. Activar el entorno virtual (en cada terminal nueva)
.\.venv\Scripts\Activate.ps1

# 3. Aplicar las migraciones a la base de datos
alembic upgrade head

# 4. Arrancar la API en modo desarrollo (se recarga al guardar cambios)
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000/salud
- Documentación interactiva: http://127.0.0.1:8000/docs

> Si PowerShell no deja ejecutar `Activate.ps1`, ejecuta una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Tests

```powershell
pytest
```

Los tests que usan la base de datos necesitan PostgreSQL en marcha y las migraciones
aplicadas (`alembic upgrade head`). Cada test trabaja dentro de una transacción que se
deshace al terminar (fixture `db` en `tests/conftest.py`), así que no deja datos.

## Reglas que hace cumplir la base de datos

| Regla | Restricción |
|---|---|
| Toda tabla (salvo `empresa`) va ligada a una empresa — GEN-01 | `empresa_id NOT NULL` + FK |
| El centro y el tipo de un vehículo son de su misma empresa — GEN-01 | FK compuestas `(empresa_id, centro_id)` y `(empresa_id, tipo_id)` |
| Matrícula única dentro de la empresa — FLO-01 | `uq_vehiculo_empresa_id_matricula` |
| Nombre de centro y de tipo únicos dentro de la empresa | `uq_centro_empresa_id_nombre`, `uq_tipo_vehiculo_empresa_id_nombre` |
| Email de usuario único | `uq_usuario_email` |
| Estados, roles, combustibles… solo valores válidos | `CHECK` de cada columna enum |
| Km ≥ 0, año entre 1950 y 2100, capacidad > 0 | `ck_vehiculo_*` |

## Migraciones (chuleta)

| Comando | Qué hace |
|---|---|
| `alembic upgrade head` | Aplica todas las migraciones pendientes |
| `alembic downgrade -1` | Deshace la última migración |
| `alembic current` | Muestra en qué migración está la BD |
| `alembic history` | Lista todas las migraciones |
| `alembic revision --autogenerate -m "mensaje"` | Genera una migración comparando los modelos con la BD |
| `alembic check` | Falla si hay cambios en los modelos sin migración (lo ejecuta también CI) |

Revisa siempre a mano las migraciones generadas con `--autogenerate` antes de aplicarlas.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/salud` | 200 si la API y la BD funcionan; 503 si la BD no responde |
