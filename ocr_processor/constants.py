import re
from enum import Enum

class OCRInputFormats(Enum):
    SECTION_7_START = re.compile(r'7\.\s*LOGROS/PREMIOS DEPORTIVOS.*', re.IGNORECASE)
    SECTION_7_END   = re.compile(r'TODAS LAS ACTIVIDADES QUE EL ESTUDIANTE SEÑALE', re.IGNORECASE)
    YEAR_RE         = re.compile(r'\b(?:19|20)\d{2}\b')
    PLACE_RE        = re.compile(r'\d+(?:er|ro|do|avo)\b', flags=re.IGNORECASE)
    FILENAME_PATTERN = re.compile(
        r'(?P<rut>[\d\.]+(?:-[\dKk])?)_Post-(?P<id>[^_]+)_(?P<tipo>CV|NotasMedia)\.pdf',
        re.IGNORECASE
    )
    RUN_RE          = re.compile(r'RUN\s*([\d\.]+-[\dKk])')
    CERT_PATTERN    = re.compile(r'A[NÑ]O ESCOLAR\s*20[0-9]{2}.*?([1-7]\.[0-9])', flags=re.DOTALL | re.IGNORECASE)
    RUT_LABEL       = re.compile(r'CERTIFICADO DE CONCENTRACION DE NOTAS', flags=re.IGNORECASE)
