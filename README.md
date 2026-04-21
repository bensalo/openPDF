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

## PDF Web
/pdfweb
PDFweb contains the Frontend, the Computer Vision algorithms, the Testbase, the Metrics and the Database. Basically its the whole Project

## PDF Kit
/pdfkit
PDFkit contains a few scripts that provided example pdf forms with the FPDF library for the test base.
