"""Comando de carga: ``python -m app.load <ruta.csv>``.

Idempotente por contenido de archivo (sha256): si el mismo archivo ya se cargó,
no se vuelve a aplicar. Dentro de un archivo gana la última fila y, entre
archivos, gana el que llegó después (orden de ``loads.id``).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from psycopg.types.json import Json

from .db import connect, ensure_schema
from .normalize import InvalidRow, REQUIRED_COLUMNS, Reading, parse_row

UPSERT_SQL = """
INSERT INTO readings (device_id, recorded_at, value, lat, lon, load_id)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (device_id, recorded_at) DO UPDATE
   SET value = EXCLUDED.value,
       lat   = EXCLUDED.lat,
       lon   = EXCLUDED.lon,
       load_id = EXCLUDED.load_id
 WHERE readings.load_id < EXCLUDED.load_id
"""


@dataclass
class LoadStats:
    rows_read: int = 0
    rows_valid: int = 0
    duplicated_in_file: int = 0
    without_position: int = 0
    rejected: Counter = field(default_factory=Counter)

    @property
    def rows_rejected(self) -> int:
        return sum(self.rejected.values())


def read_file(path: Path) -> tuple[list[Reading], LoadStats]:
    """Lee y valida el CSV. Devuelve las lecturas únicas (ya deduplicadas)."""
    stats = LoadStats()
    unique: dict[tuple[str, datetime], Reading] = {}

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit(f"El archivo {path} no tiene encabezado")

        # Encabezado tolerante: sin BOM, sin espacios y en minúsculas.
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise SystemExit(
                f"Faltan columnas obligatorias en {path.name}: {', '.join(missing)}"
            )

        for raw in reader:
            stats.rows_read += 1
            try:
                reading = parse_row(raw)
            except InvalidRow as invalid:
                stats.rejected[invalid.reason] += 1
                continue

            stats.rows_valid += 1
            if not reading.has_position:
                stats.without_position += 1

            key = (reading.device_id, reading.recorded_at)
            if key in unique:
                stats.duplicated_in_file += 1
            unique[key] = reading  # la última del archivo pisa a la anterior

    return list(unique.values()), stats


def load_file(path: Path) -> int:
    """Carga el archivo y deja el resumen por stdout. Devuelve el exit code."""
    if not path.is_file():
        raise SystemExit(f"No existe el archivo {path}")

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    readings, stats = read_file(path)

    with connect() as conn:
        ensure_schema(conn)

        previous = conn.execute(
            "SELECT id, loaded_at FROM loads WHERE file_hash = %s", (digest,)
        ).fetchone()
        if previous is not None:
            print(f"Archivo: {path} (sha256 {digest[:12]}…)")
            print(
                "  ya estaba cargado "
                f"(load #{previous['id']} de {previous['loaded_at']:%Y-%m-%d %H:%M:%S}); "
                "no se aplican cambios"
            )
            return 0

        load_id = conn.execute(
            """
            INSERT INTO loads (file_name, file_hash, rows_read, rows_valid,
                               rows_rejected, rows_without_position, rejections)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                path.name,
                digest,
                stats.rows_read,
                stats.rows_valid,
                stats.rows_rejected,
                stats.without_position,
                Json(dict(stats.rejected)),
            ),
        ).fetchone()["id"]

        device_ids = sorted({reading.device_id for reading in readings})
        if device_ids:
            with conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO devices (device_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    [(device_id,) for device_id in device_ids],
                )

        before = conn.execute("SELECT count(*) AS total FROM readings").fetchone()["total"]
        with conn.cursor() as cursor:
            # Modo pipeline: muchos INSERT en un solo viaje a la base.
            with cursor.pipeline():
                for reading in readings:
                    cursor.execute(
                        UPSERT_SQL,
                        (
                            reading.device_id,
                            reading.recorded_at,
                            reading.value,
                            reading.lat,
                            reading.lon,
                            load_id,
                        ),
                    )
        after = conn.execute("SELECT count(*) AS total FROM readings").fetchone()["total"]
        inserted = after - before
        updated = len(readings) - inserted

        conn.execute(
            "UPDATE loads SET rows_inserted = %s, rows_updated = %s WHERE id = %s",
            (inserted, updated, load_id),
        )

    print_summary(
        path, digest, stats, unique=len(readings), inserted=inserted, updated=updated
    )
    return 0


def print_summary(
    path: Path,
    digest: str,
    stats: LoadStats,
    unique: int,
    inserted: int,
    updated: int,
) -> None:
    print(f"Archivo: {path} (sha256 {digest[:12]}…)")
    print(f"  filas leídas ............ {stats.rows_read}")
    print(f"  filas válidas ........... {stats.rows_valid}")
    print(f"  lecturas únicas ......... {unique}")
    print(f"  duplicadas en el archivo  {stats.duplicated_in_file}")
    print(f"  filas descartadas ....... {stats.rows_rejected}")
    for reason, count in sorted(stats.rejected.items()):
        print(f"      - {reason}: {count}")
    print(f"  lecturas sin posición ... {stats.without_position}")
    print(f"  lecturas insertadas ..... {inserted}")
    print(f"  lecturas actualizadas ... {updated}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.load",
        description="Carga un lote CSV de lecturas en PostgreSQL (idempotente).",
    )
    parser.add_argument("path", type=Path, help="ruta del archivo CSV a cargar")
    args = parser.parse_args(argv)
    return load_file(args.path)


if __name__ == "__main__":
    sys.exit(main())
