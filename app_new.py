"""
Legacy entry point — la app principal ahora vive en `app.py`.
Ejecutar: `streamlit run app.py`
"""
from runpy import run_path

run_path("app.py", run_name="__main__")
