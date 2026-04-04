import pandas as pd
import os

# 1. Ubicamos el archivo
base_path = os.path.dirname(os.path.abspath(__file__))
nombre_archivo = "personal_data.xlsx"
ruta_completa = os.path.join(base_path, nombre_archivo)

try:
    # 2. Leemos el archivo. 
    # Usamos header=None para decirle a LIA que NO use a Camila como título
    df_estudiantes = pd.read_excel(ruta_completa, skiprows=7, header=None, engine='openpyxl')

    print("\n--- 🤖 CEREBRO LIA: ANALIZANDO ESTUDIANTES PARA RETENCIÓN ---")
    
    # 3. Iteramos (repasamos) fila por fila
    estudiantes_en_riesgo = 0
    
    for index, fila in df_estudiantes.iterrows():
        nombre = fila[5]
        telefono = fila[9]
        feedback = fila[45]
        estado = fila[74]
        
        # Filtramos: Solo si hay un nombre escrito y el estado es "Fail"
        if pd.notna(nombre) and str(estado).strip() == "Fail":
            estudiantes_en_riesgo += 1
            print(f"👤 ALERTA ESTUDIANTE: {nombre}")
            print(f"📱 Enviar WhatsApp al: {telefono}")
            print(f"💡 Contexto para la IA (Feedback): {feedback}")
            print("-" * 40)
            
    print(f"\nResumen: LIA ha detectado {estudiantes_en_riesgo} estudiante(s) que necesitan tutoría proactiva hoy a las 8:00 PM.")

except Exception as e:
    print(f"\n❌ Error técnico: {e}")