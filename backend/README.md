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
│   ├── reglas/        Motor de reglas en Python puro (sin BD): estado_vehiculo.py (FLO-03),
│   │                  km.py (FLO-05), vencimientos.py (FLO-06/07)
│   ├── servicios/     Unen las reglas con la BD (p. ej. actualizar_estado del vehículo)
│   ├── routers/       Endpoints agrupados por área (auth, vehiculos, lecturas_km…)
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
pytest                       # todos los tests
pytest --cov                 # con informe de cobertura (líneas sin probar en "Missing")
coverage report --include="app/reglas/*" --fail-under=90   # el motor debe estar ≥ 90 % (CI lo exige)
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

## Datos de demostración (GEN-04)

```powershell
python -m app.scripts.demo              # crea "Transportes Demo (ficticia)"
python -m app.scripts.demo --reiniciar  # la borra y la vuelve a crear (solo la demo)
```

Crea 2 centros, 5 tipos de vehículo, 25 vehículos con ~6 meses de lecturas de km semanales,
tipos de vencimiento de vehículo y de persona, y vencimientos con casos en rojo (2 vehículos
no aptos) y en ámbar. Usuarios `admin`, `trafico`, `taller` y `conductor` `@demo.example.com`
con la contraseña `demostracion`. Todo es inventado; los datos son siempre los mismos (semilla
fija) y las fechas se calculan desde el día en que se ejecuta. Personas e historial de
mantenimiento se añadirán cuando existan sus tablas.

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
| GET | `/panel` | todos | Panel de flota: contadores, vehículos con aptitud y alertas (filtros `centro_id`, `tipo_id`) |
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
| GET | `/vehiculos/{id}/km` | todos | Historial de lecturas de km (de la más reciente a la más antigua) |
| POST | `/vehiculos/{id}/km` | todos | Registrar una lectura `{"km": …, "fecha": opcional}` |
| DELETE | `/vehiculos/{id}/km/{lectura_id}` | admin, tráfico | Borrar una lectura errónea (no la única) |
| GET | `/tipos-vencimiento` | todos | Tipos de vencimiento (filtro `aplica_a=vehiculo` o `persona`) |
| POST | `/tipos-vencimiento` | admin | Crear un tipo con sus días de aviso y si bloquea la salida |
| GET | `/vehiculos/{id}/vencimientos` | todos | Documentos con semáforo, días restantes y si son el vigente |
| POST | `/vehiculos/{id}/vencimientos` | admin, tráfico | Registrar un documento o su renovación |
| DELETE | `/vehiculos/{id}/vencimientos/{venc_id}` | admin, tráfico | Borrar un vencimiento registrado por error |
| GET | `/vehiculos/{id}/aptitud` | todos | ¿Apto para salir? Con motivos y el peor semáforo |

La matrícula se normaliza al guardar (`"1234 abc"`, `"1234-ABC"` → `"1234ABC"`), así que la regla
de unicidad no se puede saltar escribiéndola de otra forma. Una matrícula dada de baja sigue ocupada.

**Lecturas de km (FLO-05):** una lectura debe encajar entre sus vecinas en el tiempo
(≥ la anterior y ≤ la posterior, si es de una fecha pasada) y no puede ser de una fecha futura.
`km_actuales` es siempre el de la última lectura; el alta del vehículo crea la lectura inicial.
La regla vive en `app/reglas/km.py` y se prueba sin base de datos (`tests/test_reglas_km.py`).

**Vencimientos (FLO-06, FLO-07):** semáforo rojo si ya caducó, ámbar si quedan ≤ `dias_aviso`
del tipo (un documento que caduca hoy es ámbar) y verde en otro caso. Al renovar se registra un
vencimiento nuevo: de cada tipo solo cuenta el que caduca más tarde (el vigente). Un vehículo
es apto para salir si está activo, operativo y sin documentos vigentes caducados de tipos que
bloquean la salida. Reglas en `app/reglas/vencimientos.py`.

**Panel de flota (FLO-04):** `GET /panel` calcula contadores, tabla y alertas sobre la misma lista de
vehículos activos (los totales coinciden con el listado filtrado) con solo dos consultas a la BD;
un test comprueba que responde en menos de 1 s con 150 vehículos.

**Estado del vehículo (FLO-03, regla 1):** de baja si está inactivo; en taller si tiene una OT
abierta que inmoviliza; inmovilizado si tiene una avería "inmoviliza" sin OT abierta; si no,
operativo. El estado nunca se asigna a mano: lo calcula `app/reglas/estado_vehiculo.py` y lo
guarda `app/servicios/estado_vehiculo.py::actualizar_estado()`, que hay que llamar tras cualquier
cambio que pueda alterarlo (baja, y en el futuro OT y averías).
