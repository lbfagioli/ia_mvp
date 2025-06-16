import os
import re
import csv
from glob import glob
from unstructured.partition.pdf import partition_pdf

def calculate_NEM(grades):
    grades = [float(g) for g in grades if 1.0 <= float(g) <= 7.0]
    return round(sum(grades) / len(grades), 2) if grades else None

def extract_details_auto(text_pages):
    rut = None
    grades = []

    full_text = "\n".join(text_pages)
    rut_match = re.search(r'RUN\s*([\d\.]+-[\dKk])', full_text)
    if rut_match:
        rut = rut_match.group(1).replace('.', '')
    else:
        raise ValueError("No se encontró RUT válido.")

    first_page_text = text_pages[0]

    if "CERTIFICADO DE CONCENTRACION DE NOTAS" in first_page_text.upper():
        grades = re.findall(r'Año Escolar 20[0-9]{2}.*?([1-7]\.[0-9])', first_page_text, flags=re.DOTALL)
    else:
        valid_pages = [page for page in text_pages if "CERTIFICADO ANUAL DE ESTUDIOS" in page.upper()]
        if not valid_pages:
            raise ValueError("No se encontraron páginas válidas con 'CERTIFICADO ANUAL DE ESTUDIOS'.")

        for page in valid_pages:
            colon_matches = re.findall(r':\s*(\d\.\d)', page)
            if colon_matches:
                grades.extend(colon_matches)
            else:
                promedio_matches = re.findall(r'PROMEDIO GENERAL\s*(\d+)\.(\d)', page.upper())
                for whole_part, decimal_part in promedio_matches:
                    last_digit = whole_part[-1]
                    grade = f"{last_digit}.{decimal_part}"
                    grades.append(grade)

    if not grades:
        raise ValueError("No se encontraron notas finales válidas.")

    return {
        "grades": grades,
        "rut": rut
    }

def procesar_pdfs_en_carpeta(input_folder):
    # PDFs en la raíz
    all_pdfs = glob(os.path.join(input_folder, '*.pdf'))
    pdf_files_root = [f for f in all_pdfs if os.path.dirname(f) == input_folder]
    pdf_files_all = glob(os.path.join(input_folder, '**', '*.pdf'), recursive=True)

    # Detectar si hay archivos en subcarpetas
    pdf_files_subcarpetas = [f for f in pdf_files_all if os.path.dirname(f) != input_folder]

    resultados = []
    logs = []

    for pdf_file in pdf_files_root:
        try:
            elements = partition_pdf(pdf_file)
            pages = {}
            for el in elements:
                page_num = el.metadata.page_number
                pages.setdefault(page_num, "")
                pages[page_num] += el.text + " "
            text_pages = [pages[p] for p in sorted(pages)]

            details = extract_details_auto(text_pages)
            nem = calculate_NEM(details['grades'])

            if nem is None:
                msg = f"⚠️ No se encontraron notas válidas en: {os.path.basename(pdf_file)}"
                logs.append(msg)
                continue

            resultados.append([details['rut'], nem])
            logs.append(f"✅ {details['rut']} → NEM: {nem}")
        except Exception as e:
            logs.append(f"❌ Error procesando {os.path.basename(pdf_file)}: {e}")

    if pdf_files_subcarpetas:
        logs.append(f"⚠️ Se ignoraron {len(pdf_files_subcarpetas)} archivos PDF que estaban en subcarpetas.")

    return resultados, logs

def exportar_resultados_csv(resultados, output_csv):
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['RUT', 'NEM'])
        writer.writerows(resultados)
    print(f"\n📄 CSV exportado a: {output_csv}")