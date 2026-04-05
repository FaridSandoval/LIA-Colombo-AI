import os
import pytesseract
from pdf2image import convert_from_path

# =================================================================
# CONFIGURACIÓN DE HERRAMIENTAS DE RECONOCIMIENTO (OCR)
# =================================================================

# Definición del ejecutable de Tesseract en el sistema
ruta_tesseract = r'C:\Tesseract-OCR\tesseract.exe'
pytesseract.pytesseract.tesseract_cmd = ruta_tesseract

# Gestión inteligente de rutas para evitar errores de "Archivo no encontrado"
base_path = os.path.dirname(os.path.abspath(__file__)) # Carpeta 'src'
ruta_proyecto = os.path.abspath(os.path.join(base_path, "..")) # Carpeta principal

# Ubicación de insumos y resultados
ruta_pdf = os.path.join(ruta_proyecto, "books", "studentbook.pdf")
archivo_salida = os.path.join(base_path, "libro_texto.txt")

# Ruta de binarios de Poppler (Necesario para la conversión de PDF a imagen)
# Se asume que la carpeta 'bin' está dentro de 'src'
ruta_poppler = os.path.join(base_path, "bin")

def ejecutar_digitalizacion_ocr():
    """
    Módulo de digitalización por OCR:
    Transforma las páginas del PDF (imágenes) en texto editable. 
    Este proceso permite que el material didáctico del Colombo Americano 
    sea procesable por algoritmos de Inteligencia Artificial.
    """
    print("--- INICIANDO PROCESO DE DIGITALIZACIÓN (OCR) ---")
    
    # Verificación de pre-requisitos técnicos
    if not os.path.exists(ruta_tesseract):
        print(f"Error Crítico: El motor Tesseract no se encuentra en {ruta_tesseract}")
        return
    if not os.path.exists(ruta_pdf):
        print(f"Error Crítico: No se localizó el libro en {ruta_pdf}")
        return

    try:
        print(f"Documento detectado. Iniciando conversión de páginas...")
        
        # Procesamiento de páginas (Rango configurado: 1 a 99)
        # Nota: Este proceso consume recursos de CPU ya que 'lee' visualmente el libro.
        paginas = convert_from_path(
            ruta_pdf, 
            poppler_path=ruta_poppler, 
            first_page=1, 
            last_page=99
        )
        
        texto_completo = ""
        for i, pagina in enumerate(paginas):
            num_pag = i + 1
            print(f"Procesando y extrayendo texto de página {num_pag}...")
            
            # Aplicación del algoritmo OCR en idioma inglés
            texto = pytesseract.image_to_string(pagina, lang='eng')
            texto_completo += f"\n--- CONTENIDO PÁGINA {num_pag} ---\n{texto}\n"

        # Almacenamiento del conocimiento extraído en formato de texto plano
        with open(archivo_salida, "w", encoding="utf-8") as f:
            f.write(texto_completo)
            
        print("\n" + "="*50)
        print("¡OPERACIÓN EXITOSA!")
        print(f"El libro ha sido digitalizado en: {archivo_salida}")
        print("="*50)

    except Exception as e:
        print(f"\nSe ha detectado un fallo en el procesamiento: {e}")

if __name__ == "__main__":
    ejecutar_digitalizacion_ocr()