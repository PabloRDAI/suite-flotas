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
│   │                  km.py (FLO-05), vencimientos.py (FLO-06/07), asignaciones.py (PER-03/04),
│   │                  preventivo.py (MAN-01/02), ordenes.py (MAN-05/06),
│   │                  indicadores.py (MAN-08)
│   ├── servicios/     Unen las reglas con la BD (estado del vehículo, preventivos, demo…)
│   │                  y adjuntos.py: guardar y servir fotos con seguridad
│   ├── routers/       Endpoints agrupados por área (auth, vehiculos, lecturas_km…)
│   ├── scripts/       Comandos de línea (crear_admin)
│   └── models/        Modelos (tablas): empresa, centro, usuario, vehículos, lecturas de km,
│                      vencimientos, personas, asignaciones y planes de mantenimiento
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

Crea 2 centros, 5 tipos de vehículo, 25 vehículos con ~6 meses de lecturas de km semanales
(km iniciales coherentes con la antigüedad), tipos de vencimiento de vehículo y de persona,
vencimientos con casos en rojo (2 vehículos no aptos) y en ámbar, y 30 personas (20 conductores,
5 mecánicos, 3 de tráfico y 2 de otros puestos) con su documentación, también con casos en rojo y ámbar, y 27 asignaciones
conductor-vehículo con historial y un aviso de documentación caducada, y 9 planes preventivos
con 2 vencidos (uno por km y otro por fecha) y 2 próximos, 4 averías (una que inmoviliza) y 6 meses de historial de órdenes de trabajo (preventivas y
correctivas con costes), con una OT en curso que deja un vehículo en taller. Usuarios `admin`, `trafico`, `taller` y `conductor` `@demo.example.com`
con la contraseña `demostracion`. Todo es inventado; los datos son siempre los mismos (semilla
fija) y las fechas se calculan desde el día en que se ejecuta. El historial de mantenimiento se
añadirá cuando existan sus tablas.

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
| GET | `/panel` | todos | Panel de flota: contadores, vehículos con aptitud y alertas de averías, documentación y preventivos (filtros `centro_id`, `tipo_id`) |
| GET | `/panel/indicadores` | todos | Indicadores de mantenimiento (MAN-08) del periodo `desde`–`hasta` (por defecto, los últimos 6 meses): coste total y por vehículo, coste por km, averías, días de inmovilización y % de preventivo (filtros `centro_id`, `tipo_id`) |
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
| GET | `/personas` | todos | Personal con el semáforo de su documentación; filtros `centro_id`, `puesto`, `incluir_bajas` |
| POST | `/personas` | admin, tráfico | Alta (solo datos mínimos: sin DNI ni datos bancarios) |
| GET | `/personas/{id}` | todos | Ficha de la persona (también si está de baja) |
| PATCH | `/personas/{id}` | admin, tráfico | Edición parcial; `usuario_id` enlaza o desenlaza su usuario |
| DELETE | `/personas/{id}` | admin, tráfico | Baja lógica con fecha de baja |
| GET/POST | `/personas/{id}/vencimientos` | todos / admin, tráfico | Documentos de la persona (permiso, CAP…) con semáforo |
| DELETE | `/personas/{id}/vencimientos/{venc_id}` | admin, tráfico | Borrar un vencimiento registrado por error |
| GET | `/vehiculos/{id}/asignaciones` | todos | Historial de conductores del vehículo, con avisos |
| GET | `/personas/{id}/asignaciones` | todos | Historial de vehículos de la persona, con avisos |
| POST | `/asignaciones` | admin, tráfico | Asignar conductor/a (habitual o temporal); 409 si hay otro habitual en esas fechas |
| POST | `/asignaciones/{id}/finalizar` | admin, tráfico | Poner fecha de fin (por defecto, ayer) |
| DELETE | `/asignaciones/{id}` | admin, tráfico | Borrar una asignación registrada por error |
| GET | `/planes` | todos | Planes preventivos con sus tareas (filtro `tipo_vehiculo_id`) |
| POST | `/planes` | admin, taller | Crear un plan (km, días o ambos); los vehículos de ese tipo empiezan a contar desde hoy |
| GET/PATCH/DELETE | `/planes/{id}` | todos / admin, taller | Ver, editar (recalcula los próximos) o dar de baja |
| GET | `/vehiculos/{id}/preventivos` | todos | Situación de cada plan en el vehículo (vencidos primero) |
| GET | `/averias/vehiculos-sugeridos` | todos | Vehículos asignados al usuario (para preseleccionar) |
| POST | `/averias` | todos | Comunicar avería (multipart: `vehiculo_id`, `descripcion`, `gravedad`, `foto` opcional) |
| GET | `/averias` | todos | Averías (abiertas por defecto; `abiertas=false`, `vehiculo_id`, `gravedad`) |
| GET | `/averias/{id}` y `/averias/{id}/foto` | todos | Una avería y su foto (solo de la propia empresa) |
| POST | `/averias/{id}/resolver` | admin, taller | Resolver sin OT, con nota (409 si tiene una OT abierta: se resuelve al cerrarla) |
| GET | `/ordenes-trabajo` | todos | OT (filtros `abiertas`, `estado`, `tipo`, `vehiculo_id`, `cerradas_desde`), con líneas y coste |
| GET | `/vehiculos/{id}/historial` | todos | Historial de mantenimiento (MAN-07): todas sus OT con fecha, tipo, km y coste, y resumen |
| POST | `/ordenes-trabajo` | admin, taller | Crear desde una avería (`averia_id`), desde un plan (`plan_id` + `vehiculo_id`) o a mano |
| GET/PATCH | `/ordenes-trabajo/{id}` | todos / admin, taller | Ver o editar (descripción, inmoviliza, responsable) |
| POST | `/ordenes-trabajo/{id}/iniciar`, `/cerrar`, `/cancelar` | admin, taller | Flujo abierta → en curso → cerrada (con `km` y `fecha`) o cancelada |
| POST/DELETE | `/ordenes-trabajo/{id}/lineas` | admin, taller | Líneas de coste: mano de obra, recambio o externo |
| GET | `/preventivos/prevision` | todos | Previsión (MAN-02): vencidos y lo que toca en 30 días o 2.000 km, por urgencia (filtros `centro_id`, `tipo_id`) |
| POST | `/vehiculos/{id}/preventivos/{plan_id}/realizado` | admin, taller | Registrar que se hizo (fecha y km) y recalcular |

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
bloquean la salida. Reglas en `app/reglas/vencimientos.py`. Los vencimientos de personas (PER-02)
usan la misma tabla, el mismo servicio (`app/servicios/vencimientos.py`) y las mismas reglas; un
`CHECK` garantiza que cada vencimiento es de un vehículo o de una persona, nunca de ambos.

**Panel de flota (FLO-04):** `GET /panel` calcula contadores, tabla y alertas sobre la misma lista de
vehículos activos (los totales coinciden con el listado filtrado) con solo dos consultas a la BD;
un test comprueba que responde en menos de 1 s con 150 vehículos.

**Indicadores de mantenimiento (MAN-08):** `GET /panel/indicadores`, sobre los vehículos activos.
Coste = líneas de las OT **cerradas** en el periodo; km recorridos = última lectura hasta el fin
menos la última antes del inicio; días de inmovilización = días **distintos** en que el vehículo
estuvo parado por una avería o una OT que inmoviliza (si se solapan, cuentan una vez); % preventivo,
por número de OT y por coste. Cálculos en `app/reglas/indicadores.py`. Los tests comprueban que
coinciden con un cálculo hecho a mano, por otro camino, sobre los datos de demostración.

**Asignaciones (PER-03, PER-04):** un vehículo tiene como máximo un conductor habitual a la vez
(las temporales pueden coincidir). Se comprueba en `app/reglas/asignaciones.py` y, como última
barrera, con una restricción de exclusión de PostgreSQL (`EXCLUDE USING gist … daterange(desde,
hasta, '[]') WITH &&`, extensión `btree_gist`). Las asignaciones no se borran al terminar: se
finalizan con fecha de fin, y así se conserva el historial. Si la documentación imprescindible del
conductor está caducada, la respuesta incluye `avisos`, pero la asignación se hace igualmente.

**Mantenimiento preventivo (MAN-01, regla 3):** cada plan es "cada X km o Y días (lo que llegue
antes)", por tipo de vehículo. Para cada vehículo se guarda el último realizado y se calcula el
próximo (`proxima_fecha = ultima_fecha + intervalo_dias`, `proximos_km = ultimos_km + intervalo_km`).
Vence cuando se alcanza la primera de las dos; está "próximo" si faltan ≤ 30 días o ≤ 2.000 km
(margen de MAN-02). Regla en `app/reglas/preventivo.py`; al crear un plan o un vehículo, se empieza
a contar desde hoy y sus km actuales, hasta que el taller registre la realización real.

**Previsión de preventivos (MAN-02):** `GET /preventivos/prevision` reúne los vencidos y los
próximos de toda la flota y los ordena por un índice de urgencia (`urgencia()` en el motor): la
fracción del margen que queda (días / 30 o km / 2.000, lo que llegue antes). Negativo = vencido,
cuanto más negativo más atrasado. Un test comprueba que la lista coincide con el cálculo directo
del motor. Los mismos preventivos aparecen como alertas del panel (rojo vencido, ámbar próximo);
un preventivo vencido avisa, pero no impide salir.

**Averías (MAN-03):** cualquier rol puede comunicarlas; una avería que "inmoviliza" deja el
vehículo inmovilizado en la misma petición (el motor de estado lee ahora las averías no resueltas)
y la respuesta trae el estado nuevo. Las fotos (JPEG, PNG o WebP, máx. 5 MB) se validan por su
firma de bytes, se guardan con nombre aleatorio en `CARPETA_ADJUNTOS` (por defecto `uploads/`,
fuera de Git) y solo se sirven con sesión y a la propia empresa.

**Órdenes de trabajo (MAN-04 a MAN-06):** desde una avería (que pasa a "en reparación" y, si
inmovilizaba, la OT también inmoviliza), desde un plan (preventiva) o a mano. Flujo abierta → en
curso → cerrada o cancelada (`app/reglas/ordenes.py`). Al cerrar se exigen km y fecha: los km se
registran como lectura (validada con FLO-05), la avería queda resuelta y, si es preventiva, el plan
recalcula el próximo. Cancelar devuelve la avería a "comunicada". Mientras una OT que inmoviliza
está abierta, el vehículo está "en taller". Coste = suma de las líneas (cantidad × precio), con
`Decimal` y redondeo a céntimos; la BD exige km y fecha en las OT cerradas.

**Estado del vehículo (FLO-03, regla 1):** de baja si está inactivo; en taller si tiene una OT
abierta que inmoviliza; inmovilizado si tiene una avería "inmoviliza" sin OT abierta; si no,
operativo. El estado nunca se asigna a mano: lo calcula `app/reglas/estado_vehiculo.py` y lo
guarda `app/servicios/estado_vehiculo.py::actualizar_estado()`, que hay que llamar tras cualquier
cambio que pueda alterarlo (baja, y en el futuro OT y averías).
