# OPERA Cloud OHIP Streaming API -> AWS BYOD Lakehouse

Proyecto Python para recibir eventos de OPERA Cloud por OHIP Streaming API, publicarlos en SQS FIFO, procesarlos en ECS Fargate, guardar el payload raw en S3 y persistir una vista idempotente en Aurora PostgreSQL.

La arquitectura queda asi:

```text
OPERA Cloud Business Events
        |
        v
OHIP Streaming API WebSocket graphql-transport-ws
        |
        v
ECS Fargate listener
  - OAuth client_credentials
  - application key SHA256 en query string
  - ping/pong heartbeat
  - reconexion exponencial
  - offsets en S3
        |
        v
SQS FIFO + DLQ
  - MessageDeduplicationId = uniqueEventId
  - MessageGroupId = opera-ohip-stream
        |
        v
ECS Fargate consumer
  - long polling
  - retries por visibilidad SQS
  - DLQ por redrive policy
        |
        +--> S3 raw JSON
        |
        +--> Aurora PostgreSQL
             - UNIQUE(unique_event_id)
             - INSERT ON CONFLICT DO NOTHING
```

## Estructura

```text
.
├── src/ohip_bridge/          # Codigo Python productivo
├── tests/                    # Pruebas unitarias
├── examples/ohip-business-events/
│                              # Business Events sinteticos para pruebas locales
├── db/migrations/            # SQL inicial de Aurora/PostgreSQL
├── terraform/                # AWS: VPC, ECS, ECR, SQS, S3, Aurora, IAM, CloudWatch
├── docs/ohip-setup.md        # Guia OHIP Developer Portal + OPERA Cloud
├── Dockerfile.listener       # Imagen ECS listener
├── Dockerfile.consumer       # Imagen ECS consumer
├── docker-compose.yml        # PostgreSQL + LocalStack para desarrollo local
├── .env.example              # Variables placeholder
└── pyproject.toml
```

## Componentes Python

- `listener`: abre el WebSocket OHIP con subprotocolo `graphql-transport-ws`, obtiene OAuth, mantiene heartbeat ping/pong, reconecta, persiste offset en S3 y publica a SQS FIFO.
- `consumer`: lee SQS con long polling, escribe el evento raw en S3, inserta en PostgreSQL con idempotencia por `unique_event_id` y borra el mensaje solo si todo termina bien.
- `health`: expone `/live` y `/ready` para health checks ECS.
- `metrics`: expone metricas Prometheus en `:9100`.
- `logging`: logs JSON para CloudWatch.

## Variables principales

Copia `.env.example` a `.env` para local. En AWS, guarda los valores OHIP en Secrets Manager.

Placeholders requeridos:

- `OHIP_GATEWAY_URL`
- `OHIP_STREAMING_WS_URL`
- `OHIP_TOKEN_URL`
- `OHIP_APPLICATION_KEY`
- `OHIP_CLIENT_ID`
- `OHIP_CLIENT_SECRET`
- `OHIP_ENTERPRISE_ID`
- `OHIP_SCOPE`
- `OHIP_CHAIN_CODE`
- `OHIP_HOTEL_IDS`
- `OHIP_EXTERNAL_SYSTEM_CODE`

No incluyas secretos reales en `.env.example`, `terraform/example.tfvars` ni README.

## Ejecucion local

1. Instala dependencias:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

2. Levanta servicios locales:

```bash
docker compose up -d postgres localstack
./scripts/init-local-aws.sh
```

3. Aplica el SQL si no usas el init automatico de Docker:

```bash
psql postgresql://app_user:app_password@localhost:5432/opera_ohip -f db/migrations/001_init.sql
```

4. Ejecuta pruebas:

```bash
pytest
```

5. Ejecuta el consumer local contra LocalStack ajustando `.env` a tus endpoints locales.

El listener requiere credenciales OHIP validas y acceso al gateway WebSocket real.

### Prueba E2E de rendimiento local

Con PostgreSQL y LocalStack levantados, el harness E2E publica eventos sinteticos en SQS FIFO, los consume, enriquece contra un cliente OHIP local, persiste en PostgreSQL y ejecuta el snapshot analitico:

```bash
PYTHONPATH=src:.python-packages:. python3 scripts/perf_streaming_e2e.py \
  --messages 100000 \
  --min-seconds 0.1 \
  --max-seconds 0.5 \
  --min-batch-size 100 \
  --max-batch-size 1000 \
  --seed 7 \
  --optimized \
  --timeout-seconds 3600 \
  --output outputs/streaming-e2e-concurrent-100000-report.json
```

El modo `--optimized` usa publicacion SQS por lotes, particiones de `MessageGroupId`, workers concurrentes y persistencia PostgreSQL por lotes. Sin `--no-realtime`, el harness simula llegada progresiva desde el WebSocket y consume SQS mientras publica. El reporte actual de referencia esta en `outputs/streaming-e2e-concurrent-100000-report.json`.

## Despliegue AWS con Terraform

1. Prepara imagenes y ECR. Terraform crea los repositorios ECR, por lo que el primer ciclo habitual es:

```bash
cd terraform
terraform init
terraform apply -target=aws_ecr_repository.listener -target=aws_ecr_repository.consumer
terraform output listener_repository_url
terraform output consumer_repository_url
```

2. Construye y sube imagenes:

```bash
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.eu-west-1.amazonaws.com

docker build -f Dockerfile.listener -t <listener-repo>:0.1.0 .
docker build -f Dockerfile.consumer -t <consumer-repo>:0.1.0 .
docker push <listener-repo>:0.1.0
docker push <consumer-repo>:0.1.0
```

3. Crea un `terraform.tfvars` privado a partir de `terraform/example.tfvars` y reemplaza solo placeholders. No lo commits.

4. Despliega infraestructura completa:

```bash
cd terraform
terraform plan
terraform apply
```

5. Aplica migracion en Aurora. Puedes hacerlo desde una tarea administrativa en la misma VPC, un bastion/VPN autorizado o un job temporal:

```bash
psql "$DATABASE_URL" -f db/migrations/001_init.sql
```

## Seguridad e IAM minimo

Terraform crea roles separados:

- Listener: `sqs:SendMessage`, `s3:GetObject/PutObject` solo para offsets, `secretsmanager:GetSecretValue`, KMS necesario.
- Consumer: `sqs:ReceiveMessage/DeleteMessage/GetQueueAttributes/ChangeMessageVisibility`, `s3:PutObject` solo para raw events, `secretsmanager:GetSecretValue`, KMS necesario.
- Aurora: solo acepta conexiones desde el security group de ECS.
- ECS corre en subredes privadas, con salida por NAT para llegar a OHIP y servicios AWS.

## DLQ y reintentos

SQS FIFO usa `maxReceiveCount = 5`. Si el consumer falla repetidamente, no borra el mensaje; SQS lo reentrega hasta moverlo a la DLQ. La idempotencia se mantiene en dos capas:

- SQS FIFO: `MessageDeduplicationId = uniqueEventId`.
- PostgreSQL: `UNIQUE(unique_event_id)` con `ON CONFLICT DO NOTHING`.

## Offsets

El listener guarda el ultimo offset conocido en S3:

```text
s3://<raw-bucket>/ohip/offsets/<subscription-name>.json
```

Si el payload OHIP no trae `offset`, se guarda igualmente el ultimo `uniqueEventId`. Ajusta la extraccion en `events.py` si el esquema de tu tenant usa otro campo para cursor/secuencia.

## Query GraphQL

El proyecto incluye una suscripcion base `newEvent` en `src/ohip_bridge/graphql.py` alineada con Oracle OHIP Streaming: `metadata.offset`, `metadata.uniqueEventId`, `eventName`, `primaryKey`, `hotelId` y `detail`. Como Oracle publica el esquema de Streaming en GitHub y puede variar por version/tenant, puedes montar un archivo propio y configurar:

```bash
OHIP_SUBSCRIPTION_QUERY_FILE=/app/config/ohip-subscription.graphql
```

Notas operativas:

- Mantener una sola conexion activa por `applicationKey + gateway URL + chainCode`.
- El listener envia `connection_init` con `Authorization` y `x-app-key`, responde `ping` con `pong`, envia `ping` cada 15 segundos y persiste el ultimo `offset` recibido.
- Si pruebas con Postman o GraphiQL, usa otra application key o detén el listener para evitar errores `4409`.
- Checklist de validacion: [docs/oracle-ohip-validation.md](docs/oracle-ohip-validation.md).
- Ejemplos sinteticos de Business Events consumibles: [docs/ohip-business-event-examples.md](docs/ohip-business-event-examples.md).

## Configuracion OHIP y OPERA Cloud

La guia detallada esta en `docs/ohip-setup.md`. Resumen:

1. En OHIP Developer Portal, crea la aplicacion, scope, client credentials y habilita Streaming API.
2. En OPERA Cloud, configura External System, por ejemplo `AWS_BYOD`.
3. Si OPERA lo requiere, crea External Database como codigo logico. No es Aurora, no pide host/puerto/credenciales.
4. Configura Business Events por property, modulo, action type y data elements.
5. Genera eventos de prueba y valida CloudWatch, SQS, S3 y Aurora.

## Referencias oficiales

- Oracle OHIP client runtime para Streaming API: https://docs.oracle.com/en/industries/hospitality/integration-platform/stmig/c_client_runtime.htm
- Repositorio oficial Oracle Hospitality API docs: https://github.com/oracle/hospitality-api-docs
- Esquema GraphQL Streaming: https://github.com/oracle/hospitality-api-docs/tree/main/graphql/streaming
- Business Events OPERA Cloud: https://docs.oracle.com/en/industries/hospitality/opera-cloud/25.1/ocsuh/t_admin_interfaces_configuring_business_events.htm
- Integration Processor API `getBusinessEvents`: https://github.com/oracle/hospitality-api-docs/blob/main/rest-api-specs/property/int.json

## Estado de primera version

Esta es una base ejecutable y clara para integracion real. Antes de produccion, confirma con tu tenant OHIP:

- URL exacta de OAuth y WebSocket.
- Cabeceras requeridas por tu gateway.
- Query GraphQL final segun `StreamingGraphQLSchema.json`.
- Nombre exacto del campo de offset/cursor.
- Modulos y Business Events suscritos en OPERA.


## Servicio Event Enricher

El proyecto incorpora un tercer servicio ECS: `event-enricher`. El flujo enriquecido recomendado queda asi:

```text
OHIP Streaming API
  -> ECS Listener
  -> SQS FIFO
  -> ECS Event Enricher
  -> OHIP Property APIs
  -> PostgreSQL opera_events/opera_raw/opera_core
```

El listener sigue usando `uniqueEventId` como `MessageDeduplicationId` de SQS FIFO. El enriquecedor nunca usa `uniqueEventId` para consultar OHIP Property APIs.

### Identificadores

| Campo | Uso correcto |
|---|---|
| `uniqueEventId` | Deduplicacion del mensaje e idempotencia del evento. |
| `offset` | Control de posicion, replay y restriccion adicional `chain_code + offset`. |
| `primaryKey` | Identificador inicial del recurso OPERA; puede representar distintos recursos. |
| `moduleName + eventName` | Selecciona que API OHIP debe invocarse. |
| `hotelId` | Contexto de propiedad y header `x-hotelid`. |

Para folios y transacciones, `primaryKey` no se asume siempre como `reservationId`. `IdentifierResolver` busca `reservationId`, `transactionNo`, `profileId` u otros identificadores en `primaryKey`, `detail[].elementName`, `detail[].newValue`, `detail[].oldValue` y metadatos del evento.

### Matriz evento -> API

| moduleName | eventName | Operation ID | API OHIP | Identificador |
|---|---|---|---|---|
| Reservation | `*` | `getReservation` | `GET /rsv/v1/hotels/{hotelId}/reservations/{primaryKey}` | `reservationId` |
| Profile | `*` | `getProfile` | `GET /crm/v1/profiles/{primaryKey}` | `profileId` |
| Cashiering | Folio | `getFolio` | `GET /csh/v1/hotels/{hotelId}/reservations/{reservationId}/folios` | `reservationId` |
| Cashiering | Transaction | `getFolioTransactionDetails` | `GET /csh/v1/hotels/{hotelId}/transactionDetails?transactionNo={primaryKey}` | `transactionNo` |

La configuracion esta en `config/event-router.yaml` y puede cambiarse con:

```bash
ENRICHER_ROUTER_CONFIG=config/event-router.yaml
```

El enriquecimiento por defecto es minimo:

```yaml
enrichment:
  reservation:
    fetch_reservation: true
    fetch_related_profiles: false
    fetch_folios: false
```

Las llamadas relacionadas, como perfiles o folios vinculados a una reserva, deben habilitarse de forma explicita para evitar multiplicar llamadas OHIP.

### Procesamiento transaccional

El `event-enricher` ejecuta estos pasos:

1. Lee un mensaje de SQS.
2. Registra el evento en `opera_events.event` si no existe.
3. Si el evento ya esta `COMPLETED`, borra el mensaje de SQS sin reprocesar.
4. Resuelve ruta e identificador funcional.
5. Consulta la OHIP Property API correspondiente.
6. Guarda la respuesta completa en `opera_raw.resource_snapshot`.
7. Transforma el JSON a tablas relacionales en `opera_core`.
8. Marca el evento como `COMPLETED`.
9. Confirma la transaccion PostgreSQL.
10. Solo entonces elimina el mensaje de SQS.

`opera_raw`, `opera_core` y el cambio de estado del evento se guardan dentro de la misma transaccion PostgreSQL.

### Migraciones PostgreSQL

Aplica ambas migraciones:

```bash
psql "$DATABASE_URL" -f db/migrations/001_init.sql
psql "$DATABASE_URL" -f db/migrations/002_enrichment.sql
```

La migracion `002_enrichment.sql` crea:

- `opera_events.event`
- `opera_raw.resource_snapshot`
- `opera_core.reservation`
- `opera_core.profile`
- `opera_core.folio`
- `opera_core.folio_transaction`

La idempotencia se implementa con `UNIQUE(unique_event_id)`, indice unico parcial por `chain_code + stream_offset`, y UPSERT funcional por claves como `(hotel_id, reservation_id)` o `(hotel_id, transaction_no)`. Los UPSERT evitan que un evento antiguo sobrescriba una version mas reciente usando `last_event_at`.

### Tratamiento de errores OHIP

| Caso | Comportamiento |
|---|---|
| 401 | Invalida token OAuth y reintenta una vez. |
| 404 en DELETE/CANCEL | Marca snapshot de recurso eliminado cuando procede. |
| 429 | Respeta `Retry-After`, cambia visibilidad SQS y no borra el mensaje. |
| 5xx | Reintento con backoff/SQS visibility timeout. |
| 400 o identificador irresoluble | Marca error; tras `ENRICHER_MAX_ATTEMPTS`, envia a DLQ y borra el original. |
| Fallo PostgreSQL antes de commit | No borra el mensaje SQS. |

### Ejecucion local del enricher

```bash
docker compose up -d postgres localstack
./scripts/init-local-aws.sh
psql postgresql://app_user:app_password@localhost:5432/opera_ohip -f db/migrations/001_init.sql
psql postgresql://app_user:app_password@localhost:5432/opera_ohip -f db/migrations/002_enrichment.sql
python -m ohip_bridge.event_enricher
```

Para construir la imagen:

```bash
docker build -f Dockerfile.enricher -t opera-ohip-enricher:local .
```

### Despliegue ECS del enricher

Terraform crea:

- ECR `opera-ohip-<env>-enricher`.
- ECS task definition y service `event-enricher` en subredes privadas.
- IAM minimo para SQS, DLQ, Secrets Manager, KMS, CloudWatch metrics y S3 raw opcional.
- Auto scaling por profundidad de SQS.
- Alarmas por DLQ con mensajes y antiguedad del mensaje mas antiguo.

Actualiza `terraform.tfvars` con `enricher_image_uri` y ejecuta:

```bash
terraform plan
terraform apply
```

### Diagnostico rapido

- 401 repetidos: revisar `client_id`, `client_secret`, scope, enterprise ID y application key.
- 404 en eventos no DELETE/CANCEL: revisar route/identifier resolver; puede estar usando `primaryKey` equivocado.
- 429: reducir concurrencia del ECS service o aumentar visibility timeout.
- DLQ con mensajes: inspeccionar `opera_events.event.error_message` y CloudWatch Logs `/ecs/<name>/enricher`.
- Eventos duplicados: confirmar `uniqueEventId` y el indice `opera_event_chain_offset_uk`.


## Analitica PMS: snapshots y pickups

Para analitica de negocio PMS, los pickups de 1, 3, 7 y 15 dias no deben depender solo de `opera_core`, porque `opera_core` guarda el estado actual mediante UPSERT. El proyecto incorpora una capa `opera_analytics` con snapshots diarios materializados y estables.

Flujo recomendado e implementado:

```text
EventBridge diario
  -> ECS analytics-snapshot-job
  -> lee opera_core + ultimo opera_raw.resource_snapshot
  -> genera snapshot diario
  -> guarda opera_analytics.reservation_daily_snapshot
  -> refresca opera_analytics.reservation_last_status_daily
  -> refresca opera_analytics.pickup_metric
```

La migracion [003_analytics_snapshots.sql](db/migrations/003_analytics_snapshots.sql) crea:

- `opera_analytics.reservation_daily_snapshot`
- `opera_analytics.pickup_metric`

La migracion [004_reservation_last_status.sql](db/migrations/004_reservation_last_status.sql) crea:

- `opera_analytics.reservation_last_status_daily`
- `opera_analytics.v_reservation_last_status_current`

El job se ejecuta con el entrypoint `ohip-analytics-snapshot` y la imagen [Dockerfile.analytics](Dockerfile.analytics). Terraform crea el ECR `analytics`, la task definition ECS y la regla EventBridge diaria configurada por `analytics_schedule_expression`.

Variables principales:

```bash
ANALYTICS_PICKUP_DAYS=1,3,7,15
ANALYTICS_STAY_HORIZON_DAYS=730
ANALYTICS_SNAPSHOT_DATE=2026-08-04  # opcional para backfill manual
```

Para ejecutar localmente:

```bash
psql "$DATABASE_URL" -f db/migrations/003_analytics_snapshots.sql
psql "$DATABASE_URL" -f db/migrations/004_reservation_last_status.sql
python -m ohip_bridge.analytics_snapshot
```

Los ejemplos de queries para analistas de negocio estan en [docs/analytics-pickups.md](docs/analytics-pickups.md): pickup de habitaciones, revenue, ADR, rooms on the books, segmentacion por canal/mercado/source y cancelaciones entre snapshots.

Para la funcionalidad `last status`, el informe debe leer de `opera_analytics.reservation_last_status_daily` o de la vista `opera_analytics.v_reservation_last_status_current`. Esta capa devuelve una fila unica por reserva para la fecha de ejecucion del informe e incluye reservas `CANCELLED` y `NO_SHOW` como ultimo estado. Los ejemplos funcionales estan en [docs/analytics-last-status.md](docs/analytics-last-status.md).
