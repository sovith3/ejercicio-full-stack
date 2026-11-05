"""Reglas del proveedor: normalización, validación y descarte de filas.

Todo lo de este módulo es puro (sin base de datos ni I/O), para poder probarlo
con tests unitarios rápidos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

#: Columnas que el archivo debe traer. `value`, `lat` y `lon` pueden venir
#: vacías; el encabezado, no.
REQUIRED_COLUMNS = ("device_id", "recorded_at", "value", "lat", "lon")

#: Motivos de descarte. Se informan tal cual en el resumen de la carga.
REASON_COLUMNS = "columnas_invalidas"
REASON_DEVICE_EMPTY = "device_id_vacio"
REASON_TS_MISSING = "recorded_at_ausente"
REASON_TS_NAIVE = "recorded_at_sin_zona"
REASON_TS_INVALID = "recorded_at_invalido"
REASON_VALUE_INVALID = "value_no_numerico"

#: `value` vacío o `NaN` significa "sin dato" (la lectura existe y no promedia).
NO_DATA_VALUES = frozenset({"", "nan"})


class InvalidRow(ValueError):
    """Fila descartada. ``reason`` viaja al resumen de la carga."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Reading:
    """Una lectura ya normalizada."""

    device_id: str
    recorded_at: datetime
    value: float | None
    lat: float | None
    lon: float | None

    @property
    def has_position(self) -> bool:
        return self.lat is not None and self.lon is not None


def normalize_device_id(raw: str | None) -> str:
    """Regla 1: `device_id` no distingue mayúsculas y puede traer espacios.

    Se almacena siempre en mayúsculas y sin espacios alrededor, así que
    ``" d-0014 "`` y ``"D-0014"`` son el mismo dispositivo.
    """
    device = (raw or "").strip().upper()
    if not device:
        raise InvalidRow(REASON_DEVICE_EMPTY)
    return device


def parse_recorded_at(raw: str | None) -> datetime:
    """Regla 2: ISO-8601 **con** zona horaria; fecha imposible = fila inválida."""
    text = (raw or "").strip()
    if not text:
        raise InvalidRow(REASON_TS_MISSING)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:  # fecha imposible, formato raro, hora 25:00, etc.
        raise InvalidRow(REASON_TS_INVALID) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidRow(REASON_TS_NAIVE)
    return parsed


def parse_value(raw: str | None) -> float | None:
    """Regla 3: numérico; vacío o `NaN` = "sin dato" (``None``)."""
    text = (raw or "").strip()
    if text.lower() in NO_DATA_VALUES:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise InvalidRow(REASON_VALUE_INVALID) from exc
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def parse_position(
    lat_raw: str | None, lon_raw: str | None
) -> tuple[float | None, float | None]:
    """Regla 5: posición vacía, en ``(0, 0)`` o fuera de rango = "sin posición".

    Ojo: no descarta la fila. Solo deja la lectura fuera del mapa.
    """
    lat_text = (lat_raw or "").strip()
    lon_text = (lon_raw or "").strip()
    if not lat_text or not lon_text:
        return None, None
    try:
        lat = float(lat_text)
        lon = float(lon_text)
    except ValueError:
        return None, None
    if math.isnan(lat) or math.isnan(lon):
        return None, None
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        return None, None
    if lat == 0.0 and lon == 0.0:
        return None, None
    return lat, lon


def parse_row(row: Mapping[str, str | None]) -> Reading:
    """Convierte una fila del CSV en :class:`Reading` o lanza :class:`InvalidRow`."""
    # DictReader deja la clave None cuando la fila trae más columnas que el
    # encabezado, y las columnas faltantes simplemente no aparecen: ambos casos
    # son "columnas inválidas" y descartan la fila (regla 6).
    if None in row or any(column not in row for column in REQUIRED_COLUMNS):
        raise InvalidRow(REASON_COLUMNS)

    device_id = normalize_device_id(row["device_id"])
    recorded_at = parse_recorded_at(row["recorded_at"])
    value = parse_value(row["value"])
    lat, lon = parse_position(row["lat"], row["lon"])
    return Reading(
        device_id=device_id,
        recorded_at=recorded_at,
        value=value,
        lat=lat,
        lon=lon,
    )
