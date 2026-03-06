from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from docx import Document


class Exporter:

    # -------------------------
    # EXPORT PDF
    # -------------------------
    def export_pdf(self, text: str, file_path):

        c = canvas.Canvas(str(file_path), pagesize=letter)

        width, height = letter
        y = height - 40

        for line in text.split("\n"):
            c.drawString(40, y, line[:90])
            y -= 15

            if y < 40:
                c.showPage()
                y = height - 40

        c.save()

    # -------------------------
    # EXPORT DOCX
    # -------------------------
    def export_docx(self, text: str, file_path):

        doc = Document()

        for line in text.split("\n"):
            doc.add_paragraph(line)

        doc.save(file_path)

