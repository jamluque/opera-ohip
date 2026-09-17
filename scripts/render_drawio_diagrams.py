# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "drawio"
OUT.mkdir(parents=True, exist_ok=True)

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
    "code_bg": "#eef2ff",
    "aws_bg": "#edf7f4",
    "data_bg": "#fff7ed",
    "vpc_bg": "#eef6ff",
    "private_bg": "#edf7f4",
    "support_bg": "#f8fafc",
}


def style_box(stroke: str, fill: str = "#ffffff", font_size: int = 14, bold: bool = False) -> str:
    font_style = "1" if bold else "0"
    return (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=12;spacing=10;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth=2;"
        "fontFamily=Segoe UI;align=center;verticalAlign=middle;"
        f"fontSize={font_size};fontStyle={font_style};fontColor={COLORS['ink']};"
    )


def style_container(stroke: str, fill: str) -> str:
    return (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;spacing=12;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth=3;"
        "fontFamily=Segoe UI;fontSize=20;fontStyle=1;align=left;verticalAlign=top;"
        f"fontColor={stroke};"
    )


def style_edge(color: str) -> str:
    return (
        "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
        f"strokeColor={color};strokeWidth=2;endArrow=block;endFill=1;"
        "fontFamily=Segoe UI;fontSize=11;fontColor=#172033;labelBackgroundColor=#f7f8fb;"
    )


class DrawioPage:
    def __init__(self, name: str, width: int = 1600, height: int = 1000) -> None:
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

    def title(self, text: str, subtitle: str | None = None) -> None:
        self.text(text, 40, 30, self.width - 80, 50, size=26, bold=True, color=COLORS["ink"])
        if subtitle:
            self.text(subtitle, 42, 82, self.width - 84, 34, size=14, color=COLORS["muted"])

    def text(self, value: str, x: int, y: int, w: int, h: int, *, size: int = 13, bold: bool = False, color: str = "#172033") -> str:
        cell_id = self._id("text")
        style = (
            "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;"
            f"fontFamily=Segoe UI;fontSize={size};fontStyle={'1' if bold else '0'};fontColor={color};"
        )
        cell = ET.SubElement(self.root, "mxCell", {"id": cell_id, "value": value, "style": style, "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        return cell_id

    def rect(self, value: str, x: int, y: int, w: int, h: int, *, stroke: str = "#2563ad", fill: str = "#ffffff", size: int = 14, bold: bool = False) -> str:
        cell_id = self._id("node")
        cell = ET.SubElement(self.root, "mxCell", {"id": cell_id, "value": value, "style": style_box(stroke, fill, size, bold), "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        return cell_id

    def container(self, value: str, x: int, y: int, w: int, h: int, *, stroke: str, fill: str) -> str:
        cell_id = self._id("container")
        cell = ET.SubElement(self.root, "mxCell", {"id": cell_id, "value": value, "style": style_container(stroke, fill), "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        return cell_id

    def edge(self, source: str, target: str, label: str = "", *, color: str = "#475569") -> str:
        cell_id = self._id("edge")
        cell = ET.SubElement(
            self.root,
            "mxCell",
            {
                "id": cell_id,
                "value": label,
                "style": style_edge(color),
                "edge": "1",
                "parent": "1",
                "source": source,
                "target": target,
            },
        )
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        return cell_id

    def to_diagram(self, name: str | None = None) -> ET.Element:
        diagram = ET.Element("diagram", {"id": self._id("page"), "name": name or self.name})
        diagram.append(self.model)
        return diagram


def box_label(title: str, *lines: str) -> str:
    body = "<br/>".join(lines)
    return f"<b>{title}</b><br/>{body}" if body else f"<b>{title}</b>"


def page_architecture() -> DrawioPage:
    p = DrawioPage("Arquitectura Last Status", 1700, 1050)
    p.title("Arquitectura actualizada OPERA Cloud Analytics", "Streaming OHIP, SQS, enrichment, raw/core, snapshots, pickups y last status")
    opera = p.rect(box_label("OPERA Cloud", "Business Events", "reservas / folios / perfiles"), 40, 180, 190, 110, stroke=COLORS["blue"])
    ohip = p.rect(box_label("OHIP Streaming", "WebSocket GraphQL", "OAuth + app key"), 280, 180, 190, 110, stroke=COLORS["purple"])
    listener = p.rect(box_label("ECS Listener", "heartbeat", "reconexion", "offsets S3"), 520, 180, 190, 110, stroke=COLORS["green"])
    sqs = p.rect(box_label("SQS FIFO + DLQ", "orden", "buffer", "reintentos"), 760, 180, 190, 110, stroke=COLORS["orange"])
    enricher = p.rect(box_label("ECS Enricher", "OHIP APIs", "normaliza recursos"), 1000, 180, 210, 110, stroke=COLORS["green"])
    aurora_s3 = p.rect(box_label("Aurora + S3", "core SQL", "raw JSON", "idempotencia"), 1270, 180, 210, 110, stroke=COLORS["teal"])
    eventbridge = p.rect(box_label("EventBridge", "schedule diario"), 330, 450, 210, 110, stroke=COLORS["orange"])
    job = p.rect(box_label("ECS Analytics Job", "snapshot", "last status", "pickups"), 610, 450, 230, 110, stroke=COLORS["green"])
    snapshot = p.rect(box_label("reservation_daily_snapshot", "reserva + stay_date", "base pickups"), 930, 395, 250, 110, stroke=COLORS["blue"])
    last = p.rect(box_label("reservation_last_status_daily", "reserva unica", "incluye CANCELLED/NO_SHOW"), 930, 555, 250, 110, stroke=COLORS["red"])
    pickup = p.rect(box_label("pickup_metric", "1, 3, 7, 15 dias", "rooms / revenue / ADR"), 1270, 395, 230, 110, stroke=COLORS["purple"])
    bi = p.rect(box_label("BI / Negocio", "dashboards", "queries estables"), 1270, 555, 230, 110, stroke=COLORS["blue"])
    for a, b, label in [(opera, ohip, "1"), (ohip, listener, "2"), (listener, sqs, "3"), (sqs, enricher, "4"), (enricher, aurora_s3, "5")]:
        p.edge(a, b, label, color=COLORS["slate"])
    p.edge(aurora_s3, job, "6 lee core/raw", color=COLORS["teal"])
    p.edge(eventbridge, job, "schedule", color=COLORS["orange"])
    p.edge(job, snapshot, "7", color=COLORS["blue"])
    p.edge(job, last, "8", color=COLORS["red"])
    p.edge(snapshot, pickup, "9", color=COLORS["purple"])
    p.edge(last, bi, "last status", color=COLORS["blue"])
    p.edge(pickup, bi, "pickups", color=COLORS["blue"])
    p.rect(box_label("Regla clave", "Last status no filtra canceladas ni no-show.", "Pickups compara snapshots entre fechas."), 80, 800, 1450, 110, stroke=COLORS["orange"], fill="#fff7ed", size=16)
    return p


def page_functional() -> DrawioPage:
    p = DrawioPage("Vista Funcional", 1600, 1000)
    p.title("Vista funcional para negocio", "Tres salidas analiticas separadas sobre el dato PMS gobernado en AWS")
    data = p.rect(box_label("Dato PMS procesado y gobernado", "Eventos OHIP convertidos en modelo analitico propio", "sin consultas directas al PMS"), 170, 155, 1180, 110, stroke=COLORS["green"], fill="#edf7f4", size=17, bold=True)
    last = p.rect(box_label("Last Status", "En que estado esta cada reserva hoy?", "Granularidad: reserva unica", "Incluye CANCELLED y NO_SHOW"), 90, 390, 390, 240, stroke=COLORS["red"], size=15)
    pickups = p.rect(box_label("Pickups", "Que cambio vs 1/3/7/15 dias?", "Granularidad: reserva + stay_date", "Rooms, revenue, ADR"), 590, 390, 390, 240, stroke=COLORS["purple"], size=15)
    otb = p.rect(box_label("Rooms / Revenue OTB", "Cuanto tenemos vendido a futuro?", "Hotel, stay_date y segmento", "Mercado, canal, source"), 1090, 390, 390, 240, stroke=COLORS["blue"], size=15)
    ops = p.rect(box_label("Operaciones", "llegadas", "in-house", "checked-out"), 150, 760, 260, 110, stroke=COLORS["slate"], fill="#f8fafc")
    revenue = p.rect(box_label("Revenue", "pickups", "ADR", "forecast base"), 490, 760, 260, 110, stroke=COLORS["slate"], fill="#f8fafc")
    direccion = p.rect(box_label("Direccion", "resumen por hotel", "estado"), 830, 760, 260, 110, stroke=COLORS["slate"], fill="#f8fafc")
    bi = p.rect(box_label("BI / Data", "dashboards", "SQL estable"), 1170, 760, 260, 110, stroke=COLORS["slate"], fill="#f8fafc")
    for target in [last, pickups, otb]:
        p.edge(data, target, color=COLORS["slate"])
    p.edge(last, ops, color=COLORS["red"])
    p.edge(pickups, revenue, color=COLORS["purple"])
    p.edge(last, direccion, color=COLORS["blue"])
    p.edge(otb, bi, color=COLORS["blue"])
    return p


def page_daily_flow() -> DrawioPage:
    p = DrawioPage("Flujo Diario Analytics", 1600, 1100)
    p.title("Flujo diario actualizado de analytics-snapshot-job", "El mismo job materializa snapshots por noche, last status por reserva y pickups comparativos")
    steps = [
        ("1", "Cierre / fecha informe", "snapshot_date = fecha de ejecucion del informe", COLORS["orange"]),
        ("2", "Leer estado curado", "Aurora opera_core.reservation + ultimo raw snapshot", COLORS["teal"]),
        ("3", "Expandir por estancia", "una fila por reserva y stay_date futura", COLORS["blue"]),
        ("4", "Guardar snapshot diario", "reservation_daily_snapshot estable", COLORS["blue"]),
        ("5", "Compactar reserva unica", "reservation_last_status_daily toma ultimo estado", COLORS["red"]),
        ("6", "Calcular pickups", "pickup_metric compara 1/3/7/15 dias", COLORS["purple"]),
        ("7", "Consumir en BI", "dashboards leen tablas materializadas", COLORS["green"]),
    ]
    previous = None
    for idx, (n, title, body, color) in enumerate(steps):
        y = 155 + idx * 115
        node = p.rect(box_label(f"{n}. {title}", body), 240, y, 1050, 78, stroke=color, size=15)
        if previous:
            p.edge(previous, node, color=COLORS["slate"])
        previous = node
    p.rect(box_label("Regla funcional", "Last status no filtra canceladas ni no-show.", "Pickups conserva la comparativa entre fechas."), 250, 950, 1030, 90, stroke=COLORS["orange"], fill="#fff7ed")
    return p


def page_infrastructure() -> DrawioPage:
    p = DrawioPage("Infraestructura y Flujos", 2200, 1450)
    p.title("Arquitectura de infraestructura y flujos", "VPC, ECS, SQS, S3, Aurora, seguridad, observabilidad y analytics")
    p.container("Oracle Hospitality", 40, 160, 300, 300, stroke=COLORS["slate"], fill="#ffffff")
    opera = p.rect(box_label("OPERA Cloud PMS", "Business Events"), 75, 245, 230, 75, stroke=COLORS["blue"])
    ohip = p.rect(box_label("OHIP", "OAuth", "Streaming + Property APIs"), 75, 355, 230, 95, stroke=COLORS["purple"])
    p.edge(opera, ohip, color=COLORS["purple"])
    p.container("AWS Account / Region - VPC multi-AZ", 400, 160, 1710, 900, stroke=COLORS["blue"], fill=COLORS["vpc_bg"])
    p.container("Subredes publicas", 440, 245, 1580, 135, stroke=COLORS["orange"], fill="#fff7ed")
    p.rect(box_label("Internet Gateway"), 500, 300, 210, 55, stroke=COLORS["orange"])
    nat = p.rect(box_label("NAT Gateway", "salida a OHIP"), 785, 300, 210, 55, stroke=COLORS["orange"])
    p.rect(box_label("Route Tables"), 1070, 300, 210, 55, stroke=COLORS["orange"])
    p.container("Subredes privadas ECS", 440, 430, 1580, 275, stroke=COLORS["green"], fill=COLORS["private_bg"])
    listener = p.rect(box_label("ECS Listener", "WebSocket", "offsets"), 500, 520, 210, 90, stroke=COLORS["green"])
    fifo = p.rect(box_label("SQS FIFO", "dedupe", "ordering"), 785, 520, 210, 90, stroke=COLORS["orange"])
    enricher = p.rect(box_label("ECS Enricher", "OHIP APIs", "upsert"), 1070, 520, 210, 90, stroke=COLORS["green"])
    dlq = p.rect(box_label("SQS DLQ", "errores"), 1355, 520, 210, 90, stroke=COLORS["red"])
    analytics = p.rect(box_label("ECS Analytics Job", "snapshots", "last status", "pickups"), 1640, 520, 230, 90, stroke=COLORS["green"])
    p.container("Capa de datos", 440, 770, 1580, 175, stroke=COLORS["teal"], fill="#f5f3ff")
    s3 = p.rect(box_label("S3 Raw", "raw JSON", "offsets"), 500, 835, 210, 70, stroke=COLORS["teal"])
    aurora = p.rect(box_label("Aurora PostgreSQL", "events/raw/core"), 785, 835, 230, 70, stroke=COLORS["teal"])
    snapshot = p.rect(box_label("Snapshots", "daily_snapshot"), 1090, 835, 210, 70, stroke=COLORS["blue"])
    last = p.rect(box_label("Last Status", "reserva unica"), 1375, 835, 210, 70, stroke=COLORS["red"])
    pickup = p.rect(box_label("Pickups", "1/3/7/15"), 1660, 835, 210, 70, stroke=COLORS["purple"])
    p.container("Soporte", 440, 1100, 1580, 170, stroke=COLORS["slate"], fill="#f8fafc")
    secrets = p.rect(box_label("Secrets Manager"), 500, 1165, 210, 60, stroke=COLORS["purple"])
    iam = p.rect(box_label("IAM + KMS"), 785, 1165, 210, 60, stroke=COLORS["purple"])
    cw = p.rect(box_label("CloudWatch"), 1070, 1165, 210, 60, stroke=COLORS["red"])
    eb = p.rect(box_label("EventBridge"), 1355, 1165, 210, 60, stroke=COLORS["orange"])
    ecr = p.rect(box_label("ECR"), 1640, 1165, 210, 60, stroke=COLORS["orange"])
    p.edge(ohip, listener, "1 WS", color=COLORS["purple"])
    p.edge(listener, fifo, "2", color=COLORS["orange"])
    p.edge(fifo, enricher, "3", color=COLORS["orange"])
    p.edge(fifo, dlq, "redrive", color=COLORS["red"])
    p.edge(enricher, nat, "OHIP REST", color=COLORS["purple"])
    p.edge(enricher, s3, "4 raw", color=COLORS["teal"])
    p.edge(enricher, aurora, "5 upsert", color=COLORS["teal"])
    p.edge(eb, analytics, "6 schedule", color=COLORS["orange"])
    p.edge(analytics, aurora, "lee core", color=COLORS["teal"])
    p.edge(analytics, snapshot, "7", color=COLORS["blue"])
    p.edge(snapshot, last, "8", color=COLORS["red"])
    p.edge(snapshot, pickup, "9", color=COLORS["purple"])
    for support, target in [(secrets, listener), (iam, enricher), (cw, analytics), (ecr, analytics)]:
        p.edge(support, target, color=COLORS["slate"])
    return p


def page_source_flow() -> DrawioPage:
    p = DrawioPage("Codigo Infra OHIP Storage", 2100, 1300)
    p.title("Flujo codigo fuente -> infraestructura -> OHIP y almacenamiento", "Modulos Python ejecutados en ECS y persistencia en S3/Aurora")
    p.container("Codigo fuente Python", 40, 160, 520, 880, stroke=COLORS["purple"], fill=COLORS["code_bg"])
    listener_py = p.rect(box_label("listener.py", "graphql.py", "oauth.py", "offsets.py"), 80, 250, 430, 80, stroke=COLORS["purple"])
    sqs_py = p.rect(box_label("sqs.py + events.py", "publicacion FIFO"), 80, 360, 430, 80, stroke=COLORS["purple"])
    enricher_py = p.rect(box_label("event_enricher.py", "router + resolver"), 80, 470, 430, 80, stroke=COLORS["purple"])
    ohip_py = p.rect(box_label("ohip_client.py + oauth.py", "REST Property APIs"), 80, 580, 430, 80, stroke=COLORS["purple"])
    store_py = p.rect(box_label("raw_store.py + repositories.py", "S3 + PostgreSQL"), 80, 690, 430, 80, stroke=COLORS["purple"])
    analytics_py = p.rect(box_label("analytics_snapshot.py", "snapshots", "pickups", "last status"), 80, 800, 430, 95, stroke=COLORS["purple"])
    p.container("Infraestructura AWS", 650, 160, 610, 880, stroke=COLORS["green"], fill=COLORS["aws_bg"])
    ecs_listener = p.rect(box_label("ECS Listener"), 700, 250, 210, 70, stroke=COLORS["green"])
    fifo = p.rect(box_label("SQS FIFO"), 980, 250, 210, 70, stroke=COLORS["orange"])
    ecs_enricher = p.rect(box_label("ECS Enricher"), 700, 470, 210, 70, stroke=COLORS["green"])
    dlq = p.rect(box_label("SQS DLQ"), 980, 470, 210, 70, stroke=COLORS["red"])
    ecs_analytics = p.rect(box_label("ECS Analytics Task", "EventBridge"), 700, 800, 250, 80, stroke=COLORS["green"])
    support = p.rect(box_label("Secrets / IAM / KMS", "CloudWatch / ECR"), 700, 915, 490, 75, stroke=COLORS["slate"], fill="#f8fafc")
    p.container("OHIP y almacenamiento", 1360, 160, 670, 880, stroke=COLORS["teal"], fill=COLORS["data_bg"])
    stream = p.rect(box_label("OHIP Streaming API", "WebSocket GraphQL"), 1410, 250, 540, 85, stroke=COLORS["purple"])
    property_api = p.rect(box_label("OHIP Property APIs", "Reservation / Profile / Cashiering"), 1410, 430, 540, 85, stroke=COLORS["purple"])
    s3 = p.rect(box_label("S3 Raw Bucket", "raw JSON", "resource snapshots", "offsets"), 1410, 625, 540, 95, stroke=COLORS["teal"])
    pg = p.rect(box_label("Aurora PostgreSQL", "opera_events", "opera_raw", "opera_core", "opera_analytics"), 1410, 780, 540, 115, stroke=COLORS["teal"])
    bi = p.rect(box_label("BI / SQL", "dashboards y analistas"), 1410, 940, 540, 70, stroke=COLORS["blue"])
    for src, dst in [(listener_py, ecs_listener), (sqs_py, fifo), (enricher_py, ecs_enricher), (analytics_py, ecs_analytics)]:
        p.edge(src, dst, color=COLORS["slate"])
    p.edge(stream, ecs_listener, "1 business events", color=COLORS["purple"])
    p.edge(ecs_listener, fifo, "2 SendMessage", color=COLORS["orange"])
    p.edge(fifo, ecs_enricher, "3 Receive", color=COLORS["orange"])
    p.edge(fifo, dlq, "redrive", color=COLORS["red"])
    p.edge(ecs_enricher, property_api, "4 GET detail", color=COLORS["purple"])
    p.edge(ohip_py, property_api, color=COLORS["purple"])
    p.edge(store_py, s3, "5 put raw", color=COLORS["teal"])
    p.edge(store_py, pg, "6 upsert", color=COLORS["teal"])
    p.edge(ecs_enricher, s3, color=COLORS["teal"])
    p.edge(ecs_enricher, pg, color=COLORS["teal"])
    p.edge(ecs_analytics, pg, "7 analytics", color=COLORS["blue"])
    p.edge(pg, bi, "8 reporting", color=COLORS["blue"])
    p.edge(support, ecs_listener, color=COLORS["slate"])
    p.edge(support, ecs_enricher, color=COLORS["slate"])
    p.edge(support, ecs_analytics, color=COLORS["slate"])
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


def main() -> None:
    factories = [
        ("architecture-last-status-updated.drawio", page_architecture),
        ("functional-analytics-last-status.drawio", page_functional),
        ("flow-analytics-last-status.drawio", page_daily_flow),
        ("infrastructure-flows-detailed-last-status.drawio", page_infrastructure),
        ("source-infra-ohip-storage-flow.drawio", page_source_flow),
    ]
    pages = []
    for filename, factory in factories:
        page = factory()
        pages.append(page)
        write_drawio(OUT / filename, [page])
    write_drawio(OUT / "opera-analytics-all-diagrams.drawio", pages)


if __name__ == "__main__":
    main()
