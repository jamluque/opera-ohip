# Analitica PMS: last status de reservas

`last status` representa el estado diario de una reserva en la fecha en la que se ejecuta el informe. A diferencia de pickups, no mide cambios entre dias: devuelve una fila unica por reserva con el ultimo estado conocido en el snapshot diario.

## Definicion funcional

- Fecha de consulta: `snapshot_date`, normalmente `CURRENT_DATE` o la business date acordada para el informe.
- Granularidad: una fila por `hotel_id + reservation_id`.
- Estados: texto flexible, no enum cerrado. Estados base esperados: `RESERVED`, `CHECKED_IN`, `CHECKED_OUT`, `CANCELLED`, `NO_SHOW`, `UPDATE`.
- Canceladas y no-show: deben aparecer como ultimo estado, sin filtrarlas.
- Historico de cambios: no se resuelve aqui; queda para analisis de pickups u otra capa historica si negocio lo pide mas adelante.

## Tabla analitica

El `analytics-snapshot-job` refresca diariamente:

```text
opera_analytics.reservation_last_status_daily
```

Clave primaria:

```text
snapshot_date + hotel_id + reservation_id
```

La tabla se construye desde `opera_analytics.reservation_daily_snapshot`, compactando las noches de estancia en una unica reserva. Esto evita que el equipo de negocio vea varias filas de la misma reserva por cada noche.

## Vista de informe actual

Para informes del dia en curso:

```sql
SELECT *
FROM opera_analytics.v_reservation_last_status_current
ORDER BY hotel_id, arrival_date, reservation_id;
```

## Last status por hotel

```sql
SELECT
    hotel_id,
    last_status,
    COUNT(*) AS reservations
FROM opera_analytics.reservation_last_status_daily
WHERE snapshot_date = CURRENT_DATE
GROUP BY hotel_id, last_status
ORDER BY hotel_id, reservations DESC;
```

## Detalle de reservas con su ultimo estado

```sql
SELECT
    snapshot_date,
    hotel_id,
    reservation_id,
    confirmation_no,
    arrival_date,
    departure_date,
    last_status,
    last_status_event_at,
    room_type,
    rate_code,
    market_code,
    source_code,
    channel_code
FROM opera_analytics.reservation_last_status_daily
WHERE snapshot_date = CURRENT_DATE
  AND hotel_id = 'HOTEL_ID'
ORDER BY arrival_date, reservation_id;
```

## Canceladas y no-show incluidas

```sql
SELECT
    hotel_id,
    last_status,
    COUNT(*) AS reservations
FROM opera_analytics.reservation_last_status_daily
WHERE snapshot_date = CURRENT_DATE
  AND last_status IN ('CANCELLED', 'NO_SHOW')
GROUP BY hotel_id, last_status
ORDER BY hotel_id, last_status;
```

## Llegadas del dia por ultimo estado

```sql
SELECT
    hotel_id,
    last_status,
    COUNT(*) AS arrivals
FROM opera_analytics.reservation_last_status_daily
WHERE snapshot_date = CURRENT_DATE
  AND arrival_date = CURRENT_DATE
GROUP BY hotel_id, last_status
ORDER BY hotel_id, arrivals DESC;
```

## In-house y checked-out

```sql
SELECT
    hotel_id,
    last_status,
    COUNT(*) AS reservations
FROM opera_analytics.reservation_last_status_daily
WHERE snapshot_date = CURRENT_DATE
  AND last_status IN ('CHECKED_IN', 'CHECKED_OUT')
GROUP BY hotel_id, last_status
ORDER BY hotel_id, last_status;
```

## Segmentacion por mercado, canal y source

```sql
SELECT
    hotel_id,
    COALESCE(market_code, 'UNMAPPED') AS market_code,
    COALESCE(channel_code, 'UNMAPPED') AS channel_code,
    COALESCE(source_code, 'UNMAPPED') AS source_code,
    last_status,
    COUNT(*) AS reservations
FROM opera_analytics.reservation_last_status_daily
WHERE snapshot_date = CURRENT_DATE
GROUP BY
    hotel_id,
    COALESCE(market_code, 'UNMAPPED'),
    COALESCE(channel_code, 'UNMAPPED'),
    COALESCE(source_code, 'UNMAPPED'),
    last_status
ORDER BY reservations DESC;
```

## Consulta de una fecha pasada

Si negocio necesita consultar el informe tal como quedo en una fecha anterior:

```sql
SELECT
    hotel_id,
    reservation_id,
    confirmation_no,
    arrival_date,
    departure_date,
    last_status,
    last_status_event_at
FROM opera_analytics.reservation_last_status_daily
WHERE snapshot_date = DATE '2026-08-05'
ORDER BY hotel_id, arrival_date, reservation_id;
```

## Recomendacion operativa

Ejecuta `ohip-analytics-snapshot` una vez al dia despues del cierre operativo o en la hora acordada con negocio. El mismo job refresca:

- `opera_analytics.reservation_daily_snapshot`
- `opera_analytics.reservation_last_status_daily`
- `opera_analytics.pickup_metric`

Los dashboards de `last status` deben leer desde `reservation_last_status_daily` o desde `v_reservation_last_status_current`, no desde `reservation_daily_snapshot`, porque esta ultima tiene granularidad por noche de estancia.
