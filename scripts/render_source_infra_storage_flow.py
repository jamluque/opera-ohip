# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
DOCS = ROOT / "docs"
OUTPUTS.mkdir(exist_ok=True)
DOCS.mkdir(exist_ok=True)

W, H = 3200, 2050
BG = "#f7f8fb"
INK = "#172033"
MUTED = "#5f6b7a"
CARD = "#ffffff"
LINE = "#d8dee9"
BLUE = "#2563ad"
GREEN = "#168064"
ORANGE = "#d97706"
PURPLE = "#6d5bd0"
RED = "#b42318"
TEAL = "#0f766e"
SLATE = "#475569"
CODE_BG = "#eef2ff"
AWS_BG = "#edf7f4"
DATA_BG = "#fff7ed"
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
    "title": font(64, True),
    "subtitle": font(32),
    "section": font(39, True),
    "h": font(29, True),
    "body": font(24),
    "small": font(20),
    "tiny": font(17),
    "num": font(22, True),
}


def rounded(d: ImageDraw.ImageDraw, xy, fill=CARD, outline=LINE, radius=24, width=2):
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


def arrow(d: ImageDraw.ImageDraw, start, end, color=SLATE, width=7, label: str | None = None, offset=0):
    sx, sy = start
    ex, ey = end
    if offset:
        sy += offset
        ey += offset
    d.line([(sx, sy), (ex, ey)], fill=color, width=width)
    if abs(ex - sx) >= abs(ey - sy):
        pts = [(ex, ey), (ex - 24 if ex >= sx else ex + 24, ey - 14), (ex - 24 if ex >= sx else ex + 24, ey + 14)]
    else:
        pts = [(ex, ey), (ex - 14, ey - 24 if ey >= sy else ey + 24), (ex + 14, ey - 24 if ey >= sy else ey + 24)]
    d.polygon(pts, fill=color)
    if label:
        lx = (sx + ex) // 2
        ly = (sy + ey) // 2 - 40
        bbox = d.textbbox((0, 0), label, font=F["tiny"])
        rounded(d, (lx - bbox[2] // 2 - 10, ly - 6, lx + bbox[2] // 2 + 10, ly + 25), fill=BG, outline=LINE, radius=12, width=1)
        d.text((lx - bbox[2] // 2, ly), label, fill=color, font=F["tiny"])


def badge(d: ImageDraw.ImageDraw, x: int, y: int, n: str, color=BLUE):
    d.ellipse((x, y, x + 38, y + 38), fill=color)
    bbox = d.textbbox((0, 0), n, font=F["num"])
    d.text((x + 19 - bbox[2] / 2, y + 17 - bbox[3] / 2), n, fill="white", font=F["num"])


def box(d: ImageDraw.ImageDraw, xy, title: str, body: str, color=BLUE, fill=CARD):
    rounded(d, xy, fill=fill, outline=color, radius=22, width=4)
    d.text((xy[0] + 22, xy[1] + 19), title, fill=color, font=F["h"])
    wrap(d, body, xy[0] + 22, xy[1] + 64, xy[2] - xy[0] - 44, 27, F["small"], INK)


def save(img: Image.Image, name: str):
    img.save(OUTPUTS / f"{name}.png", optimize=True)
    img.save(OUTPUTS / f"{name}.jpg", quality=96, subsampling=0)


def render():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((85, 60), "Flujo codigo fuente -> infraestructura -> OHIP y almacenamiento", fill=INK, font=F["title"])
    d.text((88, 136), "Mapa de ejecucion de los modulos Python en ECS y sus interacciones con SQS, S3, Aurora PostgreSQL y OHIP", fill=MUTED, font=F["subtitle"])

    rounded(d, (80, 240, 875, 1580), fill=CODE_BG, outline=PURPLE, radius=32, width=4)
    d.text((120, 282), "Codigo fuente Python", fill=PURPLE, font=F["section"])
    source = [
        ((125, 370, 830, 500), "listener.py", "Abre WebSocket OHIP Streaming, autentica OAuth, mantiene ping/pong, reconecta y lee offsets."),
        ((125, 535, 830, 665), "sqs.py + events.py", "Normaliza Business Events, deduplica por uniqueEventId y publica mensajes FIFO."),
        ((125, 700, 830, 830), "event_enricher.py", "Consume SQS, resuelve identificadores, decide ruta OHIP y coordina persistencia."),
        ((125, 865, 830, 995), "ohip_client.py + oauth.py", "Gestiona tokens, cabeceras, retries y llamadas REST a OHIP Property APIs."),
        ((125, 1030, 830, 1160), "transformers.py + repositories.py", "Convierte payloads a opera_core y ejecuta UPSERT idempotente en PostgreSQL."),
        ((125, 1195, 830, 1325), "raw_store.py + offsets.py", "Guarda raw JSON y offsets/cursor en S3."),
        ((125, 1360, 830, 1515), "analytics_snapshot.py", "Job diario: snapshots por stay_date, pickups y last status por reserva unica."),
    ]
    for xy, title, body in source:
        box(d, xy, title, body, PURPLE)

    rounded(d, (965, 240, 2210, 1580), fill=AWS_BG, outline=GREEN, radius=32, width=4)
    d.text((1005, 282), "Infraestructura de ejecucion", fill=GREEN, font=F["section"])
    infra = [
        ((1015, 370, 1385, 520), "ECS Service Listener", "Imagen Dockerfile.listener\nsubred privada\nIAM: SQS + S3 offsets + Secrets"),
        ((1490, 370, 1860, 520), "SQS FIFO", "cola principal\nMessageDeduplicationId\nDLQ redrive policy"),
        ((1015, 675, 1385, 825), "ECS Service Enricher", "Imagen Dockerfile.enricher\nlong polling SQS\nllamadas OHIP REST"),
        ((1490, 675, 1860, 825), "SQS DLQ", "mensajes no procesables\nanalisis operativo\nreproceso manual"),
        ((1015, 1010, 1385, 1160), "ECS Analytics Task", "Imagen Dockerfile.analytics\nEventBridge schedule\nlee Aurora + raw"),
        ((1490, 1010, 1860, 1160), "Secrets / IAM / KMS", "client credentials\nDATABASE_URL\nleast privilege"),
        ((1015, 1325, 1385, 1475), "CloudWatch", "logs JSON\nmetricas Prometheus\nalarmas"),
        ((1490, 1325, 1860, 1475), "ECR", "imagenes listener\nenricher\nanalytics"),
    ]
    for xy, title, body in infra:
        color = ORANGE if "SQS" in title else (RED if "CloudWatch" in title else GREEN)
        box(d, xy, title, body, color)

    rounded(d, (2300, 240, 3120, 1580), fill=DATA_BG, outline=TEAL, radius=32, width=4)
    d.text((2340, 282), "OHIP y almacenamiento", fill=TEAL, font=F["section"])
    targets = [
        ((2350, 370, 3070, 535), "OHIP Streaming API", "WebSocket graphql-transport-ws\nBusiness Events\nOAuth client credentials", PURPLE),
        ((2350, 600, 3070, 765), "OHIP Property APIs", "getReservation, getProfile, folios, transactionDetails\nconsulta con identificador funcional", PURPLE),
        ((2350, 850, 3070, 1015), "S3 Raw Bucket", "raw events JSON\nresource snapshots\noffsets de listener", TEAL),
        ((2350, 1080, 3070, 1285), "Aurora PostgreSQL", "opera_events.event\nopera_raw.resource_snapshot\nopera_core.reservation/profile/folio\nopera_analytics snapshots/pickups/last_status", TEAL),
        ((2350, 1370, 3070, 1515), "BI / SQL", "dashboards y consultas\nlee tablas materializadas\nno consulta OPERA directamente", BLUE),
    ]
    for xy, title, body, color in targets:
        box(d, xy, title, body, color)

    # arrows source -> infra
    arrow(d, (830, 435), (1015, 445), PURPLE, label="build/run")
    arrow(d, (830, 600), (1490, 445), ORANGE, label="send FIFO")
    arrow(d, (830, 765), (1015, 750), GREEN, label="consume/process")
    arrow(d, (830, 930), (2350, 685), PURPLE, label="REST OHIP")
    arrow(d, (830, 1095), (2350, 1175), TEAL, label="UPSERT")
    arrow(d, (830, 1260), (2350, 935), TEAL, label="put raw/offsets")
    arrow(d, (830, 1435), (1015, 1085), BLUE, label="daily job")

    # infra flows
    arrow(d, (1385, 445), (1490, 445), ORANGE, label="1 SendMessage")
    arrow(d, (1675, 520), (1200, 675), ORANGE, label="2 ReceiveMessage")
    arrow(d, (1860, 750), (1490, 750), RED, label="redrive")
    arrow(d, (1385, 750), (2350, 685), PURPLE, label="3 enrich")
    arrow(d, (1200, 825), (2520, 850), TEAL, label="4 raw")
    arrow(d, (1325, 825), (2520, 1080), TEAL, label="5 core")
    arrow(d, (1200, 1010), (2520, 1080), BLUE, label="6 lee/escribe analytics")
    arrow(d, (2700, 1285), (2700, 1370), BLUE, label="7 consume")

    # target relation
    arrow(d, (2700, 535), (2700, 600), PURPLE, label="API context")
    arrow(d, (2700, 1015), (2700, 1080), TEAL, label="metadata/raw ref")

    rounded(d, (80, 1645, 3120, 1955), fill=CARD, outline=LINE, radius=30, width=3)
    d.text((120, 1685), "Lectura del flujo", fill=INK, font=F["section"])
    steps = [
        ("1", "listener.py corre como ECS Listener, se autentica contra OHIP y publica cada evento en SQS FIFO."),
        ("2", "event_enricher.py corre como ECS Enricher, consume SQS y llama OHIP Property APIs para completar el dato."),
        ("3", "raw_store.py escribe evidencia raw en S3; repositories.py persiste evento, snapshot y core en Aurora."),
        ("4", "analytics_snapshot.py corre por EventBridge y genera reservation_daily_snapshot, pickup_metric y reservation_last_status_daily."),
        ("5", "BI y analistas leen Aurora materializado; S3 queda para auditoria, replay y reprocesos."),
    ]
    y = 1760
    for idx, (n, text) in enumerate(steps):
        x = 130 + (idx % 3) * 980
        yy = y + (idx // 3) * 92
        badge(d, x, yy, n, BLUE if n not in {"3", "4"} else (TEAL if n == "3" else PURPLE))
        wrap(d, text, x + 55, yy - 2, 850, 28, F["small"], INK)

    save(img, "source-infra-ohip-storage-flow")


def write_mermaid_doc():
    doc = """# Flujo codigo fuente - infraestructura - OHIP - almacenamiento

```mermaid
flowchart LR
    subgraph SRC["Codigo fuente Python"]
        LISTENER_PY["listener.py<br/>graphql.py, oauth.py, offsets.py"]
        SQS_PY["sqs.py + events.py<br/>publicacion FIFO"]
        ENRICHER_PY["event_enricher.py<br/>event_router.py, identifier_resolver.py"]
        OHIP_PY["ohip_client.py + oauth.py<br/>Property APIs"]
        STORE_PY["raw_store.py<br/>enrichment_repositories.py"]
        ANALYTICS_PY["analytics_snapshot.py<br/>snapshots, pickups, last status"]
    end

    subgraph RUN["Infraestructura de ejecucion AWS"]
        ECS_LISTENER["ECS Fargate Listener"]
        FIFO["SQS FIFO"]
        DLQ["SQS DLQ"]
        ECS_ENRICHER["ECS Fargate Event Enricher"]
        ECS_ANALYTICS["ECS Analytics Task<br/>EventBridge schedule"]
        SUPPORT["Secrets Manager / IAM / KMS / CloudWatch / ECR"]
    end

    subgraph EXT["OHIP"]
        STREAM["OHIP Streaming API<br/>WebSocket GraphQL"]
        PROPERTY["OHIP Property APIs<br/>Reservation, Profile, Cashiering"]
    end

    subgraph DATA["Almacenamiento"]
        S3["S3 Raw Bucket<br/>raw JSON, resource snapshots, offsets"]
        PG["Aurora PostgreSQL<br/>opera_events, opera_raw, opera_core, opera_analytics"]
        BI["BI / SQL<br/>dashboards y analistas"]
    end

    LISTENER_PY --> ECS_LISTENER
    SQS_PY --> FIFO
    ENRICHER_PY --> ECS_ENRICHER
    OHIP_PY --> PROPERTY
    STORE_PY --> S3
    STORE_PY --> PG
    ANALYTICS_PY --> ECS_ANALYTICS

    STREAM -- "1 business events" --> ECS_LISTENER
    ECS_LISTENER -- "2 SendMessage uniqueEventId" --> FIFO
    FIFO -- "3 ReceiveMessage" --> ECS_ENRICHER
    FIFO -- "redrive" --> DLQ
    ECS_ENRICHER -- "4 GET resource details" --> PROPERTY
    ECS_ENRICHER -- "5 put raw" --> S3
    ECS_ENRICHER -- "6 upsert idempotente" --> PG
    ECS_ANALYTICS -- "7 lee core/raw metadata" --> PG
    ECS_ANALYTICS -- "8 materializa analytics" --> PG
    PG --> BI
    SUPPORT --> ECS_LISTENER
    SUPPORT --> ECS_ENRICHER
    SUPPORT --> ECS_ANALYTICS
```

## Secuencia operativa

```mermaid
sequenceDiagram
    participant SRC as Codigo Python
    participant OHIP as OHIP Streaming/API
    participant LIS as ECS Listener
    participant SQS as SQS FIFO/DLQ
    participant ENR as ECS Event Enricher
    participant S3 as S3 Raw
    participant PG as Aurora PostgreSQL
    participant JOB as Analytics Job
    participant BI as BI / Analistas

    SRC->>LIS: listener.py desplegado en ECS
    OHIP->>LIS: Business Event por WebSocket
    LIS->>SQS: Publica mensaje FIFO con uniqueEventId
    SQS->>ENR: Entrega mensaje al enricher
    ENR->>OHIP: ohip_client.py consulta Property API
    ENR->>S3: raw_store.py guarda raw JSON
    ENR->>PG: repositories.py ejecuta UPSERT idempotente
    JOB->>PG: analytics_snapshot.py lee opera_core
    JOB->>PG: Escribe snapshots, pickups y last status
    BI->>PG: Consulta tablas materializadas
```
"""
    (DOCS / "source-infra-ohip-storage-flow.md").write_text(doc, encoding="utf-8")


def main():
    render()
    write_mermaid_doc()


if __name__ == "__main__":
    main()
