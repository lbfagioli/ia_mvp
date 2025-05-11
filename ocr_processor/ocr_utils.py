import re
import os
from pdf2image import convert_from_path
from unstructured.partition import pdf
import pytesseract
import numpy as np

def calculate_NEM(grades):
    num_grades = [float(grade) for grade in grades]
    if num_grades:
        return sum(num_grades) / len(num_grades)
    return None

def extract_details_unique(text):
    # Extraer las notas
    grade_pattern = r'Año Escolar 20[0-9]{2}.*?([1-7]\.[0-9])'
    grades = re.findall(grade_pattern, text, flags=re.DOTALL)

    # Extraer el RUT del estudiante (se asume formato típico de RUT chileno, precedido por "RUN ")
    id_pattern = r'RUN\s*([\d\.]+-[\dKk])'
    student_ids = re.findall(id_pattern, text)

    # Extraer el nombre del estudiante (se asume que está en mayúsculas y precedido por "NOMBRE:")
    name_pattern = r'CERTIFICADO DE CONCENTRACION DE NOTAS\s+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+),\s*RUN'
    names = re.findall(name_pattern, text)

    rut = student_ids[0].replace('.', '') if student_ids else None

    return {
        "grades": [grade for grade in grades],
        "rut": rut,
        "full_text": text # Para propósitos de debugging o mostrar el texto crudo
    }

def procesar_pdf_concentracion(pdf_path):
    try:
        elements = pdf.partition_pdf(pdf_path)
        full_text = " ".join([
            el.text for el in elements if el.metadata.page_number == 1
        ])
        details = extract_details_unique(full_text)
        if details and details['grades']:
            nem = calculate_NEM(details['grades'])
            return {
                'rut': details['rut'],
                'nem': nem,
                'grades': details['grades'],
                'full_text': full_text
            }
        else:
            return None
    except Exception as e:
        print(f"Error al procesar el PDF: {e}")
        return None