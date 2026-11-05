"""Sesiones, días y formatos de fecha del negocio.

- **Sesión:** lecturas de un dispositivo sin cortes de más de 10 minutos.
- **Día:** día calendario en ``America/Santiago``.
- Una sesión pertenece al día en que empieza, aunque termine al día siguiente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

from .config import SESSION_GAP_MINUTES, TIMEZONE
from .normalize import Reading

TZ = ZoneInfo(TIMEZONE)
SESSION_GAP = timedelta(minutes=SESSION_GAP_MINUTES)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Rango semiabierto ``[inicio, fin)`` del día local, en hora de Santiago."""
    start = datetime.combine(day, time.min, tzinfo=TZ)
    return start, start + timedelta(days=1)


def local_date(moment: datetime) -> date:
    """Día calendario (Santiago) de un instante."""
    return moment.astimezone(TZ).date()


def to_local_iso(moment: datetime) -> str:
    """ISO-8601 con el offset de Santiago, como lo muestra la API."""
    return moment.astimezone(TZ).isoformat()


@dataclass(frozen=True)
class Session:
    """Tramo continuo de lecturas de un dispositivo."""

    readings: Sequence[Reading]

    @property
    def start(self) -> datetime:
        return self.readings[0].recorded_at

    @property
    def end(self) -> datetime:
        return self.readings[-1].recorded_at

    @property
    def count(self) -> int:
        return len(self.readings)

    @property
    def positions(self) -> list[Reading]:
        """Lecturas con posición, en orden temporal (las que van al mapa)."""
        return [reading for reading in self.readings if reading.has_position]

    @property
    def duration_minutes(self) -> float:
        return round((self.end - self.start).total_seconds() / 60, 2)

    def to_dict(self) -> dict:
        return {
            "start": to_local_iso(self.start),
            "end": to_local_iso(self.end),
            "readings": self.count,
            "duration_min": self.duration_minutes,
        }


def build_sessions(readings: Iterable[Reading]) -> list[Session]:
    """Corta la serie ordenada por instante en sesiones (corte > 10 minutos)."""
    ordered = sorted(readings, key=lambda reading: reading.recorded_at)
    sessions: list[Session] = []
    current: list[Reading] = []

    for reading in ordered:
        if current and reading.recorded_at - current[-1].recorded_at > SESSION_GAP:
            sessions.append(Session(current))
            current = []
        current.append(reading)

    if current:
        sessions.append(Session(current))
    return sessions


def sessions_starting_on(readings: Iterable[Reading], day: date) -> list[Session]:
    """Sesiones cuyo inicio cae en ``day``, ordenadas por inicio."""
    return [
        session for session in build_sessions(readings) if local_date(session.start) == day
    ]
