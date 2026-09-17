# Analitica PMS: snapshots diarios y pickups

Para analitica de negocio sobre OPERA Cloud PMS, los pickups de 1, 3, 7 y 15 dias deben calcularse sobre snapshots diarios materializados y estables.

La arquitectura de streaming captura la materia prima:

- `opera_events.event`: historico de eventos, estado y errores.
- `opera_raw.resource_snapshot`: respuesta JSON completa recuperada desde OHIP.
- `opera_core`: estado relacional normalizado mas reciente.

Pero `opera_core` representa el estado actual por UPSERT. Para analizar como cambiaron las reservas entre dos fechas de observacion, se anade una capa analitica:

```text
EventBridge diario
  -> ECS analytics-snapshot-job
  -> lee opera_core + ultimo opera_raw.resource_snapshot
  -> genera snapshot diario
  -> guarda opera_analytics.reservation_daily_snapshot
  -> refresca opera_analytics.pickup_metric
```

## Query base: pickup 1, 3, 7 y 15 dias

```sql
SELECT
    today.hotel_id,
    today.stay_date,
    today.market_code,
    today.channel_code,
    SUM(today.rooms - COALESCE(d1.rooms, 0)) AS pickup_rooms_1d,
    SUM(today.rooms - COALESCE(d3.rooms, 0)) AS pickup_rooms_3d,
    SUM(today.rooms - COALESCE(d7.rooms, 0)) AS pickup_rooms_7d,
    SUM(today.rooms - COALESCE(d15.rooms, 0)) AS pickup_rooms_15d
FROM opera_analytics.reservation_daily_snapshot today
LEFT JOIN opera_analytics.reservation_daily_snapshot d1
  ON d1.hotel_id = today.hotel_id
 AND d1.reservation_id = today.reservation_id
 AND d1.stay_date = today.stay_date
 AND d1.snapshot_date = today.snapshot_date - INTERVAL '1 day'
LEFT JOIN opera_analytics.reservation_daily_snapshot d3
  ON d3.hotel_id = today.hotel_id
 AND d3.reservation_id = today.reservation_id
 AND d3.stay_date = today.stay_date
 AND d3.snapshot_date = today.snapshot_date - INTERVAL '3 days'
LEFT JOIN opera_analytics.reservation_daily_snapshot d7
  ON d7.hotel_id = today.hotel_id
 AND d7.reservation_id = today.reservation_id
 AND d7.stay_date = today.stay_date
 AND d7.snapshot_date = today.snapshot_date - INTERVAL '7 days'
LEFT JOIN opera_analytics.reservation_daily_snapshot d15
  ON d15.hotel_id = today.hotel_id
 AND d15.reservation_id = today.reservation_id
 AND d15.stay_date = today.stay_date
 AND d15.snapshot_date = today.snapshot_date - INTERVAL '15 days'
WHERE today.snapshot_date = CURRENT_DATE
  AND today.reservation_status NOT IN ('CANCELLED', 'NO_SHOW')
GROUP BY today.hotel_id, today.stay_date, today.market_code, today.channel_code
ORDER BY today.hotel_id, today.stay_date;
```

## Pickup de revenue y ADR a 7 dias

```sql
SELECT
    today.hotel_id,
    today.stay_date,
    today.market_code,
    SUM(today.room_revenue - COALESCE(old.room_revenue, 0)) AS pickup_room_revenue_7d,
    SUM(today.rooms - COALESCE(old.rooms, 0)) AS pickup_rooms_7d,
    CASE
        WHEN SUM(today.rooms - COALESCE(old.rooms, 0)) = 0 THEN NULL
        ELSE SUM(today.room_revenue - COALESCE(old.room_revenue, 0))
             / SUM(today.rooms - COALESCE(old.rooms, 0))
    END AS pickup_adr_7d
FROM opera_analytics.reservation_daily_snapshot today
LEFT JOIN opera_analytics.reservation_daily_snapshot old
  ON old.hotel_id = today.hotel_id
 AND old.reservation_id = today.reservation_id
 AND old.stay_date = today.stay_date
 AND old.snapshot_date = today.snapshot_date - INTERVAL '7 days'
WHERE today.snapshot_date = CURRENT_DATE
GROUP BY today.hotel_id, today.stay_date, today.market_code
ORDER BY today.hotel_id, today.stay_date, today.market_code;
```

## Rooms on the books

```sql
SELECT
    hotel_id,
    stay_date,
    SUM(rooms) AS rooms_on_books,
    SUM(room_revenue) AS room_revenue_on_books,
    CASE WHEN SUM(rooms) = 0 THEN NULL ELSE SUM(room_revenue) / SUM(rooms) END AS adr_on_books
FROM opera_analytics.reservation_daily_snapshot
WHERE snapshot_date = CURRENT_DATE
  AND reservation_status NOT IN ('CANCELLED', 'NO_SHOW')
GROUP BY hotel_id, stay_date
ORDER BY hotel_id, stay_date;
```

## Pickup por canal, mercado y source

```sql
SELECT
    today.hotel_id,
    today.channel_code,
    today.market_code,
    today.source_code,
    SUM(today.rooms - COALESCE(old.rooms, 0)) AS pickup_rooms_15d,
    SUM(today.total_revenue - COALESCE(old.total_revenue, 0)) AS pickup_total_revenue_15d
FROM opera_analytics.reservation_daily_snapshot today
LEFT JOIN opera_analytics.reservation_daily_snapshot old
  ON old.hotel_id = today.hotel_id
 AND old.reservation_id = today.reservation_id
 AND old.stay_date = today.stay_date
 AND old.snapshot_date = today.snapshot_date - INTERVAL '15 days'
WHERE today.snapshot_date = CURRENT_DATE
  AND today.stay_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days'
GROUP BY today.hotel_id, today.channel_code, today.market_code, today.source_code
ORDER BY pickup_total_revenue_15d DESC;
```

## Cancelaciones desde el snapshot de hace 7 dias

```sql
SELECT
    today.hotel_id,
    today.stay_date,
    today.market_code,
    COUNT(*) AS cancellations_since_7d,
    SUM(COALESCE(old.room_revenue, 0)) AS cancelled_room_revenue_since_7d
FROM opera_analytics.reservation_daily_snapshot today
JOIN opera_analytics.reservation_daily_snapshot old
  ON old.hotel_id = today.hotel_id
 AND old.reservation_id = today.reservation_id
 AND old.stay_date = today.stay_date
 AND old.snapshot_date = today.snapshot_date - INTERVAL '7 days'
WHERE today.snapshot_date = CURRENT_DATE
  AND today.reservation_status IN ('CANCELLED', 'NO_SHOW')
  AND old.reservation_status NOT IN ('CANCELLED', 'NO_SHOW')
GROUP BY today.hotel_id, today.stay_date, today.market_code
ORDER BY today.hotel_id, today.stay_date;
```

## Recomendacion operativa

Ejecuta el `analytics-snapshot-job` una vez al dia, despues del cierre operativo nocturno o en la ventana acordada con negocio. Para hoteles con operacion 24 horas, define explicitamente la hora de corte, por ejemplo `snapshot_date = business_date` y `snapshot_taken_at = now()`.

El dashboard debe leer preferentemente de `opera_analytics.pickup_metric` para informes recurrentes, y de `opera_analytics.reservation_daily_snapshot` para analisis ad hoc.


## Relacion con last status

`last status` es una necesidad analitica distinta a pickups. Pickups compara snapshots entre fechas; `last status` muestra el ultimo estado diario de una reserva unica en la fecha de ejecucion del informe.

Para informes de estado de reservas, usa `opera_analytics.reservation_last_status_daily` o `opera_analytics.v_reservation_last_status_current`. La documentacion y queries estan en [analytics-last-status.md](analytics-last-status.md).
