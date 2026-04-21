import json
import os
import uuid
import datetime
from prod import pdfgen
from django.core.files.storage import default_storage
from pdffrontend import models

# del load_templates_json() -> unneccessary one liner
# del load_template() -> same

class Pdf_template:
    """
    A class to manage PDF templates, including loading, updating, and saving template data.
    """
    def __init__(self, temp_id=None, form_dict=None, **kwargs):
        """
        Initializes a Pdf_template object.

        Args:
            temp_id (str, optional): The template ID to load an existing template.
            form_dict (dict, optional): A dictionary to create a new template if `temp_id` is not provided.
        """
        if temp_id:
            # Load existing template
            try:
                self.template = models.Template.objects.get(id=temp_id)
                self.temp_id = temp_id
            except Exception as e:
                print("Error loading Template: " + str(e))
        elif form_dict:
            # Initialize new template
            self.temp_id = form_dict.get("temp_id", str(uuid.uuid4()))
            self.template = models.Template(
                id=self.temp_id,
                name=form_dict.get("template_name"),
                created_at=datetime.date.today(),
                font=form_dict.get("font", "Courier"),
                font_size=form_dict.get("font_size", 10),
                last_updated=datetime.date.today(),
                template_index=form_dict.get("source_template", {}).get("index", 0),
                template_pages=form_dict.get("source_template", {}).get("pages", 0),
                file_path=form_dict.get("source_template", {}).get("file_path", ""),
                label_path=form_dict.get("source_template", {}).get("label_path", ""),
                prediction_path=form_dict.get("source_template", {}).get("prediction_path", ""),
                attachments=form_dict.get("source_attachments", []),
                field_detection_method=form_dict.get("field_detection_method", "traditional"),
                llm_details=form_dict.get("llm_details", {})
            )
            self.template.save()

            if "fields" in form_dict:
                self.set_fields(form_dict["fields"])

    def get_source(self):
        # unneccessary function!
        
        """
        Retrieves the source of the template, including the template and attachments.

        Returns:
            dict: The source information of the template.
        """
        return self.template.source

    def set_source(self, new_source):
        # ? unneccessary function

        """
        Sets the new source information for the template.

        Args:
            new_source (dict): The new source data.

        Saves changes to DB.
        """
        # TODO: Implement index validation logic
        self.template["source"] = new_source
        self.save_json()

    def get_fields(self):
        """
        Retrieves the fields of the template.

        Returns:
            list: A list of fields in the template.
        """
        return models.Field.objects.filter(template=self.template).order_by('-pos_y')

    def set_fields(self, fields):
        """
        Sets the fields of the template after removing empty dictionaries.

        Args:
            fields (list): List of fields to be updated.

        Saves changes to the JSON file.
        """
        # Delete existing fields
        self.template.fields.all().delete()

        # Add new fields
        for field in self.remove_empty_dicts(fields):
            models.Field.objects.create(
                template=self.template,
                name=field["name"],
                field_type=field["field_type"],
                required=field.get("required", False),
                page_index=field["page_index"],
                pos_x=field["pos_x"],
                pos_y=field["pos_y"],
                font_size=field["font_size"],
                font=field["font"]
            )


        # self.template["fields"] = self.remove_empty_dicts(fields)
        # self.save_json()

    def check_fields(self, fields):
        """
        Validates fields, removing those with empty names or duplicate names.

        Args:
            fields (list): List of fields to be checked.

        Returns:
            list: A list of valid fields.
        """
        origin_fields = self.template.get("fields")
        field_names = [field.get("name") for field in origin_fields]
        
        for field in fields:
            if field.get("name") == "":
                del field  # Remove empty name fields
            elif field.get("name") in field_names:
                del field  # Remove duplicate name fields

        return fields

    def get_template(self):
        """
        Retrieves the entire template.

        Returns:
            dict: The complete template data.
        """
        return self.template

    def update_template(self, update_dict, files=None):
        """
        Updates the template with new data and optionally uploads new files.
        
        Args:
            update_dict (dict): Dictionary containing updated template data.
            files (dict, optional): Files to be added to the template.
        
        Saves changes to the database.
        """
        update_dict = self.parse_fields_from_dict(update_dict)

        # Update basic template attributes
        template_fields = ['name', 'font', 'font_size']
        for key in template_fields:
            if key in update_dict:
                setattr(self.template, key, update_dict[key])

        # Update template source details
        if 'source_template_index' in update_dict and 'source_template_pages' in update_dict:
            self.template.template_index = int(update_dict['source_template_index'])
            self.template.template_pages = int(update_dict['source_template_pages'])

        # Handle template file upload
        if files and 'template_file' in files:
            template_file = files['template_file']
            file_path = default_storage.save(f'templates/{template_file.name}', template_file)
            self.template.file_path = file_path

        # Update attachments
        attachments = []
        attachment_counter = 1

        while f'attachment_name_{attachment_counter}' in update_dict:
            if update_dict.get(f'attachment_delete_{attachment_counter}') == 'DELETE':
                attachment_counter += 1
                continue

            if files and f'attachment_file_{attachment_counter}' in files:
                attachment_file = files[f'attachment_file_{attachment_counter}']
                file_path = default_storage.save(f'attachments/{self.temp_id}_{attachment_file.name}', attachment_file)[12:]
            else:
                file_path = self.template.attachments[attachment_counter - 1]["file_path"]

            attachment = {
                'name': update_dict[f'attachment_name_{attachment_counter}'],
                'index': int(update_dict[f'attachment_index_{attachment_counter}']),
                'pages': int(update_dict[f'attachment_pages_{attachment_counter}']),
                'file_path': file_path,
            }
            attachments.append(attachment)
            attachment_counter += 1

        self.template.attachments = attachments
        self.template.save()

        # Update fields
        self.template.fields.all().delete()  # Clear existing fields
        field_counter = 1

        while f'field_name_{field_counter}' in update_dict:
            if update_dict.get(f'field_delete_{field_counter}') == 'DELETE':
                field_counter += 1
                continue

            field_data = {
                'name': update_dict[f'field_name_{field_counter}'],
                'field_type': update_dict[f'field_type_{field_counter}'],
                'required': update_dict.get(f'field_required_{field_counter}', 'off') == 'on',
                'page_index': int(update_dict[f'field_page_index_{field_counter}']),
                'pos_x': float(update_dict[f'field_pos_x_{field_counter}']),
                'pos_y': float(update_dict[f'field_pos_y_{field_counter}']),
                'font_size': int(update_dict.get(f'field_font_size_{field_counter}', self.template.font_size)),
                'font': update_dict.get(f'field_font_{field_counter}', self.template.font),
            }

            # Add optional width for textarea fields
            if field_data['field_type'] == 'textarea':
                field_data['width'] = int(update_dict.get(f'field_width_{field_counter}', 0))

            models.Field.objects.create(template=self.template, **field_data)
            field_counter += 1

        # Save the updated template
        self.template.last_updated = datetime.date.today()
        self.template.save()


    def parse_fields_from_dict(self, update_dict):
        """
        Extracts and parses field data from the update dictionary.

        Args:
            update_dict (dict): Dictionary containing update information.

        Returns:
            dict: Updated dictionary with parsed fields.
        """
        fields = []
        del_keys = []

        for key, value in update_dict.items():
            if key.startswith('fields['):
                # Extract index and attribute name
                parts = key.split('[')
                index = int(parts[1].strip(']'))
                attribute = parts[2].strip(']')

                # Ensure the list is long enough
                while len(fields) <= index:
                    fields.append({})

                # Handle checkbox values (convert 'on' to True)
                if attribute == 'required' and value in ['on', 'true', 'True']:
                    value = True
                elif attribute == 'required':
                    value = False
                
                fields[index][attribute] = value
                del_keys.append(key)
        
        for key in del_keys:
            del update_dict[key]
        
        if len(fields) != 0:
            update_dict["fields"] = fields
        return update_dict

    def remove_empty_dicts(self, arr):
        """
        Removes empty dictionaries from a list.

        Args:
            arr (list): List that may contain empty dictionaries.

        Returns:
            list: List without empty dictionaries.
        """
        return [item for item in arr if not (isinstance(item, dict) and not item)]

    def save_json(self):
        """
        Saves the current template as a JSON file in the APPDATA_PATH directory.

        Updates the "last_updated" attribute before saving.
        """
        try:
            self.template.last_updated = datetime.date.today()
            self.template.save()
            #with open(f'{APPDATA_PATH}{self.temp_id}.json', 'w', encoding='utf-8') as f:
            #    self.template["last_updated"] = str(datetime.date.today())
            #    json.dump(self.template, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print("Error saving Template: " + str(e))

    def gen_pdf(self, field_value_dict):
        """
        Generates a PDF using the current template.

        Args:
            field_value_dict (dict): Dictionary of field values.

        Returns:
            PDF file: The generated PDF.
        """
        return pdfgen.pdfgen(self.template).gen_pdf(field_value_dict)
