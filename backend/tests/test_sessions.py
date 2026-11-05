"""Sesiones (cortes de 10 minutos) y asignación de día en America/Santiago."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.normalize import Reading
from app.sessions import build_sessions, sessions_starting_on, to_local_iso


def reading(iso: str, value: float | None = 1.0, lat=-33.425, lon=-70.636) -> Reading:
    return Reading(
        device_id="D-0001",
        recorded_at=datetime.fromisoformat(iso),
        value=value,
        lat=lat,
        lon=lon,
    )


def cadena(inicio: str, fin: str, paso_min: int = 5) -> list[Reading]:
    """Lecturas cada ``paso_min`` minutos entre ``inicio`` y ``fin``.

    Con ``paso_min <= 10`` ningún salto corta la sesión, así que todas las
    lecturas quedan en una sola sesión (como una sesión larga real).
    """
    momento = datetime.fromisoformat(inicio)
    limite = datetime.fromisoformat(fin)
    paso = timedelta(minutes=paso_min)
    serie = [reading(momento.isoformat())]
    while momento + paso < limite:
        momento += paso
        serie.append(reading(momento.isoformat()))
    serie.append(reading(fin))
    return serie


def test_corte_de_menos_de_diez_minutos_es_la_misma_sesion():
    sessions = build_sessions(
        [
            reading("2026-09-05T10:00:00-04:00"),
            reading("2026-09-05T10:05:00-04:00"),
            reading("2026-09-05T10:15:00-04:00"),  # exactamente 10 min: sigue
        ]
    )
    assert len(sessions) == 1
    assert sessions[0].count == 3


def test_corte_de_mas_de_diez_minutos_abre_sesion_nueva():
    sessions = build_sessions(
        [
            reading("2026-09-05T10:00:00-04:00"),
            reading("2026-09-05T10:10:01-04:00"),  # 10 min 1 s: corta
        ]
    )
    assert [session.count for session in sessions] == [1, 1]


def test_las_lecturas_se_ordenan_por_instante_antes_de_cortar():
    sessions = build_sessions(
        [
            reading("2026-09-05T10:05:00-04:00"),
            reading("2026-09-05T10:00:00-04:00"),
            reading("2026-09-05T10:10:00-04:00"),
        ]
    )
    assert len(sessions) == 1
    assert sessions[0].start == datetime.fromisoformat("2026-09-05T10:00:00-04:00")


def test_duracion_y_conteos_de_la_sesion():
    serie = cadena("2026-09-05T10:15:02-04:00", "2026-09-05T12:01:40-04:00")
    # La última lectura llega sin posición: cuenta para la sesión, no para el mapa.
    serie[-1] = reading("2026-09-05T12:01:40-04:00", value=20.0, lat=None, lon=None)

    session = build_sessions(serie)[0]
    assert session.count == len(serie)
    assert len(session.positions) == len(serie) - 1
    assert session.duration_minutes == 106.63


def test_sesion_de_una_sola_lectura_dura_cero():
    session = build_sessions([reading("2026-09-05T10:15:02-04:00")])[0]
    assert session.duration_minutes == 0.0
    assert session.to_dict()["start"] == "2026-09-05T10:15:02-04:00"


def test_to_dict_expone_el_offset_de_santiago():
    serie = cadena("2026-09-05T14:15:02Z", "2026-09-05T16:01:40Z")  # en UTC
    session = build_sessions(serie)[0]
    assert session.to_dict() == {
        "start": "2026-09-05T10:15:02-04:00",
        "end": "2026-09-05T12:01:40-04:00",
        "readings": len(serie),
        "duration_min": 106.63,
    }


def test_to_local_iso_cambia_de_dia_en_utc_pero_no_en_santiago():
    moment = datetime.fromisoformat("2026-09-05T03:30:00Z")
    assert to_local_iso(moment) == "2026-09-04T23:30:00-04:00"


def test_una_sesion_pertenece_al_dia_en_que_comienza():
    series = [
        reading("2026-09-05T03:30:00Z"),  # 2026-09-04 23:30 en Santiago
        reading("2026-09-05T03:40:00Z"),  # 2026-09-04 23:40 en Santiago
        reading("2026-09-05T04:10:00Z"),  # 2026-09-05 00:10 en Santiago (30 min: corta)
    ]

    del_dia_4 = sessions_starting_on(series, date(2026, 9, 4))
    del_dia_5 = sessions_starting_on(series, date(2026, 9, 5))

    assert [session.count for session in del_dia_4] == [2]
    assert [session.count for session in del_dia_5] == [1]


def test_sin_lecturas_no_hay_sesiones():
    assert build_sessions([]) == []
    assert sessions_starting_on([], date(2026, 9, 5)) == []
