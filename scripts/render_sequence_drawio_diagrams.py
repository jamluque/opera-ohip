# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "drawio"
DOCS = ROOT / "docs"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(exist_ok=True)

COLORS = {
    "ink": "#172033",
    "muted": "#5f6b7a",
    "line": "#d8dee9",
    "blue": "#2563ad",
    "green": "#168064",
    "orange": "#d97706",
    "purple": "#6d5bd0",
    "red": "#b42318",
    "teal": "#0f766e",
    "slate": "#475569",
    "bg": "#f7f8fb",
    "note": "#fff7ed",
}


def esc(value: str) -> str:
    return value.replace("\n", "<br/>")


def box_label(title: str, *lines: str) -> str:
    body = "<br/>".join(lines)
    return f"<b>{title}</b><br/>{body}" if body else f"<b>{title}</b>"


class DrawioPage:
    def __init__(self, name: str, width: int = 1900, height: int = 1250) -> None:
        self.name = name
        self.width = width
        self.height = height
        self.counter = 2
        self.model = ET.Element(
            "mxGraphModel",
            {
                "dx": "1600",
                "dy": "1000",
                "grid": "1",
                "gridSize": "10",
                "guides": "1",
                "tooltips": "1",
                "connect": "1",
                "arrows": "1",
                "fold": "1",
                "page": "1",
                "pageScale": "1",
                "pageWidth": str(width),
                "pageHeight": str(height),
                "math": "0",
                "shadow": "0",
            },
        )
        self.root = ET.SubElement(self.model, "root")
        ET.SubElement(self.root, "mxCell", {"id": "0"})
        ET.SubElement(self.root, "mxCell", {"id": "1", "parent": "0"})

    def _id(self, prefix: str) -> str:
        value = f"{prefix}-{self.counter}"
        self.counter += 1
        return value

    def text(self, value: str, x: int, y: int, w: int, h: int, *, size: int = 14, bold: bool = False, color: str = "#172033") -> str:
        cell_id = self._id("text")
        style = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;fontFamily=Segoe UI;" + f"fontSize={size};fontStyle={'1' if bold else '0'};fontColor={color};"
        cell = ET.SubElement(self.root, "mxCell", {"id": cell_id, "value": value, "style": style, "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        return cell_id

    def title(self, title: str, subtitle: str) -> None:
        self.text(title, 40, 30, self.width - 80, 48, size=26, bold=True)
        self.text(subtitle, 42, 78, self.width - 84, 36, size=14, color=COLORS["muted"])

    def rect(self, value: str, x: int, y: int, w: int, h: int, *, stroke: str = "#2563ad", fill: str = "#ffffff", size: int = 13, bold: bool = False) -> str:
        cell_id = self._id("node")
        style = "rounded=1;whiteSpace=wrap;html=1;arcSize=10;spacing=8;fillColor={};strokeColor={};strokeWidth=2;fontFamily=Segoe UI;align=center;verticalAlign=middle;fontSize={};fontStyle={};fontColor={};".format(fill, stroke, size, "1" if bold else "0", COLORS["ink"])
        cell = ET.SubElement(self.root, "mxCell", {"id": cell_id, "value": value, "style": style, "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        return cell_id

    def line(self, x: int, y: int, h: int, *, color: str = "#94a3b8") -> str:
        cell_id = self._id("life")
        style = f"shape=line;html=1;strokeColor={color};strokeWidth=1;dashed=1;dashPattern=8 6;direction=south;"
        cell = ET.SubElement(self.root, "mxCell", {"id": cell_id, "value": "", "style": style, "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": "1", "height": str(h), "as": "geometry"})
        return cell_id

    def activation(self, x: int, y: int, h: int, *, color: str = "#2563ad") -> str:
        return self.rect("", x - 8, y, 16, h, stroke=color, fill="#ffffff", size=1)

    def anchor(self, x: int, y: int) -> str:
        cell_id = self._id("anchor")
        style = "ellipse;html=1;fillColor=none;strokeColor=none;opacity=0;"
        cell = ET.SubElement(self.root, "mxCell", {"id": cell_id, "value": "", "style": style, "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": "1", "height": "1", "as": "geometry"})
        return cell_id

    def message(self, x1: int, x2: int, y: int, label: str, *, color: str = "#475569", dashed: bool = False) -> None:
        a = self.anchor(x1, y)
        b = self.anchor(x2, y)
        dash = "dashed=1;dashPattern=8 6;" if dashed else ""
        style = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;labelBackgroundColor=#f7f8fb;fontFamily=Segoe UI;fontSize=12;fontColor=#172033;" + dash + f"strokeColor={color};strokeWidth=2;"
        cell = ET.SubElement(self.root, "mxCell", {"id": self._id("msg"), "value": esc(label), "style": style, "edge": "1", "parent": "1", "source": a, "target": b})
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    def note(self, value: str, x: int, y: int, w: int, h: int) -> str:
        style = "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;darkOpacity=0.05;fillColor=#fff7ed;strokeColor=#d97706;strokeWidth=2;fontFamily=Segoe UI;fontSize=12;fontColor=#172033;align=left;spacing=10;"
        cell_id = self._id("note")
        cell = ET.SubElement(self.root, "mxCell", {"id": cell_id, "value": esc(value), "style": style, "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        return cell_id

    def to_diagram(self, name: str | None = None) -> ET.Element:
        diagram = ET.Element("diagram", {"id": self._id("page"), "name": name or self.name})
        diagram.append(self.model)
        return diagram


class SequenceBuilder:
    def __init__(self, page: DrawioPage, participants: list[tuple[str, str, str]], *, start_x: int = 90, gap: int = 190, top: int = 145, bottom: int = 1090) -> None:
        self.p = page
        self.x: dict[str, int] = {}
        self.top = top
        self.bottom = bottom
        for idx, (key, label, color) in enumerate(participants):
            x = start_x + idx * gap
            self.x[key] = x
            page.rect(label, x - 72, top, 144, 56, stroke=color, fill="#ffffff", size=12, bold=True)
            page.line(x, top + 56, bottom - top - 40)

    def activate(self, key: str, y: int, h: int, color: str) -> None:
        self.p.activation(self.x[key], y, h, color=color)

    def msg(self, src: str, dst: str, y: int, label: str, color: str = COLORS["slate"], dashed: bool = False) -> None:
        self.p.message(self.x[src], self.x[dst], y, label, color=color, dashed=dashed)


def page_analytics_sequence() -> DrawioPage:
    p = DrawioPage("Secuencia Analitica", 1900, 1250)
    p.title("Secuencia analitica actualizada", "analytics-snapshot-job: snapshots diarios, last status por reserva unica y pickups 1/3/7/15")
    participants = [
        ("eb", "EventBridge", COLORS["orange"]),
        ("ecs", "ECS Analytics\nTask", COLORS["green"]),
        ("sec", "Secrets\nManager", COLORS["purple"]),
        ("db", "Aurora\nPostgreSQL", COLORS["teal"]),
        ("core", "opera_core\nreservation", COLORS["teal"]),
        ("raw", "opera_raw\nresource_snapshot", COLORS["teal"]),
        ("snap", "reservation_daily\nsnapshot", COLORS["blue"]),
        ("last", "reservation_last\nstatus_daily", COLORS["red"]),
        ("pick", "pickup_metric", COLORS["purple"]),
        ("cw", "CloudWatch", COLORS["red"]),
        ("bi", "BI /\nAnalistas", COLORS["blue"]),
    ]
    s = SequenceBuilder(p, participants, start_x=100, gap=165, top=150, bottom=1135)
    for key, y, h, color in [("ecs", 245, 720, COLORS["green"]), ("db", 410, 435, COLORS["teal"]), ("bi", 1010, 80, COLORS["blue"]), ("cw", 895, 95, COLORS["red"] )]:
        s.activate(key, y, h, color)
    s.msg("eb", "ecs", 245, "1 trigger schedule diario\nsnapshot_date = fecha informe", COLORS["orange"])
    s.msg("ecs", "sec", 310, "2 load DATABASE_URL / settings", COLORS["purple"])
    s.msg("sec", "ecs", 355, "secret values", COLORS["purple"], dashed=True)
    s.msg("ecs", "db", 420, "3 connect + transaction", COLORS["teal"])
    s.msg("db", "core", 475, "4 SELECT reservas horizonte", COLORS["teal"])
    s.msg("db", "raw", 530, "5 LEFT JOIN ultimo payload raw", COLORS["teal"])
    s.msg("db", "snap", 600, "6 DELETE/INSERT daily snapshot\nreserva + stay_date", COLORS["blue"])
    s.msg("db", "last", 675, "7 compactar a reserva unica\nsin filtrar CANCELLED/NO_SHOW", COLORS["red"])
    s.msg("db", "pick", 750, "8 refrescar pickups\n1,3,7,15 dias", COLORS["purple"])
    s.msg("db", "ecs", 825, "commit OK", COLORS["teal"], dashed=True)
    s.msg("ecs", "cw", 900, "9 logs y metricas", COLORS["red"])
    s.msg("bi", "last", 1020, "10 consulta last status diario", COLORS["blue"])
    s.msg("bi", "pick", 1080, "11 consulta pickups", COLORS["blue"])
    p.note("Regla funcional: last status representa el estado diario de la reserva en la fecha de ejecucion del informe. Es una fila por reserva y conserva canceladas/no-show.", 1180, 1135, 600, 75)
    return p


def page_enricher_sequence() -> DrawioPage:
    p = DrawioPage("Secuencia Event Enricher", 1900, 1320)
    p.title("Secuencia de procesamiento del event-enricher", "SQS -> router/resolver -> OHIP Property APIs -> Aurora PostgreSQL -> commit/delete message")
    participants = [
        ("sqs", "SQS FIFO", COLORS["orange"]),
        ("proc", "SQSMessage\nProcessor", COLORS["green"]),
        ("parser", "OperaEvent\nParser", COLORS["purple"]),
        ("svc", "OperaEnrichment\nService", COLORS["green"]),
        ("router", "EventRouter", COLORS["slate"]),
        ("resolver", "Identifier\nResolver", COLORS["slate"]),
        ("ohip", "OHIP\nClient", COLORS["purple"]),
        ("api", "OHIP Property\nAPIs", COLORS["purple"]),
        ("db", "Aurora\nPostgreSQL", COLORS["teal"]),
        ("repo", "Repositories\n+ Transformers", COLORS["teal"]),
        ("dlq", "SQS DLQ", COLORS["red"]),
    ]
    s = SequenceBuilder(p, participants, start_x=95, gap=165, top=150, bottom=1190)
    for key, y, h, color in [("proc", 240, 820, COLORS["green"]), ("svc", 405, 520, COLORS["green"]), ("ohip", 565, 150, COLORS["purple"]), ("db", 750, 235, COLORS["teal"]), ("repo", 800, 150, COLORS["teal"] )]:
        s.activate(key, y, h, color)
    s.msg("sqs", "proc", 245, "1 ReceiveMessage long polling", COLORS["orange"])
    s.msg("proc", "parser", 310, "2 parse OperaBusinessEvent", COLORS["purple"])
    s.msg("parser", "proc", 355, "event normalizado", COLORS["purple"], dashed=True)
    s.msg("proc", "svc", 410, "3 enrich(event)", COLORS["green"])
    s.msg("svc", "router", 465, "4 route_for(moduleName,eventName)", COLORS["slate"])
    s.msg("svc", "resolver", 520, "5 resolve primaryKey/detail fields", COLORS["slate"])
    s.msg("svc", "ohip", 575, "6 fetch(operation_id, identifier)", COLORS["purple"])
    s.msg("ohip", "api", 630, "7 GET reservation/profile/folio/transaction", COLORS["purple"])
    s.msg("api", "ohip", 690, "payload JSON / HTTP error", COLORS["purple"], dashed=True)
    s.msg("svc", "db", 755, "8 open transaction", COLORS["teal"])
    s.msg("db", "repo", 810, "9 register_event\nUNIQUE uniqueEventId", COLORS["teal"])
    s.msg("db", "repo", 865, "10 save opera_raw.resource_snapshot", COLORS["teal"])
    s.msg("db", "repo", 920, "11 transform + UPSERT opera_core", COLORS["teal"])
    s.msg("repo", "db", 975, "12 mark COMPLETED + commit", COLORS["teal"])
    s.msg("proc", "sqs", 1040, "13 DeleteMessage solo si commit OK", COLORS["orange"])
    s.msg("proc", "dlq", 1120, "fallos no recuperables / maxReceiveCount", COLORS["red"], dashed=True)
    p.note("Idempotencia: si el evento ya esta COMPLETED, se confirma transaccion y se devuelve como deduplicado. Los errores 429/5xx se reintentan; 400 o identificador irresoluble se clasifican como poison.", 1045, 1195, 720, 85)
    return p


def page_end_to_end_sequence() -> DrawioPage:
    p = DrawioPage("Secuencia End to End", 1900, 1320)
    p.title("Secuencia general end-to-end", "OPERA Cloud -> OHIP Streaming -> ECS Listener -> SQS -> Enricher -> S3/Aurora -> Analytics -> BI")
    participants = [
        ("opera", "OPERA Cloud\nPMS", COLORS["blue"]),
        ("stream", "OHIP\nStreaming", COLORS["purple"]),
        ("listener", "ECS\nListener", COLORS["green"]),
        ("sqs", "SQS FIFO\n+ DLQ", COLORS["orange"]),
        ("enricher", "ECS Event\nEnricher", COLORS["green"]),
        ("api", "OHIP Property\nAPIs", COLORS["purple"]),
        ("s3", "S3 Raw\nBucket", COLORS["teal"]),
        ("db", "Aurora\nPostgreSQL", COLORS["teal"]),
        ("job", "ECS Analytics\nJob", COLORS["green"]),
        ("bi", "BI /\nAnalistas", COLORS["blue"]),
    ]
    s = SequenceBuilder(p, participants, start_x=120, gap=175, top=150, bottom=1180)
    for key, y, h, color in [("listener", 280, 240, COLORS["green"]), ("enricher", 520, 360, COLORS["green"]), ("db", 695, 385, COLORS["teal"]), ("job", 915, 170, COLORS["green"]), ("bi", 1095, 55, COLORS["blue"] )]:
        s.activate(key, y, h, color)
    s.msg("opera", "stream", 245, "1 Business Event", COLORS["blue"])
    s.msg("stream", "listener", 305, "2 WebSocket event", COLORS["purple"])
    s.msg("listener", "sqs", 365, "3 SendMessage FIFO\nuniqueEventId", COLORS["orange"])
    s.msg("listener", "s3", 425, "4 save offset/cursor", COLORS["teal"])
    s.msg("sqs", "enricher", 535, "5 ReceiveMessage", COLORS["orange"])
    s.msg("enricher", "api", 600, "6 GET resource details", COLORS["purple"])
    s.msg("api", "enricher", 660, "payload JSON", COLORS["purple"], dashed=True)
    s.msg("enricher", "s3", 725, "7 store raw event/resource JSON", COLORS["teal"])
    s.msg("enricher", "db", 790, "8 UPSERT event/raw/core", COLORS["teal"])
    s.msg("enricher", "sqs", 855, "9 DeleteMessage after commit", COLORS["orange"])
    s.msg("job", "db", 930, "10 daily snapshot job", COLORS["green"])
    s.msg("db", "job", 990, "core + raw metadata", COLORS["teal"], dashed=True)
    s.msg("job", "db", 1050, "11 materialize snapshots\npickups + last status", COLORS["blue"])
    s.msg("bi", "db", 1130, "12 SQL dashboards", COLORS["blue"])
    p.note("El PMS queda desacoplado: BI consulta Aurora materializado; S3 conserva raw para auditoria y reprocesos.", 1150, 1185, 600, 70)
    return p


def page_listener_sequence() -> DrawioPage:
    p = DrawioPage("Secuencia ECS Listener", 1900, 1320)
    p.title("Secuencia especifica del ECS listener", "Bootstrap, Secrets Manager, OAuth, WebSocket graphql-transport-ws, SQS FIFO, offsets S3 y reconexion")
    participants = [
        ("ecs", "ECS Task\nlistener.py", COLORS["green"]),
        ("secret", "Secrets\nManager", COLORS["purple"]),
        ("health", "Health +\nMetrics", COLORS["red"]),
        ("offset", "S3Offset\nStore", COLORS["teal"]),
        ("oauth", "OAuth\nClient", COLORS["purple"]),
        ("token", "OHIP Token\nEndpoint", COLORS["purple"]),
        ("ws", "OHIP Streaming\nWebSocket", COLORS["purple"]),
        ("parser", "parse_ohip\nevent", COLORS["slate"]),
        ("sqs", "SQS FIFO", COLORS["orange"]),
        ("cw", "CloudWatch", COLORS["red"]),
    ]
    s = SequenceBuilder(p, participants, start_x=110, gap=175, top=150, bottom=1195)
    for key, y, h, color in [("ecs", 235, 850, COLORS["green"]), ("oauth", 445, 155, COLORS["purple"]), ("ws", 600, 270, COLORS["purple"]), ("sqs", 780, 115, COLORS["orange"]), ("offset", 350, 610, COLORS["teal"] )]:
        s.activate(key, y, h, color)
    s.msg("ecs", "secret", 240, "1 load_secret_into_environment", COLORS["purple"])
    s.msg("secret", "ecs", 295, "OHIP credentials + config", COLORS["purple"], dashed=True)
    s.msg("ecs", "health", 350, "2 start /live /ready + metrics", COLORS["red"])
    s.msg("ecs", "offset", 405, "3 load(subscription_name)", COLORS["teal"])
    s.msg("offset", "ecs", 455, "last offset / uniqueEventId", COLORS["teal"], dashed=True)
    s.msg("ecs", "oauth", 505, "4 request access token", COLORS["purple"])
    s.msg("oauth", "token", 560, "client_credentials", COLORS["purple"])
    s.msg("token", "oauth", 615, "access_token", COLORS["purple"], dashed=True)
    s.msg("ecs", "ws", 675, "5 connect graphql-transport-ws\nwith offset", COLORS["purple"])
    s.msg("ws", "ecs", 735, "connection_ack + events", COLORS["purple"], dashed=True)
    s.msg("ecs", "parser", 795, "6 parse raw event", COLORS["slate"])
    s.msg("ecs", "sqs", 850, "7 publish(event)\nMessageDeduplicationId=uniqueEventId", COLORS["orange"])
    s.msg("ecs", "offset", 910, "8 save offset + uniqueEventId", COLORS["teal"])
    s.msg("ecs", "cw", 970, "9 metrics/logs last_event_timestamp", COLORS["red"])
    s.msg("ws", "ecs", 1050, "disconnect/error", COLORS["red"], dashed=True)
    s.msg("ecs", "ws", 1120, "10 reconnect with exponential backoff + jitter", COLORS["red"])
    p.note("El listener no consulta Property APIs ni escribe PostgreSQL. Su responsabilidad es mantener el stream, publicar eventos fiables en SQS FIFO y persistir el cursor en S3.", 1030, 1198, 680, 80)
    return p


def build_mxfile(pages: list[DrawioPage]) -> ET.Element:
    mxfile = ET.Element(
        "mxfile",
        {
            "host": "app.diagrams.net",
            "modified": datetime.now(UTC).isoformat(),
            "agent": "Codex",
            "version": "24.7.17",
            "type": "device",
        },
    )
    for page in pages:
        mxfile.append(page.to_diagram())
    return mxfile


def write_drawio(path: Path, pages: list[DrawioPage]) -> None:
    tree = ET.ElementTree(build_mxfile(pages))
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def write_mermaid_doc() -> None:
    doc = """# Diagramas de secuencia actualizados

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
    STREAM->>LIS: WebSocket event
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
    ECS->>WS: connect graphql-transport-ws with offset
    WS-->>ECS: connection_ack + events
    ECS->>PARSE: parse raw event
    ECS->>SQS: publish with MessageDeduplicationId=uniqueEventId
    ECS->>OFF: save offset + uniqueEventId
    ECS->>CW: metrics/logs last_event_timestamp
    WS-->>ECS: disconnect/error
    ECS->>WS: reconnect exponential backoff + jitter
```
"""
    (DOCS / "sequence-diagrams-updated.md").write_text(doc, encoding="utf-8")


def main() -> None:
    pages = [
        page_analytics_sequence(),
        page_enricher_sequence(),
        page_end_to_end_sequence(),
        page_listener_sequence(),
    ]
    files = [
        "sequence-analytics-last-status.drawio",
        "sequence-event-enricher.drawio",
        "sequence-end-to-end.drawio",
        "sequence-ecs-listener.drawio",
    ]
    for page, filename in zip(pages, files, strict=True):
        write_drawio(OUT / filename, [page])
    write_drawio(OUT / "opera-sequence-diagrams.drawio", pages)
    write_mermaid_doc()


if __name__ == "__main__":
    main()
