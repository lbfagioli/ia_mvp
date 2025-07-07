# -*- coding: utf-8 -*-
"""
International Grades Module
Converted from Colab notebook to Python script.
"""
import glob
import fitz  # PyMuPDF
from PIL import Image
import io
import json
import statistics
import google.generativeai as genai
import os
import pandas as pd

# === CONFIGURATION ===

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')  # Make sure this env variable is set
if not GOOGLE_API_KEY:
    raise ValueError("Please set the GOOGLE_API_KEY environment variable.")
genai.configure(api_key=GOOGLE_API_KEY)

# === INITIALIZE GEMINI MODEL ===

gemini_model = genai.GenerativeModel('gemini-2.0-flash-lite')

# === IMAGE EXTRACTION ===

def images_from_pdf(pdf_path):
    images = []
    try:
        pdf_document = fitz.open(pdf_path)
        for page_number in range(pdf_document.page_count):
            page = pdf_document.load_page(page_number)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        pdf_document.close()
        print(f"[images_from_pdf]: Successfully extracted {len(images)} images from the PDF.")
    except FileNotFoundError:
        print(f"[images_from_pdf]: Error: The file was not found at {pdf_path}")
    except Exception as e:
        print(f"[images_from_pdf]: An error occurred: {e}")
    return images

# === LLM INVOCATION ===

def invoke_llm(images):
    extracted_text_llm = ""
    try:
        image_parts = []
        for i, img in enumerate(images):
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            image_parts.append({
                "mime_type": "image/jpeg",
                "data": img_byte_arr.getvalue()
            })

        json_prompt = (
            "Extract all the text from these images in order. "
            "They constitute a grades certificate from a foreign country. "
            "Having this done, process the text in order to deliver { country: x, years: [ year: y, subjects: [ name: z, grade: w ] ] }, in JSON format. "
            "I need you to just output the JSON, nothing else."
        )
        content = [{"text": json_prompt}] + image_parts
        print(f"[invoke_llm]: Sending {len(images)} images in a single request...")

        response = gemini_model.generate_content(content)
        extracted_text_llm = response.text

    except Exception as e:
        print(f"[invoke_llm]: An error occurred: {e}")
    return extracted_text_llm

# === TEXT TO JSON PARSING ===

def text_to_json(extracted_text_llm):
    if "json" in extracted_text_llm:
        text = extracted_text_llm.split("json")[1].split("```")[0]
    else:
        text = extracted_text_llm
    dic = json.loads(text)
    if isinstance(dic, list):
        dic = dic[0]
    return dic

def pick_last_four_years(dic):
    sorted_years = sorted(dic["years"], key=lambda x: -int(x["year"]))
    return sorted_years[:4]

# === GRADE CALCULATION ===

def year_average_grade(subjects):
    grades = [float(s["grade"]) for s in subjects if s.get("grade")]
    return statistics.mean(grades) if grades else 0

def four_years_grade(years):
    return statistics.mean([
        year_average_grade(y["subjects"]) for y in years
    ])

def nem(country, grade):
    result = -1
    match country.lower():
        case "venezuela":
            result = (((grade - 10) * 3) / 10) + 4
        case "bolivia":
            result = (((grade - 50) * 3) / 50) + 4
        case "panama":
            result = (((grade - 3) * 3) / 2) + 4
        case _:
            print(f"[nem]: Country not supported for \"{country}\"")
    return result

# === CSV EXPORT ===

def exportar_resultados_csv(df: pd.DataFrame, output_csv: str):
    df.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"\n📄 CSV exportado a: {output_csv}")


# === MAIN FLOW (example) ===


# TO WORK WITH PREVIOUS FUNCTIONS
# SHOULD INVOLVE THE FOLLOWING STEPS
"""
if __name__ == "__main__":
    input_pdf = 'path/to/your/file.pdf'  # Update this path
    images = images_from_pdf(input_pdf)
    extracted_text = invoke_llm(images)

    if extracted_text:
        json_text = text_to_json(extracted_text)
        last_four_years = pick_last_four_years(json_text)
        grade = four_years_grade(last_four_years)
        calculated_nem = nem(json_text["country"], grade)
"""
def procesar_pdfs_en_carpeta_internacional(input_folder, output_csv_path):
    all_pdfs = glob.glob(os.path.join(input_folder, '*.pdf'))
    pdf_files_root = [f for f in all_pdfs if os.path.dirname(f) == input_folder]
    pdf_files_all = glob.glob(os.path.join(input_folder, '**', '*.pdf'), recursive=True)
    pdf_files_subcarpetas = [f for f in pdf_files_all if os.path.dirname(f) != input_folder]

    resultados = []
    logs = []

    for pdf_file in pdf_files_root:
        try:
            images = images_from_pdf(pdf_file)
            extracted_text = invoke_llm(images)

            if not extracted_text:
                logs.append(f"⚠️ No se pudo extraer texto del archivo: {os.path.basename(pdf_file)}")
                continue

            json_data = text_to_json(extracted_text)
            last_four_years = pick_last_four_years(json_data)
            avg_grade = four_years_grade(last_four_years)
            calculated_nem = nem(json_data["country"], avg_grade)

            if calculated_nem == -1:
                logs.append(f"⚠️ País no soportado en: {os.path.basename(pdf_file)}")
                continue

            filename = os.path.splitext(os.path.basename(pdf_file))[0]
            resultados.append({"FILE": filename, "GRADE": round(avg_grade, 2), "NEM": round(calculated_nem, 2)})
            logs.append(f"✅ {filename} → Promedio extranjero: {round(avg_grade, 2)} → NEM: {round(calculated_nem, 2)}")

        except Exception as e:
            logs.append(f"❌ Error procesando {os.path.basename(pdf_file)}: {e}")

    if pdf_files_subcarpetas:
        logs.append(f"⚠️ Se ignoraron {len(pdf_files_subcarpetas)} archivos PDF en subcarpetas.")

    # Crear DataFrame con resultados
    import pandas as pd
    df_resultados = pd.DataFrame(resultados)

    # Exportar CSV directamente aquí
    exportar_resultados_csv(df_resultados, output_csv_path)

    return df_resultados, logs