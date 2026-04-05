import fitz  # Librería PyMuPDF: Especializada en la gestión y extracción de datos de archivos PDF
import os

# =================================================================
# CONFIGURACIÓN DE ACCESO AL MATERIAL DIDÁCTICO
# =================================================================

# Buscamos la carpeta 'books' de forma inteligente
# Esto permite que el script funcione si lo lanzas desde la carpeta principal o desde 'src'
base_path = os.path.dirname(os.path.abspath(__file__))
ruta_proyecto = os.path.abspath(os.path.join(base_path, ".."))
ruta_libro = os.path.join(ruta_proyecto, "books", "studentbook.pdf")

def ejecutar_diagnostico_de_lectura():
    """
    Función de control de calidad:
    Verifica si el archivo PDF contiene capas de texto digital.
    """
    
    # Validación de existencia: Comprueba que el archivo esté en la carpeta 'books'.
    if not os.path.exists(ruta_libro):
        print(f"Error: No se ha localizado el archivo en la ruta esperada: {ruta_libro}")
        print("Asegúrese de que el PDF se llame 'studentbook.pdf' y esté dentro de la carpeta 'books'.")
        return

    print(f"Iniciando análisis de integridad en: {ruta_libro}")
    
    try:
        # Apertura del documento
        doc = fitz.open(ruta_libro)
        
        # Analizamos las primeras 3 páginas
        texto_extraido = ""
        limite_paginas = min(3, len(doc))
        
        for i in range(limite_paginas):
            texto_extraido += doc[i].get_text()

        print("-" * 50)
        
        if len(texto_extraido.strip()) < 10:
            print("ALERTA TÉCNICA: El documento no contiene texto digital indexable.")
            print("El archivo parece ser una imagen escaneada. Se recomienda usar el script de OCR.")
        else:
            print("RESULTADO: EXITO. Texto digital detectado correctamente.")
            print("El material es apto para el entrenamiento del asistente LIA.")
            print("-" * 50)
            print("MUESTRA DE DATOS EXTRAÍDOS (Primeros 500 caracteres):")
            print(texto_extraido[:500])
            print("-" * 50)
        
        doc.close()

    except Exception as e:
        print(f"Se ha producido un error durante el proceso de lectura: {e}")

if __name__ == "__main__":
    print("PROYECTO LIA: MÓDULO DE DIAGNÓSTICO DE MATERIALES")
    ejecutar_diagnostico_de_lectura()