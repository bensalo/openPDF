from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_bill_pdf(filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Set up some positions and constants
    margin = 50
    line_height = 14
    start_y = height - margin

    # Draw the fields
    fields = [
        ("Invoice Number:", margin, start_y),
        ("Date:", margin, start_y - line_height * 2),
        ("Billing Address:", margin, start_y - line_height * 4),
        ("Item Description:", margin, start_y - line_height * 8),
        ("Quantity:", margin + 300, start_y - line_height * 8),
        ("Price:", margin + 400, start_y - line_height * 8),
        ("Total:", margin, start_y - line_height * 14)
    ]

    for label, x, y in fields:
        c.drawString(x, y, label)

    c.save()

create_bill_pdf("bill_template.pdf")
