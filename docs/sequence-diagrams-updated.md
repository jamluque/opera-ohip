# Diagramas de secuencia actualizados

## Secuencia analitica

```mermaid
sequenceDiagram
    participant EB as EventBridge
    participant JOB as ECS Analytics Task
    participant SEC as Secrets Manager
    participant DB as Aurora PostgreSQL
    participant CORE as opera_core.reservation
    participant RAW as opera_raw.resource_snapshot
    participant SNAP as reservation_daily_snapshot
    participant LAST as reservation_last_status_daily
    participant PICK as pickup_metric
    participant CW as CloudWatch
    participant BI as BI / Analistas

    EB->>JOB: Trigger diario snapshot_date = fecha informe
    JOB->>SEC: Carga DATABASE_URL/settings
    SEC-->>JOB: Secret values
    JOB->>DB: Abre transaccion
    DB->>CORE: SELECT reservas horizonte
    DB->>RAW: LEFT JOIN ultimo payload raw
    DB->>SNAP: DELETE/INSERT daily snapshot
    DB->>LAST: Compacta reserva unica sin filtrar CANCELLED/NO_SHOW
    DB->>PICK: Refresca pickups 1/3/7/15
    DB-->>JOB: Commit OK
    JOB->>CW: Logs y metricas
    BI->>LAST: Consulta last status diario
    BI->>PICK: Consulta pickups
```

## Secuencia event-enricher

```mermaid
sequenceDiagram
    participant SQS as SQS FIFO
    participant PROC as SQSMessageProcessor
    participant PARSER as OperaEventParser
    participant SVC as OperaEnrichmentService
    participant ROUTER as EventRouter
    participant RES as IdentifierResolver
    participant CLIENT as OHIPClient
    participant API as OHIP Property APIs
    participant DB as Aurora PostgreSQL
    participant REPO as Repositories/Transformers
    participant DLQ as SQS DLQ

    SQS->>PROC: ReceiveMessage long polling
    PROC->>PARSER: Parse OperaBusinessEvent
    PARSER-->>PROC: Evento normalizado
    PROC->>SVC: enrich(event)
    SVC->>ROUTER: route_for(moduleName,eventName)
    SVC->>RES: resolve primaryKey/detail fields
    SVC->>CLIENT: fetch(operation_id, identifier)
    CLIENT->>API: GET reservation/profile/folio/transaction
    API-->>CLIENT: Payload JSON / HTTP error
    SVC->>DB: Open transaction
    DB->>REPO: register_event UNIQUE uniqueEventId
    DB->>REPO: save opera_raw.resource_snapshot
    DB->>REPO: transform + UPSERT opera_core
    REPO-->>DB: mark COMPLETED + commit
    PROC->>SQS: DeleteMessage solo si commit OK
    PROC-->>DLQ: Fallos no recuperables / maxReceiveCount
```

## Secuencia general end-to-end

```mermaid
sequenceDiagram
    participant OPERA as OPERA Cloud PMS
    participant STREAM as OHIP Streaming
    participant LIS as ECS Listener
    participant SQS as SQS FIFO/DLQ
    participant ENR as ECS Event Enricher
    participant API as OHIP Property APIs
    participant S3 as S3 Raw Bucket
    participant DB as Aurora PostgreSQL
    participant JOB as ECS Analytics Job
    participant BI as BI / Analistas

    OPERA->>STREAM: Business Event
    LIS->>STREAM: connection_init Authorization + x-app-key
    STREAM-->>LIS: connection_ack
    LIS->>STREAM: subscribe newEvent(chainCode, offset opcional)
    STREAM->>LIS: next newEvent metadata.offset/uniqueEventId
    LIS->>SQS: SendMessage FIFO uniqueEventId
    LIS->>S3: Save offset/cursor
    SQS->>ENR: ReceiveMessage
    ENR->>API: GET resource details
    API-->>ENR: Payload JSON
    ENR->>S3: Store raw event/resource JSON
    ENR->>DB: UPSERT event/raw/core
    ENR->>SQS: DeleteMessage after commit
    JOB->>DB: Daily snapshot job
    DB-->>JOB: Core + raw metadata
    JOB->>DB: Materialize snapshots, pickups and last status
    BI->>DB: SQL dashboards
```

## Secuencia ECS listener

```mermaid
sequenceDiagram
    participant ECS as ECS Task listener.py
    participant SEC as Secrets Manager
    participant HM as Health/Metrics
    participant OFF as S3OffsetStore
    participant OAUTH as OAuthClient
    participant TOKEN as OHIP Token Endpoint
    participant WS as OHIP Streaming WebSocket
    participant PARSE as parse_ohip_event
    participant SQS as SQS FIFO
    participant CW as CloudWatch

    ECS->>SEC: load_secret_into_environment
    SEC-->>ECS: OHIP credentials + config
    ECS->>HM: start /live /ready + metrics
    ECS->>OFF: load(subscription_name)
    OFF-->>ECS: last offset / uniqueEventId
    ECS->>OAUTH: request access token
    OAUTH->>TOKEN: client_credentials
    TOKEN-->>OAUTH: access_token
    ECS->>WS: open wss /subscriptions?key=sha256(app key)
    ECS->>WS: connection_init Authorization + x-app-key
    WS-->>ECS: connection_ack
    ECS->>WS: subscribe newEvent(chainCode, offset opcional)
    ECS->>WS: ping cada 15s
    WS-->>ECS: pong / next events
    ECS->>PARSE: parse raw event
    ECS->>SQS: publish with MessageDeduplicationId=uniqueEventId
    ECS->>OFF: save offset + uniqueEventId
    ECS->>CW: metrics/logs last_event_timestamp
    ECS->>WS: complete con subscription id antes de cerrar
    WS-->>ECS: disconnect/error
    ECS->>WS: reconnect exponential backoff + jitter
```

Notas Oracle Streaming:

- Solo debe existir una suscripcion activa por `applicationKey + gateway URL + chainCode`.
- Si el listener no reconecta en 24 horas, debe enviar el ultimo `offset` guardado.
- OHIP conserva eventos para replay durante 7 dias.
