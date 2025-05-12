import os
import re
from glob import glob
from concurrent.futures import ProcessPoolExecutor
from PyPDF2 import PdfMerger
from unstructured.partition import pdf

def calculate_NEM(grades):
    nums = [float(g) for g in grades]
    return sum(nums) / len(nums) if nums else None

def extract_details_merged(text):
    grade_pattern = r': (\d+(\.\d+)?) :'
    grades = [g[0] for g in re.findall(grade_pattern, text)]
    id_pattern = r'RUN (\d{1,9}-[\dK])'
    student_ids = re.findall(id_pattern, text)
    return {"grades": grades, "rut": student_ids[0] if student_ids else None}

def extract_details_unique(text):
    grade_pattern = r'Año Escolar 20[0-9]{2}.*?([1-7]\.[0-9])'
    grades = re.findall(grade_pattern, text, flags=re.DOTALL)
    id_pattern = r'RUN\s*([\d\.]+-[\dKk])'
    student_ids = re.findall(id_pattern, text)
    return {"grades": grades, "rut": student_ids[0].replace('.', '') if student_ids else None}

def save_csv(rut, nem, out_path):
    import csv
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['RUT', 'NEM'])
        writer.writerow([rut, nem])

def _procesar_pdf(pdf_path, extractor, first_page_only=False):
    elements = pdf.partition_pdf(pdf_path)
    if first_page_only:
        texts = [el.text for el in elements if el.metadata.page_number == 1]
    else:
        texts = [el.text for el in elements]
    full_text = "\n".join(texts)
    details = extractor(full_text)
    if details and details["grades"]:
        nem = calculate_NEM(details["grades"])
        return {**details, "nem": nem}
    return None

def procesar_pdfs_merged(folder, max_workers=4):
    """Caso 1: PDFs ya unidos manualmente, un solo archivo por alumno."""
    pdfs = glob(os.path.join(folder, '*.pdf'))
    return [(_archivo := os.path.basename(p), _archivo, 
             _procesar_pdf(p, extract_details_merged)) for p in pdfs]

def procesar_pdfs_yearly(folder, max_workers=4):
    """Caso 2: PDFs uno por año; agrupa por base de nombre y concatena."""
    from itertools import groupby
    pdfs = sorted(glob(os.path.join(folder, '*.pdf')))
    # agrupar por nombre base ("TEST_1.pdf","TEST_2.pdf"→"TEST")
    groups = {}
    for p in pdfs:
        base = re.sub(r'_\d+\.pdf$', '', os.path.basename(p))
        groups.setdefault(base, []).append(p)

    resultados = []
    for base, files in groups.items():
        all_text = ""
        for p in sorted(files):
            all_text += "\n".join([el.text for el in pdf.partition_pdf(p)]) + "\n"
        details = extract_details_merged(all_text)
        if details["grades"]:
            nem = calculate_NEM(details["grades"])
            resultados.append((base, f"{base}.pdf", {**details, "nem": nem}))
    return resultados

def procesar_pdfs_concentracion(folder, max_workers=4):
    """Caso 3: PDFs de concentración; solo primera página."""
    pdfs = glob(os.path.join(folder, '*.pdf'))
    resultados = []
    for p in pdfs:
        details = _procesar_pdf(p, extract_details_unique, first_page_only=True)
        if details:
            resultados.append((os.path.splitext(os.path.basename(p))[0], 
                               os.path.basename(p), details))
    return resultados

def procesar_individual(path, modo):
    if modo == "1":
        return _procesar_pdf(path, extract_details_merged)
    elif modo == "2":
        # Modo 2 requiere múltiples PDFs por alumno. No aplica a uno solo.
        return None
    elif modo == "3":
        return _procesar_pdf(path, extract_details_unique, first_page_only=True)
    return None

# Mapeo de opciones a funciones y subcarpetas
PROCESSORS = {
    "1": (procesar_pdfs_merged, "pdfs_unidos_manualmente"),
    "2": (procesar_pdfs_yearly,   "pdfs_notas_para_cada_año"),
    "3": (procesar_pdfs_concentracion, "pdfs_concentracion_de_notas"),
}