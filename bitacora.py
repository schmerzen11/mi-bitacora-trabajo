import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import gspread
from datetime import datetime

# --- CONFIGURACIÓN ---
ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

def guardar_en_drive(imagen_bytes, nombre_archivo):
    """Sube la imagen a la carpeta específica de Google Drive."""
    try:
        creds = obtener_credenciales() # Usa tu función existente
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': nombre_archivo,
            'parents': [ID_CARPETA_DRIVE]
        }
        
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg')
        
        # supportsAllDrives=True es clave para evitar el error de cuota del robot
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True 
        ).execute()

        return f"https://drive.google.com/file/d/{file.get('id')}/view"
    
    except Exception as e:
        st.error(f"❌ Error al subir a Drive: {e}")
        return None

def guardar_en_sheets(fecha, hora, actividad, link_imagen):
    """Registra los datos y el link de la foto en el Google Sheet."""
    try:
        creds = obtener_credenciales() # Usa tu función existente
        client = gspread.authorize(creds)
        sheet = client.open(NOMBRE_EXCEL).sheet1

        # Preparamos la fila
        nueva_fila = [str(fecha), str(hora), actividad, link_imagen]
        
        # Insertamos al final
        sheet.append_row(nueva_fila)
        return True

    except Exception as e:
        st.error(f"❌ Error al guardar en Sheets: {e}")
        return False

# --- BLOQUE PRINCIPAL (Lo que va en el botón de Guardar) ---
# Sustituye la lógica de tu botón con esto:

if st.button("🚀 Guardar en Google Drive"):
    if actividad_input: # Asegúrate de que el usuario escribió algo
        with st.spinner("Subiendo evidencia y registrando datos..."):
            
            link_foto = "Sin evidencia"
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            hora_hoy = datetime.now().strftime("%H:%M:%S")

            # 1. Procesar Imagen (si existe)
            if foto_input: # Cambia por el nombre de tu variable de st.camera_input o file_uploader
                img_byte_arr = io.BytesIO()
                # ... (aquí va tu lógica de procesar la imagen con PIL) ...
                nombre_img = f"evidencia_{fecha_hoy}_{hora_hoy}.jpg"
                
                res_drive = guardar_en_drive(img_byte_arr, nombre_img)
                if res_drive:
                    link_foto = res_drive

            # 2. Guardar en Sheets
            exito = guardar_en_sheets(fecha_hoy, hora_hoy, actividad_input, link_foto)
            
            if exito:
                st.success("✅ ¡Todo guardado con éxito!")
            else:
                st.error("⚠️ La foto se subió, pero no se pudo registrar en el Excel.")
    else:
        st.warning("Escribe una actividad antes de guardar.")
