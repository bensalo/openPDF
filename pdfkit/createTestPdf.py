from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        # Set font for header
        self.set_font("Arial", "B", 14)
        self.cell(180, 10, "Rechnung", 0, 1, "C")
        self.ln(10)

    def create_header2(self):
        # Set font for the address details
        self.set_font("Arial", "", 12)
        self.set_xy(30, 20)  # Set the starting position to (30, 20)
        
        # Adding the name and address details, ensuring all lines start from the correct x position
        self.cell(0, 6, "Absender:", 0, 1, "L")
        self.set_x(30)
        self.cell(0, 6, "Max Mustermann", 0, 1, "L")
        self.set_x(30)
        self.cell(0, 6, "Musterweg 1", 0, 1, "L")
        self.set_x(30)
        self.cell(0, 6, "12345 Berlin", 0, 1, "L")
        self.ln(10)

    def create_form_field(self, x, y, label_text, label_position="above", field_width=60, field_height=8):
        """
        Draw a form field with a label.

        Parameters:
        - x, y: Coordinates for the top-left corner of the label or field.
        - label_text: Text for the label.
        - label_position: "above", "beside", or "below" to indicate the label's position relative to the field.
        - field_width: Width of the input field.
        - field_height: Height of the input field.
        """
        self.set_xy(x, y)
        self.set_font("Arial", "", 12)

        if label_position == "above":
            # Draw label above the field with a smaller gap
            self.cell(field_width, 6, label_text, 0, 1)  # Reduce height of the cell to bring it closer
            self.set_xy(x, y + 5)  # Move just slightly below the label
            self.rect(x, y + 6, field_width, field_height)  # Draw the rectangle for the field
        elif label_position == "beside":
            # Draw label beside the field with a smaller gap
            self.cell(30, 10, label_text, 0, 0)  # Label width is 30
            self.set_xy(x + 20, y)  # Move to the right of the label with a smaller gap
            self.rect(x + 20, y + 2, field_width, field_height)  # Draw the rectangle for the field
        elif label_position == "below":
            # Draw field first, then label below it with a smaller gap
            self.rect(x, y, field_width, field_height)  # Draw the rectangle for the field
            self.set_xy(x, y + field_height + 2)  # Move closer below the rectangle
            self.cell(field_width, 6, label_text, 0, 1)  # Reduce height of the cell to bring it closer

# Create instance of PDF
pdf = PDF()
pdf.add_page()

# Add the contact details in the top left corner
pdf.create_header2()

# Example usage of create_form_field function with closer labels
pdf.create_form_field(x=120, y=20, label_text="Datum", label_position="beside", field_width=40)
pdf.create_form_field(x=120, y=30, label_text="R.-Nr.", label_position="beside", field_width=40)
pdf.create_form_field(x=30, y=50, label_text="Vorname", label_position="above")
pdf.create_form_field(x=120, y=50, label_text="Nachname", label_position="above")
pdf.create_form_field(x=30, y=70, label_text="Addresse", label_position="above", field_width=150)
pdf.create_form_field(x=30, y=90, label_text="E-Mail", label_position="above", field_width=150)


pdf.create_form_field(x=30, y=160, label_text="Artikel", label_position="below", field_width=100)
pdf.create_form_field(x=150, y=160, label_text="Anzahl", label_position="below", field_width=30)
pdf.create_form_field(x=150, y=180, label_text="Preis", label_position="below", field_width=30)


# Output PDF
pdf.output("pdfkit/output/rechnung.pdf")
