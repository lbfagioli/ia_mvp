from django import forms

class UploadPDFForm(forms.Form):
    pdf_file = forms.FileField(label='Selecciona un archivo PDF')