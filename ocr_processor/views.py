import os
import tempfile
import uuid
from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import UploadPDFForm
from .ocr_utils import procesar_pdfs_en_carpeta, exportar_resultados_csv
from .ocr_utils_2 import procesar_pdfs_en_carpeta as procesar_pdfs_en_carpeta_cv

def upload_pdf(request):
    if request.method == "POST":
        archivos = request.FILES.getlist("ocr_files")
        if not archivos:
            return render(request, "ocr_processor/resultado_ocr.html", {
                'error': "No se subieron archivos."
            })
        
        # Crear carpeta temporal para esta sesión de procesamiento
        session_id = uuid.uuid4().hex
        temp_dir = os.path.join(tempfile.gettempdir(), f"ocr_session_{session_id}")
        os.makedirs(temp_dir, exist_ok=True)

        # Guardar PDFs subidos en temp_dir
        pdf_files = []
        for archivo in archivos:
            if archivo.name.lower().endswith('.pdf'):
                if '/' in archivo.name or '\\' in archivo.name:
                    # Está en una subcarpeta, lo ignoramos
                    continue
                file_path = os.path.join(temp_dir, archivo.name)
                with open(file_path, "wb") as f:
                    for chunk in archivo.chunks():
                        f.write(chunk)
                pdf_files.append(archivo.name)

        # Procesar PDFs: esta función debe devolver
        # - resultados: dict {nombre_archivo: nem}
        # - logs: lista de strings con mensajes por archivo
        resultados, logs = procesar_pdfs_en_carpeta(temp_dir)

        total_docs = len(pdf_files)
        procesados_ok = len(resultados)
        errores = total_docs - procesados_ok

        output_folder = os.path.join("media", "ocr_csvs")
        os.makedirs(output_folder, exist_ok=True)
        output_csv_name = f"ocr_resultado_{session_id}.csv"
        output_csv_path = os.path.join(output_folder, output_csv_name)

        exportar_resultados_csv(resultados, output_csv_path)

        # Guardar resultados y logs en sesión para mostrarlos en GET
        request.session['ocr_resultados'] = {
            'total_docs': total_docs,
            'procesados_ok': procesados_ok,
            'errores': errores,
            'csv_url': f"/media/ocr_csvs/{output_csv_name}",
            'logs': logs,
        }

        # Redirigir a la vista de resultados (GET)
        return redirect(reverse('resultado_ocr'))

    # GET: mostrar formulario
    form = UploadPDFForm()
    return render(request, "ocr_processor/upload_form.html", {'form': form})

def resultado_ocr(request):
    resultados = request.session.get('ocr_resultados')
    if not resultados:
        # Si no hay resultados en sesión, redirigir al formulario
        return redirect(reverse('upload_pdf'))

    return render(request, "ocr_processor/resultado_ocr.html", resultados)

def upload_pdf_cv(request):
    if request.method == "POST":
        archivos = request.FILES.getlist("ocr_files")
        if not archivos:
            return render(request, "ocr_processor/resultado_ocr.html", {
                'error': "No se subieron archivos."
            })
        
        session_id = uuid.uuid4().hex
        temp_dir = os.path.join(tempfile.gettempdir(), f"ocr_session_{session_id}")
        os.makedirs(temp_dir, exist_ok=True)

        # Guardar PDFs subidos
        pdf_files = []
        for archivo in archivos:
            if archivo.name.lower().endswith('.pdf'):
                file_path = os.path.join(temp_dir, os.path.basename(archivo.name))
                with open(file_path, "wb") as f:
                    for chunk in archivo.chunks():
                        f.write(chunk)
                pdf_files.append(archivo.name)

        # Procesamiento
        output_folder = os.path.join("media", "ocr_csvs")
        os.makedirs(output_folder, exist_ok=True)
        output_csv_name = f"ocr_resultado_cv_{session_id}.csv"
        output_csv_path = os.path.join(output_folder, output_csv_name)

        df_resultados, logs = procesar_pdfs_en_carpeta_cv(temp_dir, output_csv_path)

        total_docs = len(pdf_files)
        procesados_ok = len(df_resultados)
        errores = total_docs - procesados_ok

        request.session['ocr_resultados'] = {
            'total_docs': total_docs,
            'procesados_ok': procesados_ok,
            'errores': errores,
            'csv_url': f"/media/ocr_csvs/{output_csv_name}",
            'logs': logs,
        }

        return redirect(reverse('resultado_ocr_cv'))
    
    # GET: mostrar formulario
    form = UploadPDFForm()
    return render(request, "ocr_processor/upload_form_cv.html", {'form': form})

def resultado_ocr_cv(request):
    resultados = request.session.get('ocr_resultados')
    if not resultados:
        # Si no hay resultados en sesión, redirigir al formulario
        return redirect(reverse('upload_pdf_cv'))

    return render(request, "ocr_processor/resultado_ocr_cv.html", resultados)

def home(request):
    return render(request, 'ocr_processor/home.html')