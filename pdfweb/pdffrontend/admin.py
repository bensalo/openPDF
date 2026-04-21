from django.contrib import admin
from .models import Template, Field, Generation, Dataset


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'font', 'font_size', 'last_updated', 'template_pages', 'file_path')
    search_fields = ('name', 'font')
    list_filter = ('created_at', 'last_updated')


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'field_type', 'template', 'required', 'page_index', 'pos_x', 'pos_y')
    search_fields = ('name', 'field_type', 'template__name')
    list_filter = ('field_type', 'required', 'template')


@admin.register(Generation)
class GenerationAdmin(admin.ModelAdmin):
    list_display = ('name', 'template', 'created_at')
    search_fields = ('name', 'template__name')
    list_filter = ('created_at', 'template')


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'generation', 'created_at')
    search_fields = ('name', 'generation__name')
    list_filter = ('created_at', 'generation')
