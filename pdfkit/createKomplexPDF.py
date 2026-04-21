from fpdf import FPDF

class TrapPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(180, 10, "Komplexes Auftragsformular", 0, 1, "C")
        self.ln(5)

    def create_contact_header(self):
        self.set_font("Arial", "", 12)
        self.set_xy(30, 20)
        self.cell(0, 6, "Absender:", 0, 1, "L")
        self.set_x(30)
        self.cell(0, 6, "Max Mustermann", 0, 1, "L")
        self.set_x(30)
        self.cell(0, 6, "Musterweg 1", 0, 1, "L")
        self.set_x(30)
        self.cell(0, 6, "12345 Berlin", 0, 1, "L")
        self.ln(10)

    def draw_raw_field(self, x, y, w, h):
        """Zeichnet nur eine Box (für manuelle Fallen)"""
        self.rect(x, y, w, h)

    def draw_raw_label(self, x, y, text):
        """Zeichnet nur Text (für manuelle Fallen)"""
        self.set_xy(x, y)
        self.set_font("Arial", "", 11)
        self.cell(self.get_string_width(text), 6, text, 0, 1)

# --- Instanz erstellen ---
pdf = TrapPDF()
pdf.add_page()
pdf.create_contact_header()

# ==========================================
# TRAP 1: Semantische Varianz (Für Bild 12)
# ==========================================
# Hier scheitert der traditionelle Algo mit hardcodierten Dictionaries,
# weil er "Tel.-Nr." nicht als "Telefon" erkennt. Das LLM glänzt hier.
pdf.set_font("Arial", "B", 12)
pdf.set_xy(30, 55)
pdf.cell(0, 6, "1. Kontaktdaten")

pdf.draw_raw_label(30, 65, "Geb.-Datum:")
pdf.draw_raw_field(30, 72, 60, 8)

pdf.draw_raw_label(100, 65, "Tel.-Nr. (mobil):")
pdf.draw_raw_field(100, 72, 60, 8)

pdf.draw_raw_label(30, 85, "E-Post / Kontakt:")
pdf.draw_raw_field(30, 92, 130, 8)


# ==========================================
# TRAP 2: Geometrisches Versagen (Für Bild 09)
# ==========================================
# Ein Layout, bei dem das Label euklidisch viel näher an einem 
# FALSCHEN Feld liegt als an seinem eigenen.
pdf.set_font("Arial", "B", 12)
pdf.set_xy(30, 115)
pdf.cell(0, 6, "2. Auftragsdetails")

# Label "Kundennummer" gehört zur Box darunter.
pdf.draw_raw_label(30, 125, "Kundennummer:")
pdf.draw_raw_field(30, 138, 50, 8) # Feld ist extra weit unten! (Distanz Y=13)

# Aber hier kommt die Falle: Ein anderes Feld wird rechts daneben gequetscht.
pdf.draw_raw_field(72, 125, 40, 8) # Feld ist direkt hinter dem Text! (Distanz X=2)
pdf.draw_raw_label(115, 125, "<- R.-Datum") # Label steht ungewöhnlich rechts davon

# ERGEBNIS: Der OpenCV Code wird "Kundennummer:" zwingend dem Feld rechts daneben 
# zuordnen, weil es 2 Pixel entfernt ist, während das echte Feld 13 Pixel entfernt ist.


# ==========================================
# TRAP 3: Grid / Tabellen (Die LLM Schwäche)
# ==========================================
# LLMs tun sich extrem schwer mit 2D-Rastern, wenn sie nur 1D-Text(Koordinaten) 
# im Prompt bekommen. Wenn Labels in Tabellen-Köpfen stehen, halluziniert das LLM oft.
pdf.set_font("Arial", "B", 12)
pdf.set_xy(30, 160)
pdf.cell(0, 6, "3. Bestellmatrix")

# Tabellen-Header
pdf.draw_raw_label(30, 170, "Artikelnummer")
pdf.draw_raw_label(90, 170, "Menge")
pdf.draw_raw_label(140, 170, "Einzelpreis")

# Zeile 1 (Ohne eigene Labels, nur Felder)
pdf.draw_raw_field(30, 178, 50, 8)
pdf.draw_raw_field(90, 178, 30, 8)
pdf.draw_raw_field(140, 178, 30, 8)

# Zeile 2 (Ohne eigene Labels, nur Felder)
pdf.draw_raw_field(30, 188, 50, 8)
pdf.draw_raw_field(90, 188, 30, 8)
pdf.draw_raw_field(140, 188, 30, 8)

# Output PDF
pdf.output("pdfkit/output/rechnung_falle.pdf")
print("Toxisches PDF erfolgreich erstellt!")