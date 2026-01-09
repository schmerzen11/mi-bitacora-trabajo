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

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Bitácora de Trabajo", page_icon="📝", layout="wide")

# Credenciales confirmadas en pasos anteriores
ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

# --- 2. FUNCIONES DE CONEXIÓN ---
def obtener_credenciales():
    """Conecta con Google usando los secretos de Streamlit Cloud."""
    if "gcp_service_account" in st.secrets:
        try:
            info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            return Credentials.from_service_account_info(info_dict, scopes=scopes)
        except Exception as e:
            st.error(f"Error en credenciales: {e}")
            return None
    return None

def guardar_evidencia_drive(imagen_bytes, nombre_archivo):
    """Sube la foto a Drive. Si falla por cuota, se registra solo el texto."""
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': nombre_archivo,
            'parents': [ID_CARPETA_DRIVE]
        }
        
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg', resumable=True)
        
        # supportsAllDrives ayuda, pero no garantiza saltar la cuota 0 de robots en Gmail personal
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True 
        ).execute()
        
        return f"https://drive.google.com/file/d/{file.get('id')}/view"
    except Exception as e:
        # Si falla por cuota, notificamos pero permitimos seguir con el registro de texto
        st.warning(f"⚠️ Nota: La foto no se subió por límites de Google (Cuota). Error: {e}")
        return "Error de Cuota - Ver logs"

# --- 3. INTERFAZ PRINCIPAL ---
st.title("🗒️ Bitácora de Trabajo")

tabs = st.tabs(["✍️ Registro Diario", "📂 Historial y Reportes"])

# --- TAB 1: REGISTRO ---
with tabs[0]:
    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            descripcion = st.text_area("Descripción de la actividad:", placeholder="¿Qué tareas realizaste hoy?")
        with col2:
            # Usamos file_uploader para que NO se abra la cámara automáticamente
            archivo = st.file_uploader("Adjuntar evidencia (Foto)", type=['jpg', 'jpeg', 'png'])
        
        btn_enviar = st.form_submit_button("🚀 Guardar Actividad")

    if btn_enviar:
        if descripcion:
            with st.spinner("Procesando registro..."):
                ahora = datetime.now()
                fecha_str = ahora.strftime("%d/%m/%Y")
                hora_str = ahora.strftime("%H:%M:%S")
                link_evidencia = "Sin evidencia"

                if archivo:
                    # Procesar imagen para asegurar compatibilidad
                    img = Image.open(archivo)
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG')
                    buf.seek(0)
                    
                    nombre_img = f"evidencia_{ahora.strftime('%Y%m%d_%H%M%S')}.jpg"
                    res_url = guardar_evidencia_drive(buf, nombre_img)
                    if res_url: link_evidencia = res_url

                # Guardar en Sheets
                try:
                    creds = obtener_credenciales()
                    client = gspread.authorize(creds)
                    sheet = client.open(NOMBRE_EXCEL).sheet1
                    sheet.append_row([fecha_str, hora_str, descripcion, link_evidencia])
                    st.success("✅ ¡Registro guardado exitosamente!")
                except Exception as e:
                    st.error(f"❌ Error al conectar con Sheets: {e}")
        else:
            st.warning("⚠️ Debes escribir una descripción.")

# --- TAB 2: CALENDARIO Y REPORTES ---
with tabs[1]:
    st.subheader("Filtrar Historial")
    fecha_consulta = st.date_input("Selecciona el día a consultar:", datetime.now())
    
    if st.button("🔍 Consultar Fecha"):
        try:
            creds = obtener_credenciales()
            client = gspread.authorize(creds)
            records = client.open(NOMBRE_EXCEL).sheet1.get_all_records()
            df = pd.DataFrame(records)
            
            # Filtro por calendario
            f_buscada = fecha_consulta.strftime("%d/%m/%Y")
            resultado = df[df['Fecha'] == f_buscada]

            if not resultado.empty:
                st.dataframe(resultado, use_container_width=True)
                
                # --- GENERACIÓN DE REPORTE WORD ---
                doc = Document()
                doc.add_heading(f'Reporte de Trabajo - {f_buscada}', 0)
                
                for _, fila in resultado.iterrows():
                    doc.add_paragraph(f"🕒 Hora: {fila['Hora']}")
                    doc.add_paragraph(f"📝 Actividad: {fila['Descripción']}")
                    doc.add_paragraph(f"🔗 Enlace Evidencia: {fila['Link']}")
                    doc.add_paragraph("-" * 20)

                buffer_word = io.BytesIO()
                doc.save(buffer_word)
                buffer_word.seek(0)
                
                st.download_button(
                    label="📄 Descargar Reporte Word",
                    data=buffer_word,
                    file_name=f"Reporte_{f_buscada.replace('/','-')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                st.info(f"No hay registros para el día {f_buscada}.")
        except Exception as e:
            st.error(f"Error al cargar datos: {e}")
