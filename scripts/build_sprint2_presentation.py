"""Build the delivery PDF from verified evidence (requires reportlab)."""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/delivery/dataforge-sprint2.pdf"
REPO = "https://github.com/jcramonp/DataForge"
WIDTH, HEIGHT = 960, 540
NAVY = colors.HexColor("#12233d")
BLUE = colors.HexColor("#155eef")
MUTED = colors.HexColor("#4b5e75")


def main() -> None:
    regular = Path("C:/Windows/Fonts/arial.ttf")
    bold = Path("C:/Windows/Fonts/arialbd.ttf")
    font, strong = "Helvetica", "Helvetica-Bold"
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("Deck", str(regular)))
        pdfmetrics.registerFont(TTFont("DeckBold", str(bold)))
        font, strong = "Deck", "DeckBold"
    styles = {
        "body": ParagraphStyle("body", fontName=font, fontSize=19, leading=27, textColor=NAVY),
        "small": ParagraphStyle("small", fontName=font, fontSize=14, leading=19, textColor=MUTED),
        "cell": ParagraphStyle("cell", fontName=font, fontSize=16, leading=22, textColor=NAVY),
        "code": ParagraphStyle("code", fontName="Courier", fontSize=15, leading=22, textColor=NAVY),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(WIDTH, HEIGHT))
    pdf.setTitle("DataForge - Sprint 2 | Evidencia y demostracion")
    pdf.setAuthor("Equipo DataForge")
    page = 0

    def paragraph(text, y, style="body", x=54, width=852):
        p = Paragraph(text, styles[style])
        _, h = p.wrap(width, HEIGHT)
        if y - h < 64:
            raise ValueError(f"Slide {page}: text exceeds content area")
        p.drawOn(pdf, x, y - h)
        return y - h - 18

    def start(title, subtitle):
        nonlocal page
        if page:
            pdf.showPage()
        page += 1
        pdf.setFillColor(colors.white)
        pdf.rect(0, 0, WIDTH, HEIGHT, fill=1, stroke=0)
        pdf.setFillColor(BLUE)
        pdf.rect(0, HEIGHT - 10, WIDTH, 10, fill=1, stroke=0)
        pdf.setFont(strong, 12)
        pdf.drawString(54, 497, "DATAFORGE  /  SPRINT 2  /  26 OCT 2026")
        pdf.setFillColor(NAVY)
        pdf.setFont(strong, 30)
        pdf.drawString(54, 447, title)
        paragraph(subtitle, 420, "small")
        pdf.setStrokeColor(colors.HexColor("#d8e0eb"))
        pdf.line(54, 51, 906, 51)
        pdf.setFont(font, 10)
        pdf.setFillColor(MUTED)
        pdf.drawString(54, 32, REPO + "  |  Version de entrega: develop")
        pdf.linkURL(REPO + "/tree/develop", (54, 24, 650, 45), relative=0)
        pdf.drawRightString(906, 32, f"{page:02d}")

    def bullets(items, y=365):
        for index, item in enumerate(items, 1):
            y = paragraph(f'<font color="#155eef">{index:02d}</font>  {item}', y)

    def table(rows, widths, y=365):
        cells = [[Paragraph(escape(str(v)), styles["cell"]) for v in row] for row in rows]
        t = Table(cells, colWidths=widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0ff")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fc")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        _, h = t.wrap(852, HEIGHT)
        if y - h < 64:
            raise ValueError(f"Slide {page}: table exceeds content area")
        t.drawOn(pdf, 54, y - h)
        return y - h - 22

    results = json.loads((ROOT / "docs/evidence/metadata-performance-results.json").read_text())
    live = json.loads((ROOT / "docs/evidence/olist-final-live-run.json").read_text())
    if live["status"]["state"] != "success":
        raise ValueError("Olist final evidence is not successful")

    start("De un piloto a una plataforma por contratos", "Entrega local verificable: captura, limpieza, almacenamiento y gobierno de datos.")
    bullets([
        "Sprint 1: flujo específico de Olist. Sprint 2: motores reutilizables para CSV, PostgreSQL y REST.",
        "Un contrato define esquema, transformaciones y calidad; Airflow ejecuta etapas comunes.",
        "Demostraciones reales: Olist completo, ventas CSV y tareas REST con cuarentena y linaje.",
        "Repositorio privado: confirmar acceso del profesor y publicar este conjunto de cambios antes de entregar.",
    ])

    start("Qué cambió frente al Sprint 1", "El avance principal es la generalización y la operación desde un control plane.")
    table([
        ["Sprint 1", "Sprint 2"],
        ["Scripts de Olist", "Contratos tipados y conectores/motores genéricos"],
        ["Configuración y ejecución técnica", "Onboarding API/UI y contratos con revisiones persistidas"],
        ["Calidad y capas del piloto", "Profiling, reglas configurables y cuarentena por severidad"],
        ["Modelo inicial de gobierno", "Linaje de activos, certificación auditada y copilot con aprobación"],
    ], [330, 522])

    start("Arquitectura que está funcionando", "PostgreSQL guarda metadatos; MinIO guarda los registros de negocio en Parquet.")
    table([
        ["Capa", "Componentes y flujo"],
        ["Operación", "React → FastAPI → contratos PostgreSQL → Airflow"],
        ["Datos", "CSV / PostgreSQL / REST → Bronze → profiling → Silver/calidad"],
        ["Salida", "Silver validado o cuarentena → Gold configurado → gobierno"],
        ["Copilot", "Bedrock propone JSON; validación y aprobación crean una revisión"],
    ], [180, 672])

    start("Código e infraestructura como código", "La entrega ejecutada es local. AWS es una referencia, no un despliegue demostrado.")
    bullets([
        "Docker Compose declara servicios, dependencias, redes, volúmenes y healthchecks; Dockerfiles construyen API y Airflow.",
        "Migraciones versionadas inicializan y actualizan PostgreSQL con checksum e idempotencia.",
        "Están implementados conectores, Bronze, profiling, Silver/calidad, Gold, orquestación, API y UI.",
        "DataOps completo y consumo downstream corresponden al Sprint Final según la rúbrica.",
    ])

    start("Demo en vivo: seis ventas, dos errores", "Fuente: data/demo/ventas_demo.csv | contrato demostrado #12 | orquestación #16.")
    y = table([
        ["Bronze", "Silver validado", "Cuarentena"],
        ["6 filas", "4 filas", "2 filas"],
    ], [284, 284, 284])
    y = paragraph("Reglas críticas: cantidad &gt; 0 y precio &gt; 0; mostly=1; allow_null=false.", y)
    paragraph("Venta 4: cantidad=0. Venta 5: precio=-3000. Mostrar reglas, activos almacenados, filas aisladas y linaje; esperar SUCCESS sobre el mismo ID.", y)

    start("Regresión completa y segunda fuente", "Olist se volvió a ejecutar por API + Airflow con el contrato genérico #13.")
    y = table([
        ["Evidencia", "Resultado observado"],
        ["Olist: orquestación #17", "SUCCESS; cuatro datasets + Gold + evaluación de certificación"],
        ["Olist: entrada y salida", "344.483 filas Bronze; products: 32.947 Silver + 4 cuarentena"],
        ["Olist: integración Gold", "112.642 filas; 9 relaciones de linaje hacia activos nuevos"],
        ["REST: /todos", "200 Bronze → 160 Silver + 40 cuarentena por userId > 8"],
    ], [285, 567])
    paragraph("REST corresponde a la corrida demostrada #11. Una nueva extracción depende del servicio externo. Gold puede reducir filas por joins: esa diferencia no es cuarentena.", y, "small")

    for name, title, description in [
        ("latest_version_index", "Optimización 1: índice compuesto", "Última versión por dataset: filtro y orden resueltos por un índice B-tree."),
        ("materialized_run_totals", "Optimización 2: vista materializada", "Reporte de corridas preagregado; refresco explícito y datos snapshot."),
    ]:
        start(title, description)
        q = escape(results["queries"][name]).replace("\n", "<br/>")
        y = paragraph(q, 365, "code")
        before = results["before"][name]["median_ms"]
        after = results["after"][name]["median_ms"]
        y = table([["Antes", "Después", "Resultados"],
                   [f"{before:.3f} ms", f"{after:.3f} ms", f"Iguales; {before / after:.2f}x"]],
                  [250, 250, 352], y)
        paragraph("SQL idéntico antes/después. 300.000 versiones y 300.000 corridas sintéticas aisladas; 7 muestras, mediana y caché caliente. Planes completos en metadata-performance-results.json.", y, "small")

    start("Optimizaciones aplicadas y límites", "Migración 0008 aplicada a la base real; el benchmark de volumen no altera sus datos.")
    bullets([
        "Índice de última versión y materializado creados en PostgreSQL. El snapshot se verificó contra la agregación real: igualdad exacta.",
        f"Construcción conjunta en prueba: {results['build_ms']:.1f} ms. Refresco: {results['refresh_ms']:.1f} ms; ambos costos se reportan.",
        "El índice agrega espacio y costo de escritura. La vista requiere refresco y puede quedar desactualizada; el overview mantiene consultas vivas.",
        "Las mejoras medidas son locales sobre volumen sintético. No se extrapolan a AWS ni se cuenta el experimento temporal Parquet como optimización productiva.",
    ])

    start("Calidad y gobierno que se pueden inspeccionar", "El repositorio y la interfaz muestran definiciones, resultados y trazabilidad.")
    table([
        ["Requisito", "Dónde se verifica"],
        ["Diccionario y catálogo", "Significado, tipo, claves, nulos y clasificación; tablas + API/UI"],
        ["Reglas implementadas", "Contrato activo → quality_result → Silver o cuarentena"],
        ["Linaje", "asset_lineage enlaza activos de origen y salida; 9 links en Olist final"],
        ["RACI y certificación", "Responsabilidades operativas; transiciones explícitas y auditadas"],
    ], [270, 582])

    start("Problemas encontrados y cómo se resolvieron", "Las evidencias distinguen fallos de monitoreo, configuración y calidad de datos.")
    table([
        ["Problema", "Resolución"],
        ["npm ausente / puerto API ocupado", "Configurar Node; identificar y reiniciar la instancia correcta"],
        ["Consulta de estado falla temporalmente", "Reintentar el mismo ID; no duplicar la corrida aceptada"],
        ["Propuesta LLM inválida o campo inexistente", "Validación estricta y explicación; ninguna aplicación automática"],
        ["Optimización sin baseline comparable", "Mismo SQL, resultados iguales, muestras y planes antes/después"],
    ], [340, 512])

    start("Conocimientos aplicados", "Mapeo técnico para la sustentación; el equipo valida los nombres oficiales de sus materias.")
    y = table([
        ["Origen", "Aplicación concreta"],
        ["Curso", "ETL/ELT, calidad, capas de almacenamiento, modelado y optimización"],
        ["Otras materias de la trayectoria", "Bases de datos: SQL/índices; programación: módulos/pruebas; estadística: profiling; APIs"],
        ["Aprendizaje autónomo del proyecto", "Pydantic, Airflow/FastAPI/React, S3/MinIO y Bedrock con aprobación humana"],
    ], [275, 577])
    paragraph("Cada integrante prepara un ejemplo que pueda explicar y ajusta este mapeo a su experiencia real. No se atribuyen al curso contenidos ni aportes individuales sin confirmación.", y, "small")

    start("Verificación y entrega", "Código, documentación y evidencia vinculados en docs/delivery/sprint2-requirements.md.")
    bullets([
        "Suite Python: 349 casos, 35 omitidos por integración; sin fallos. Después se añadieron y pasaron 2 pruebas PostgreSQL nuevas.",
        "Todas las migraciones se aplicaron dos veces sobre un esquema aislado nuevo; benchmark verificó igualdad y rollback.",
        "Ensayo real Olist completo exitoso; CSV con SUCCESS automático confirmado. Ruff pasó en el conjunto de cambios.",
        "Antes de entregar: integrar el PR, verificar CI, abrir este PDF, ensayar y comprobar acceso del profesor al repositorio privado.",
    ])
    pdf.save()
    print(f"Created {OUTPUT} ({page} slides)")


if __name__ == "__main__":
    main()
