import os
import pytesseract
from pdf2image import convert_from_path

# =================================================
# CONFIGURACIÓN DE RUTAS
# =================================================
# Asegúrate de que esta ruta sea la correcta en tu PC
ruta_tesseract = r'C:\Tesseract-OCR\tesseract.exe' 

# Ruta de Poppler (la carpeta 'bin')
ruta_poppler = os.path.join("bin")

# Archivos
ruta_pdf = "books/studentbook.pdf"
archivo_salida = "src/libro_texto.txt"
# =================================================

pytesseract.pytesseract.tesseract_cmd = ruta_tesseract

def ejecutar_ocr_colombo():
    print("--- INICIANDO LECTURA DE LIBRO COLOMBO AI ---")
    
    if not os.path.exists(ruta_tesseract):
        print(f"ERROR: No se encuentra Tesseract en: {ruta_tesseract}")
        return
    if not os.path.exists(ruta_pdf):
        print(f"ERROR: No se encuentra el PDF en: {ruta_pdf}")
        return

    try:
        print(f"Abriendo {ruta_pdf}...")
        # Procesamos solo las primeras 5 páginas para una prueba rápida
        paginas = convert_from_path(
            ruta_pdf, 
            poppler_path=ruta_poppler, 
            first_page=1, 
            last_page=99
        )
        
        texto_completo = ""
        for i, pagina in enumerate(paginas):
            num_pag = i + 1
            print(f"Leyendo página {num_pag}...")
            texto = pytesseract.image_to_string(pagina, lang='eng')
            texto_completo += f"\n--- CONTENIDO PÁGINA {num_pag} ---\n{texto}\n"

        with open(archivo_salida, "w", encoding="utf-8") as f:
            f.write(texto_completo)
            
        print("\n" + "="*40)
        print("¡OPERACIÓN EXITOSA!")
        print(f"Texto guardado en: {archivo_salida}")
        print("="*40)

    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    ejecutar_ocr_colombo()