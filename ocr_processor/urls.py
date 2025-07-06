from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('nem', views.upload_pdf, name='upload_pdf'),
    path('resultado_nem/', views.resultado_ocr, name='resultado_ocr'),
    path('cv', views.upload_pdf_cv, name='upload_pdf_cv'),
    path('resultado_cv/', views.resultado_ocr_cv, name='resultado_ocr_cv'),
    path('nem_internacional/', views.upload_pdf_internacional, name='upload_pdf_internacional'),
    path('resultado_internacional/', views.resultado_ocr_internacional, name='resultado_ocr_internacional'),
]