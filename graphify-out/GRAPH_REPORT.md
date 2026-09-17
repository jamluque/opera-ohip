# Graph Report - opera-ohip  (2026-08-21)

## Corpus Check
- 103 files · ~231,036 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 596 nodes · 1382 edges · 31 communities (24 shown, 7 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 236 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 32|Community 32]]

## God Nodes (most connected - your core abstractions)
1. `_run_e2e_async()` - 34 edges
2. `OperaEnrichmentService` - 30 edges
3. `OperaBusinessEvent` - 30 edges
4. `OperaEventParser` - 27 edges
5. `SQSMessageProcessor` - 26 edges
6. `EnrichmentResult` - 24 edges
7. `IdentifierResolver` - 24 edges
8. `OHIPClient` - 24 edges
9. `Settings` - 21 edges
10. `EnrichmentPoisonError` - 21 edges

## Surprising Connections (you probably didn't know these)
- `LocalOhipClient` --uses--> `AnalyticsSettings`  [INFERRED]
  scripts/perf_streaming_e2e.py → src/ohip_bridge/analytics_snapshot.py
- `LocalOhipClient` --uses--> `AnalyticsSnapshotJob`  [INFERRED]
  scripts/perf_streaming_e2e.py → src/ohip_bridge/analytics_snapshot.py
- `LocalOhipClient` --uses--> `OperaEnrichmentService`  [INFERRED]
  scripts/perf_streaming_e2e.py → src/ohip_bridge/enrichment_service.py
- `LocalOhipClient` --uses--> `EventRouter`  [INFERRED]
  scripts/perf_streaming_e2e.py → src/ohip_bridge/event_router.py
- `LocalOhipClient` --uses--> `OhipStreamingClient`  [INFERRED]
  scripts/perf_streaming_e2e.py → src/ohip_bridge/graphql.py

## Import Cycles
- None detected.

## Communities (31 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (34): BaseSettings, LogRecord, BootstrapSettings, get_bootstrap_settings(), get_settings(), _event_from_message(), main(), run() (+26 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (34): EventRepository, RuntimeError, Settings, EventRepository, Any, datetime, RawSnapshotRepository, EnrichmentPoisonError (+26 more)

### Community 2 - "Community 2"
Cohesion: 0.14
Nodes (14): Decimal, AnalyticsSettings, AnalyticsSnapshotJob, main(), Any, Connection, date, ReservationSnapshotRow (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (17): AsyncClient, LocalOhipClient, Settings, OAuthClient, OAuthToken, Settings, OAuthTokenProvider, OHIPClient (+9 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (24): InfrastructureMonitor, CloudWatchMetrics, MetricPoint, main(), run(), Path, start_metrics_server(), OperaEventParser (+16 more)

### Community 5 - "Community 5"
Cohesion: 0.20
Nodes (13): build_mxfile(), DrawioPage, esc(), main(), page_analytics_sequence(), page_end_to_end_sequence(), page_enricher_sequence(), page_listener_sequence() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.24
Nodes (15): box_label(), build_mxfile(), DrawioPage, main(), page_architecture(), page_daily_flow(), page_functional(), page_infrastructure() (+7 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (34): Analitica PMS: last status de reservas, Canceladas y no-show incluidas, Consulta de una fecha pasada, Definicion funcional, Detalle de reservas con su ultimo estado, In-house y checked-out, Last status por hotel, Llegadas del dia por ultimo estado (+26 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (24): Analitica PMS: snapshots y pickups, Componentes Python, Configuracion OHIP y OPERA Cloud, Despliegue AWS con Terraform, Despliegue ECS del enricher, Diagnostico rapido, DLQ y reintentos, Ejecucion local (+16 more)

### Community 10 - "Community 10"
Cohesion: 0.35
Nodes (15): arrow(), box(), canvas(), font(), main(), FreeTypeFont, Image, ImageDraw (+7 more)

### Community 11 - "Community 11"
Cohesion: 0.31
Nodes (13): arrow(), box(), font(), main(), FreeTypeFont, Image, ImageDraw, render() (+5 more)

### Community 12 - "Community 12"
Cohesion: 0.31
Nodes (13): arrow(), badge(), box(), font(), main(), FreeTypeFont, Image, ImageDraw (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.25
Nodes (7): OhipStreamingClient, Any, settings(), test_connection_init_carries_oracle_auth_payload(), test_default_subscription_uses_new_event_and_saved_offset(), test_extract_payloads_reads_new_event(), WebSocketClientProtocol

### Community 14 - "Community 14"
Cohesion: 0.25
Nodes (4): BaseHTTPRequestHandler, _HealthHandler, HealthState, Any

### Community 15 - "Community 15"
Cohesion: 0.09
Nodes (52): Lock, Random, _apply_migrations(), _chunked(), _configure_local_aws(), _consume(), _consume_optimized(), count_new_event_ids() (+44 more)

### Community 16 - "Community 16"
Cohesion: 0.20
Nodes (9): Configuracion, Conteos finales en PostgreSQL, E2E concurrente OPERA OHIP - 200000 registros, Grafo del flujo con tiempos, Notas, Recursos observados, Resultado global, Tabla de inicio a fin (+1 more)

### Community 17 - "Community 17"
Cohesion: 0.20
Nodes (9): Comprobacion Local, Ejemplo 1: Reserva Actualizada, Ejemplo 2: Perfil Actualizado, Ejemplo 3: Folio Actualizado, Ejemplo 4: Detalle De Transaccion, Ejemplo 5: Cancelacion Con Recurso Ya No Disponible, Flujo Definido En El Proyecto, Metodos Cubiertos (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.33
Nodes (5): Diagramas de secuencia actualizados, Secuencia analitica, Secuencia ECS listener, Secuencia event-enricher, Secuencia general end-to-end

### Community 19 - "Community 19"
Cohesion: 0.40
Nodes (4): Arquitectura end-to-end, Diagramas actualizados - OPERA Cloud Analytics con last status, Flujo diario, Vista funcional

### Community 20 - "Community 20"
Cohesion: 0.40
Nodes (4): AWS_ACCESS_KEY_ID, AWS_DEFAULT_REGION, AWS_SECRET_ACCESS_KEY, init-local-aws.sh script

### Community 27 - "Community 27"
Cohesion: 0.29
Nodes (6): Global Constraints, Oracle OHIP Streaming Compliance Implementation Plan, Task 1: Oracle Streaming Subscription, Task 2: Connection Init, Complete, and Payload Extraction, Task 3: REST Trace Headers, Task 4: Defaults and Operator Notes

### Community 28 - "Community 28"
Cohesion: 0.32
Nodes (5): EventRepository, Any, Connection, datetime, Settings

### Community 29 - "Community 29"
Cohesion: 0.38
Nodes (3): Any, Settings, S3OffsetStore

### Community 32 - "Community 32"
Cohesion: 0.67
Nodes (3): Path, test_docker_compose_allows_postgres_port_override(), test_init_local_aws_passes_redrive_policy_as_json()

## Knowledge Gaps
- **86 isolated node(s):** `opera-ohip-streaming-aws`, `init-local-aws.sh script`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (+81 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_run_e2e_async()` connect `Community 15` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 13`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `OperaEnrichmentService` connect `Community 1` to `Community 0`, `Community 3`, `Community 4`, `Community 15`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `Settings` connect `Community 1` to `Community 0`, `Community 3`, `Community 4`, `Community 13`, `Community 28`, `Community 29`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `_run_e2e_async()` (e.g. with `AnalyticsSettings` and `AnalyticsSnapshotJob`) actually correct?**
  _`_run_e2e_async()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `OperaEnrichmentService` (e.g. with `InfrastructureMonitor` and `LocalOhipClient`) actually correct?**
  _`OperaEnrichmentService` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `OperaBusinessEvent` (e.g. with `EventRepository` and `RawSnapshotRepository`) actually correct?**
  _`OperaBusinessEvent` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `OperaEventParser` (e.g. with `InfrastructureMonitor` and `LocalOhipClient`) actually correct?**
  _`OperaEventParser` has 16 INFERRED edges - model-reasoned connections that need verification._