import os
import tempfile
import uuid
import pathlib
from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import UploadPDFForm
from .ocr_utils import procesar_pdfs_en_carpeta, exportar_resultados_csv
from .ocr_utils_2 import procesar_pdfs_en_carpeta as procesar_pdfs_en_carpeta_cv
from .ocr_international import procesar_pdfs_en_carpeta_internacional

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse

def upload_pdf(request):
    if request.method == "POST":
        archivos = request.FILES.getlist("ocr_files")
        if not archivos:
            return render(request, "ocr_processor/resultado_ocr.html", {
                'error': "No se subieron archivos."
            })

        pdf_files = [a for a in archivos if a.name.lower().endswith('.pdf')]
        no_pdf_files = [a for a in archivos if not a.name.lower().endswith('.pdf')]

        if not pdf_files:
            return render(request, "ocr_processor/resultado_ocr.html", {
                'error': "No se aceptan archivos que no sean PDF."
            })

        logs = [f"⚠️ Archivo no compatible ignorado: {a.name}" for a in no_pdf_files]
        
        # Crear carpeta temporal para esta sesión de procesamiento
        session_id = uuid.uuid4().hex
        temp_dir = os.path.join(tempfile.gettempdir(), f"ocr_session_{session_id}")
        os.makedirs(temp_dir, exist_ok=True)

        # Guardar PDFs subidos en temp_dir
        pdf_files = []
        for archivo in archivos:
                path_parts = pathlib.PurePath(archivo.name).parts
                if len(path_parts) > 1:
                    continue
                file_path = os.path.join(temp_dir, archivo.name)
                with open(file_path, "wb") as f:
                    for chunk in archivo.chunks():
                        f.write(chunk)
                pdf_files.append(archivo.name)

        # Procesar PDFs: esta función debe devolver
        # - resultados: dict {nombre_archivo: nem}
        # - logs: lista de strings con mensajes por archivo
        resultados, process_logs = procesar_pdfs_en_carpeta(temp_dir)
        logs.extend(process_logs)

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
            'logs': '\n'.join(logs),
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
        try:
            archivos = request.FILES.getlist("ocr_files")
            if not archivos:
                raise ValueError("No se subieron archivos.")

            pdf_files = [a for a in archivos if a.name.lower().endswith('.pdf')]
            no_pdf_files = [a for a in archivos if not a.name.lower().endswith('.pdf')]

            if not pdf_files:
                return render(request, "ocr_processor/resultado_ocr.html", {
                    'error': "No se aceptan archivos que no sean PDF."
                })

            logs = [f"⚠️ Archivo no compatible ignorado: {a.name}" for a in no_pdf_files]
            
            # Carpeta temporal
            sid      = uuid.uuid4().hex
            temp_dir = os.path.join(tempfile.gettempdir(), f"ocr_{sid}")
            os.makedirs(temp_dir, exist_ok=True)

            # Guardar PDFs
            pdfs = []
            for a in archivos:
                if a.name.lower().endswith('.pdf'):
                    dest = os.path.join(temp_dir, os.path.basename(a.name))
                    with open(dest, 'wb') as f:
                        for chunk in a.chunks():
                            f.write(chunk)
                    pdfs.append(a.name)

            # Procesar y CSV
            out_dir     = os.path.join("media", "ocr_csvs")
            os.makedirs(out_dir, exist_ok=True)
            csv_name    = f"ocr_cv_{sid}.csv"
            csv_path    = os.path.join(out_dir, csv_name)
            df, process_logs = procesar_pdfs_en_carpeta_cv(temp_dir, csv_path)
            logs.extend(process_logs)

            # Guardar en sesión
            request.session['ocr_resultados'] = {
                'total_docs':    len(pdfs),
                'procesados_ok': len(df),
                'errores':       len(pdfs) - len(df),
                'csv_url':       f"/media/ocr_csvs/{csv_name}",
                'logs':          '\n'.join(logs),
            }

            redirect_url = reverse('resultado_ocr_cv')
            # Si AJAX, devolvemos JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'redirect_url': redirect_url})
            return redirect(redirect_url)

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=500)
            return render(request, "ocr_processor/resultado_ocr.html", {'error': str(e)})

    # GET
    form = UploadPDFForm()
    return render(request, "ocr_processor/upload_form_cv.html", {'form': form})

def upload_pdf_internacional(request):
    if request.method == "POST":
        try:
            archivos = request.FILES.getlist("ocr_files")
            if not archivos:
                raise ValueError("No se subieron archivos.")

            pdf_files = [a for a in archivos if a.name.lower().endswith('.pdf')]
            no_pdf_files = [a for a in archivos if not a.name.lower().endswith('.pdf')]

            if not pdf_files:
                return render(request, "ocr_processor/resultado_ocr.html", {
                    'error': "No se aceptan archivos que no sean PDF."
                })
            
            logs = []
            for archivo in no_pdf_files:
                logs.append(f"⚠️ Archivo no compatible ignorado: {archivo.name}")
            
            # Crear carpeta temporal
            sid = uuid.uuid4().hex
            temp_dir = os.path.join(tempfile.gettempdir(), f"ocr_internacional_{sid}")
            os.makedirs(temp_dir, exist_ok=True)

            # Guardar PDFs
            pdfs = []
            for a in archivos:
                if a.name.lower().endswith('.pdf'):
                    if '/' in a.name or '\\' in a.name:
                        continue  # Ignorar archivos en subcarpetas
                    dest = os.path.join(temp_dir, os.path.basename(a.name))
                    with open(dest, 'wb') as f:
                        for chunk in a.chunks():
                            f.write(chunk)
                    pdfs.append(a.name)

            # Procesar y generar CSV

            out_dir = os.path.join("media", "ocr_csvs")
            os.makedirs(out_dir, exist_ok=True)
            csv_name = f"ocr_internacional_{sid}.csv"
            csv_path = os.path.join(out_dir, csv_name)
            resultados, procesar_logs = procesar_pdfs_en_carpeta_internacional(temp_dir, csv_path)
            logs.extend(procesar_logs)

            # Guardar en sesión
            request.session['ocr_resultados'] = {
                'total_docs':    len(pdfs),
                'procesados_ok': len(resultados),
                'errores':       len(pdfs) - len(resultados),
                'csv_url':       f"/media/ocr_csvs/{csv_name}",
                'logs':          '\n'.join(logs),
            }

            redirect_url = reverse('resultado_ocr_internacional')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'redirect_url': redirect_url})
            return redirect(redirect_url)

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=500)
            return render(request, "ocr_processor/resultado_ocr_internacional.html", {'error': str(e)})

    # GET
    form = UploadPDFForm()
    return render(request, "ocr_processor/upload_form_internacional.html", {'form': form})

def resultado_ocr_internacional(request):
    resultados = request.session.get('ocr_resultados')
    if not resultados:
        return redirect(reverse('upload_pdf_internacional'))

    return render(request, "ocr_processor/resultado_ocr_internacional.html", resultados)

def resultado_ocr_cv(request):
    resultados = request.session.get('ocr_resultados')
    if not resultados:
        # Si no hay resultados en sesión, redirigir al formulario
        return redirect(reverse('upload_pdf_cv'))

    return render(request, "ocr_processor/resultado_ocr_cv.html", resultados)

def home(request):
    return render(request, 'ocr_processor/home.html')