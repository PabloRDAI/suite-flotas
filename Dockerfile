# Imagen completa de Suite Flotas: API (FastAPI) + web (React compilada) en un solo contenedor.
# La usan la demo local (docker-compose.demo.yml) y el despliegue (docs/adr/0002).
#
# Dos etapas: la primera compila el frontend con Node; la segunda solo lleva Python y el
# resultado de la compilación (Node no llega a la imagen final, que así es más pequeña).

# --- Etapa 1: compilar el frontend -------------------------------------------
FROM node:26-alpine AS web
WORKDIR /web
# Primero solo las dependencias: si no cambian, Docker reutiliza esta capa y no las reinstala.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Etapa 2: la aplicación ---------------------------------------------------
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CARPETA_WEB=/app/web \
    CARPETA_ADJUNTOS=/app/uploads
WORKDIR /app/backend

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY --from=web /web/dist /app/web
COPY docker/arranque.sh /usr/local/bin/arranque.sh

# Sin privilegios de administrador dentro del contenedor (buena práctica de seguridad).
RUN useradd --create-home --uid 10001 suite \
    && mkdir -p /app/uploads && chown suite /app/uploads \
    && chmod +x /usr/local/bin/arranque.sh
USER suite

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/salud', timeout=4)"
CMD ["arranque.sh"]
