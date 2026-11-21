# Backend

API REST con **FastAPI**, **SQLAlchemy** y **Alembic** sobre PostgreSQL, tests con **pytest**.

## Estructura

```
backend/
├── app/
│   ├── config.py      Configuración leída del .env (DATABASE_URL, JWT_SECRETO…)
│   ├── db.py          Conexión a PostgreSQL: engine, sesiones, Base y convención de nombres
│   ├── main.py        Aplicación FastAPI: registra los routers
│   ├── seguridad.py   Hash de contraseñas (Argon2) y tokens de sesión (JWT)
│   ├── deps.py        Dependencias: usuario actual (401) y control de roles (403)
│   ├── schemas.py     Esquemas Pydantic: lo que entra y sale por la API
│   ├── routers/       Endpoints agrupados por área (auth, vehiculos…)
│   ├── scripts/       Comandos de línea (crear_admin)
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
.\.venv\Scripts\Activate.ps1      # PowerShell
.venv\Scripts\activate.bat        # CMD

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

Los tests necesitan PostgreSQL en marcha, pero **nunca usan tu base de datos de desarrollo**:
`tests/conftest.py` cambia la conexión a una base de datos aparte (`suite_flotas_test`, o la de
`TEST_DATABASE_URL` si la defines), la crea si no existe y le aplica las migraciones. Además,
cada test trabaja dentro de una transacción que se deshace al terminar (fixture `db`).

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

## Autenticación y permisos

1. **Crear la primera empresa y su administrador** (pide la contraseña sin mostrarla):

   ```powershell
   python -m app.scripts.crear_admin --empresa "Transportes Ficticios" --email admin@example.com --nombre "Ana Admin"
   ```

2. **Login:** `POST /auth/login` con `{"email": "...", "password": "..."}` → devuelve `access_token`.
3. **Usar el token:** en cada petición, cabecera `Authorization: Bearer <access_token>`.
   En `/docs`, pulsa **Authorize** y pega el token.

| Código | Significado |
|---|---|
| 401 | Sin token, token falso o caducado, o usuario desactivado |
| 403 | Usuario identificado, pero su rol no permite la acción |
| 404 | El recurso no existe **o es de otra empresa** (no se revela que existe) |

Reglas de diseño: todas las consultas filtran por `usuario.empresa_id` (GEN-01); el rol se comprueba
con la dependencia `requiere_roles(...)` (GEN-02); el usuario se relee de la BD en cada petición,
así que desactivarlo o cambiarle el rol surte efecto al momento.

## Endpoints

| Método | Ruta | Roles | Descripción |
|---|---|---|---|
| GET | `/salud` | público | 200 si la API y la BD funcionan; 503 si la BD no responde |
| POST | `/auth/login` | público | Email + contraseña → token de sesión |
| GET | `/auth/yo` | todos | Datos del usuario conectado |
| GET | `/centros` | todos | Centros activos de la empresa |
| POST | `/centros` | admin | Crear un centro (409 si el nombre ya existe) |
| GET | `/tipos-vehiculo` | todos | Tipos de vehículo activos de la empresa |
| POST | `/tipos-vehiculo` | admin | Crear un tipo de vehículo (409 si el nombre ya existe) |
| GET | `/vehiculos` | todos | Vehículos de la empresa; filtros `centro_id`, `tipo_id`, `incluir_bajas` |
| POST | `/vehiculos` | admin, tráfico | Alta (409 si la matrícula ya existe en la empresa) |
| GET | `/vehiculos/{id}` | todos | Ficha del vehículo (también si está dado de baja) |
| PATCH | `/vehiculos/{id}` | admin, tráfico | Edición parcial (no estado, km ni activo) |
| DELETE | `/vehiculos/{id}` | admin, tráfico | Baja lógica del vehículo |

La matrícula se normaliza al guardar (`"1234 abc"`, `"1234-ABC"` → `"1234ABC"`), así que la regla
de unicidad no se puede saltar escribiéndola de otra forma. Una matrícula dada de baja sigue ocupada.
