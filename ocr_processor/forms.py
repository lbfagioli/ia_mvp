from django import forms

class UploadPDFForm(forms.Form):
    dummy = forms.CharField(widget=forms.HiddenInput(), required=False)
