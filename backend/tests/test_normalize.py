"""Reglas del proveedor: normalización y descarte (sin base de datos)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.normalize import (
    InvalidRow,
    REASON_COLUMNS,
    REASON_DEVICE_EMPTY,
    REASON_TS_INVALID,
    REASON_TS_MISSING,
    REASON_TS_NAIVE,
    REASON_VALUE_INVALID,
    normalize_device_id,
    parse_position,
    parse_recorded_at,
    parse_row,
    parse_value,
)


def test_device_id_se_normaliza_a_mayusculas_sin_espacios():
    assert normalize_device_id("  d-0014 ") == "D-0014"
    assert normalize_device_id("D-0014") == "D-0014"


def test_device_id_vacio_es_fila_invalida():
    with pytest.raises(InvalidRow) as error:
        normalize_device_id("   ")
    assert error.value.reason == REASON_DEVICE_EMPTY


@pytest.mark.parametrize(
    "texto",
    [
        "2026-09-04T04:02:46Z",
        "2026-09-04T04:02:30.000Z",
        "2026-09-04T00:05:07-04:00",
        "2026-09-06T12:00:14+00:00",
    ],
)
def test_recorded_at_acepta_los_formatos_del_proveedor(texto):
    parsed = parse_recorded_at(texto)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None


def test_recorded_at_sin_zona_es_fila_invalida():
    with pytest.raises(InvalidRow) as error:
        parse_recorded_at("2026-09-04T04:02:46")
    assert error.value.reason == REASON_TS_NAIVE


def test_recorded_at_vacio_es_fila_invalida():
    with pytest.raises(InvalidRow) as error:
        parse_recorded_at("")
    assert error.value.reason == REASON_TS_MISSING


@pytest.mark.parametrize("texto", ["2026-02-30T10:00:00Z", "2026-09-04T25:00:00Z", "ayer"])
def test_recorded_at_imposible_es_fila_invalida(texto):
    with pytest.raises(InvalidRow) as error:
        parse_recorded_at(texto)
    assert error.value.reason == REASON_TS_INVALID


@pytest.mark.parametrize("texto", ["", "  ", "NaN", "nan"])
def test_value_sin_dato_no_promedia(texto):
    assert parse_value(texto) is None


def test_value_no_numerico_es_fila_invalida():
    with pytest.raises(InvalidRow) as error:
        parse_value("abc")
    assert error.value.reason == REASON_VALUE_INVALID


@pytest.mark.parametrize(
    "lat, lon",
    [("", ""), ("", "-70.6"), ("0", "0"), ("0.0", "0.0"), ("91", "-70.6"), ("-33.4", "181")],
)
def test_posiciones_invalidas_significan_sin_posicion(lat, lon):
    assert parse_position(lat, lon) == (None, None)


def test_posicion_valida_se_conserva():
    assert parse_position("-33.425101", "-70.636526") == (-33.425101, -70.636526)


def test_parse_row_completa():
    reading = parse_row(
        {
            "device_id": " d-0037 ",
            "recorded_at": "2026-09-04T04:02:46Z",
            "value": "47.77",
            "lat": "-33.425101",
            "lon": "-70.636526",
        }
    )
    assert reading.device_id == "D-0037"
    assert reading.recorded_at == datetime(2026, 9, 4, 4, 2, 46, tzinfo=timezone.utc)
    assert reading.value == 47.77
    assert reading.has_position is True


def test_parse_row_con_columnas_de_mas_es_invalida():
    with pytest.raises(InvalidRow) as error:
        parse_row(
            {
                "device_id": "D-0037",
                "recorded_at": "2026-09-04T04:02:46Z",
                "value": "47.77",
                "lat": "-33.4",
                "lon": "-70.6",
                None: ["sobra"],
            }
        )
    assert error.value.reason == REASON_COLUMNS


def test_parse_row_con_columna_faltante_es_invalida():
    with pytest.raises(InvalidRow) as error:
        parse_row({"device_id": "D-0037", "recorded_at": "2026-09-04T04:02:46Z"})
    assert error.value.reason == REASON_COLUMNS
