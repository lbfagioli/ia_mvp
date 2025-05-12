import os, tempfile
from django.shortcuts import render
from .forms import UploadPDFForm
from .ocr_utils import procesar_pdf_concentracion

def upload_pdf(request):
    if request.method == 'POST':
        # POST: procesamiento y render de resultados
        archivos = request.FILES.getlist('pdf_files')
        resultados = []
        for archivo in archivos:
            with tempfile.NamedTemporaryFile(delete=False,
                                             suffix=os.path.splitext(archivo.name)[1]) as tmp:
                for chunk in archivo.chunks():
                    tmp.write(chunk)
                tmp.flush()
                resultado = procesar_pdf_concentracion(tmp.name)
            os.remove(tmp.name)
            resultados.append({
                'filename': archivo.name,
                **(resultado or {})
            })
        return render(request, 'ocr_processor/resultado_ocr.html', {
            'resultados': resultados
        })

    # GET: mostrar form de subida
    form = UploadPDFForm()
    return render(request, 'ocr_processor/upload_form.html', {
        'form': form
    })