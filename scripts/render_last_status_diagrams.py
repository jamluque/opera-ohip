# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)

W, H = 2400, 1500
BG = "#f7f8fb"
INK = "#172033"
MUTED = "#607086"
LINE = "#d7deea"
CARD = "#ffffff"
BLUE = "#2563ad"
GREEN = "#168064"
ORANGE = "#d97706"
PURPLE = "#6d5bd0"
RED = "#b42318"
TEAL = "#0f766e"
SLATE = "#475569"
YELLOW_BG = "#fff7ed"


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
    "title": font(58, True),
    "subtitle": font(29),
    "h1": font(40, True),
    "h2": font(31, True),
    "body": font(26),
    "small": font(22),
    "tiny": font(18),
    "metric": font(50, True),
}


def canvas(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((90, 72), title, fill=INK, font=F["title"])
    d.text((92, 145), subtitle, fill=MUTED, font=F["subtitle"])
    return img, d


def rounded(d: ImageDraw.ImageDraw, xy, *, fill=CARD, outline=LINE, radius=24, width=2):
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


def arrow(d: ImageDraw.ImageDraw, start, end, *, color=SLATE, width=7):
    d.line([start, end], fill=color, width=width)
    sx, sy = start
    ex, ey = end
    if abs(ex - sx) >= abs(ey - sy):
        if ex >= sx:
            pts = [(ex, ey), (ex - 25, ey - 14), (ex - 25, ey + 14)]
        else:
            pts = [(ex, ey), (ex + 25, ey - 14), (ex + 25, ey + 14)]
    else:
        if ey >= sy:
            pts = [(ex, ey), (ex - 14, ey - 25), (ex + 14, ey - 25)]
        else:
            pts = [(ex, ey), (ex - 14, ey + 25), (ex + 14, ey + 25)]
    d.polygon(pts, fill=color)


def box(d, xy, title, body, color, *, fill=CARD):
    rounded(d, xy, fill=fill, outline=color, radius=24, width=4)
    d.text((xy[0] + 28, xy[1] + 24), title, fill=color, font=F["h2"])
    wrap(d, body, xy[0] + 28, xy[1] + 76, xy[2] - xy[0] - 56, 31, F["small"], INK)


def save(img: Image.Image, name: str):
    img.save(OUTPUTS / f"{name}.png", optimize=True)
    img.save(OUTPUTS / f"{name}.jpg", quality=96, subsampling=0)


def render_architecture():
    img, d = canvas(
        "Arquitectura actualizada OPERA Cloud Analytics",
        "Streaming OHIP, procesamiento desacoplado, raw auditable, snapshots diarios, pickups y last status por reserva.",
    )
    top = [
        ((90, 285, 390, 455), "OPERA Cloud", "Business Events\nReservas, folios, perfiles", BLUE),
        ((455, 285, 755, 455), "OHIP Streaming", "WebSocket GraphQL\nOAuth + app key", PURPLE),
        ((820, 285, 1120, 455), "ECS Listener", "Heartbeat, reconexion\noffsets en S3", GREEN),
        ((1185, 285, 1485, 455), "SQS FIFO + DLQ", "Orden, buffer,\nreintentos", ORANGE),
        ((1550, 285, 1880, 455), "ECS Enricher", "OHIP APIs\nnormaliza recursos", GREEN),
        ((1945, 285, 2310, 455), "Aurora + S3", "Core SQL + raw JSON\nidempotencia", TEAL),
    ]
    for xy, title, body, color in top:
        box(d, xy, title, body, color)
    for i in range(len(top) - 1):
        arrow(d, (top[i][0][2] + 8, 370), (top[i + 1][0][0] - 16, 370))

    middle = [
        ((480, 690, 850, 885), "EventBridge", "Dispara el analytics-snapshot-job\ntras el cierre operativo", ORANGE),
        ((930, 690, 1320, 885), "ECS Analytics Job", "Construye snapshots diarios\ny refresca metricas", GREEN),
        ((1400, 620, 1780, 810), "reservation_daily_snapshot", "Base por noche de estancia\npara pickups y OTB", BLUE),
        ((1400, 850, 1780, 1040), "reservation_last_status_daily", "Una fila por reserva\nincluye canceladas/no-show", RED),
        ((1860, 620, 2250, 810), "pickup_metric", "Pickups 1, 3, 7, 15 dias\nrevenue, rooms, ADR", PURPLE),
        ((1860, 850, 2250, 1040), "BI / Negocio", "Dashboards y queries\nestables para analistas", BLUE),
    ]
    for xy, title, body, color in middle:
        box(d, xy, title, body, color)
    arrow(d, (2125, 463), (1125, 680), color=SLATE)
    arrow(d, (852, 785), (920, 785), color=SLATE)
    arrow(d, (1322, 785), (1390, 715), color=SLATE)
    arrow(d, (1322, 805), (1390, 945), color=SLATE)
    arrow(d, (1782, 715), (1850, 715), color=SLATE)
    arrow(d, (1782, 945), (1850, 945), color=SLATE)
    arrow(d, (2060, 820), (2060, 842), color=SLATE)

    rounded(d, (90, 1180, 2310, 1365), fill="#eef6ff", outline="#bfdbfe", radius=24)
    d.text((130, 1218), "Que cambia con last status", fill=BLUE, font=F["h1"])
    points = [
        "No se consulta OPERA para el informe: se lee una tabla diaria ya materializada.",
        "La granularidad se adapta a negocio: reserva unica, no una fila por noche.",
        "Los estados son texto flexible para absorber cambios de OPERA o decisiones de negocio.",
        "Canceladas y no-show quedan visibles como ultimo estado; pickups conserva la logica comparativa.",
    ]
    x = 130
    y = 1290
    for idx, point in enumerate(points):
        bx = x + idx * 540
        d.ellipse((bx, y + 8, bx + 16, y + 24), fill=GREEN)
        wrap(d, point, bx + 28, y, 480, 30, F["small"], INK)
    save(img, "architecture-last-status-updated")


def render_functional():
    img, d = canvas(
        "Vista funcional para negocio",
        "Tres salidas analiticas separadas: estado diario, pickups comparativos y rendimiento on-the-books.",
    )
    rounded(d, (100, 255, 2300, 430), fill="#edf7f4", outline="#b7e4d8", radius=24)
    d.text((145, 292), "Dato PMS procesado y gobernado", fill=GREEN, font=F["h1"])
    wrap(
        d,
        "Los eventos OHIP se convierten en una base analitica propia en AWS. Negocio no depende de extracciones manuales ni de consultas directas al PMS.",
        690,
        292,
        1500,
        36,
        F["body"],
        INK,
    )

    cards = [
        ((110, 585, 750, 990), "Last Status", "Pregunta que responde:\nEn que estado esta cada reserva hoy?\n\nGranularidad:\nUna fila por reserva.\n\nIncluye:\nRESERVED, CHECKED_IN, CHECKED_OUT, CANCELLED, NO_SHOW, UPDATE y nuevos estados.", RED),
        ((880, 585, 1520, 990), "Pickups", "Pregunta que responde:\nQue ha cambiado respecto a 1, 3, 7 o 15 dias?\n\nGranularidad:\nReserva + noche de estancia.\n\nIncluye:\nrooms, revenue, ADR, cancelaciones y segmentacion.", PURPLE),
        ((1650, 585, 2290, 990), "Rooms / Revenue OTB", "Pregunta que responde:\nCuanto tenemos vendido para una fecha futura?\n\nGranularidad:\nHotel, stay date y segmento.\n\nIncluye:\nhabitaciones, revenue, ADR, mercado, canal y source.", BLUE),
    ]
    for xy, title, body, color in cards:
        box(d, xy, title, body, color)

    bottom = [
        ((210, 1160, 610, 1320), "Direccion", "Vision resumida por hotel y estado", SLATE),
        ((730, 1160, 1130, 1320), "Revenue", "Pickups, ADR y revenue futuro", SLATE),
        ((1250, 1160, 1650, 1320), "Operaciones", "Llegadas, in-house, checked-out", SLATE),
        ((1770, 1160, 2170, 1320), "BI / Data", "Modelo estable para dashboards", SLATE),
    ]
    for xy, title, body, color in bottom:
        box(d, xy, title, body, color, fill="#f8fafc")
    for cx in (430, 950, 1470, 1990):
        arrow(d, (cx, 1000), (cx, 1150), color=SLATE)
    save(img, "functional-analytics-last-status")


def render_flow():
    img, d = canvas(
        "Flujo diario actualizado de analytics-snapshot-job",
        "El mismo job materializa snapshots por noche, last status por reserva y pickups comparativos.",
    )
    steps = [
        ("1", "Cierre / fecha informe", "Se fija snapshot_date = fecha de ejecucion del informe.", ORANGE),
        ("2", "Leer estado curado", "Aurora opera_core.reservation + ultimo raw snapshot.", TEAL),
        ("3", "Expandir por estancia", "Una fila por reserva y stay_date futura.", BLUE),
        ("4", "Guardar snapshot diario", "reservation_daily_snapshot queda estable.", BLUE),
        ("5", "Compactar reserva unica", "reservation_last_status_daily toma ultimo estado por reserva.", RED),
        ("6", "Calcular pickups", "pickup_metric compara contra snapshots 1/3/7/15 dias.", PURPLE),
        ("7", "Consumir en BI", "Dashboards leen tablas materializadas, no eventos raw.", GREEN),
    ]
    x0, y0 = 120, 270
    gap = 165
    for idx, (num, title, body, color) in enumerate(steps):
        y = y0 + idx * gap
        d.ellipse((x0, y, x0 + 88, y + 88), fill=color)
        d.text((x0 + 30, y + 19), num, fill="white", font=F["h1"])
        rounded(d, (260, y - 22, 2260, y + 118), fill=CARD, outline=color, radius=22, width=3)
        d.text((300, y + 5), title, fill=color, font=F["h2"])
        d.text((780, y + 8), body, fill=INK, font=F["body"])
        if idx < len(steps) - 1:
            arrow(d, (x0 + 44, y + 92), (x0 + 44, y + gap - 12), color=SLATE, width=6)

    rounded(d, (1450, 1185, 2260, 1370), fill=YELLOW_BG, outline="#fed7aa", radius=24)
    d.text((1490, 1222), "Regla funcional clave", fill=ORANGE, font=F["h1"])
    wrap(
        d,
        "Last status no filtra canceladas ni no-show. Su objetivo es mostrar el ultimo estado diario de cada reserva; pickups se encarga de comparar cambios entre fechas.",
        1490,
        1282,
        700,
        34,
        F["small"],
        INK,
    )
    save(img, "flow-analytics-last-status")


def write_mermaid_doc():
    doc = """# Diagramas actualizados - OPERA Cloud Analytics con last status

## Arquitectura end-to-end

```mermaid
flowchart LR
    OPERA["OPERA Cloud PMS<br/>Business Events"] --> OHIP["OHIP Streaming API<br/>WebSocket GraphQL"]
    OHIP --> LISTENER["ECS Fargate Listener<br/>OAuth, heartbeat, offsets"]
    LISTENER --> SQS["SQS FIFO + DLQ<br/>orden, buffer, reintentos"]
    SQS --> ENRICHER["ECS Event Enricher<br/>OHIP Property APIs"]
    ENRICHER --> RAW["S3 raw JSON<br/>evidencia auditable"]
    ENRICHER --> CORE["Aurora PostgreSQL<br/>opera_core actual"]
    CORE --> JOB["ECS analytics-snapshot-job<br/>diario"]
    RAW --> JOB
    JOB --> SNAP["reservation_daily_snapshot<br/>reserva + stay_date"]
    JOB --> LAST["reservation_last_status_daily<br/>reserva unica"]
    SNAP --> PICKUP["pickup_metric<br/>1, 3, 7, 15 dias"]
    LAST --> BI["BI / Negocio<br/>last status"]
    PICKUP --> BI
```

## Vista funcional

```mermaid
flowchart TB
    DATA["Dato PMS gobernado en AWS"] --> LAST["Last Status<br/>Estado diario por reserva unica<br/>Incluye CANCELLED y NO_SHOW"]
    DATA --> PICKUPS["Pickups<br/>Comparacion 1, 3, 7, 15 dias<br/>Rooms, revenue, ADR"]
    DATA --> OTB["On the Books<br/>Habitaciones y revenue futuro"]
    LAST --> OPS["Operaciones<br/>Llegadas, in-house, checked-out"]
    LAST --> DIR["Direccion<br/>Resumen por hotel y estado"]
    PICKUPS --> REV["Revenue Management<br/>Evolucion de demanda"]
    OTB --> BI["BI<br/>Dashboards estables"]
```

## Flujo diario

```mermaid
sequenceDiagram
    participant EVT as EventBridge diario
    participant JOB as ECS analytics-snapshot-job
    participant CORE as Aurora opera_core
    participant RAW as S3/opera_raw
    participant SNAP as reservation_daily_snapshot
    participant LAST as reservation_last_status_daily
    participant PICK as pickup_metric
    participant BI as BI / Analistas

    EVT->>JOB: Ejecuta snapshot_date = fecha informe
    JOB->>CORE: Lee reservas actuales
    JOB->>RAW: Recupera payload raw mas reciente
    JOB->>SNAP: Materializa reserva + stay_date
    JOB->>LAST: Compacta a reserva unica y ultimo estado
    JOB->>PICK: Calcula pickups 1/3/7/15 dias
    BI->>LAST: Consulta last status diario
    BI->>PICK: Consulta pickups comparativos
```
"""
    (ROOT / "docs" / "architecture-diagrams-last-status.md").write_text(doc, encoding="utf-8")


def main():
    render_architecture()
    render_functional()
    render_flow()
    write_mermaid_doc()


if __name__ == "__main__":
    main()
