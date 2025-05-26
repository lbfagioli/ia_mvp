from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_pdf, name='upload_pdf'),
    path('resultado/', views.resultado_ocr, name='resultado_ocr'),
]