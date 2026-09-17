# Enricher Correctness & Performance (Wave 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir la completitud del dato OHIP y el rendimiento del enricher con cambios mínimos, sin depender de decisiones de negocio/infra pendientes.

**Architecture:** Cuatro cambios independientes en la capa de aplicación del enricher: (1) pedir `fetchInstructions` a las Property APIs para que OPERA devuelva payloads completos; (2) detectar borrado/cancelación desde el `detail` del evento (OHIP no tiene `actionType`); (3) refresco de token OAuth *single-flight*; (4) pool de conexiones PostgreSQL. Cada uno es aislado y testeable por separado.

**Tech Stack:** Python 3.11+, httpx, psycopg + psycopg_pool (ya en dependencias), pytest, pytest-asyncio, ruff.

**Spec:** Base de entendimiento en memoria del proyecto (`target-functional-objective`, `ohip-api-reference`) + esquema OHIP autoritativo `oracle/hospitality-api-docs` y colecciones en `docs/ohip/postman/`. Endpoints y `fetchInstructions` verificados contra la colección `1. Property REST APIs By Module`.

## Global Constraints

- **Ponytail full:** solución mínima que funcione; nada de abstracciones especulativas ni dependencias nuevas (psycopg_pool ya viene con `psycopg[pool]`).
- **No borrado físico en Aurora** (invariante). Este plan no toca borrado; solo lo prepara al arreglar la detección de acción.
- **No tocar la vía v1 compartida** (`listener`, `sqs.py`, `config` fuera de los campos añadidos aquí). La retirada de v1 y la infra (SNS/Firehose) van en planes aparte.
- **Endpoints y fetchInstructions verbatim** de la colección Postman: getReservation `fetchInstructions=Reservation`; getProfile `Profile`+`Communication`; getFolios `Postings`+`Totalbalance`+`Transactioncodes`+`Windowbalances`; getFolioTransactionDetails `includeGenerates=true`.
- Commits pequeños y frecuentes; ejecutar `ruff check .` antes de cada commit.

---

### Task 1: `fetchInstructions` en OHIPClient (completitud del dato)

**Problema:** `ohip_client.py` no envía `fetchInstructions`, así que OPERA devuelve reservas/perfiles/folios mínimos. Es la causa raíz del `opera_core` "fino".

**Files:**
- Modify: `src/ohip_bridge/ohip_client.py` (métodos `get_reservation`, `get_profile`, `get_folios`, `get_transaction_details`)
- Test: `tests/test_ohip_client.py`

**Interfaces:**
- Consumes: `OHIPClient._request(method: str, path: str, hotel_id: str | None, params: dict | None)` (ya forwarda `params` a httpx; los valores lista se serializan como parámetros repetidos).
- Produces: mismos métodos con la misma firma pública; solo cambian los `params` enviados.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ohip_client.py  (añadir; reutiliza settings() y FakeTokenProvider ya presentes en este módulo)
import httpx
import pytest
from ohip_bridge.ohip_client import OHIPClient


class _Recorder:
    def __init__(self):
        self.calls = []

    async def request(self, method, url, headers=None, params=None):
        self.calls.append((method, url, params))
        return httpx.Response(200, json={"reservation": {}})


@pytest.mark.asyncio
async def test_get_reservation_sends_fetch_instructions():
    rec = _Recorder()
    client = OHIPClient(settings(), FakeTokenProvider(), http_client=rec)
    await client.get_reservation("MAD01", "resv-1")
    _, url, params = rec.calls[-1]
    assert url.endswith("/rsv/v1/hotels/MAD01/reservations/resv-1")
    assert params["fetchInstructions"] == ["Reservation"]


@pytest.mark.asyncio
async def test_get_folios_sends_fetch_instructions():
    rec = _Recorder()
    client = OHIPClient(settings(), FakeTokenProvider(), http_client=rec)
    await client.get_folios("MAD01", "resv-1")
    _, _, params = rec.calls[-1]
    assert params["fetchInstructions"] == [
        "Postings", "Totalbalance", "Transactioncodes", "Windowbalances",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_ohip_client.py -k fetch_instructions -v`
Expected: FAIL — `params` es `None` (o no contiene `fetchInstructions`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/ohip_bridge/ohip_client.py
    async def get_reservation(self, hotel_id: str, reservation_id: str) -> OHIPResponse:
        payload = await self._request(
            "GET", f"/rsv/v1/hotels/{hotel_id}/reservations/{reservation_id}", hotel_id,
            params={"fetchInstructions": ["Reservation"]},
        )
        return OHIPResponse("getReservation", "reservation", reservation_id, payload, 200)

    async def get_profile(self, profile_id: str, hotel_id: str | None = None) -> OHIPResponse:
        payload = await self._request(
            "GET", f"/crm/v1/profiles/{profile_id}", hotel_id,
            params={"fetchInstructions": ["Profile", "Communication"]},
        )
        return OHIPResponse("getProfile", "profile", profile_id, payload, 200)

    async def get_folios(self, hotel_id: str, reservation_id: str) -> OHIPResponse:
        payload = await self._request(
            "GET", f"/csh/v1/hotels/{hotel_id}/reservations/{reservation_id}/folios", hotel_id,
            params={"fetchInstructions": [
                "Postings", "Totalbalance", "Transactioncodes", "Windowbalances",
            ]},
        )
        return OHIPResponse("getFolio", "folio", reservation_id, payload, 200)

    async def get_transaction_details(self, hotel_id: str, transaction_no: str) -> OHIPResponse:
        payload = await self._request(
            "GET", f"/csh/v1/hotels/{hotel_id}/transactionDetails", hotel_id,
            params={"transactionNo": transaction_no, "includeGenerates": "true"},
        )
        return OHIPResponse(
            "getFolioTransactionDetails", "folio_transaction", transaction_no, payload, 200
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_ohip_client.py -v`
Expected: PASS (los tests previos del módulo siguen verdes).

- [ ] **Step 5: Commit**

```bash
git add src/ohip_bridge/ohip_client.py tests/test_ohip_client.py
git commit -m "feat(ohip): request fetchInstructions so OPERA returns full payloads"
```

---

### Task 2: Detección de acción desde `detail` (OHIP no tiene `actionType`)

**Problema:** `OperaBusinessEvent.is_delete_or_cancel` lee `metadata.actionType`, campo que **no existe** en el esquema de streaming. Según Oracle, la operación se infiere del `detail`: borrado = todos los `newValue` vacíos; cancelación = `elementName` de estado con `newValue` CANCELLED/NO_SHOW.

**Files:**
- Modify: `src/ohip_bridge/opera_event_parser.py` (propiedad `OperaBusinessEvent.is_delete_or_cancel`)
- Test: `tests/test_events.py`

**Interfaces:**
- Consumes: `OperaBusinessEvent.details: list[dict]` (cada `detail` con `elementName`, `oldValue`, `newValue`), `event_name: str | None`.
- Produces: propiedad `is_delete_or_cancel: bool` (misma firma) usada por `enrichment_service` → `RetryClassifier.classify_http(..., is_delete_or_cancel=...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events.py  (añadir)
from datetime import UTC, datetime
from ohip_bridge.opera_event_parser import OperaBusinessEvent


def _event(**kw):
    base = dict(
        unique_event_id="e", offset=None, primary_key=None,
        module_name="Reservation", event_name="UpdateReservation",
        hotel_id="H", chain_code="C", occurred_at=datetime.now(UTC),
    )
    base.update(kw)
    return OperaBusinessEvent(**base)


def test_cancel_detected_from_detail_status():
    ev = _event(details=[{"elementName": "reservationStatus",
                          "oldValue": "RESERVED", "newValue": "CANCELLED"}])
    assert ev.is_delete_or_cancel is True


def test_deletion_detected_when_all_new_values_empty():
    ev = _event(details=[{"elementName": "x", "oldValue": "1", "newValue": ""}])
    assert ev.is_delete_or_cancel is True


def test_plain_update_not_flagged():
    ev = _event(details=[{"elementName": "roomType", "oldValue": "A", "newValue": "B"}])
    assert ev.is_delete_or_cancel is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_events.py -k "cancel or deletion or plain_update" -v`
Expected: FAIL — la lógica actual solo mira texto de `event_name`/`actionType`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/ohip_bridge/opera_event_parser.py  (reemplazar la propiedad)
    @property
    def is_delete_or_cancel(self) -> bool:
        name = (self.event_name or "").upper()
        if "DELETE" in name or "CANCEL" in name:
            return True
        # OHIP no expone actionType: la acción se infiere del detail.
        if self.details and all(
            (d.get("newValue") in (None, "")) for d in self.details
        ):
            return True  # borrado de recurso => todos los newValue vacíos
        for d in self.details:
            if "status" in str(d.get("elementName") or "").lower():
                new = str(d.get("newValue") or "").upper().replace(" ", "_")
                if new in {"CANCELLED", "CANCELED", "NO_SHOW"}:
                    return True
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_events.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ohip_bridge/opera_event_parser.py tests/test_events.py
git commit -m "fix(enricher): infer delete/cancel from detail (OHIP has no actionType)"
```

---

### Task 3: Refresco OAuth *single-flight* + quitar `x-hotelid` del token

**Problema:** `OAuthClient.token()` no tiene lock → con concurrencia, N tareas refrescan el token a la vez. Además el token `client_credentials` no requiere `x-hotelid` (la colección no lo envía) y `ohip_hotel_ids[0]` revienta si la lista está vacía.

**Files:**
- Modify: `src/ohip_bridge/oauth.py`
- Test: `tests/test_ohip_client.py` (o `tests/test_oauth.py` nuevo)

**Interfaces:**
- Consumes: `Settings.ohip_token_refresh_skew_seconds`, `OAuthClient._fetch_token()`.
- Produces: `OAuthClient.token()` async, idempotente bajo concurrencia (una sola llamada a `_fetch_token` por refresco).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_oauth.py  (nuevo)
import asyncio
import time
import pytest
from ohip_bridge.oauth import OAuthClient, OAuthToken


@pytest.mark.asyncio
async def test_token_refresh_is_single_flight(monkeypatch):
    client = OAuthClient(settings())
    calls = []

    async def fake_fetch():
        calls.append(1)
        await asyncio.sleep(0.01)
        return OAuthToken("tok", time.time() + 3600)

    monkeypatch.setattr(client, "_fetch_token", fake_fetch)
    await asyncio.gather(*(client.token() for _ in range(5)))
    assert len(calls) == 1
```

(Reutiliza el factory `settings()` de la suite; si no es importable, replícalo en un `conftest` local.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_oauth.py -v`
Expected: FAIL — `_fetch_token` se llama 5 veces (sin lock).

- [ ] **Step 3: Write minimal implementation**

```python
# src/ohip_bridge/oauth.py
import asyncio
# ...
class OAuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token: OAuthToken | None = None
        self._lock = asyncio.Lock()

    async def token(self) -> OAuthToken:
        skew = self.settings.ohip_token_refresh_skew_seconds
        if self._token and not self._token.is_expiring(skew):
            return self._token
        async with self._lock:
            if self._token and not self._token.is_expiring(skew):
                return self._token
            self._token = await self._fetch_token()
            return self._token
```

En `_fetch_token`, eliminar la línea `"x-hotelid": self.settings.ohip_hotel_ids[0],` del dict `headers`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_oauth.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ohip_bridge/oauth.py tests/test_oauth.py
git commit -m "fix(oauth): single-flight token refresh; drop x-hotelid from token call"
```

---

### Task 4: Pool de conexiones PostgreSQL en el enricher

**Problema:** `OperaEnrichmentService` abre `psycopg.connect()` por evento (handshake por mensaje → latencia y riesgo de agotar conexiones de Aurora). `psycopg_pool` ya está disponible vía `psycopg[binary,pool]`.

**Files:**
- Modify: `src/ohip_bridge/config.py` (nuevo campo `enricher_pool_max_size`)
- Modify: `src/ohip_bridge/enrichment_service.py` (pool en `__init__`, reemplazar `_connect`)
- Modify: `src/ohip_bridge/event_enricher.py` (abrir/cerrar el pool)
- Test: `tests/test_enrichment_service_pool.py` (nuevo)

**Interfaces:**
- Consumes: `Settings.database_url: SecretStr`, `Settings.enricher_pool_max_size: int`.
- Produces: `OperaEnrichmentService._pool: psycopg_pool.ConnectionPool` (max_size configurable, `open=False` por defecto para testear sin BD); método privado `_conn()` que devuelve `self._pool.connection()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrichment_service_pool.py  (nuevo)
from ohip_bridge.enrichment_service import OperaEnrichmentService
from ohip_bridge.event_router import EventRouter
from ohip_bridge.identifier_resolver import IdentifierResolver


def test_service_builds_pool_with_configured_size():
    s = settings()  # factory de la suite
    svc = OperaEnrichmentService(
        settings=s, router=EventRouter([], {}),
        resolver=IdentifierResolver(), ohip_client=None,
    )
    assert svc._pool.max_size == s.enricher_pool_max_size
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_enrichment_service_pool.py -v`
Expected: FAIL — `AttributeError: _pool` (y `enricher_pool_max_size` no existe).

- [ ] **Step 3: Write minimal implementation**

```python
# src/ohip_bridge/config.py  (junto a los demás campos enricher_*)
    enricher_pool_max_size: int = 10
```

```python
# src/ohip_bridge/enrichment_service.py
from psycopg_pool import ConnectionPool
# ... en __init__, tras asignar self.settings:
        self._pool = ConnectionPool(
            self.settings.database_url.get_secret_value(),
            min_size=1,
            max_size=self.settings.enricher_pool_max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )
# reemplazar _connect() por:
    def _conn(self):
        return self._pool.connection()
# y en _persist/_mark_deleted/mark_failed cambiar
#   with self._connect() as conn:  ->  with self._conn() as conn:
```

```python
# src/ohip_bridge/event_enricher.py  (en run(), tras crear service)
    service._pool.open()
    try:
        await processor.run_forever()
    finally:
        await ohip_client.close()
        service._pool.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_enrichment_service_pool.py -v`
Expected: PASS.

> **Verificación de integración (requiere BD):** con PostgreSQL local, `python -m ohip_bridge.event_enricher` debe arrancar, procesar un evento y reutilizar conexiones (sin abrir una por mensaje). No es un test unitario; hazlo en el checkpoint de review con la skill `verify`.

- [ ] **Step 5: Commit**

```bash
git add src/ohip_bridge/config.py src/ohip_bridge/enrichment_service.py \
        src/ohip_bridge/event_enricher.py tests/test_enrichment_service_pool.py
git commit -m "perf(enricher): pooled PostgreSQL connections instead of connect-per-event"
```

---

## Fuera de alcance (siguientes olas — ver tablero)

Estas acciones dependen de decisiones pendientes y van en planes aparte:

- **Concurrencia del enricher** — depende de particionar `MessageGroupId` por hotel/`hotelCode` (para no romper el orden FIFO).
- **Router sin pérdida (evento no mapeado → `SKIPPED`)** — requiere migración (añadir `SKIPPED` al CHECK de `opera_events.event`) y decidir el estado.
- **Soft-delete en `opera_core`** (`deleted_at`) — pendiente de convención con negocio.
- **SNS fan-out + Bronze (Kinesis Firehose → S3 particionado)** — Terraform, plan de infra propio.
- **Retirar la vía v1** (Opción B) — cambio quirúrgico + reescritura del benchmark.
- **business-date + watermark** en el corte analítico — pendiente de negocio.
- **R&A GraphQL bulk** como segunda fuente del enricher (vs REST N+1).

## Self-Review

- **Cobertura:** las 4 tareas cubren completitud de datos (T1), corrección de la detección de acción (T2), robustez/coste de OAuth (T3) y rendimiento de BD (T4). Lo demás está listado explícitamente como fuera de alcance con su bloqueo.
- **Placeholders:** ninguno; cada paso trae test e implementación reales.
- **Consistencia de tipos:** `is_delete_or_cancel` mantiene firma `-> bool`; `OHIPClient` mantiene firmas públicas; `_conn()` sustituye a `_connect()` en los tres sitios; `enricher_pool_max_size` se define en `config.py` y se consume en `enrichment_service.py`.
