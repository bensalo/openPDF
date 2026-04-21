import cv2
import numpy as np
from pathlib import Path
from pdf2image import convert_from_path

import CVprod

def generate_full_chapter_visuals(pdf_path: str, output_dir: str, llm_provider: str = 'gemini'):
    in_path = Path(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        raise FileNotFoundError(f"PDF nicht gefunden: {in_path}")

    # Extrahiere den reinen Dateinamen ohne Endung (z.B. 'rechnung_falle')
    pdf_name = in_path.stem
    print(f"Starte Visualisierungs-Pipeline für {pdf_name} (200 DPI)")
    
    # 1. PDFMiner Text-Extraktion 
    text_layout = CVprod.extract_text(str(in_path))

    # 2. Rasterisierung
    pages = convert_from_path(str(in_path), dpi=200)

    for page_idx, page_img in enumerate(pages):
        page_num = page_idx + 1
        # Prefix für Dateinamen (inkl. Seitenzahl, falls mehrseitig)
        file_prefix = f"{pdf_name}_p{page_num}"
        
        print(f"Verarbeite Seite {page_num}...")

        img_array = np.array(page_img.convert('RGB'))
        bgr_image = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # --- KAPITEL 3 & 4 (Traditionelle Schritte) ---
        # Alle Vorverarbeitungsschritte gehören zur 'trad' Kette
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 75, 200)
        
        cv2.imwrite(str(out_dir / f"{file_prefix}_trad_01_original.png"), bgr_image)
        cv2.imwrite(str(out_dir / f"{file_prefix}_trad_02_grayscale.png"), gray)
        cv2.imwrite(str(out_dir / f"{file_prefix}_trad_03_gaussian_blur.png"), blurred)
        cv2.imwrite(str(out_dir / f"{file_prefix}_trad_04_canny_edges.png"), edged)

        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        canvas_raw_contours = bgr_image.copy()
        canvas_filtered = bgr_image.copy()
        
        raw_fields = []
        for cnt in contours:
            epsilon = 0.02 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                cv2.rectangle(canvas_raw_contours, (x, y), (x+w, y+h), (0, 0, 255), 2)
                if w >= 40 and h >= 20: 
                    cv2.rectangle(canvas_filtered, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    raw_fields.append({'id': f'f_{len(raw_fields)}', 'bbox': [x, y, x+w, y+h], 'text': ''})

        cv2.imwrite(str(out_dir / f"{file_prefix}_trad_05_all_quadrilaterals.png"), canvas_raw_contours)
        cv2.imwrite(str(out_dir / f"{file_prefix}_trad_06_filtered_fields.png"), canvas_filtered)

        page_texts = [t for t in text_layout if t['page_index'] == page_idx]
        fields, cleaned_texts = CVprod.clean_text_fields(raw_fields, page_texts)
        
        # --- KAPITEL 5: FINALES OUTPUT (A/B VERGLEICH) ---

        # 1. TRADITIONELLER LAUF
        _, final_labeled_trad, _ = CVprod.prediction(fields, cleaned_texts, use_llm=False)
        final_img_trad = CVprod.show_detected_fields(page_img, final_labeled_trad, cleaned_texts)
        cv2.imwrite(str(out_dir / f"{file_prefix}_trad_final.png"), cv2.cvtColor(final_img_trad, cv2.COLOR_RGB2BGR))
        
        # 2. KI (LLM) LAUF
        print(f" -> Frage {llm_provider} API an...")
        _, final_labeled_llm, _ = CVprod.prediction(fields, cleaned_texts, use_llm=True, llm_provider=llm_provider)
        
        if final_labeled_llm:
            final_img_llm = CVprod.show_detected_fields(page_img, final_labeled_llm, cleaned_texts)
            # Hier nutzen wir das '_gemini_' (oder entsprechend Provider) Tag
            cv2.imwrite(str(out_dir / f"{file_prefix}_{llm_provider}_final.png"), cv2.cvtColor(final_img_llm, cv2.COLOR_RGB2BGR))

        print(f" -> Seite {page_num} abgeschlossen.\n")

if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).parent.resolve()
    # Das Skript liegt in pdfweb/prod/, wir gehen hoch zu openPDF/docs/
    PDF_FILE = SCRIPT_DIR / "docs" / "bewerbungsformular_falle.pdf" 
    
    # Output landet direkt im docs/ Ordner
    OUTPUT_FOLDER = SCRIPT_DIR / "docs"
    
    try:
        generate_full_chapter_visuals(str(PDF_FILE), str(OUTPUT_FOLDER), llm_provider='gemini')
        print(f"Erfolg! Bilder liegen in {OUTPUT_FOLDER}")
    except Exception as e:
        print(f"Fehler: {e}")