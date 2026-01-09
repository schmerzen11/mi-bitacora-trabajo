import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
import gspread
import io
import json
import pandas as pd
from datetime import datetime
from PIL import Image
from docx import Document

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Bitácora de Trabajo", layout="wide")

# ID de carpeta y Excel confirmados en tus imágenes
ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

def obtener_credenciales():
    if "gcp_service_account" in st.secrets:
        info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_info(info_dict, scopes=scopes)
    return None

def guardar_evidencia(imagen_bytes, nombre_archivo):
    """Intenta subir la foto. Si falla por cuota, devuelve un mensaje de error en lugar de romper la app."""
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': nombre_archivo, 'parents': [ID_CARPETA_DRIVE]}
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg')
        
        # Intentamos la subida con soporte para drives compartidos
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True 
        ).execute()
        return f"https://drive.google.com/file/d/{file.get('id')}/view"
    except Exception as e:
        # Aquí rompemos el bucle: si falla la cuota, avisamos pero NO detenemos el proceso
        st.warning(f"⚠️ La foto no se subió (Límite de Google: {e}). Se guardará solo el texto.")
        return "Foto no disponible (Error de Cuota)"

# --- 2. INTERFAZ ---
st.title("🗒️ Bitácora de Trabajo")
tab1, tab2 = st.tabs(["✍️ Registro", "📊 Historial y Reportes"])

with tab1:
    with st.form("registro_form", clear_on_submit=True):
        descripcion = st.text_area("Descripción de la actividad:")
        # File uploader evita que la cámara se abra sola
        archivo = st.file_uploader("Adjuntar foto (opcional)", type=['jpg', 'jpeg', 'png'])
        enviar = st.form_submit_button("🚀 Guardar Actividad")

    if enviar:
        if descripcion:
            with st.spinner("Guardando registro..."):
                ahora = datetime.now()
                f_s, h_s = ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")
                link_drive = "Sin evidencia"
                
                if archivo:
                    img = Image.open(archivo).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG')
                    buf.seek(0)
                    link_drive = guardar_evidencia(buf, f"evid_{ahora.strftime('%Y%m%d_%H%M%S')}.jpg")

                # Guardar en Sheets (Esto siempre debería funcionar si compartiste el Excel)
                try:
                    creds = obtener_credenciales()
                    client = gspread.authorize(creds)
                    sheet = client.open(NOMBRE_EXCEL).sheet1
                    sheet.append_row([f_s, h_s, descripcion, link_drive])
                    st.success("✅ Registro completado.")
                except Exception as e:
                    st.error(f"Error en Sheets: {e}")

with tab2:
    st.subheader("Consultar por Calendario")
    fecha_sel = st.date_input("Selecciona el día:", datetime.now())
    
    if st.button("🔍 Ver Datos"):
        try:
            creds = obtener_credenciales()
            client = gspread.authorize(creds)
            df = pd.DataFrame(client.open(NOMBRE_EXCEL).sheet1.get_all_records())
            
            f_buscada = fecha_sel.strftime("%d/%m/%Y")
            filtro = df[df['Fecha'] == f_buscada]
            
            if not filtro.empty:
                st.dataframe(filtro, use_container_width=True)
                
                # Generar Word
                doc = Document()
                doc.add_heading(f'Reporte - {f_buscada}', 0)
                for _, fila in filtro.iterrows():
                    doc.add_paragraph(f"Hora: {fila['Hora']}\nActividad: {fila['Descripción']}\nLink: {fila['Link']}\n" + "-"*20)
                
                buf_word = io.BytesIO()
                doc.save(buf_word)
                buf_word.seek(0)
                st.download_button("📥 Descargar Word", buf_word, f"reporte_{f_buscada}.docx")
            else:
                st.info("No hay registros para este día.")
        except Exception as e:
            st.error(f"Error al cargar historial: {e}")
