import re
from glob import glob
import os
import pdfplumber
from unstructured.partition.pdf import partition_pdf
import pandas as pd
import re
from typing import Union, Pattern

import nltk
nltk.download('averaged_perceptron_tagger')

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

FILENAME_PATTERN = re.compile(
    r'(?P<rut>[\d\.]+(?:-[\dKk])?)_Post-(?P<id>[^_]+)_(?P<tipo>CV|NotasMedia)\.pdf',
    re.IGNORECASE
)

def list_pdf_files(input_folder):
    """Devuelve la lista de rutas *.pdf en la carpeta."""
    files = glob(os.path.join(input_folder, '*.pdf'))
    print(f"[list_pdf_files] Encontrados {len(files)} PDFs")
    return files

def group_by_rut_and_id(pdf_paths):
    """
    Agrupa rutas en un dict:
    { (rut, post_id): {'cv': path, 'notasmedia': path} }
    """
    grupos = {}
    for path in pdf_paths:
        fname = os.path.basename(path)
        m = FILENAME_PATTERN.match(fname)
        if not m:
            print(f"[group] Ignorando archivo con nombre inválido: {fname}")
            continue
        rut    = m.group('rut').replace('.', '')
        post_id = m.group('id')
        tipo   = m.group('tipo').lower()
        key = (rut, post_id)
        grupos.setdefault(key, {})[tipo] = path
    return grupos

def extract_text_pages(pdf_path, first_page_only=False):
    """Partition + agrupa por página, devuelve lista de textos por página."""
    elems = partition_pdf(pdf_path)
    pages = {}
    for el in elems:
        if first_page_only and el.metadata.page_number != 1:
            continue
        pages.setdefault(el.metadata.page_number, "")
        pages[el.metadata.page_number] += el.text + " "
    sorted_pages = [pages[p] for p in sorted(pages)]
    return sorted_pages

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

def count_section_entries(
    text: str,
    point_mult: int,
    start_pattern: Union[str, Pattern],
    end_pattern: Union[str, Pattern],
    max_count: int = 4,
    year_pattern: Pattern = YearPat
) -> int:
    """
    Usa subfunciones para contar líneas con años en una sección del texto,
    luego aplica multiplicador y máximo permitido.
    """
    start_pat = compile_pattern(start_pattern, flags=re.IGNORECASE | re.DOTALL)
    end_pat = compile_pattern(end_pattern, flags=re.IGNORECASE)
    section = extract_section(text, start_pat, end_pat)
    count = count_year_lines(section, year_pattern)
    return min(count, max_count) * point_mult


def exportar_resultados_csv(df: pd.DataFrame, output_csv: str):
    df.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"\n📄 CSV exportado a: {output_csv}")

def main_loop(base_path, output_csv_path):
    df = tabular_folder(base_path)

    for i in range(5):
        print(repr(df['cv_text'][i]))
        print()

    df["sport_selection"] = df["cv_text"].apply(rank_sports_from_selection)

    # 1) Selección deportiva escolar (sección 4…ESCOLAR…AÑO hasta '\n5.')
    df['count_school'] = df['cv_text'].apply(
        lambda txt: count_section_entries(
            txt,
            1,
            r'4\.\s*PARTICIPACIÓN\s*EN\s*SELECCIÓN\s*DEPORTIVA\s*ESCOLAR.*?AÑO',
            r'\*Si el estudiante.*?dejar en blanco\.|\n5\.'
        )
    )

    # 2) Club deportivo (sección 3…CLUBDEPORTIVO…AÑO hasta '\n4.' o similar)
    df['count_club'] = df['cv_text'].apply(
        lambda txt: count_section_entries(
            txt,
            2, #2
            r'3\.\s*PARTICIPACIÓN\s*EN\s*CLUB\s*DEPORTIVO.*?AÑO',
            r'\*Si el estudiante.*?dejar en blanco\.|\n4\.'
        )
    )

    # 3) Nacional (sección 2…NACIONAL…AÑO hasta '*Si el estudiante…' o '\n3.')
    df['count_national'] = df['cv_text'].apply(
        lambda txt: count_section_entries(
            txt,
            3, #3
            r'2\.\s*PARTICIPACIÓN\s*EN\s*SELECCIÓN\s*NACIONAL.*?AÑO',
            r'\*Si el estudiante.*?dejar en blanco\.|\n3\.'
        )
    )

    # 4) Torneos Locales (Escolares + Nacionales) — sección 5 hasta sección 6
    df['local_tournaments'] = df['cv_text'].apply(
        lambda txt: count_section_entries(
            text=txt,
            point_mult=1,  # solo contamos
            start_pattern=r'5\.\s*PARTICIPACIÓN\s*EN\s*ACTIVIDADES\s*DEPORTIVAS.*?AÑO',
            end_pattern=r'\*Si el estudiante.*?agregar otra fila\.|\n6\.',
            max_count=90,
            # el year_pattern ya por defecto es YearPat
        )
    )

    # 5) Torneos Internacionales (Mundiales / Panamericanos / Sudamericanos) — sección 6 hasta sección 7
    df['international_tournaments'] = df['cv_text'].apply(
        lambda txt: count_section_entries(
            text=txt,
            point_mult=1,
            start_pattern=(
                r'6\.\s*PARTICIPACIÓN\s*EN[:\s]*'
                r'MUNDIALES.*?JUEGOS\s*OLÍMPICOS.*?TORNEOS\s*PANAMERICANOS'
                r'.*?SUDAMERICANOS.*?AÑO'
            ),
            end_pattern=r'\*Si el estudiante.*?dejar en blanco\.|\n7\.',
            max_count=90,
        )
    )

    # Unimos al DataFrame original
    df["cantidad_de_torneos"] = df[["local_tournaments", "international_tournaments"]].sum(axis=1)

    df_sorted = df.sort_values(
        by=[
            "sport_selection",
            "count_school",
            "count_club",
            "count_national",
            "international_tournaments",
            "local_tournaments",
            "nem"
        ],
    )

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
            log_entry = f"✅ RUT: {row['rut']} - POST: {row['post_id']} - NEM: {row['nem']}"
            logs.append(log_entry)

        return df, logs
    except Exception as e:
        return pd.DataFrame(), [f"❌ Error general en procesamiento: {e}"]