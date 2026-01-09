import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
import gspread
import io
import json
from datetime import datetime
from PIL import Image

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="Bitácora de Trabajo", page_icon="📝", layout="centered")

# ID de la carpeta que confirmamos en tus imágenes
ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

# --- 2. FUNCIONES DE CONEXIÓN ---
def obtener_credenciales():
    """Conecta con Google usando tus secretos de Streamlit Cloud."""
    if "gcp_service_account" in st.secrets:
        info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        return Credentials.from_service_account_info(info_dict, scopes=scopes)
    return None

def guardar_evidencia(imagen_bytes, nombre_archivo):
    """Sube la foto a Drive usando la cuota del dueño de la carpeta."""
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {'name': nombre_archivo, 'parents': [ID_CARPETA_DRIVE]}
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg')
        
        # supportsAllDrives=True es vital para evitar el error de storage quota
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True 
        ).execute()
        
        return f"https://drive.google.com/file/d/{file.get('id')}/view"
    except Exception as e:
        st.error(f"Error subiendo imagen: {e}")
        return None

def registrar_en_sheets(datos):
    """Añade una fila con la actividad al Google Sheet."""
    try:
        creds = obtener_credenciales()
        client = gspread.authorize(creds)
        sheet = client.open(NOMBRE_EXCEL).sheet1
        sheet.append_row(datos)
        return True
    except Exception as e:
        st.error(f"Error en Sheets: {e}")
        return False

# --- 3. INTERFAZ DE USUARIO (TU DISEÑO) ---
st.title("📝 Bitácora de Trabajo")

with st.form("formulario_bitacora", clear_on_submit=True):
    descripcion = st.text_area("Descripción de la actividad:", placeholder="¿Qué estuviste haciendo?")
    foto = st.camera_input("Capturar evidencia")
    
    boton_guardar = st.form_submit_button("🚀 Guardar en Google Drive")

if boton_guardar:
    if descripcion:
        with st.spinner("Guardando reporte..."):
            ahora = datetime.now()
            fecha = ahora.strftime("%d/%m/%Y")
            hora = ahora.strftime("%H:%M:%S")
            link_foto = "Sin foto"

            # Procesar foto si se capturó
            if foto:
                image = Image.open(foto)
                img_ram = io.BytesIO()
                image.save(img_ram, format='JPEG')
                img_ram.seek(0)
                
                nombre_img = f"evidencia_{ahora.strftime('%Y%m%d_%H%M%S')}.jpg"
                res_url = guardar_evidencia(img_ram, nombre_img)
                if res_url:
                    link_foto = res_url

            # Registrar todo en el Excel
            datos_fila = [fecha, hora, descripcion, link_foto]
            if registrar_en_sheets(datos_fila):
                st.success("✅ Actividad registrada correctamente.")
            else:
                st.error("❌ No se pudo actualizar el Excel.")
    else:
        st.warning("⚠️ Por favor escribe una descripción de la actividad.")
