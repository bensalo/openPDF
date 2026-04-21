import os
import io
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from django.core.files.storage import default_storage
from django.conf import settings
from pathlib import Path

# get path from django settings
TEMPLATES_PATH = Path(settings.MEDIA_ROOT) / 'source_files'
ATTACHMENTS_PATH = Path(settings.MEDIA_ROOT) / 'attachments'

class pdfgen:

    def __init__(self, template, **kwargs):
        self.PAGESIZE = A4  # A4
        self.template = template
        # FONTS: Helvetica, Courier, Times Roman
        self.default_font = template.font
        self.default_font_size = template.font_size

    def gen_pdf(self, field_value_dict):
        pages = self.template.template_pages
        template_file = self.template.file_path

        # Load the template once
        template_reader = PdfReader(f'{TEMPLATES_PATH}/{template_file}')
        template_index = self.template.template_index

        temp_buffers = []

        # Generate individual pages and store them in temp_buffers
        for n in range(pages):
            page_buffer = io.BytesIO()
            c = canvas.Canvas(page_buffer, pagesize=self.PAGESIZE)

            target_fields = self.template.fields.filter(page_index=n)

            c.drawString(0, 0, "")  # Force page creation

            for field in target_fields:
                field_value = field_value_dict.get(field.name)
                if field_value is not None:
                    if field.field_type == "text":
                        self.write_text(field, c, field_value)
                    elif field.field_type == "textarea":
                        self.write_textarea(field, c, field_value)
                    elif field.field_type == "checkbox":
                        self.write_checkbox(field, c)

            c.save()
            page_buffer.seek(0)
            temp_buffers.append(page_buffer)

        output_pdf_writer = PdfWriter()
        output_buffer = io.BytesIO()

        # Get prefix and postfix attachments
        attachments_sorted = sorted(self.template.attachments, key=lambda x: x['index'])
        pre_attachments = [att for att in attachments_sorted if att['index'] < template_index]
        post_attachments = [att for att in attachments_sorted if att['index'] >= template_index]

        self.add_attachments(pre_attachments, output_pdf_writer, field_value_dict)

        # Merge generated pages with the template pages
        for n, page_buffer in enumerate(temp_buffers):
            try:
                if n < len(template_reader.pages):
                    template_page = template_reader.pages[n]
                    overlay_reader = PdfReader(page_buffer)
                    template_page.merge_page(overlay_reader.pages[0])
                    output_pdf_writer.add_page(template_page)
                else:
                    print(f"Template does not have page {n}.")
            except Exception as e:
                print(f"Error merging pages: {e} for page {n}")

        self.add_attachments(post_attachments, output_pdf_writer, field_value_dict)

        output_pdf_writer.write(output_buffer)
        output_buffer.seek(0)

        return output_buffer

    def add_attachments(self, attachments, pdf_writer, field_value_dict):
        for attachment in attachments:
            if field_value_dict.get(f'attachment_{attachment["name"]}') == 'on':
                pdf_reader = PdfReader(f'{ATTACHMENTS_PATH}{attachment["file_path"]}')
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)

    def write_text(self, field, c, text):
        c.setFont(field.font, field.font_size)
        c.drawString(field.pos_x, field.pos_y, text)

    def write_textarea(self, field, c, text):
        c.setFont(field.font, field.font_size)
        text_object = c.beginText(field.pos_x, field.pos_y)
        text_object.setFont(field.font, field.font_size)
        for line in text.split("\n"):
            text_object.textLine(line)
        c.drawText(text_object)

    def write_checkbox(self, field, c):
        c.setFont(field.font, field.font_size)
        c.drawString(field.pos_x, field.pos_y, 'X')
