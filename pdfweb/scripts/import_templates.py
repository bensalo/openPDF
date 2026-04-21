import os
import json
import datetime
from pdffrontend import models  # Adjust the import according to your Django app structure

# Define the directory containing the JSON files
TEMPLATE_JSON_DIR = 'media/templates'  # Replace with the actual path to your JSON files

def import_template(json_file_path):
    """
    Imports a template from a JSON file and saves it to the database.
    
    Args:
        json_file_path (str): Path to the JSON file.
    """
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)

        # Create or update the Template object
        template, created = models.Template.objects.update_or_create(
            id=data["id"],
            defaults={
                "name": data["name"],
                "created_at": datetime.datetime.strptime(data["created_at"], "%Y-%m-%d").date(),
                "font": data["font"],
                "font_size": data["font_size"],
                "last_updated": datetime.datetime.strptime(data["last_updated"], "%Y-%m-%d").date(),
                "template_index": data["source"]["template"]["index"],
                "template_pages": data["source"]["template"]["pages"],
                "file_path": data["source"]["template"]["file_path"],
                "label_path": data["source"]["template"].get("label_path", ""),
                "prediction_path": data["source"]["template"].get("prediction_path", ""),
                "attachments": data["source"].get("attachments", []),
            }
        )

        # Clear existing fields for the template
        template.fields.all().delete()

        # Create Field objects
        for field_data in data["fields"]:
            models.Field.objects.create(
                template=template,
                name=field_data["name"],
                field_type=field_data["field_type"],
                required=field_data["required"],
                page_index=field_data["page_index"],
                pos_x=field_data["pos_x"],
                pos_y=field_data["pos_y"],
                font_size=field_data["font_size"],
                font=field_data["font"]
            )

        print(f"{'Created' if created else 'Updated'} template: {template.name}")
    
    except Exception as e:
        print(f"Error importing {json_file_path}: {e}")

def run():
    """
    Imports all template JSON files from the specified directory.
    """
    for filename in os.listdir(TEMPLATE_JSON_DIR):
        if filename.endswith('.json'):
            json_file_path = os.path.join(TEMPLATE_JSON_DIR, filename)
            import_template(json_file_path)
