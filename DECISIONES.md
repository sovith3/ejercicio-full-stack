# Decisiones

1. La deduplicación vive en la llave primaria `readings (device_id, recorded_at)`: la regla "gana la última recibida" es una restricción de la base, no lógica repartida por el código.
2. La idempotencia la da el `sha256` del archivo en `loads`: recargar el mismo lote no reescribe nada, y un lote posterior siempre pisa al anterior (orden de `loads.id`).
3. `device_id` se normaliza (mayúsculas, sin espacios) al cargar. `value` vacío o `NaN` y una posición inválida se guardan como `NULL`: la lectura existe y cuenta para todo lo demás.
4. Posición inválida (vacía, `(0,0)`, fuera de rango o par incompleto) no descarta la fila; se informa como contador aparte de los descartes por motivo.
5. Las sesiones se calculan en Python sobre la serie completa del dispositivo; con más volumen movería la ventana a SQL o a una tabla materializada.
6. El conteo y el promedio del día se resuelven en SQL con los bordes del día calculados en `America/Santiago` (rango semiabierto).
7. Fuera de alcance: autenticación, migraciones versionadas (el DDL idempotente de `schema.sql` hace de esquema inicial), borrado de lotes y paginación de `/devices`.
8. Con más tiempo: tests de integración contra una base real, revisar planes de ejecución (`EXPLAIN`), y carga por streaming en vez de deduplicar el lote en memoria.
