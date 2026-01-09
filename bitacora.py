import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
import gspread
import io
import json
from datetime import datetime
from PIL import Image

# --- CONFIGURACIÓN GLOBAL ---
ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

# --- CONEXIÓN CON GOOGLE ---
def obtener_credenciales():
    """Lee el secreto desde la configuración de Streamlit"""
    if "gcp_service_account" in st.secrets:
        try:
            info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
            scope = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            return Credentials.from_service_account_info(info_dict, scopes=scope)
        except Exception as e:
            st.error(f"Error leyendo secretos: {e}")
            return None
    return None

def guardar_en_drive(imagen_bytes, nombre_archivo):
    """Sube la imagen a la carpeta de Google Drive."""
    try:
        creds = obtener_credenciales()
        if not creds: return None
        
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': nombre_archivo, 'parents': [ID_CARPETA_DRIVE]}
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg')
        
        # supportsAllDrives=True soluciona el error de quota del robot
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True 
        ).execute()

        return f"https://drive.google.com/file/d/{file.get('id')}/view"
    except Exception as e:
        st.error(f"❌ Error Drive: {e}")
        return None

def guardar_en_sheets(fecha, hora, actividad, link_imagen):
    """Guarda una nueva fila en el Google Sheet."""
    try:
        creds = obtener_credenciales()
        if not creds: return False
        
        client = gspread.authorize(creds)
        sheet = client.open(NOMBRE_EXCEL).sheet1
        
        fila = [str(fecha), str(hora), actividad, link_imagen]
        sheet.append_row(fila)
        return True
    except Exception as e:
        st.error(f"❌ Error Sheets: {e}")
        return False

# --- INTERFAZ DE USUARIO ---
st.title("🗒️ Bitácora de Trabajo")

actividad = st.text_area("Descripción de la actividad:")
foto = st.camera_input("Capturar evidencia")

if st.button("🚀 Guardar en Google Drive"):
    if actividad:
        with st.spinner("Procesando..."):
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            hora_hoy = datetime.now().strftime("%H:%M:%S")
            link_foto = "Sin evidencia"

            if foto:
                # Procesar imagen
                image = Image.open(foto)
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")
                
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG')
                img_byte_arr.seek(0)
                
                nombre_img = f"evidencia_{fecha_hoy}_{hora_hoy}.jpg"
                res_drive = guardar_en_drive(img_byte_arr, nombre_img)
                if res_drive:
                    link_foto = res_drive

            # Guardar en Sheets
            if guardar_en_sheets(fecha_hoy, hora_hoy, actividad, link_foto):
                st.success("✅ ¡Actividad registrada con éxito!")
            else:
                st.error("Hubo un problema al registrar en el Excel.")
    else:
        st.warning("Por favor escribe una actividad.")
