from django.db import models
import uuid

class Template(models.Model):

    def json_default_list():
        return []

    def json_default_dict():
        return {}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateField()
    font = models.CharField(max_length=100)
    font_size = models.IntegerField()
    last_updated = models.DateField()
    template_index = models.IntegerField()
    template_pages = models.IntegerField()
    file_path = models.CharField(max_length=255)
    label_path = models.CharField(max_length=255)
    prediction_path = models.CharField(max_length=255, blank=True)
    field_detection_method = models.CharField(
        max_length=20, 
        default='traditional',
        choices=[('traditional', 'Traditional'), ('llm', 'LLM')]
    )
    llm_details = models.JSONField(default=json_default_dict, blank=True)
    attachments = models.JSONField(default=json_default_list, blank=True)

    def __str__(self):
        return self.name


class Field(models.Model):
    FIELD_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        # Add more field types as needed
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(Template, related_name='fields', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    required = models.BooleanField(default=False)
    page_index = models.IntegerField()
    pos_x = models.FloatField()
    pos_y = models.FloatField()
    font_size = models.IntegerField(blank=True)
    font = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name


class Generation(models.Model):

    def json_default_list():
        return []

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    template = models.ForeignKey(Template, related_name='generations', on_delete=models.CASCADE)
    created_at = models.DateField(auto_now_add=True)
    
    field_values = models.JSONField(default=json_default_list, blank=True)
    attachments = models.JSONField(default=json_default_list, blank=True)

    def __str__(self):
        return self.name

class Dataset(models.Model):
    def json_default_dict():
        return {}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    generation = models.ForeignKey(Generation, related_name='datasets', on_delete=models.CASCADE)
    created_at = models.DateField(auto_now_add=True)
    fields = models.JSONField(default=json_default_dict, blank=True)

    def __str__(self):
        return self.name