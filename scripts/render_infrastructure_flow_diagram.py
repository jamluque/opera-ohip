# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
DOCS = ROOT / "docs"
OUTPUTS.mkdir(exist_ok=True)
DOCS.mkdir(exist_ok=True)

W, H = 3400, 2300
BG = "#f6f8fb"
INK = "#162033"
MUTED = "#5e6b7c"
LINE = "#d6deea"
CARD = "#ffffff"
BLUE = "#2563ad"
GREEN = "#168064"
ORANGE = "#d97706"
PURPLE = "#6d5bd0"
RED = "#b42318"
TEAL = "#0f766e"
SLATE = "#475569"
AWS = "#ff9900"
VPC_BG = "#eef6ff"
PRIVATE_BG = "#edf7f4"
PUBLIC_BG = "#fff7ed"
DATA_BG = "#f5f3ff"
OBS_BG = "#f8fafc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/mnt/c/Windows/Fonts/segoeuib.ttf" if bold else "/mnt/c/Windows/Fonts/segoeui.ttf",
        "/mnt/c/Windows/Fonts/arialbd.ttf" if bold else "/mnt/c/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


F = {
    "title": font(72, True),
    "subtitle": font(34),
    "section": font(42, True),
    "h": font(32, True),
    "body": font(26),
    "small": font(22),
    "tiny": font(18),
    "num": font(25, True),
}


def rounded(d: ImageDraw.ImageDraw, xy, fill=CARD, outline=LINE, radius=26, width=2):
    d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def wrap(d: ImageDraw.ImageDraw, text: str, x: int, y: int, max_width: int, line_h: int, fnt, fill=INK) -> int:
    for paragraph in text.split("\n"):
        words = paragraph.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if d.textbbox((0, 0), test, font=fnt)[2] <= max_width:
                line = test
                continue
            if line:
                d.text((x, y), line, fill=fill, font=fnt)
                y += line_h
            line = word
        if line:
            d.text((x, y), line, fill=fill, font=fnt)
            y += line_h
    return y


def arrow(d: ImageDraw.ImageDraw, start, end, color=SLATE, width=8, label: str | None = None, label_pos: str = "above"):
    d.line([start, end], fill=color, width=width)
    sx, sy = start
    ex, ey = end
    if abs(ex - sx) >= abs(ey - sy):
        pts = [(ex, ey), (ex - 28 if ex >= sx else ex + 28, ey - 16), (ex - 28 if ex >= sx else ex + 28, ey + 16)]
    else:
        pts = [(ex, ey), (ex - 16, ey - 28 if ey >= sy else ey + 28), (ex + 16, ey - 28 if ey >= sy else ey + 28)]
    d.polygon(pts, fill=color)
    if label:
        lx = (sx + ex) // 2
        ly = (sy + ey) // 2 - 46 if label_pos == "above" else (sy + ey) // 2 + 14
        bbox = d.textbbox((0, 0), label, font=F["tiny"])
        pad = 10
        rounded(d, (lx - bbox[2] // 2 - pad, ly - 7, lx + bbox[2] // 2 + pad, ly + 28), fill=BG, outline=LINE, radius=12, width=1)
        d.text((lx - bbox[2] // 2, ly), label, fill=color, font=F["tiny"])


def step_badge(d: ImageDraw.ImageDraw, x: int, y: int, n: str, color=BLUE):
    d.ellipse((x, y, x + 44, y + 44), fill=color)
    bbox = d.textbbox((0, 0), n, font=F["num"])
    d.text((x + 22 - bbox[2] / 2, y + 20 - bbox[3] / 2), n, fill="white", font=F["num"])


def box(d: ImageDraw.ImageDraw, xy, title: str, body: str, color=BLUE, fill=CARD):
    rounded(d, xy, fill=fill, outline=color, radius=24, width=4)
    d.text((xy[0] + 24, xy[1] + 22), title, fill=color, font=F["h"])
    wrap(d, body, xy[0] + 24, xy[1] + 72, xy[2] - xy[0] - 48, 29, F["small"], INK)


def save(img: Image.Image, name: str):
    img.save(OUTPUTS / f"{name}.png", optimize=True)
    img.save(OUTPUTS / f"{name}.jpg", quality=96, subsampling=0)


def render():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((90, 68), "Arquitectura de infraestructura y flujos", fill=INK, font=F["title"])
    d.text((92, 154), "OPERA Cloud OHIP Streaming -> AWS ECS/SQS/S3/Aurora -> Analytics snapshots, pickups y last status", fill=MUTED, font=F["subtitle"])

    # External zone
    rounded(d, (90, 250, 560, 690), fill="#ffffff", outline="#cbd5e1", radius=30, width=3)
    d.text((130, 290), "Oracle Hospitality", fill=INK, font=F["section"])
    box(d, (130, 365, 520, 510), "OPERA Cloud PMS", "Business Events\nreservas, folios, perfiles", BLUE)
    box(d, (130, 540, 520, 650), "OHIP", "OAuth + Streaming API\nProperty APIs", PURPLE)
    arrow(d, (325, 512), (325, 535), color=PURPLE, width=6)

    # AWS account/VPC
    rounded(d, (620, 250, 3310, 1715), fill=VPC_BG, outline=BLUE, radius=34, width=4)
    d.text((660, 290), "AWS Account / Region", fill=BLUE, font=F["section"])
    d.text((1065, 300), "VPC multi-AZ con subredes publicas y privadas", fill=MUTED, font=F["body"])

    rounded(d, (660, 380, 3230, 615), fill=PUBLIC_BG, outline="#fed7aa", radius=28, width=3)
    d.text((700, 418), "Subredes publicas", fill=ORANGE, font=F["h"])
    box(d, (720, 475, 1040, 575), "Internet Gateway", "Entrada/salida internet", ORANGE)
    box(d, (1130, 475, 1450, 575), "NAT Gateway", "Salida ECS privado\nhacia OHIP", ORANGE)
    box(d, (1540, 475, 1860, 575), "Public route table", "Rutas IGW/NAT", ORANGE)

    rounded(d, (660, 675, 3230, 1385), fill=PRIVATE_BG, outline="#b7e4d8", radius=28, width=3)
    d.text((700, 713), "Subredes privadas ECS", fill=GREEN, font=F["h"])
    ecs_boxes = [
        ((720, 790, 1055, 950), "ECS Listener", "WebSocket OHIP\nheartbeat, reconnect\noffsets"),
        ((1140, 790, 1475, 950), "SQS FIFO", "cola principal\nuniqueEventId\nmessage group"),
        ((1560, 790, 1895, 950), "ECS Event Enricher", "consume SQS\nOHIP Property APIs\nnormaliza"),
        ((1980, 790, 2315, 950), "SQS DLQ", "fallos tras reintentos\ninspeccion operativa"),
        ((2400, 790, 2735, 950), "ECS Analytics Job", "diario/EventBridge\nsnapshots + KPIs"),
    ]
    for xy, title, body in ecs_boxes:
        box(d, xy, title, body, GREEN if "ECS" in title else ORANGE)
    box(d, (2820, 790, 3175, 950), "ECR", "imagenes Docker\nlistener/consumer/enricher/analytics", AWS)

    rounded(d, (700, 1065, 3190, 1325), fill="#f8fafc", outline=LINE, radius=24, width=2)
    d.text((730, 1100), "Servicios de soporte en subred privada / endpoints", fill=SLATE, font=F["h"])
    support = [
        ((760, 1170, 1040, 1280), "Secrets Manager", "credenciales OHIP\nDATABASE_URL", PURPLE),
        ((1110, 1170, 1390, 1280), "KMS", "cifrado secretos\ny storage", PURPLE),
        ((1460, 1170, 1740, 1280), "VPC Endpoints", "S3, SQS, ECR, Logs\nmenos NAT", TEAL),
        ((1810, 1170, 2090, 1280), "IAM Roles", "least privilege\npor servicio", SLATE),
        ((2160, 1170, 2440, 1280), "CloudWatch", "logs, metricas\nalarmas", RED),
        ((2510, 1170, 2790, 1280), "EventBridge", "schedule diario\nanalytics", ORANGE),
    ]
    for xy, title, body, color in support:
        box(d, xy, title, body, color)

    rounded(d, (660, 1430, 3230, 1665), fill=DATA_BG, outline="#ddd6fe", radius=28, width=3)
    d.text((700, 1468), "Capa de datos", fill=PURPLE, font=F["h"])
    data_boxes = [
        ((730, 1535, 1070, 1635), "S3 Raw", "eventos JSON + offsets", TEAL),
        ((1160, 1535, 1500, 1635), "Aurora PostgreSQL", "opera_events / raw / core", TEAL),
        ((1590, 1535, 1930, 1635), "Snapshots", "reservation_daily_snapshot", BLUE),
        ((2020, 1535, 2360, 1635), "Last Status", "reservation_last_status_daily", RED),
        ((2450, 1535, 2790, 1635), "Pickups", "pickup_metric 1/3/7/15", PURPLE),
        ((2880, 1535, 3180, 1635), "BI", "queries y dashboards", BLUE),
    ]
    for xy, title, body, color in data_boxes:
        box(d, xy, title, body, color)

    # Main flows
    arrow(d, (520, 595), (720, 860), color=PURPLE, label="1 streaming WS", label_pos="above")
    arrow(d, (1055, 870), (1130, 870), color=ORANGE, label="2 send message", label_pos="above")
    arrow(d, (1475, 870), (1550, 870), color=ORANGE, label="3 consume", label_pos="above")
    arrow(d, (1895, 870), (1970, 870), color=RED, label="fallos", label_pos="above")
    arrow(d, (1728, 950), (900, 1528), color=TEAL, label="4 raw", label_pos="above")
    arrow(d, (1728, 950), (1330, 1528), color=TEAL, label="5 upsert", label_pos="above")
    arrow(d, (2570, 950), (1760, 1528), color=BLUE, label="6 snapshot diario", label_pos="above")
    arrow(d, (1930, 1585), (2010, 1585), color=RED, label="7 compacta reserva", label_pos="above")
    arrow(d, (1930, 1618), (2440, 1618), color=PURPLE, label="8 compara snapshots", label_pos="below")
    arrow(d, (2360, 1585), (2870, 1585), color=BLUE, label="9 reporting", label_pos="above")
    arrow(d, (2790, 1618), (2870, 1618), color=BLUE, label="BI", label_pos="below")

    # OHIP enrichment outbound
    arrow(d, (1560, 820), (525, 590), color=PURPLE, label="OHIP Property APIs", label_pos="above")
    arrow(d, (1450, 525), (1560, 820), color=ORANGE, label="NAT egress", label_pos="above")

    # Security/observability flows
    arrow(d, (890, 1170), (890, 950), color=PURPLE, width=5, label="secrets", label_pos="above")
    arrow(d, (2300, 1170), (2300, 950), color=RED, width=5, label="logs/metrics", label_pos="above")
    arrow(d, (2650, 1170), (2570, 950), color=ORANGE, width=5, label="schedule", label_pos="above")
    arrow(d, (1600, 1170), (920, 1535), color=TEAL, width=5, label="private endpoints", label_pos="above")

    # Flow legend
    rounded(d, (90, 1770, 3310, 2185), fill=CARD, outline=LINE, radius=30, width=3)
    d.text((130, 1810), "Leyenda de flujos", fill=INK, font=F["section"])
    flows = [
        ("1", "Captura", "Listener abre WebSocket OHIP con OAuth, application key y heartbeat; persiste offsets en S3."),
        ("2", "Desacoplamiento", "Cada Business Event se publica en SQS FIFO con deduplicacion por uniqueEventId."),
        ("3", "Enriquecimiento", "Event Enricher consume SQS, resuelve identificadores y llama OHIP Property APIs."),
        ("4", "Raw auditable", "La respuesta completa se guarda en S3 para reprocesos, auditoria y conciliacion."),
        ("5", "Core idempotente", "Aurora guarda opera_events, opera_raw y opera_core con UPSERT por clave funcional."),
        ("6", "Snapshot diario", "EventBridge ejecuta analytics job para materializar reservation_daily_snapshot."),
        ("7", "Last status", "Se compacta a una fila por reserva; incluye CANCELLED y NO_SHOW como ultimo estado."),
        ("8", "Pickups", "Se calculan metricas 1, 3, 7 y 15 dias comparando snapshots estables."),
        ("9", "Consumo", "BI y analistas leen tablas materializadas, no eventos raw ni OPERA directamente."),
    ]
    col_w = 1040
    for idx, (n, title, body) in enumerate(flows):
        col = idx % 3
        row = idx // 3
        x = 140 + col * col_w
        y = 1885 + row * 92
        step_badge(d, x, y, n, BLUE if n not in {"7", "8"} else (RED if n == "7" else PURPLE))
        d.text((x + 62, y - 2), title, fill=INK, font=F["body"])
        wrap(d, body, x + 62, y + 33, col_w - 105, 25, F["tiny"], MUTED)

    save(img, "infrastructure-flows-detailed-last-status")


def write_mermaid_doc():
    doc = """# Diagrama detallado de infraestructura y flujos

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

    OHIP -- "1 Streaming WebSocket" --> LISTENER
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
    OHIP->>LIS: WebSocket graphql-transport-ws
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
"""
    (DOCS / "architecture-infrastructure-flows-detailed.md").write_text(doc, encoding="utf-8")


def main():
    render()
    write_mermaid_doc()


if __name__ == "__main__":
    main()
