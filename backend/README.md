# Backend

API REST con **FastAPI**, **SQLAlchemy** y **Alembic** sobre PostgreSQL, tests con **pytest**.

## Estructura

```
backend/
├── app/
│   ├── config.py      Configuración leída del .env (DATABASE_URL…)
│   ├── db.py          Conexión a PostgreSQL: engine, sesiones y Base de los modelos
│   └── main.py        Aplicación FastAPI y endpoints
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

`test_salud_ok_con_base_de_datos` necesita PostgreSQL en marcha.

## Migraciones (chuleta)

| Comando | Qué hace |
|---|---|
| `alembic upgrade head` | Aplica todas las migraciones pendientes |
| `alembic downgrade -1` | Deshace la última migración |
| `alembic current` | Muestra en qué migración está la BD |
| `alembic history` | Lista todas las migraciones |
| `alembic revision --autogenerate -m "mensaje"` | Genera una migración comparando los modelos con la BD |

Revisa siempre a mano las migraciones generadas con `--autogenerate` antes de aplicarlas.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/salud` | 200 si la API y la BD funcionan; 503 si la BD no responde |
