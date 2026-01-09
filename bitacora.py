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

# ID de carpeta y Excel confirmados
ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

# --- 2. FUNCIONES DE CONEXIÓN ---
def obtener_credenciales():
    if "gcp_service_account" in st.secrets:
        info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_info(info_dict, scopes=scopes)
    return None

def guardar_evidencia(imagen_bytes, nombre_archivo):
    """Sube la foto forzando el uso de la cuota del dueño de la carpeta."""
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        
        # Metadata esencial
        file_metadata = {
            'name': nombre_archivo,
            'parents': [ID_CARPETA_DRIVE]
        }
        
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg', resumable=True)
        
        # ACCIÓN CLAVE: supportsAllDrives permite que el robot use tu espacio compartido
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True 
        ).execute()
        
        return f"https://drive.google.com/file/d/{file.get('id')}/view"
    except Exception as e:
        st.error(f"Error detallado en Drive: {e}")
        return None

# --- 3. INTERFAZ DE USUARIO ---
st.title("🗒️ Bitácora de Trabajo")

tab1, tab2 = st.tabs(["✍️ Registrar Actividad", "📂 Historial y Reportes"])

# --- PESTAÑA 1: REGISTRO ---
with tab1:
    with st.form("registro_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            descripcion = st.text_area("Descripción de la tarea:")
        with col2:
            # Volvemos al file_uploader para evitar que la cámara se abra sola
            archivo = st.file_uploader("Evidencia (Foto o archivo)", type=['jpg', 'png', 'jpeg'])
        
        enviar = st.form_submit_button("🚀 Guardar Actividad")

    if enviar:
        if descripcion:
            with st.spinner("Guardando en la nube..."):
                ahora = datetime.now()
                link_drive = "Sin evidencia"
                
                if archivo:
                    img = Image.open(archivo)
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG')
                    buf.seek(0)
                    
                    nombre_img = f"evid_{ahora.strftime('%Y%m%d_%H%M%S')}.jpg"
                    res = guardar_evidencia(buf, nombre_img)
                    if res: link_drive = res

                # Guardar en Sheets
                try:
                    creds = obtener_credenciales()
                    client = gspread.authorize(creds)
                    sheet = client.open(NOMBRE_EXCEL).sheet1
                    sheet.append_row([ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), descripcion, link_drive])
                    st.success("✅ ¡Registro guardado exitosamente!")
                except Exception as e:
                    st.error(f"Error en Sheets: {e}")
        else:
            st.warning("Escribe una descripción.")

# --- PESTAÑA 2: CALENDARIO Y REPORTES ---
with tab2:
    st.subheader("Consultar por Fecha")
    fecha_filtro = st.date_input("Selecciona el día:", datetime.now())
    
    if st.button("🔍 Ver registros"):
        try:
            creds = obtener_credenciales()
            client = gspread.authorize(creds)
            data = client.open(NOMBRE_EXCEL).sheet1.get_all_records()
            df = pd.DataFrame(data)
            
            f_str = fecha_filtro.strftime("%d/%m/%Y")
            filtro = df[df['Fecha'] == f_str]
            
            if not filtro.empty:
                st.dataframe(filtro, use_container_width=True)
                
                # Crear Word
                doc = Document()
                doc.add_heading(f'Bitácora de Trabajo - {f_str}', 0)
                for _, fila in filtro.iterrows():
                    doc.add_paragraph(f"⏰ Hora: {fila['Hora']}\n📝 Tarea: {fila['Descripción']}\n🔗 Link: {fila['Link']}\n" + "-"*30)
                
                buf_word = io.BytesIO()
                doc.save(buf_word)
                buf_word.seek(0)
                
                st.download_button("📥 Descargar Reporte Word", buf_word, f"reporte_{f_str}.docx")
            else:
                st.info("No hay datos para esta fecha.")
        except Exception as e:
            st.error(f"Error al cargar historial: {e}")
