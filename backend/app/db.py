"""Conexión a PostgreSQL y creación del esquema."""

from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import database_url

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect() -> psycopg.Connection:
    """Abre una conexión nueva (una por request / por carga).

    Para el tamaño de esta prueba una conexión por request es suficiente y deja
    el código más simple de explicar que un pool.
    """
    return psycopg.connect(database_url(), row_factory=dict_row)


def ensure_schema(conn: psycopg.Connection) -> None:
    """Aplica el DDL idempotente de ``schema.sql``."""
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
