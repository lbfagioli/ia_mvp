How to Run app:
´python3 -m venv .venv´
´source .venv/bin/activate´
´pip install -r requirements.txt´
´pip install --upgrade unstructured[ocr,pdf]´
´python3 manage.py runserver´

4 css in production:
´python3 manage.py collectstatic´
´´