from fpdf import FPDF


class TrapPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(180, 10, "Bewerbungsformular", 0, 1, "C")
        self.ln(3)

    def draw_box_field(self, x, y, w, h):
        """Rechteckiges Eingabefeld (wird erkannt)"""
        self.rect(x, y, w, h)

    def draw_line_field(self, x, y, w):
        """Unterstrichen-Feld (wird NICHT erkannt - nur eine Linie)"""
        self.line(x, y, x + w, y)

    def draw_label(self, x, y, text, bold=False):
        self.set_xy(x, y)
        style = "B" if bold else ""
        self.set_font("Helvetica", style, 11)
        self.cell(self.get_string_width(text) + 2, 6, text, 0, 0)


pdf = TrapPDF()
pdf.add_page()

# ─────────────────────────────────────────────────────────────────────────────
# Absender-Block (statischer Text oben links)
# ─────────────────────────────────────────────────────────────────────────────
pdf.set_font("Helvetica", "", 10)
pdf.set_xy(15, 20)
pdf.cell(0, 5, "Muster GmbH · Musterstraße 12 · 12345 Berlin", 0, 1, "L")
pdf.set_xy(15, 26)
pdf.cell(0, 5, "Tel: 030 / 123456  ·  karriere@muster-gmbh.de", 0, 1, "L")
pdf.line(15, 33, 195, 33)

# ─────────────────────────────────────────────────────────────────────────────
# ABSCHNITT 1 – Persönliche Angaben
# FALLE: "Name" ist eine Linie (kein Rechteck) → wird vom CV-Algo NICHT erkannt
#         "Vorname" und "Nachname" sind echte Boxen → werden erkannt
#         Aber: Vorname-Label steht sehr weit links, Feld rechts daneben ist
#               geometrisch näher am Nachname-Label → falsche Zuordnung möglich
# ─────────────────────────────────────────────────────────────────────────────
pdf.set_font("Helvetica", "B", 12)
pdf.set_xy(15, 38)
pdf.cell(0, 7, "1. Persönliche Angaben", 0, 1, "L")

# Vorname / Nachname als Linien (TRAP: kein Rechteck → OpenCV findet keine Kontur)
pdf.draw_label(15, 48, "Vorname:")
pdf.draw_line_field(40, 54, 50)   # nur eine Unterstreichung

pdf.draw_label(100, 48, "Nachname:")
pdf.draw_line_field(124, 54, 63)  # nur eine Unterstreichung

# Geburtsdatum / Geburtsort: Labels oberhalb, aber enger zusammen als ihre Felder
pdf.draw_label(15, 60, "Geburtsdatum:")
pdf.draw_box_field(15, 67, 55, 8)

pdf.draw_label(80, 60, "Geburtsort:")
pdf.draw_box_field(80, 67, 110, 8)

# ─────────────────────────────────────────────────────────────────────────────
# ABSCHNITT 2 – Kontaktinformationen
# FALLE: Straße, PLZ und Ort in EINER Zeile nebeneinander
#         Labels sind direkt über ihren Feldern, ABER PLZ-Feld ist sehr schmal
#         → Distanzberechnung ordnet "Ort:" fälschlich dem PLZ-Feld zu,
#           weil PLZ-Feld horizontal fast unter dem "Ort:"-Label liegt
# ─────────────────────────────────────────────────────────────────────────────
pdf.set_font("Helvetica", "B", 12)
pdf.set_xy(15, 102)
pdf.cell(0, 7, "2. Kontaktinformationen", 0, 1, "L")

pdf.draw_label(15, 112, "Straße & Hausnummer:")
pdf.draw_box_field(15, 119, 110, 8)

# PLZ-Feld schmal, direkt daneben Ort – Labels eng, Felder versetzt
pdf.draw_label(130, 112, "PLZ:")
pdf.draw_box_field(130, 119, 20, 8)

pdf.draw_label(155, 112, "Ort:")
pdf.draw_box_field(155, 119, 40, 8)

pdf.draw_label(15, 132, "E-Mail:")
pdf.draw_box_field(15, 139, 85, 8)

pdf.draw_label(105, 132, "Telefon:")
pdf.draw_box_field(105, 139, 90, 8)

# ─────────────────────────────────────────────────────────────────────────────
# ABSCHNITT 3 – Einwilligung & Unterschrift
# FALLE A: Checkbox-Gruppe – mehrere kleine Quadrate, Label daneben
#   → Algo ordnet Label dem geometrisch nächsten Kästchen zu, nicht dem richtigen
#   → Bei eng beieinander liegenden Checkboxen greift die falsche
# FALLE B: Label UNTERHALB des Feldes (Unterschrift-Konvention)
#   → Algo erwartet Label immer oben oder links → findet kein Label → None
# ─────────────────────────────────────────────────────────────────────────────
pdf.set_font("Helvetica", "B", 12)
pdf.set_xy(15, 150)
pdf.cell(0, 7, "3. Einwilligung & Unterschrift", 0, 1, "L")

# Checkboxen: Drei Optionen nebeneinander, Labels rechts daneben
# TRAP: Checkboxen sind kleine Quadrate (5x5) – Algo erkennt sie als Felder.
#       Label "Vollzeit" steht rechts von Box 1, aber euklidisch fast gleich
#       nah an Box 2 → Zuordnung kippt je nach Abstandsberechnung.
pdf.draw_label(15, 162, "Gewünschtes Arbeitsmodell:")

# Box 1 + Label
pdf.draw_box_field(15, 171, 5, 5)
pdf.draw_label(22, 169, "Vollzeit")

# Box 2 + Label – eng daneben, Label fast gleich weit von Box 1 und Box 2
pdf.draw_box_field(60, 171, 5, 5)
pdf.draw_label(67, 169, "Teilzeit")

# Box 3 + Label
pdf.draw_box_field(105, 171, 5, 5)
pdf.draw_label(112, 169, "Freelance / Projektbasis")

# Verfügbar ab: normales Feld als Vergleich
pdf.draw_label(15, 183, "Verfuegbar ab:")
pdf.draw_box_field(15, 190, 60, 8)

# FALLE B: Unterschrift-Feld – großes leeres Feld, Label DARUNTER
# → Algo sucht Label oberhalb/links → findet keins → None
# → LLM erkennt aus Kontext "Unterschrift" als typisches Dokumentmuster
pdf.draw_box_field(100, 183, 90, 20)   # Unterschrift-Box
pdf.draw_label(100, 205, "Unterschrift & Datum")   # Label UNTERHALB

# Output
pdf.output("pdfkit/output/bewerbungsformular_falle.pdf")
print("Formular erfolgreich erstellt!")

