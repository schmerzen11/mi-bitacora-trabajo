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
from docx import Document # Asegúrate de tener python-docx en requirements.txt

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Bitácora de Trabajo", layout="centered")

ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

# --- 2. FUNCIONES DE GOOGLE ---
def obtener_credenciales():
    if "gcp_service_account" in st.secrets:
        info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_info(info_dict, scopes=scopes)
    return None

def guardar_evidencia(imagen_bytes, nombre_archivo):
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': nombre_archivo, 'parents': [ID_CARPETA_DRIVE]}
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg')
        
        # Solución al error 403 de cuota del robot
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True 
        ).execute()
        return f"https://drive.google.com/file/d/{file.get('id')}/view"
    except Exception as e:
        st.error(f"Error Drive: {e}")
        return None

# --- 3. INTERFAZ: REGISTRO ---
st.title("📝 Bitácora de Trabajo")

tab1, tab2 = st.tabs(["✍️ Registrar Actividad", "📊 Reportes y Consultas"])

with tab1:
    with st.form("registro", clear_on_submit=True):
        desc = st.text_area("Descripción:")
        foto = st.camera_input("Foto")
        if st.form_submit_button("Guardar"):
            if desc:
                ahora = datetime.now()
                link = "Sin foto"
                if foto:
                    img = Image.open(foto)
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG')
                    buf.seek(0)
                    link = guardar_evidencia(buf, f"img_{ahora.strftime('%Y%m%d_%H%M%S')}.jpg")
                
                # Guardar en Sheets
                creds = obtener_credenciales()
                client = gspread.authorize(creds)
                sheet = client.open(NOMBRE_EXCEL).sheet1
                sheet.append_row([ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), desc, link])
                st.success("Registrado correctamente")

# --- 4. INTERFAZ: CALENDARIO Y REPORTES ---
with tab2:
    st.subheader("Filtrar por Fecha")
    fecha_sel = st.date_input("Selecciona un día", datetime.now())
    
    if st.button("Consultar"):
        creds = obtener_credenciales()
        client = gspread.authorize(creds)
        data = client.open(NOMBRE_EXCEL).sheet1.get_all_records()
        df = pd.DataFrame(data)
        
        # Filtrar
        fecha_str = fecha_sel.strftime("%d/%m/%Y")
        resultado = df[df['Fecha'] == fecha_str]
        
        if not resultado.empty:
            st.write(f"Actividades del {fecha_str}:")
            st.dataframe(resultado)
            
            # Generar Word
            doc = Document()
            doc.add_heading(f'Reporte de Actividades - {fecha_str}', 0)
            for _, fila in resultado.iterrows():
                doc.add_paragraph(f"Hora: {fila['Hora']}\nActividad: {fila['Descripción']}\nLink: {fila['Link']}")
            
            target = io.BytesIO()
            doc.save(target)
            st.download_button("Descargar Reporte Word", target.getbuffer(), f"reporte_{fecha_str}.docx")
        else:
            st.info("No hay registros para este día.")
