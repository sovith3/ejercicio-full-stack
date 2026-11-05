"""API HTTP: dispositivos, resumen diario y recorrido del día (GeoJSON).

Se sirve con ``uvicorn app.api:app``. La interfaz web se monta en ``/``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIR
from .db import connect, ensure_schema
from .normalize import InvalidRow, Reading, normalize_device_id
from .sessions import day_bounds, local_date, sessions_starting_on, to_local_iso


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Crea el esquema al arrancar (DDL idempotente).

    Si la base todavía no está disponible no se aborta el arranque: la interfaz
    igual se sirve y muestra el error de conexión, que es un estado explícito
    pedido por el enunciado.
    """
    try:
        with connect() as conn:
            ensure_schema(conn)
    except psycopg.Error as error:
        print(f"[api] no se pudo preparar el esquema al arrancar: {error}")
    yield


app = FastAPI(title="Servicio de lecturas", version="1.0.0", lifespan=lifespan)


def get_connection():
    try:
        conn = connect()
    except psycopg.Error as error:  # base caída: la UI lo muestra como estado de error
        raise HTTPException(
            status_code=503, detail="base de datos no disponible"
        ) from error
    try:
        yield conn
    finally:
        conn.close()


def _normalized_or_404(device_id: str) -> str:
    try:
        return normalize_device_id(device_id)
    except InvalidRow as invalid:
        raise HTTPException(status_code=404, detail="dispositivo inexistente") from invalid


def _require_device(conn: psycopg.Connection, device_id: str) -> str:
    device = _normalized_or_404(device_id)
    row = conn.execute(
        "SELECT 1 AS ok FROM devices WHERE device_id = %s", (device,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"dispositivo {device} inexistente")
    return device


def _device_readings(conn: psycopg.Connection, device: str) -> list[Reading]:
    rows = conn.execute(
        """
        SELECT device_id, recorded_at, value, lat, lon
          FROM readings
         WHERE device_id = %s
         ORDER BY recorded_at
        """,
        (device,),
    ).fetchall()
    return [Reading(**row) for row in rows]


@app.get("/devices")
def list_devices(conn: psycopg.Connection = Depends(get_connection)):
    """Dispositivos con datos, ordenados por ``device_id``."""
    rows = conn.execute(
        """
        SELECT device_id,
               min(recorded_at) AS first_ts,
               max(recorded_at) AS last_ts
          FROM readings
         GROUP BY device_id
         ORDER BY device_id
        """
    ).fetchall()
    return [
        {
            "device_id": row["device_id"],
            "first_day": local_date(row["first_ts"]).isoformat(),
            "last_day": local_date(row["last_ts"]).isoformat(),
        }
        for row in rows
    ]


@app.get("/devices/{device_id}/days/{day}")
def daily_summary(
    device_id: str,
    day: date,
    conn: psycopg.Connection = Depends(get_connection),
):
    """Lecturas, promedio y sesiones del día (día de Santiago)."""
    device = _require_device(conn, device_id)
    start, end = day_bounds(day)
    totals = conn.execute(
        """
        SELECT count(*) AS readings, avg(value) AS avg_value
          FROM readings
         WHERE device_id = %s
           AND recorded_at >= %s
           AND recorded_at <  %s
        """,
        (device, start, end),
    ).fetchone()

    sessions = sessions_starting_on(_device_readings(conn, device), day)
    average = totals["avg_value"]
    return {
        "device_id": device,
        "date": day.isoformat(),
        "readings": totals["readings"],
        "avg_value": round(float(average), 2) if average is not None else None,
        "sessions": [session.to_dict() for session in sessions],
    }


@app.get("/devices/{device_id}/days/{day}/track")
def daily_track(
    device_id: str,
    day: date,
    conn: psycopg.Connection = Depends(get_connection),
):
    """Recorrido del día como ``FeatureCollection`` (una feature por sesión)."""
    device = _require_device(conn, device_id)
    features = []

    for session in sessions_starting_on(_device_readings(conn, device), day):
        # Orden GeoJSON: [lon, lat], y solo lecturas con posición.
        coordinates = [
            [reading.lon, reading.lat] for reading in session.positions
        ]
        if len(coordinates) > 1:
            geometry = {"type": "LineString", "coordinates": coordinates}
        elif len(coordinates) == 1:
            geometry = {"type": "Point", "coordinates": coordinates[0]}
        else:
            geometry = None

        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "start": to_local_iso(session.start),
                    "end": to_local_iso(session.end),
                    "readings": session.count,
                    "positions": len(coordinates),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


# La interfaz web se monta al final: las rutas de la API ya quedaron registradas
# y tienen prioridad sobre el catch-all de los archivos estáticos.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="web")
