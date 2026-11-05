# Trazabilidad de commits

Este proyecto llegó como **carpeta con los documentos de la prueba** (enunciado,
`docker-compose.yml` de la base, `.env.example` y dos lotes CSV): no había
repositorio git. La trazabilidad se resuelve en dos piezas:

1. **`scripts/historial-commits.sh`** construye el historial completo: 10 commits,
   en el orden de prioridad que pide el enunciado (modelo y carga → API →
   interfaz → ejecución), y con cada archivo entrando en el commit donde se
   explica.
2. **Este documento**, que amarra cada commit con el requisito del `README.md`,
   los archivos que toca y cómo comprobarlo.

## Cómo generar el historial

```bash
bash scripts/historial-commits.sh
git --no-pager log --oneline --reverse
```

El script es idempotente en el sentido útil: si ya existe `.git`, no toca nada y
muestra el historial actual. Para rehacerlo desde cero:

```bash
rm -rf .git && bash scripts/historial-commits.sh
```

> El historial se reconstruye sobre el árbol final, así que `README.md` entra
> completo en el primer commit (enunciado + sección 8 de ejecución). No se reescribe
> ningún archivo hacia atrás para fabricar commits intermedios.

## Mapa commit → requisito → verificación

| # | Commit | Requisito (`README.md`) | Archivos | Cómo se verifica |
| :-- | :--- | :--- | :--- | :--- |
| 1 | `docs: enunciado de la prueba, datos de ejemplo y .gitignore` | §3 material de trabajo | `README.md`, `data/lote_1.csv`, `data/lote_2.csv`, `assets/`, `.gitignore` | `git show --stat HEAD~9`; los CSV quedan intactos (`data/` no se modifica) |
| 2 | `feat(db): esquema PostgreSQL y conexión` | §5.1 "esquema en PostgreSQL"; regla 4 (última recibida) | `backend/app/schema.sql`, `db.py`, `config.py`, `requirements.txt` | `\d readings` en `psql`: PK `(device_id, recorded_at)`, `load_id` con FK a `loads` |
| 3 | `feat(ingesta): reglas del proveedor y descartes por motivo` | §4 reglas 1, 2, 3, 5, 6 | `backend/app/normalize.py` | `pytest tests/test_normalize.py -v` |
| 4 | `feat(ingesta): cargador idempotente con resumen de descartes` | §5.1 carga + idempotencia + resumen | `backend/app/load.py` | dos veces `python -m app.load data/lote_1.csv`: la segunda imprime `ya estaba cargado` |
| 5 | `feat(api): sesiones de 10 minutos y días en America/Santiago` | §4 definiciones (sesión, día, sesión pertenece al día que empieza) | `backend/app/sessions.py` | `pytest tests/test_sessions.py -v` |
| 6 | `feat(api): dispositivos, resumen diario y track GeoJSON` | §5.2 los tres endpoints y sus formatos exactos | `backend/app/api.py` | `curl /devices`, `curl /devices/D-0001/days/2026-09-05`, `.../track` |
| 7 | `feat(web): pantalla con filtros, sesiones y mapa Leaflet` | §5.3 interfaz, hora de Santiago, estados, mapa | `frontend/index.html`, `app.js`, `styles.css` | abrir <http://localhost:8000> y recorrer día anterior/siguiente |
| 8 | `feat(infra): servicio api en docker compose y Dockerfile` | §5.4 `docker compose up` levanta base y API | `docker-compose.yml`, `backend/Dockerfile`, `.env.example` | `docker compose up --build` y `docker compose ps` con `db` y `api` sanos |
| 9 | `test: reglas de ingesta y cortes de sesión` | §6 "opcional: tests" | `backend/tests/*`, `pytest.ini`, `requirements-dev.txt` | `cd backend && pytest` (verde, sin base de datos) |
| 10 | `docs: decisiones, trazabilidad y reconstrucción del historial` | §6 entregables (`DECISIONES.md`, README de ejecución) | `DECISIONES.md`, `TRAZABILIDAD.md`, `scripts/` | este archivo + `DECISIONES.md` (8 líneas) |

## Reglas de negocio → dónde está cada una

| Regla del proveedor (§4) | Implementación | Test |
| :--- | :--- | :--- |
| 1. `device_id` sin distinguir mayúsculas ni espacios | `normalize.normalize_device_id` | `test_device_id_*` |
| 2. `recorded_at` ISO-8601 con zona; sin zona o imposible = inválida | `normalize.parse_recorded_at` | `test_recorded_at_*` |
| 3. `value` vacío/`NaN` = sin dato | `normalize.parse_value` → `NULL` | `test_value_*` |
| 4. última recibida gana (archivo y entre archivos) | PK `(device_id, recorded_at)` + `load_id` en el `ON CONFLICT` de `load.UPSERT_SQL` | verificación manual (abajo) |
| 5. posición vacía, `(0,0)` o fuera de rango = sin posición | `normalize.parse_position` → `NULL` | `test_posiciones_*` |
| 6. filas inválidas no se cargan y se informan por motivo | `InvalidRow` + `Counter` en `load.LoadStats` + `loads.rejections` | `test_parse_row_*`, resumen de la carga |
| Sesión: corte de más de 10 minutos | `sessions.build_sessions` (`SESSION_GAP_MINUTES`) | `test_corte_*` |
| Día en `America/Santiago`; la sesión va al día que empieza | `sessions.day_bounds`, `sessions_starting_on` | `test_una_sesion_pertenece_al_dia_en_que_comienza` |

## Verificación end-to-end

```bash
# 0) entorno e historial
cp .env.example .env                        # PowerShell: Copy-Item .env.example .env
bash scripts/historial-commits.sh
git --no-pager log --oneline --reverse      # 10 commits, del enunciado a la documentación

# 1) levantar base y API
docker compose up --build -d
docker compose ps                           # db y api arriba

# 2) carga, en orden, y recarga para comprobar idempotencia
docker compose run --rm api python -m app.load /data/lote_1.csv
docker compose run --rm api python -m app.load /data/lote_2.csv
docker compose run --rm api python -m app.load /data/lote_1.csv   # "ya estaba cargado"
docker compose exec db psql -U app -d lecturas -c \
  "select id, file_name, rows_read, rows_valid, rows_inserted, rows_updated, rows_rejected from loads order by id;"

# 3) API: forma exacta, offsets de Santiago y 404
curl -s localhost:8000/devices
curl -s localhost:8000/devices/D-0001/days/2026-09-05
curl -s localhost:8000/devices/D-0001/days/2026-09-05/track
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/devices/NO-EXISTE/days/2026-09-05   # 404

# 4) tests unitarios (no necesitan base)
cd backend && pip install -r requirements-dev.txt && pytest && cd ..
```

Resultados esperados:

- `loads`: tres filas; la tercera recarga no agrega fila ni cambia `readings`.
- `/devices`: lista ordenada por `device_id`, con `first_day`/`last_day` en fechas de Santiago.
- Resumen diario: `readings`, `avg_value` (2 decimales o `null`) y `sessions` con
  `start`/`end` en ISO con offset (`-04:00` hasta el 5 de septiembre de 2026,
  `-03:00` desde el 6, cuando empieza el horario de verano).
- `/track`: `FeatureCollection` con una feature por sesión, `coordinates` en orden
  `[lon, lat]`, `Point` si la sesión tiene un solo punto y `geometry: null` si no
  tiene ninguno.
- Interfaz: al pasar el mouse por una sesión de la lista se resalta **su** línea en
  el mapa, y al hacer clic en una línea se marca su fila.
- `pytest`: suite en verde (reglas del proveedor + sesiones).

## Notas y límites

- Al momento de esta entrega el directorio no tenía `.git`, ni código de
  aplicación: solo el enunciado, el `docker-compose.yml` de la base, `.env.example`
  y los dos lotes. Todo lo demás es lo que se ve en el historial.
- Los archivos de `data/` no se modificaron (el enunciado lo prohíbe); el cargador
  los lee en modo solo lectura.
- El historial se genera en el orden de prioridad del enunciado, no en el orden
  real de escritura de los archivos. Si se necesita un historial "real", conviene
  trabajar en ramas y hacer `merge --no-ff` por etapa.

