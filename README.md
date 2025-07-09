## Requisitos Previos

1. **Responsable de Instalación**  
   - Se recomienda que un técnico o profesional de software realice la instalación y configuración.

2. **Servidor Web**  
   - Entorno: Ubuntu‑Linux (o distribución compatible).  
   - Acceso de administrador (sudo/root) y conexión SSH.

3. **Herramientas Necesarias**  
   - Python 3.8 o superior  
   - Git (opcional, para clonar el repositorio)  
   - Terminal / Cliente SSH  

---

## Preparación del Entorno

1. **Clonar el Proyecto**  
   ```bash
   git clone https://github.com/lbfagioli/ia_mvp
   cd ia_mvp
   ```

2. **Crear Archivo de Variables de Entorno**
- En la raíz del proyecto, crea un fichero llamado .env con el siguiente contenido:
   ```env
  OPENAI_API_KEY="<Tu API Key de OpenAI>"
  OPENAI_ENDPOINT="<Tu endpoint de OpenAI>"
  GOOGLE_API_KEY="<Tu API Key de Google Cloud>"
   ```
3. **Crear y Activar Entorno Virtual**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. **Instalar Dependencias**
   ```bash
   pip install -r requirements.txt
   pip install --upgrade "unstructured[ocr,pdf]"
   sudo apt-get install tesseract-ocr-spa
   ```
5. **Correr Servidor**
- Se recomienda preparar un servidor de Ngrok para hostear y conectar remotamente desde otros equipos
   ```bash
   python3 manage.py runserver
   python3 manage.py collectstatic
   ```
