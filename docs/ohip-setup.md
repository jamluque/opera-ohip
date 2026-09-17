# Configuracion OHIP y OPERA Cloud

Esta guia usa placeholders. No pegues secretos reales en archivos versionados.

## 1. OHIP Developer Portal

1. Entra al OHIP Developer Portal de Oracle Hospitality.
2. Crea o localiza la aplicacion de integracion para AWS.
3. Anota estos valores y guardalos en AWS Secrets Manager:
   - Gateway URL
   - Streaming WebSocket URL
   - OAuth token URL
   - Application key
   - Client ID
   - Client secret
   - Enterprise ID
   - Scope
   - Chain code
   - Hotel IDs
4. Habilita los permisos/scope necesarios para Streaming API y Business Events.
5. Comprueba que el entorno aparece como `Streaming Enabled`.
6. Solicita o aprueba la suscripcion de eventos para la aplicacion y hoteles necesarios.
7. Comprueba el esquema GraphQL publicado por Oracle para tu version/tenant. El repositorio incluye un query por defecto `newEvent(input: { chainCode, offset })`, pero puedes montar otro archivo y usar `OHIP_SUBSCRIPTION_QUERY_FILE`.
8. Usa una application key distinta para pruebas manuales en Postman/GraphiQL, o deten el listener antes de probar. Oracle solo permite una conexion activa por `applicationKey + gateway URL + chainCode`.

Referencias oficiales:

- https://docs.oracle.com/en/industries/hospitality/integration-platform/stmig/c_client_runtime.htm
- https://github.com/oracle/hospitality-api-docs/tree/main/graphql/streaming
- https://github.com/oracle/hospitality-api-docs

## 2. OPERA Cloud External System

1. En OPERA Cloud, abre Administration > Interfaces > Business Events.
2. Crea o activa un External System para esta integracion, por ejemplo `AWS_BYOD`.
3. Asocia las propiedades/hoteles que enviaran eventos.
4. Usa el mismo codigo en `ohip_external_system_code`.

## 3. External Database

External Database en OPERA Cloud no es un endpoint JDBC/ODBC a Aurora o RDS. Es un codigo logico de configuracion usado para asociar External System, propiedades, interfaces y Business Events. Crea un codigo como `AWS_RAW` o el que defina tu convencion interna, y asocialo donde OPERA lo pida.

## 4. Business Events

1. Selecciona Property, External System y, si aplica, External Database.
2. Activa modulos de negocio, por ejemplo Reservation, Profile, Rate, Block, Cashiering o Housekeeping.
3. Para cada modulo, selecciona Action Types concretos, por ejemplo New Reservation, Update Reservation o New Profile.
4. Selecciona Data Elements. Si no seleccionas elementos, el mensaje puede contener solo cabecera.
5. Anade Where Conditions si necesitas filtrar por hotel, tipo de reserva, rate code u otros campos.
6. Genera eventos de prueba desde OPERA y confirma que llegan al listener.
7. Para OHIP 25.4+, revisa los triggers/data elements configurados en Developer Portal: el array `detail` puede venir parcial. Este proyecto usa `primaryKey` para consultar Property APIs y obtener el estado actual del recurso.

Referencia oficial:

- https://docs.oracle.com/en/industries/hospitality/opera-cloud/25.1/ocsuh/t_admin_interfaces_configuring_business_events.htm

## 5. Validacion de conectividad Streaming

Checklist minimo en UAT:

1. OAuth devuelve token valido.
2. WebSocket responde `connection_ack` al `connection_init`.
3. La suscripcion `newEvent` recibe `metadata.offset`, `metadata.uniqueEventId`, `eventName` y `primaryKey`.
4. El listener publica en SQS FIFO con `MessageDeduplicationId=uniqueEventId`.
5. El offset se guarda en S3.
6. Al reiniciar el listener, se reusa el ultimo offset guardado.
7. No aparecen cierres repetidos `4401`, `4403`, `4409` o `4504`.

Mas detalle: [oracle-ohip-validation.md](oracle-ohip-validation.md).
