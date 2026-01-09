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
st.set_page_config(page_title="Bitácora de Trabajo", layout="centered")

# ID de carpeta confirmado en tus capturas anteriores
ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

# --- 2. FUNCIONES DE CONEXIÓN ---
def obtener_credenciales():
    """Conecta con Google usando los secretos de Streamlit."""
    if "gcp_service_account" in st.secrets:
        info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets", 
            "https://www.googleapis.com/auth/drive"
        ]
        return Credentials.from_service_account_info(info_dict, scopes=scopes)
    return None

def guardar_evidencia(imagen_bytes, nombre_archivo):
    """Sube la foto a Drive con la solución para el error de cuota."""
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': nombre_archivo, 'parents': [ID_CARPETA_DRIVE]}
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg')
        
        # supportsAllDrives=True evita el error 403 de storage quota del robot
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

# --- 3. INTERFAZ DE USUARIO ---
st.title("📝 Bitácora de Trabajo")

tab1, tab2 = st.tabs(["✍️ Registro de Actividad", "📊 Consultas y Reportes"])

# --- TAB 1: REGISTRO ---
with tab1:
    with st.form("form_registro", clear_on_submit=True):
        desc = st.text_area("Descripción de la actividad:", placeholder="Escribe aquí los detalles...")
        
        # CAMBIO SOLICITADO: file_uploader en lugar de camera_input
        # En móviles, esto permite elegir "Cámara" o "Archivos"
        archivo_foto = st.file_uploader("Adjuntar evidencia (Foto o Archivo)", type=['jpg', 'jpeg', 'png'])
        
        btn_guardar = st.form_submit_button("🚀 Guardar Reporte")

    if btn_guardar:
        if desc:
            with st.spinner("Procesando y subiendo..."):
                ahora = datetime.now()
                fecha_str = ahora.strftime("%d/%m/%Y")
                hora_str = ahora.strftime("%H:%M:%S")
                link_evidencia = "Sin foto"

                if archivo_foto:
                    # Procesar imagen con PIL
                    img = Image.open(archivo_foto)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG')
                    buf.seek(0)
                    
                    nombre_img = f"evidencia_{ahora.strftime('%Y%m%d_%H%M%S')}.jpg"
                    res_drive = guardar_evidencia(buf, nombre_img)
                    if res_drive:
                        link_evidencia = res_drive

                # Guardar en Sheets
                try:
                    creds = obtener_credenciales()
                    client = gspread.authorize(creds)
                    sheet = client.open(NOMBRE_EXCEL).sheet1
                    sheet.append_row([fecha_str, hora_str, desc, link_evidencia])
                    st.success(f"✅ Registro completado exitosamente.")
                except Exception as e:
                    st.error(f"Error al guardar en Excel: {e}")
        else:
            st.warning("⚠️ La descripción es obligatoria.")

# --- TAB 2: CONSULTAS Y CALENDARIO ---
with tab2:
    st.subheader("Filtrar historial")
    fecha_filtro = st.date_input("Selecciona la fecha a consultar:", datetime.now())
    
    if st.button("🔍 Consultar Día"):
        try:
            creds = obtener_credenciales()
            client = gspread.authorize(creds)
            records = client.open(NOMBRE_EXCEL).sheet1.get_all_records()
            df = pd.DataFrame(records)
            
            # Formatear búsqueda
            f_buscada = fecha_filtro.strftime("%d/%m/%Y")
            df_filtrado = df[df['Fecha'] == f_buscada]

            if not df_filtrado.empty:
                st.dataframe(df_filtrado, use_container_width=True)
                
                # GENERACIÓN DE REPORTE WORD
                doc = Document()
                doc.add_heading(f'Reporte de Trabajo - {f_buscada}', 0)
                
                for _, fila in df_filtrado.iterrows():
                    doc.add_paragraph(f"📌 Hora: {fila['Hora']}")
                    doc.add_paragraph(f"📝 Actividad: {fila['Descripción']}")
                    doc.add_paragraph(f"🔗 Evidencia: {fila['Link']}")
                    doc.add_rule()

                buffer_word = io.BytesIO()
                doc.save(buffer_word)
                buffer_word.seek(0)
                
                st.download_button(
                    label="📄 Descargar Reporte en Word",
                    data=buffer_word,
                    file_name=f"Reporte_{f_buscada.replace('/','-')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                st.info(f"No se encontraron registros para el día {f_buscada}.")
        except Exception as e:
            st.error(f"Error al consultar datos: {e}")
