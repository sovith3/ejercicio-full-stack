<img src="assets/migtra-logo.svg" alt="Migtra" width="210">

# Prueba técnica - Desarrollador

**Servicio de lecturas | Full stack**

**Duración:** 60 minutos en total.

| Lectura y preguntas | Construcción | Conversación final |
| :--- | :--- | :--- |
| ~5 minutos | ~40 minutos | ~15 minutos |

## 1. Contexto

Una plataforma recibe lecturas periódicas de muchos dispositivos. Los
dispositivos no envían sus datos directamente: un intermediario los junta y los
entrega en archivos CSV por lotes. Los lotes pueden solaparse, repetir
información, venir desordenados o traer datos atrasados.

Los dispositivos se mueven y cada lectura informa su posición.

Tu tarea es construir una aplicación full stack pequeña: cargar esos archivos en
PostgreSQL, exponer un resumen diario y el recorrido de cada dispositivo
mediante una API, y mostrarlos en una interfaz web con un mapa.

## 2. Reglas de la sesión

- Puedes usar asistentes de IA, documentación e internet. Lo esperamos.
- Comparte pantalla durante la construcción.
- Todo lo que entregues debes poder explicarlo y modificarlo. La última parte
  de la sesión es una conversación sobre tu código y tus decisiones.
- Preferimos algo pequeño, correcto y explicable a algo completo que no
  entiendes. Si no alcanzas a terminar, prioriza en el orden indicado abajo.
- Backend en Python 3.11 o superior. Las librerías y frameworks, de backend y
  de frontend, son libres.

## 3. Material de trabajo

| Archivo | Contenido |
| :--- | :--- |
| `docker-compose.yml` | PostgreSQL 17. |
| `.env.example` | Variables de conexión; cópialo a `.env`. |
| `data/lote_1.csv` | Primer lote recibido. |
| `data/lote_2.csv` | Segundo lote, recibido después del primero. |

> **Importante:** no modifiques los archivos de `data/`.

## 4. Datos y reglas de negocio

Columnas: `device_id`, `recorded_at`, `value`, `lat`, `lon`.

El proveedor documenta estas reglas:

1. `device_id` no distingue mayúsculas de minúsculas y puede venir con espacios
   alrededor.
2. `recorded_at` usa ISO-8601 y **debe** traer zona horaria. Cada emisor usa su
   propio formato (UTC con `Z`, offset explícito, con o sin milisegundos). Una
   fila sin zona horaria o con una fecha imposible es inválida.
3. `value` es numérico. Vacío o `NaN` significan "sin dato": la lectura existe,
   pero no participa en el promedio.
4. La lectura de un mismo dispositivo en un mismo instante puede llegar más de
   una vez. Vale la **última recibida**: dentro de un archivo, la que está más
   abajo; entre archivos, la del archivo que llegó después.
5. `lat` y `lon` son grados decimales (WGS84). Una posición vacía, en `(0, 0)` o
   fuera de rango significa "sin posición": la lectura existe y cuenta para
   todo lo demás, pero no se dibuja en el mapa.
6. Las filas inválidas no se cargan, pero la carga debe informar cuántas se
   descartaron y por qué motivo.

### Definiciones

- **Sesión:** secuencia de lecturas de un dispositivo en la que entre una
  lectura y la siguiente no pasan más de 10 minutos. Si pasan más de 10
  minutos, empieza una sesión nueva.
- **Día:** día calendario en la zona horaria `America/Santiago`.
- Una sesión pertenece al día en que **comienza**, aunque termine al día
  siguiente.

## 5. Qué construir

**Orden de prioridad:** modelo y carga, API, interfaz web y ejecución.

### 5.1 Modelo y carga

Esquema en PostgreSQL y un comando que reciba la ruta de un archivo y lo
cargue. Debe ser **idempotente**: cargar el mismo archivo dos veces no puede
cambiar el resultado. Al terminar, imprime un resumen con filas leídas, filas
válidas y filas descartadas por motivo.

### 5.2 API

#### Listado de dispositivos

`GET /devices`

Dispositivos con datos, ordenados por `device_id`:

```json
[
  { "device_id": "D-0001", "first_day": "2026-09-04", "last_day": "2026-09-07" }
]
```

`first_day` y `last_day` son los días de la primera y de la última lectura del
dispositivo.

#### Resumen diario

`GET /devices/{device_id}/days/{YYYY-MM-DD}`

Resumen de un día, con exactamente este formato:

```json
{
  "device_id": "D-0001",
  "date": "2026-09-05",
  "readings": 812,
  "avg_value": 51.23,
  "sessions": [
    {
      "start": "2026-09-05T10:15:02-04:00",
      "end": "2026-09-05T12:01:40-04:00",
      "readings": 97,
      "duration_min": 106.63
    }
  ]
}
```

- `readings`: lecturas válidas del dispositivo cuyo instante cae en ese día.
- `avg_value`: promedio de `value` de esas lecturas, sin contar las que no
  tienen dato, redondeado a 2 decimales; `null` si no hay ninguno.
- `sessions`: sesiones que comienzan ese día, ordenadas por inicio. `start` y
  `end` en ISO-8601 con offset; `readings` cuenta las lecturas de la sesión
  completa; `duration_min` es `end - start` en minutos con 2 decimales.
- Dispositivo inexistente: `404`. Dispositivo existente sin lecturas ese día:
  `readings: 0`, `avg_value: null`, `sessions: []`.

#### Recorrido del día

`GET /devices/{device_id}/days/{YYYY-MM-DD}/track`

Recorrido del día como GeoJSON: un `Feature` por sesión, con las mismas sesiones
y en el mismo orden que el endpoint anterior (ejemplo abreviado):

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[-70.6483, -33.4372], [-70.6471, -33.4365]]
      },
      "properties": {
        "start": "2026-09-05T10:15:02-04:00",
        "end": "2026-09-05T12:01:40-04:00",
        "readings": 97,
        "positions": 95
      }
    }
  ]
}
```

- `coordinates` sigue el orden GeoJSON `[lon, lat]`, con los puntos ordenados
  por instante, y solo incluye lecturas con posición.
- `positions` es la cantidad de puntos de la sesión. Con 1 punto, la geometría
  es un `Point`; sin puntos, `geometry` es `null`.
- Dispositivo inexistente: `404`.

### 5.3 Interfaz web

Una sola pantalla que permita:

- elegir un dispositivo (desde `GET /devices`) y un día, y pasar al día
  anterior o siguiente;
- ver la cantidad de lecturas, el promedio y las sesiones del día (inicio, fin,
  duración y lecturas). Una línea de tiempo del día es opcional;
- ver en un **mapa** el recorrido del día: una línea por sesión, y poder
  identificar en el mapa qué línea corresponde a cada sesión de la lista.

**Requisitos de la interfaz**

- Las fechas y horas se muestran en hora de `America/Santiago`, aunque el
  navegador de quien la usa esté en otra zona horaria.
- Estados claros: cargando, error (API o base de datos no disponibles,
  dispositivo inexistente) y día sin lecturas.
- La librería de mapas es libre (Leaflet, MapLibre, OpenLayers…). Puedes usar
  los tiles públicos de OpenStreetMap, con su atribución.
- No necesita un diseño elaborado: valoramos que sea correcta y usable.

### 5.4 Ejecución

`docker compose up` debe levantar la base de datos y la API. La interfaz puede
quedar en Docker o correr con su servidor de desarrollo; documenta en tu README
cómo levantar cada parte y cómo ejecutar la carga.

Para evaluar, cargaremos `lote_1` y luego `lote_2`, repitiendo cargas para
comprobar la idempotencia, y usaremos la API y la interfaz.

## 6. Entregables

- **Código y documentación.** Tu código en un repositorio git (o una carpeta
  comprimida) con un README que explique cómo ejecutarlo.
- **Decisiones.** `DECISIONES.md`, escrito por ti y breve (máximo 10 líneas):
  supuestos que tomaste, qué dejaste fuera y qué harías con más tiempo.
- **Opcional:** tests.

## 7. Qué valoramos

- Que los datos queden correctos y se vean correctos.
- Un modelo y unas consultas claras.
- Que se pueda ejecutar sin pasos ocultos.
- Sobre todo, que entiendas y puedas explicar lo que construiste.

---

## 8. Cómo ejecutar esta implementación

**Requisitos:** Docker + Docker Compose v2. Opcional para correr sin Docker: Python 3.11+.

### 8.1 Variables de entorno

```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
```

`POSTGRES_PASSWORD` es obligatorio: `docker-compose.yml` falla a propósito si falta.

### 8.2 Levantar base de datos y API

```bash
docker compose up --build
```

- Interfaz web y API: <http://localhost:8000> (documentación interactiva en `/docs`).
- PostgreSQL: `localhost:5432`.
- El esquema se crea solo al arrancar la API (`backend/app/schema.sql`, DDL idempotente).

### 8.3 Cargar los lotes (en este orden)

```bash
docker compose run --rm api python -m app.load /data/lote_1.csv
docker compose run --rm api python -m app.load /data/lote_2.csv
```

Repetir cualquiera de los dos comandos no cambia nada: la carga es idempotente por
`sha256` del archivo. El resumen que imprime tiene esta forma:

```text
Archivo: /data/lote_1.csv (sha256 1a2b3c4d5e6f…)
  filas leídas ............ <n>
  filas válidas ........... <n>
  lecturas únicas ......... <n>
  duplicadas en el archivo  <n>
  filas descartadas ....... <n>
      - columnas_invalidas: <n>
      - recorded_at_invalido: <n>
      - recorded_at_sin_zona: <n>
      - value_no_numerico: <n>
  lecturas sin posición ... <n>
  lecturas insertadas ..... <n>
  lecturas actualizadas ... <n>
```

### 8.4 API

```bash
curl http://localhost:8000/devices
curl http://localhost:8000/devices/D-0001/days/2026-09-05
curl http://localhost:8000/devices/D-0001/days/2026-09-05/track
```

### 8.5 Interfaz web

<http://localhost:8000> — un selector de dispositivo, navegación de día
anterior/siguiente, totales del día, lista de sesiones y mapa Leaflet con una
línea por sesión, con el mismo color en la lista y en el mapa.

### 8.6 Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Cubren las reglas del proveedor (normalización y descartes) y las sesiones
(corte de 10 minutos, asignación de día en `America/Santiago`, formatos ISO).

### 8.7 Sin Docker (backend en el host)

```bash
docker compose up -d db
cd backend
pip install -r requirements.txt
export DATABASE_URL="postgresql://app:cambiar-esto@localhost:5432/lecturas"
# PowerShell: $env:DATABASE_URL="postgresql://app:cambiar-esto@localhost:5432/lecturas"
python -m app.load ../data/lote_1.csv
uvicorn app.api:app --reload --port 8000
```

### 8.8 Estructura

```text
backend/app/config.py         configuración (DSN, zona horaria, corte de sesión)
backend/app/schema.sql        esquema PostgreSQL
backend/app/normalize.py      reglas del proveedor: validación y motivos de descarte
backend/app/load.py           comando de carga idempotente (python -m app.load)
backend/app/sessions.py       sesiones, días y formatos ISO de salida
backend/app/api.py            endpoints + servido de la interfaz
frontend/                     pantalla única (HTML/CSS/JS + Leaflet)
backend/tests/                tests unitarios de reglas y sesiones
scripts/historial-commits.sh  reconstruye el historial de commits del proyecto
TRAZABILIDAD.md               requisito -> commit -> archivo -> cómo verificarlo
```
