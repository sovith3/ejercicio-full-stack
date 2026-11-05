"""Configuración leída del entorno (sin valores mágicos repartidos por el código)."""

from __future__ import annotations

import os
from pathlib import Path

#: Raíz del repositorio (backend/app/config.py -> backend/app -> backend -> raíz).
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Carpeta servida como interfaz web.
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR") or (REPO_ROOT / "frontend"))

#: Zona horaria de negocio: define los "días" y el formato de salida de la API.
TIMEZONE = "America/Santiago"

#: Corte entre sesiones de un mismo dispositivo.
SESSION_GAP_MINUTES = 10


def database_url() -> str:
    """DSN de PostgreSQL.

    Prioriza ``DATABASE_URL`` (cómodo para tests o para una base externa) y, si
    no existe, arma el DSN con las variables que ya usa ``docker-compose.yml``.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("POSTGRES_USER", "app")
    password = os.getenv("POSTGRES_PASSWORD", "cambiar-esto")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    name = os.getenv("POSTGRES_DB", "lecturas")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"
