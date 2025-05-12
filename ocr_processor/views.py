import os
import tempfile
from glob import glob
from django.shortcuts import render
from .forms import UploadPDFForm
from .ocr_utils import PROCESSORS, save_csv, procesar_individual  # Importación corregida

def upload_pdf(request):
    if request.method == "POST":
        archivos = request.FILES.getlist("ocr_files")
        try:
            count = int(request.POST.get("files_count", 0))
        except ValueError:
            count = 0

        temp_info = []
        for idx, archivo in enumerate(archivos):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo.name)[1])
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp.flush()
            tmp.close()
            mode = request.POST.get(f"file_mode_{idx}")
            temp_info.append((archivo.name, tmp.name, mode))

        resultados = []
        for original_name, tmp_path, mode in temp_info:
            subfolder = {
                "1": "pdfs_unidos_manualmente",
                "2": "pdfs_notas_para_cada_año",
                "3": "pdfs_concentracion_de_notas",
            }.get(mode)

            data = procesar_individual(tmp_path, mode)
            if data:
                base = os.path.splitext(original_name)[0]
                csv_name = f"{base}.csv"
                csv_path = os.path.join(subfolder, csv_name)

                # Crear carpeta si no existe
                os.makedirs(subfolder, exist_ok=True)

                save_csv(data['rut'], data['nem'], csv_path)
                resultados.append({
                    'filename': original_name,
                    'rut':      data['rut'],
                    'nem':      data['nem'],
                    'grades':   data['grades'],
                    'csv_url':  f"/media/{subfolder}/{csv_name}"
                })
            else:
                resultados.append({
                    'filename': original_name,
                    'error': 'No se extrajeron datos'
                })

            os.remove(tmp_path)

        return render(request, "ocr_processor/resultado_ocr.html", {
            'resultados': resultados
        })

    # GET
    form = UploadPDFForm()
    return render(request, "ocr_processor/upload_form.html", {
        'form': form
    })
