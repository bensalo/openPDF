from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("create_template/", views.create_template, name="create_template"),
    path("generate_template/", views.generate_template, name="generate_template"),
    path('settings/', views.settings_view, name='settings'),
    path('history/', views.history_view, name='history'),
    path('history/<str:gen_id>/', views.history_detail_view, name='history_detail'),
    path("edit/<str:temp_id>/", views.template_edit, name="edit"),
    path("new/<str:temp_id>/", views.template_new_pdf, name="new"),
    path("new/<str:temp_id>/<str:gen_id>/", views.template_new_pdf, name="new_preload"),
    path("dataset/new/<str:gen_id>/", views.new_dataset, name="new_dataset"),
    path("dataset/<str:dataset_id>/", views.dataset_detail, name="dataset_detail"),
    path("dataset/use/<str:dataset_id>/temp/<str:temp_id>/", views.dataset_use, name="dataset_use"),
    path("datasets/", views.datasets, name="datasets"),
    path('media/<file_type>/<path:file_path>/', views.file_response, name='file_response'),
    path("<uuid:temp_id>/", views.template_detail, name="detail"),
    path('api/check-llm-status/', views.check_llm_status, name='check_llm_status'),
    ]