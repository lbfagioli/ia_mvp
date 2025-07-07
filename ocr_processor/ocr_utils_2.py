import re
import os
import json
import nltk
import pdfplumber
import pytesseract
import pandas as pd
from glob import glob
from tqdm import tqdm
from openai import OpenAI
from typing import Union, Pattern
from pdf2image import convert_from_path
from unstructured.partition.pdf import partition_pdf
from dotenv import load_dotenv
from .constants import OCRInputFormats
os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/4.00/tessdata"

tqdm.pandas()
nltk.download('averaged_perceptron_tagger')

# Load environment variables from .env file
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_ENDPOINT = os.getenv('OPENAI_ENDPOINT')

def _set_openai_client():
    return OpenAI(
        base_url=OPENAI_ENDPOINT,
        api_key=OPENAI_API_KEY
    )

def calculate_NEM(grades):
    grades = [float(g) for g in grades if 1.0 <= float(g) <= 7.0]
    return round(sum(grades)/len(grades), 2) if grades else None

def extract_details_auto(text_pages):
    rut = None
    grades = []

    full_text = "\n".join(text_pages)
    m = re.search(r'RUN\s*([\d\.]+-[\dKk])', full_text)
    if m:
        rut = m.group(1).replace('.', '')
    else:
        raise ValueError("No se encontró RUT válido.")

    first_page = text_pages[0].upper()
    if re.search(r'CERTIFICADO DE CONCENTRACION DE NOTAS', first_page, flags=re.IGNORECASE): #AGRUEGE IGNORECASE Y N/Ñ
        # Patrón adaptado: AÑO ESCOLAR o Año Escolar, con IGNORECASE
        pattern = re.compile(
            r'A[NÑ]O ESCOLAR\s*20[0-9]{2}.*?([1-7]\.\d+)',
            flags=re.DOTALL | re.IGNORECASE
        )
        grades = pattern.findall(first_page)
        print(f"[extract_details_auto] Matches de Concentración: {grades}") #UP TO HERE

    else:
        valid = [p for p in text_pages if "CERTIFICADO ANUAL DE ESTUDIOS" in p.upper()]
        if not valid:
            raise ValueError("No se encontraron páginas válidas con 'CERTIFICADO ANUAL DE ESTUDIOS'.")
        for page in valid:
            cm = re.findall(r':\s*(\d\.\d)', page)
            if cm:
                grades.extend(cm)
            else:
                pm = re.findall(r'PROMEDIO GENERAL\s*(\d+)\.(\d)', page.upper())
                for whole, dec in pm:
                    grades.append(f"{whole[-1]}.{dec}")

    if not grades:
        raise ValueError("No se encontraron notas finales válidas.")

    return {"grades": grades, "rut": rut}

def process_cv(cv_path):
    """Extrae texto de un CV: primero intenta con pdfplumber, luego hace fallback a OCR."""
    if not cv_path:
        return ""

    try:
        with pdfplumber.open(cv_path) as pdf:
            full_text = ""
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
                except Exception as e:
                    print(f"[process_cv] Error extrayendo texto página {page_num} en {cv_path}: {e}")
                    # Salta esta página y continúa con la siguiente
            if len(full_text.strip()) >= 20:
                print(f"[process_cv] Texto extraído con pdfplumber de {cv_path}")
                return full_text
            else:
                print(f"[process_cv] Texto insuficiente, aplicando OCR en {cv_path}")
                return ocr_fallback(cv_path)
    except Exception as e:
        print(f"[process_cv] Error con pdfplumber en {cv_path}: {e}")
        return ocr_fallback(cv_path)
    
def ocr_fallback(cv_path):
    """Extrae el texto completo de un CV.pdf. con tesseract"""
    if not cv_path:
        return ""
    pages = extract_text_pages(cv_path, first_page_only=False)
    full_text = "\n".join(pages)
    print(f"[ocr_fallback] OCR extraído de {cv_path}, {len(full_text)} caracteres")
    return full_text

def ocr_full_text(pdf_path: str, dpi: int = 200) -> str:
    """
    Convierte cada página del PDF a imagen y aplica OCR con pytesseract.
    Devuelve todo el texto concatenado.
    """
    try:
        # 1. Convertir PDF a lista de PIL Images
        pages = convert_from_path(pdf_path, dpi=dpi)
    except Exception as e:
        print(f"[ocr_full_text] Error al convertir PDF a imágenes: {e}")
        return ""

    text_pages = []
    for i, page_img in enumerate(pages, start=1):
        try:
            # 2. OCR sobre la imagen
            text = pytesseract.image_to_string(page_img, lang='spa', config='--psm 1')
            text_pages.append(text)
        except Exception as e:
            print(f"[ocr_full_text] OCR falló en página {i}: {e}")
            text_pages.append("")

    full_text = "\n".join(text_pages)
    print(f"[ocr_full_text] OCR completado para {os.path.basename(pdf_path)} ({len(pages)} páginas)")
    return full_text

def list_pdf_files(input_folder):
    """Devuelve la lista de rutas *.pdf en la carpeta."""
    files = glob(os.path.join(input_folder, '*.pdf'))
    print(f"[list_pdf_files] Encontrados {len(files)} PDFs")
    return files

def group_by_rut_and_id(pdf_paths):
    grupos = {}
    for path in pdf_paths:
        fname = os.path.basename(path)
        m = OCRInputFormats.FILENAME_PATTERN.value.match(fname)
        if not m:
            continue
        rut     = m.group('rut').replace('.', '')
        post_id = m.group('id')
        tipo    = m.group('tipo').lower()
        grupos.setdefault((rut, post_id), {})[tipo] = path
    return grupos

def extract_text_pages(pdf_path, first_page_only=False):
    """Partition + agrupa por página, devuelve lista de textos por página."""
    pages = convert_from_path(pdf_path, dpi=200)
    if first_page_only:
        pages = pages[:1]
    return [
        pytesseract.image_to_string(page, lang="spa", config="--psm 1")
        for page in pages
    ]

def process_notasmedia(notas_path):
    """Extrae rut, grades y calcula NEM a partir de NotasMedia.pdf."""
    pages = extract_text_pages(notas_path, first_page_only=False)
    detalles = extract_details_auto(pages)
    nem = calculate_NEM(detalles['grades'])
    return detalles['rut'], nem

def process_group(rut, post_id, docs):
    """Procesa un par (rut, post_id) retornando un dict con los campos."""
    notas_path = docs.get('notasmedia')
    cv_path    = docs.get('cv')
    try:
        rut_extracted, nem = process_notasmedia(notas_path)
        cv_text = process_cv(cv_path)
        return {
            'rut':     rut_extracted,
            'post_id': post_id,
            'nem':     nem,
            'cv_text': cv_text,
            'error':   None
        }
    except Exception as e:
        print(f"[process_group] ERROR en ({rut}, {post_id}): {e}")
        return {
            'rut':     rut,
            'post_id': post_id,
            'nem':     None,
            'cv_text': "",
            'error':   str(e)
        }

def tabular_folder(input_folder):
    """Función principal: devuelve un DataFrame con rut, post_id, nem, cv_text, error."""
    print(f"[tabular_folder] Iniciando en carpeta: {input_folder}")
    pdfs   = list_pdf_files(input_folder)
    grupos = group_by_rut_and_id(pdfs)

    rows = []
    for (rut, post_id), docs in grupos.items():
        row = process_group(rut, post_id, docs)
        rows.append(row)

    df = pd.DataFrame(rows, columns=['rut','post_id','nem','cv_text','error'])
    print(f"[tabular_folder] Generado DataFrame con {len(df)} filas")
    return df

def rank_sports_from_selection(text):
    deportes = [
        "hockey", "fútbol", "futbol", "rugby", "tenis",
        "atletismo", "básquetbol", "basquetbol", "natación",
        "voleibol", "handball", "escalada"
    ]
    text_lower = text.lower()
    for deporte in deportes:
        # simple substring match instead of \b…\b
        if deporte in text_lower:
            return 3
    return 0

YearPat = re.compile(r'\b(?:19|20)\d{2}\b')

def compile_pattern(pattern: Union[str, Pattern], flags=0) -> Pattern:
    return re.compile(pattern, flags) if isinstance(pattern, str) else pattern

def extract_section(text: str, start_pat: Pattern, end_pat: Pattern) -> str:
    """
    Devuelve el texto entre el patrón de inicio y fin. Si no hay fin, va hasta el final.
    """
    start_match = start_pat.search(text)
    if not start_match:
        return ""

    tail = text[start_match.end():]
    end_match = end_pat.search(tail)
    return tail[: end_match.start()] if end_match else tail

def count_year_lines(section: str, year_pattern: Pattern = YearPat) -> int:
    """
    Cuenta las líneas dentro de un texto que contienen un año.
    """
    return sum(1 for line in section.splitlines() if year_pattern.search(line))

def count_unique_year_lines_per_section(
    text: str,
    point_mult: float,
    start_pattern: str,
    end_pattern: str,
    max_count: int = 4
) -> float:
    section = extract_section(
        text,
        compile_pattern(start_pattern, flags=re.IGNORECASE),
        compile_pattern(end_pattern, flags=re.IGNORECASE)
    )
    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]
    data_lines = lines[1:-1]

    years_found = set()
    text_lines = set()

    for ln in data_lines:
        if re.fullmatch(r'[A-Z\s]{2,}', ln.upper()):
            continue

        years = YearPat.findall(ln)
        if years:
            years_found.update(int(y) for y in years)
        else:
            text_lines.add(ln)

    total_items = len(years_found) + len(text_lines)
    return min(total_items, max_count) * point_mult


def count_local_tournaments(text: str, start_pattern, end_pattern) -> float:
    section = extract_section(
        text,
        compile_pattern(start_pattern, re.IGNORECASE | re.MULTILINE),
        compile_pattern(end_pattern,   re.IGNORECASE | re.MULTILINE),
    )
    raw = [ln.strip() for ln in section.splitlines() if ln.strip()]

    event_lines = [
        ln for ln in raw
        if YearPat.search(ln) and not re.match(r'^\s*AÑO\b', ln, re.IGNORECASE)
    ]

    # Quita duplicados y multiplica
    unique_events = set(event_lines)
    return len(unique_events) * 2.5


def count_international_tournaments(text: str, start_pattern, end_pattern) -> float:
    section = extract_section(
        text,
        compile_pattern(start_pattern, re.IGNORECASE),
        compile_pattern(end_pattern, re.IGNORECASE),
    )
    lines = [line.strip().lower() for line in section.splitlines() if line.strip()]
    unique_events = {line for line in lines if YearPat.search(line)}
    return len(unique_events) * 5

def exportar_resultados_csv(df: pd.DataFrame, output_csv: str):
    df.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"\n📄 CSV exportado a: {output_csv}")

### --------------- OPENAI --------------- ###
def extract_section_7(text: str) -> str:
    start = OCRInputFormats.SECTION_7_START.value.search(text)
    if not start:
        return ""
    tail = text[start.end():]
    end = OCRInputFormats.SECTION_7_END.value.search(tail)
    return tail[:end.start()] if end else tail

def filter_interest_lines(text: str) -> str:
    lines = text.splitlines()
    year_re = OCRInputFormats.YEAR_RE.value
    place_re = OCRInputFormats.PLACE_RE.value

    return "\n".join([
        line.strip() for line in lines
        if year_re.search(line) or place_re.search(line)
    ])

### --------------- Other Tournaments --------------- ###
def extract_tournament_points(chat_context: str, client: OpenAI) -> int:
    instruction = (
        "Del siguiente texto extrae únicamente las participaciones en torneos deportivos que se mencionen explícitamente.\n"
        "- No incluyas premios, reconocimientos o logros como 'mejor jugador' o 'capitán'.\n"
        "- Solo cuenta la cantidad de torneos en los que el estudiante haya participado.\n"
        "- No repitas torneos si ya fueron mencionados.\n"
        "- Devuelve únicamente el número total de torneos.\n"
        "- Si no hay torneos, responde con 0.\n"
        "Formato de salida: solo el número, sin comillas ni texto adicional.\n\n"
        "Texto:\n" + chat_context
    )

    try:
        response = client.chat.completions.create(
            model="openai/gpt-4.1",
            temperature=0,
            messages=[
                {"role": "system", "content": "Eres un extractor preciso de participaciones en torneos deportivos y calculas puntajes."},
                {"role": "user", "content": instruction}
            ]
        )
        raw_output = response.choices[0].message.content.strip()
        print("🔎 Conteo retornado por modelo:", raw_output)
        return int(raw_output)
    except Exception as e:
        print("❌ Error extrayendo torneos:", e)
        return 0

def contar_puntaje_other_from_count(n: int) -> int:
    return min(n * 5, 90)  # 5 puntos por participación, máximo 90

### --------------- Awards --------------- ###
def extract_recognition_count(chat_context: str, client: OpenAI) -> int:
    instruction = (
        "Del siguiente texto, extrae únicamente los reconocimientos o distinciones personales vinculadas al deporte "
        "(como 'capitán', 'mejor jugador', 'destacado', 'fair play', etc). "
        "- No incluyas participaciones en torneos, lugares obtenidos, ni años.\n"
        "- No repitas reconocimientos si ya fueron mencionados.\n"
        "- Devuelve únicamente la cantidad total de reconocimientos distintos.\n"
        "- Si no hay reconocimientos, responde con 0.\n"
        "Formato de salida: solo el número, sin comillas ni texto adicional.\n\n"
        "Texto:\n" + chat_context
    )
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4.1",
            temperature=0,
            messages=[
                {"role": "system", "content": "Eres un extractor preciso de reconocimientos personales en el deporte."},
                {"role": "user", "content": instruction}
            ]
        )
        raw_output = response.choices[0].message.content.strip()
        print("🔎 Reconocimientos retornados por modelo:", raw_output)
        return int(raw_output)
    except Exception as e:
        print("❌ Error extrayendo torneos:", e)
        return 0

def filter_all_lines(text: str) -> str:
    return "\n".join([line.strip() for line in text.splitlines() if line.strip()])

def contar_puntaje_reconocimientos(n: int) -> int:
    return min(n * 1, 20)  # 1 punto por reconocimiento, máximo 20

### --------------- Performance --------------- ###
# Función que pide a GPT contar primeros, segundos y terceros lugares, devuelve dict
def contar_lugares_por_seccion(texto: str, seccion: str, client: OpenAI) -> dict:
    prompt = (
        f"Analiza el texto de la sección {seccion}.\n"
        "Cuenta cuántas veces se obtuvieron los siguientes lugares en torneos:\n"
        "- Primer lugar (ejemplos: '1er lugar', 'campeón', 'ganador')\n"
        "- Segundo lugar (ejemplos: '2do lugar', 'subcampeón', 'finalista')\n"
        "- Tercer lugar (ejemplos: '3er lugar', 'tercer puesto', 'bronce')\n"
        "- NO cuentes menciones de participación sin lugar ni repitas torneos.\n\n"
        "Responde solo con un JSON en este formato:\n"
        "{\"primeros\": 0, \"segundos\": 0, \"terceros\": 0}\n\n"
        "Texto:\n" + texto
    )
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4.1-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": "Eres un analizador preciso de resultados deportivos."},
                {"role": "user", "content": prompt}
            ]
        )
        raw = response.choices[0].message.content.strip()
        print(f"📘 JSON en sección {seccion}:", raw)
        return json.loads(raw)
    except Exception as e:
        print(f"❌ Error en sección {seccion}:", e)
        return {"primeros": 0, "segundos": 0, "terceros": 0}

def calcular_puntaje(contadores: dict) -> int:
    return contadores["primeros"] * 3 + contadores["segundos"] * 2 + contadores["terceros"] * 1

def clean_lines(text: str) -> str:
    lines = text.splitlines()
    return "\n".join([line.strip() for line in lines if line.strip()])

def procesar_lugares(txt: str, model: OpenAI) -> int:
    seccion5 = clean_lines(extract_section(txt, OCRInputFormats.SEC_5_START.value, OCRInputFormats.SEC_6_START.value))
    seccion6 = clean_lines(extract_section(txt, OCRInputFormats.SEC_6_START.value, OCRInputFormats.SECTION_7_START.value))
    seccion7 = clean_lines(extract_section(txt, OCRInputFormats.SECTION_7_START.value, OCRInputFormats.END_SECTION.value))

    contadores_totales = {"primeros": 0, "segundos": 0, "terceros": 0}
    for nombre, texto in [("5", seccion5), ("6", seccion6), ("7", seccion7)]:
        if texto:
            conteo = contar_lugares_por_seccion(texto, nombre, model)
            for key in contadores_totales:
                contadores_totales[key] += conteo.get(key, 0)

    return calcular_puntaje(contadores_totales)

### --------------- MAIN LOOP --------------- ###
def main_loop(base_path, output_csv_path):
    df = tabular_folder(base_path)
    model = _set_openai_client()

    for i in range(5):
        print(repr(df['cv_text'][i]))
        print()

    df["sport_selection"] = df["cv_text"].apply(rank_sports_from_selection)

    # 1) Selección deportiva escolar
    df['count_school'] = df['cv_text'].progress_apply(
        lambda txt: count_unique_year_lines_per_section(
            txt,
            point_mult=1,
            max_count=4,
            start_pattern=r'4\.\s*PARTICIPACIÓN\s*EN\s*SELECCIÓN\s*DEPORTIVA\s*ESCOLAR',
            end_pattern=r'5\.\s*PARTICIPACIÓN\s*EN\s*ACTIVIDADES\s*DEPORTIVAS'
        )
    )

    # 2) Club deportivo
    df['count_club'] = df['cv_text'].progress_apply(
        lambda txt: count_unique_year_lines_per_section(
            txt,
            point_mult=2,
            max_count=4,
            start_pattern=r'3\.\s*PARTICIPACIÓN\s*EN\s*CLUB',
            end_pattern=r'4\.\s*PARTICIPACIÓN\s*EN\s*SELECCIÓN\s*DEPORTIVA\s*ESCOLAR'
        )
    )

    # 3) Selección nacional
    df['count_national'] = df['cv_text'].progress_apply(
        lambda txt: count_unique_year_lines_per_section(
            txt,
            point_mult=3,
            max_count=4,
            start_pattern=r'2\.\s*PARTICIPACIÓN\s*EN\s*SELECCIÓN\s*NACIONAL',
            end_pattern=r'3\.\s*PARTICIPACIÓN\s*EN\s*CLUB'
        )
    )

    # 4) Torneos locales
    df['local_tournaments'] = df['cv_text'].progress_apply(
        lambda txt: count_local_tournaments(
            txt,
            start_pattern = r'(?m)^\s*5\.',
            end_pattern=r'6\.\s*PARTICIPACIÓN'
        )
    )

    # 5) Torneos internacionales
    df['international_tournaments'] = df['cv_text'].progress_apply(
        lambda txt: count_international_tournaments(
            txt,
            start_pattern=r'6\.\s*PARTICIPACIÓN',
            end_pattern=r'7\.\s*LOGROS|TODAS LAS ACTIVIDADES'
        )
    )

    # 6) Otros Torneos
    df["other_tournaments"] = df["cv_text"].progress_apply(
        lambda txt: contar_puntaje_other_from_count(
            extract_tournament_points(
                filter_interest_lines(
                    extract_section_7(txt)
                ),
                client=model
            )
        )
    )

    # Premios y menciones obtenidos
    df["recognitions"] = df["cv_text"].progress_apply(
        lambda txt: contar_puntaje_reconocimientos(
            extract_recognition_count(
                filter_all_lines(
                    extract_section_7(txt)
                ),
                client=model
            )
        )
    )

    df["awards_points"] = df["cv_text"].progress_apply(
        lambda txt: procesar_lugares(
            txt=txt,
            model=model
        )
    )

    # Rellenar posibles NaN con 0
    df[OCRInputFormats.PUNTAJE_COLS.value] = df[OCRInputFormats.PUNTAJE_COLS.value].fillna(0)

    # Calcular puntaje total
    df["total_score"] = df[OCRInputFormats.PUNTAJE_COLS.value].sum(axis=1)

    # Ordenar por total_score descendente
    df_sorted = df.sort_values(by=["total_score", "nem"], ascending=False)

    # Eliminar columnas innecesarias antes de exportar
    df_sorted = df_sorted.drop(columns=["cv_text", "error"], errors="ignore")
    print(df_sorted)

    # Exportar a un archivo CSV
    exportar_resultados_csv(df_sorted, output_csv_path)


def procesar_pdfs_en_carpeta(temp_dir, output_csv_path):
    try:
        # Ejecuta tu procesamiento completo
        main_loop(temp_dir, output_csv_path)
        df = pd.read_csv(output_csv_path)

        # Logs de resumen por fila
        logs = []
        for _, row in df.iterrows():
            log_entry = f"✅ RUT: {row['rut']} - POST: {row['post_id']} - NEM: {row['nem']} - PUNTAJE: {row['total_score']}"
            logs.append(log_entry)

        return df, logs
    except Exception as e:
        return pd.DataFrame(), [f"❌ Error general en procesamiento: {e}"]