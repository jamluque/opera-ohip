# Diagrama detallado de infraestructura y flujos

```mermaid
flowchart LR
    subgraph ORA["Oracle Hospitality"]
        OPERA["OPERA Cloud PMS<br/>Business Events"]
        OHIP["OHIP<br/>OAuth, Streaming API, Property APIs"]
        OPERA --> OHIP
    end

    subgraph AWS["AWS Account / Region"]
        subgraph VPC["VPC multi-AZ"]
            subgraph PUB["Subredes publicas"]
                IGW["Internet Gateway"]
                NAT["NAT Gateway"]
                RT["Public route table"]
            end

            subgraph PRIV["Subredes privadas ECS"]
                LISTENER["ECS Fargate Listener<br/>WebSocket, heartbeat, offsets"]
                FIFO["SQS FIFO<br/>uniqueEventId dedupe"]
                DLQ["SQS DLQ<br/>errores tras reintentos"]
                ENRICHER["ECS Event Enricher<br/>OHIP Property APIs"]
                ANALYTICS["ECS Analytics Snapshot Job<br/>diario"]
            end

            subgraph DATA["Capa de datos"]
                S3["S3 Raw<br/>eventos, snapshots raw, offsets"]
                AURORA["Aurora PostgreSQL<br/>opera_events, opera_raw, opera_core"]
                SNAP["reservation_daily_snapshot<br/>reserva + stay_date"]
                LAST["reservation_last_status_daily<br/>reserva unica"]
                PICKUP["pickup_metric<br/>1, 3, 7, 15 dias"]
            end

            subgraph SUPPORT["Soporte, seguridad y observabilidad"]
                SECRETS["Secrets Manager"]
                KMS["KMS"]
                IAM["IAM roles least privilege"]
                ECR["ECR Docker images"]
                CW["CloudWatch logs, metrics, alarms"]
                EB["EventBridge schedule"]
                VPCE["VPC Endpoints<br/>S3, SQS, ECR, Logs, Secrets"]
            end
        end

        BI["BI / Analistas<br/>dashboards y SQL"]
    end

    OHIP -- "1 Streaming WebSocket newEvent" --> LISTENER
    LISTENER -- "2 SendMessage FIFO" --> FIFO
    FIFO -- "3 ReceiveMessage" --> ENRICHER
    FIFO -- "redrive" --> DLQ
    ENRICHER -- "4 raw JSON" --> S3
    ENRICHER -- "5 upsert idempotente" --> AURORA
    ENRICHER -- "OHIP Property APIs via NAT" --> NAT
    NAT --> OHIP
    EB -- "6 schedule diario" --> ANALYTICS
    ANALYTICS --> AURORA
    ANALYTICS --> S3
    ANALYTICS -- "7 snapshot diario" --> SNAP
    ANALYTICS -- "8 last status" --> LAST
    SNAP -- "9 pickups" --> PICKUP
    LAST --> BI
    PICKUP --> BI
    SNAP --> BI
    SECRETS --> LISTENER
    SECRETS --> ENRICHER
    SECRETS --> ANALYTICS
    KMS --> SECRETS
    IAM --> LISTENER
    IAM --> ENRICHER
    IAM --> ANALYTICS
    ECR --> LISTENER
    ECR --> ENRICHER
    ECR --> ANALYTICS
    CW --> BI
    VPCE --> S3
    VPCE --> FIFO
```

## Secuencia principal

```mermaid
sequenceDiagram
    participant OPERA as OPERA Cloud PMS
    participant OHIP as OHIP Streaming/API
    participant LIS as ECS Listener
    participant SQS as SQS FIFO
    participant ENR as ECS Event Enricher
    participant S3 as S3 Raw
    participant DB as Aurora PostgreSQL
    participant JOB as Analytics Job
    participant BI as BI / Analistas

    OPERA->>OHIP: Business Event
    LIS->>OHIP: WebSocket graphql-transport-ws + connection_init
    LIS->>OHIP: subscribe newEvent(chainCode, offset opcional)
    OHIP->>LIS: next newEvent metadata.offset/uniqueEventId
    LIS->>SQS: SendMessage(uniqueEventId)
    SQS->>ENR: ReceiveMessage long polling
    ENR->>OHIP: Consulta Property API con identificador funcional
    ENR->>S3: Guarda payload raw JSON
    ENR->>DB: UPSERT opera_events/opera_raw/opera_core
    ENR->>SQS: DeleteMessage si commit OK
    JOB->>DB: Lee opera_core + raw metadata
    JOB->>DB: Materializa reservation_daily_snapshot
    JOB->>DB: Materializa reservation_last_status_daily
    JOB->>DB: Refresca pickup_metric
    BI->>DB: Consulta snapshots, pickups y last status
```

El listener usa `wss://<gateway>/subscriptions?key=<sha256 application key>`, envia `connection_init` con `Authorization` y `x-app-key`, mantiene `ping/pong` cada 15 segundos y envia `complete` antes de cerrar una suscripcion. Para evitar `4409`, no ejecutes dos listeners contra el mismo `applicationKey + gateway URL + chainCode`.
