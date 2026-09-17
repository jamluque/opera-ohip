# OHIP Streaming To Service API Examples

Estos ejemplos muestran el salto que hace este proyecto despues de recibir un
`newEvent` por streaming: resolver el identificador funcional, consultar OHIP
Property APIs y actualizar las tablas locales con upserts.

Los payloads sinteticos estan en
[examples/ohip-service-api-responses](../examples/ohip-service-api-responses).
No son datos reales de hotel y no contienen secretos.

## Flujo Definido En El Proyecto

1. `OhipStreamingClient` recibe `payload.data.newEvent`.
2. El listener publica el evento en SQS FIFO.
3. `OperaEnrichmentService.enrich()` parsea el mensaje y busca una ruta en
   [config/event-router.yaml](../config/event-router.yaml).
4. `IdentifierResolver` extrae `reservationId`, `profileId` o `transactionNo`.
5. `OHIPClient` llama al metodo REST expuesto.
6. Se guarda la respuesta completa en `opera_raw.resource_snapshot`.
7. El transformer correspondiente reduce la respuesta a campos core.
8. `EventRepository` hace upsert idempotente en `opera_core`.

## Metodos Cubiertos

| Evento streaming | Metodo OHIPClient | Endpoint | Ejemplo respuesta | Tabla actualizada |
|---|---|---|---|---|
| `Reservation/*` | `getReservation` | `GET /rsv/v1/hotels/{hotelId}/reservations/{reservationId}` | `get-reservation-response.json` | `opera_core.reservation` |
| `Profile/*` | `getProfile` | `GET /crm/v1/profiles/{profileId}` | `get-profile-response.json` | `opera_core.profile` |
| `Cashiering/Folio` | `getFolio` | `GET /csh/v1/hotels/{hotelId}/reservations/{reservationId}/folios` | `get-folios-response.json` | `opera_core.folio` |
| `Cashiering/Transaction` | `getFolioTransactionDetails` | `GET /csh/v1/hotels/{hotelId}/transactionDetails?transactionNo={transactionNo}` | `get-transaction-details-response.json` | `opera_core.folio_transaction` |

## Ejemplo 1: Reserva Actualizada

Evento de entrada:

```json
{
  "metadata": {
    "offset": "100002",
    "uniqueEventId": "evt-reservation-update-100002"
  },
  "chainCode": "CHAIN",
  "hotelId": "MAD01",
  "moduleName": "Reservation",
  "eventName": "UpdateReservation",
  "primaryKey": "resv-10001",
  "timestamp": "2026-08-17T10:15:00Z"
}
```

Llamada resultante:

```http
GET /rsv/v1/hotels/MAD01/reservations/resv-10001
```

Respuesta OHIP:

```json
{
  "reservation": {
    "reservationIdList": [
      {
        "type": "Reservation",
        "id": "resv-10001"
      }
    ],
    "confirmationNo": "CNF10001",
    "arrivalDate": "2026-09-02",
    "departureDate": "2026-09-05",
    "reservationStatus": "RESERVED",
    "lastModifyDateTime": "2026-08-17T10:16:10Z"
  }
}
```

Campos actualizados en `opera_core.reservation`:

```json
{
  "hotel_id": "MAD01",
  "reservation_id": "resv-10001",
  "confirmation_no": "CNF10001",
  "arrival_date": "2026-09-02",
  "departure_date": "2026-09-05",
  "reservation_status": "RESERVED",
  "source_updated_at": "2026-08-17T10:16:10Z",
  "last_event_id": "evt-reservation-update-100002",
  "last_event_at": "2026-08-17T10:15:00Z"
}
```

## Ejemplo 2: Perfil Actualizado

Evento de entrada:

```json
{
  "metadata": {
    "offset": "100004",
    "uniqueEventId": "evt-profile-new-100004"
  },
  "chainCode": "CHAIN",
  "hotelId": "MAD01",
  "moduleName": "Profile",
  "eventName": "NewProfile",
  "primaryKey": "p-9001",
  "timestamp": "2026-08-17T11:20:00Z"
}
```

Llamada resultante:

```http
GET /crm/v1/profiles/p-9001
```

Respuesta OHIP:

```json
{
  "profile": {
    "profileId": "p-9001",
    "profileType": "GUEST",
    "customer": {
      "personName": [
        {
          "givenName": "Lucia",
          "surname": "Martin"
        }
      ]
    },
    "emails": [
      {
        "email": "lucia.martin@example.invalid"
      }
    ],
    "lastModifyDateTime": "2026-08-17T11:21:30Z"
  }
}
```

Campos actualizados en `opera_core.profile`:

```json
{
  "profile_id": "p-9001",
  "profile_type": "GUEST",
  "first_name": "Lucia",
  "last_name": "Martin",
  "email": "lucia.martin@example.invalid",
  "source_updated_at": "2026-08-17T11:21:30Z",
  "last_event_id": "evt-profile-new-100004",
  "last_event_at": "2026-08-17T11:20:00Z"
}
```

## Ejemplo 3: Folio Actualizado

Evento de entrada:

```json
{
  "metadata": {
    "offset": "100005",
    "uniqueEventId": "evt-cashiering-folio-100005"
  },
  "chainCode": "CHAIN",
  "hotelId": "MAD01",
  "moduleName": "Cashiering",
  "eventName": "Folio",
  "primaryKey": "folio-1",
  "timestamp": "2026-08-17T13:00:00Z",
  "detail": [
    {
      "elementName": "reservationId",
      "newValue": "resv-10001"
    }
  ]
}
```

Llamada resultante:

```http
GET /csh/v1/hotels/MAD01/reservations/resv-10001/folios
```

Respuesta OHIP:

```json
{
  "folios": [
    {
      "folioId": "folio-1",
      "folioNo": "101",
      "balance": "248.50",
      "currencyCode": "EUR",
      "lastModifyDateTime": "2026-08-17T13:05:00Z"
    }
  ]
}
```

Campos actualizados en `opera_core.folio`:

```json
{
  "hotel_id": "MAD01",
  "reservation_id": "resv-10001",
  "folio_id": "folio-1",
  "folio_no": "101",
  "balance_amount": "248.50",
  "currency_code": "EUR",
  "source_updated_at": "2026-08-17T13:05:00Z",
  "last_event_id": "evt-cashiering-folio-100005",
  "last_event_at": "2026-08-17T13:00:00Z"
}
```

## Ejemplo 4: Detalle De Transaccion

Evento de entrada:

```json
{
  "metadata": {
    "offset": "100006",
    "uniqueEventId": "evt-cashiering-transaction-100006"
  },
  "chainCode": "CHAIN",
  "hotelId": "MAD01",
  "moduleName": "Cashiering",
  "eventName": "Transaction",
  "primaryKey": "900001",
  "timestamp": "2026-08-17T14:10:00Z"
}
```

Llamada resultante:

```http
GET /csh/v1/hotels/MAD01/transactionDetails?transactionNo=900001
```

Respuesta OHIP:

```json
{
  "transaction": {
    "transactionNo": "900001",
    "reservationId": "resv-10001",
    "folioId": "folio-1",
    "amount": "120.00",
    "currencyCode": "EUR",
    "transactionCode": "ROOM",
    "lastModifyDateTime": "2026-08-17T14:11:20Z"
  }
}
```

Campos actualizados en `opera_core.folio_transaction`:

```json
{
  "hotel_id": "MAD01",
  "transaction_no": "900001",
  "reservation_id": "resv-10001",
  "folio_id": "folio-1",
  "amount": "120.00",
  "currency_code": "EUR",
  "transaction_code": "ROOM",
  "source_updated_at": "2026-08-17T14:11:20Z",
  "last_event_id": "evt-cashiering-transaction-100006",
  "last_event_at": "2026-08-17T14:10:00Z"
}
```

## Ejemplo 5: Cancelacion Con Recurso Ya No Disponible

Para eventos de borrado o cancelacion, si OHIP devuelve `404`, el
`RetryClassifier` lo trata como recurso eliminado. No se hace upsert core; se
guarda un marcador raw:

```json
{
  "deleted": true,
  "resource_id": "resv-10003"
}
```

El evento queda `COMPLETED` para no reintentar indefinidamente una cancelacion
valida.

## Comprobacion Local

```bash
PYTHONPATH=.python-packages:src python3 -m pytest tests/test_ohip_service_response_examples.py -q
```
