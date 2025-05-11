import os
from django.shortcuts import render
from django.http import HttpResponse
from .forms import UploadPDFForm
from .ocr_utils import procesar_pdf_concentracion

def upload_pdf(request):
    if request.method == 'POST':
        form = UploadPDFForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            try:
                # Guarda temporalmente el archivo subido
                temp_pdf_path = 'temp_concentracion.pdf'
                with open(temp_pdf_path, 'wb+') as destination:
                    for chunk in pdf_file.chunks():
                        destination.write(chunk)

                resultado = procesar_pdf_concentracion(temp_pdf_path)
                os.remove(temp_pdf_path) # Limpiar el archivo temporal

                if resultado and 'nem' in resultado and 'rut' in resultado and 'grades' in resultado:
                    return render(request, 'ocr_processor/resultado_ocr.html', {
                        'texto': f"RUT: {resultado['rut']}\nNEM: {resultado['nem']:.2f}\nNotas extraídas: {resultado['grades']}",
                        'nem_value': f"{resultado['nem']:.2f}",
                        'rut_value': resultado['rut'],
                        'raw_text': resultado.get('full_text', 'No se pudo extraer el texto completo.')
                    })
                else:
                    return HttpResponse("No se pudieron extraer los detalles del PDF.")

            except Exception as e:
                return HttpResponse(f"Ocurrió un error durante el procesamiento: {e}")
    else:
        form = UploadPDFForm()
    return render(request, 'ocr_processor/upload_form.html', {'form': form})