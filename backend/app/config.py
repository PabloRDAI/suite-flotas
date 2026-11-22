"""Configuración de la aplicación.

Los valores se leen de variables de entorno o del archivo `.env` de la raíz del
repositorio (nunca se escriben en el código). Si falta alguno obligatorio, la
aplicación no arranca y lo dice claramente.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] = raíz del repositorio (suite-flotas/)
RAIZ_REPO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_REPO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # el .env tiene más variables (POSTGRES_*) que no usamos aquí
    )

    # Cadena de conexión a PostgreSQL, p. ej.:
    # postgresql+psycopg://usuario:contraseña@localhost:5432/basedatos
    database_url: str

    # Segundos máximos para ABRIR una conexión con PostgreSQL. Sin este límite,
    # si la BD está parada la petición puede quedarse colgada más de un minuto.
    db_connect_timeout: int = 3

    # Clave para firmar los tokens de sesión (JWT). Quien la conozca puede
    # fabricar tokens válidos: larga, aleatoria y solo en el .env.
    # Generar una:  python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secreto: str = Field(min_length=32)
    # Minutos que dura una sesión antes de tener que volver a hacer login.
    jwt_minutos: int = 480

    # Carpeta donde se guardan los archivos subidos (fotos de averías). Está en
    # .gitignore: son datos, no código. En producción, un disco persistente.
    carpeta_adjuntos: Path = RAIZ_REPO / "uploads"
    # Tamaño máximo de una foto (MB).
    max_foto_mb: int = 5

    # Carpeta con el frontend ya compilado (npm run build). Solo la usa app/servidor.py, el
    # servidor de la imagen Docker; en desarrollo la web la sirve Vite.
    carpeta_web: Path = RAIZ_REPO / "frontend" / "dist"

    nombre_app: str = "Suite Flotas API"


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración (se lee una sola vez y se reutiliza)."""
    return Settings()
