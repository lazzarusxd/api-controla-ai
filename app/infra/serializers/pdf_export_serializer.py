from io import BytesIO
from typing import Any, List

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.application.interfaces import IExportSerializer
from app.application.dto import ExportPackageDTO, ExportSectionDTO, SerializedExportDTO


class PdfExportSerializer(IExportSerializer):


    def __init__(self, max_rows_per_section: int, title: str = "Controla AI") -> None:
        self._title = title
        self._cell_max_chars = 42
        self._max_rows_per_section = max_rows_per_section

    def serialize(self, export_package: ExportPackageDTO) -> SerializedExportDTO:
        buffer = BytesIO()
        styles = getSampleStyleSheet()

        heading = ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], spaceAfter=4)
        footnote = ParagraphStyle(name="Footnote", parent=styles["Normal"], fontSize=7, textColor=colors.grey)

        document = SimpleDocTemplate(
            buffer,
            topMargin=14 * mm,
            author=self._title,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            bottomMargin=14 * mm,
            pagesize=landscape(A4),
            title=f"{self._title} — Exportação de dados"
        )

        scope = export_package.scope
        end = scope.end_date.isoformat() if scope.end_date is not None else "lançamento mais recente"
        start = scope.start_date.isoformat() if scope.start_date is not None else "início do histórico"

        story: List[Any] = [
            Paragraph(f"{self._title} — Exportação de dados", styles["Title"]),
            Paragraph(f"Titular: {export_package.user_id}", styles["Normal"]),
            Paragraph(f"Gerado em: {export_package.generated_at.isoformat()}", styles["Normal"]),
            Paragraph(f"Período apurado: {start} a {end}", styles["Normal"]),
            Paragraph(f"Total de registros: {export_package.total_records}", styles["Normal"]),
            Spacer(1, 8 * mm)
        ]

        truncated = False

        for section in export_package.sections:
            visible = section.rows[:self._max_rows_per_section]
            section_truncated = len(section.rows) > len(visible)
            truncated = truncated or section_truncated

            story.append(Paragraph(f"{section.title} ({section.total})", heading))

            if not visible:
                story.append(Paragraph("Nenhum registro no escopo solicitado.", footnote))
            else:
                story.append(self._to_table(section=section, rows=visible))

            if section_truncated:
                story.append(
                    Paragraph(
                        f"Exibidos {len(visible)} de {section.total} registros. O relatório em PDF é "
                        f"resumo legível; para o conjunto íntegro, solicite a exportação em JSON ou CSV.",
                        footnote
                    )
                )

            story.append(Spacer(1, 6 * mm))

        document.build(story)

        return SerializedExportDTO(
            truncated=truncated,
            file_extension="pdf",
            content=buffer.getvalue(),
            media_type="application/pdf"
        )

    def _to_table(self, section: ExportSectionDTO, rows: List[Any]) -> Table:
        data: List[List[str]] = [[self._to_header(column=column) for column in section.columns]]

        for row in rows:
            data.append([self._to_cell(value=row.get(column)) for column in section.columns])

        table = Table(data, repeatRows=1, hAlign="LEFT")

        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF2")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B9C4CF")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2)
                ]
            )
        )

        return table

    @staticmethod
    def _to_header(column: str) -> str:
        return column.replace("_", " ").strip().capitalize()

    def _to_cell(self, value: object) -> str:
        if value is None:
            return "—"

        if isinstance(value, bool):
            return "sim" if value else "não"

        text = str(value)

        if len(text) > self._cell_max_chars:
            return f"{text[: self._cell_max_chars - 1]}…"

        return text
