# OpenPDF - Bachelorarbeit Ben Salomon 2026.

# Installation / Setup

1. Install Anaconda/Miniconda for dependencies
2. create env from requirements.txt
```
conda create --name openpdf python=3.10 -r requirements.txt
```
3. activate env
```
conda activate openpdf
```
4. start server
```
python manage.py runserver
```

# Roadmap

- Template Class
- Backend Module
    - PDF-Gen
    - API 
- Frontend Module
    - Template-Editor



## PDF Web
/pdfweb
PDFweb contains the Frontend, the Computer Vision algorithms, the Testbase, the Metrics and the Database. Basically its the whole Project

## PDF Kit
/pdfkit
PDFkit is only one script that can create example pdf forms with the FPDF library. Its really not much but provided a few pdf's for the test base.
