#!/bin/sh
# Arranque del contenedor: migraciones, empresa demo (si falta) y servidor.
set -e

# Clave de las sesiones: si no se indica, se genera una aleatoria en cada arranque
# (las sesiones abiertas caducan al reiniciar; para una demo es suficiente).
if [ -z "$JWT_SECRETO" ]; then
    JWT_SECRETO="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    export JWT_SECRETO
    echo "JWT_SECRETO no indicado: se usa uno aleatorio (las sesiones caducan al reiniciar)."
fi

echo "Aplicando migraciones de la base de datos..."
alembic upgrade head

if [ "${CREAR_DEMO:-si}" = "si" ]; then
    python -m app.scripts.demo --si-no-existe
fi

# PORT: el puerto que indique la plataforma (Render lo fija así); si no, 8000.
exec uvicorn app.servidor:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
