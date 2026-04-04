import fitz  # PyMuPDF
import os

# Ruta al libro (Para el tutor: Acceso directo a archivos mediante PyMuPDF)
ruta = "books/studentbook.pdf"

def revisar_libro():
    if not os.path.exists(ruta):
        print(f"Error: No encuentro el archivo en {ruta}")
        return

    print(f"Abriendo: {ruta}")
    # Se abre el documento para extraer texto plano
    doc = fitz.open(ruta)
    
    # Extraemos las primeras 3 paginas para probar
    texto_total = ""
    for i in range(min(3, len(doc))):
        texto_total += doc[i].get_text()

    if len(texto_total.strip()) < 10:
        print("ALERTA: El PDF esta vacio o es una imagen escaneada.")
    else:
        print("EXITO: Texto detectado correctamente.")
        print("-" * 30)
        print(texto_total[:500]) # Muestra los primeros 500 caracteres
        print("-" * 30)
    
    doc.close()

if __name__ == "__main__":
    revisar_libro()