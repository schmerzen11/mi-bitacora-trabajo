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

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Bitácora de Trabajo", page_icon="📝", layout="wide")

# Datos confirmados en capturas previas
ID_CARPETA_DRIVE = '1Tjfn-lrjI338bBmfKHvQdnttu6JtRsfA'
NOMBRE_EXCEL = "DB_BITACORA"

# --- 2. FUNCIONES DE CONEXIÓN ---
def obtener_credenciales():
    """Obtiene credenciales desde los secretos de Streamlit Cloud."""
    if "gcp_service_account" in st.secrets:
        info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        return Credentials.from_service_account_info(info_dict, scopes=scopes)
    return None

def guardar_evidencia_drive(imagen_bytes, nombre_archivo):
    """Sube la imagen a Drive. Maneja el error de cuota 403."""
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {'name': nombre_archivo, 'parents': [ID_CARPETA_DRIVE]}
        media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg', resumable=True)
        
        # supportsAllDrives intenta usar la cuota de la carpeta compartida
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True 
        ).execute()
        
        return f"https://drive.google.com/file/d/{file.get('id')}/view"
    except Exception as e:
        # Si hay error de cuota, mostramos aviso pero no bloqueamos el registro
        st.warning(f"⚠️ La foto no se subió por límites de espacio del robot (Cuota). Error: {e}")
        return "Pendiente de subida manual (Error Cuota)"

# --- 3. INTERFAZ: TABS PARA ORGANIZACIÓN ---
st.title("🗒️ Bitácora de Trabajo")
tab_registro, tab_reportes = st.tabs(["✍️ Registro", "📊 Historial y Reportes"])

# --- TAB DE REGISTRO ---
with tab_registro:
    with st.form("form_registro", clear_on_submit=True):
        col_desc, col_file = st.columns([2, 1])
        with col_desc:
            descripcion = st.text_area("Descripción de la actividad:")
        with col_file:
            # st.file_uploader NO abre la cámara automáticamente
            archivo = st.file_uploader("Evidencia (Foto)", type=['jpg', 'jpeg', 'png'])
        
        btn_enviar = st.form_submit_button("🚀 Guardar Actividad")

    if btn_enviar:
        if descripcion:
            with st.spinner("Guardando..."):
                ahora = datetime.now()
                fecha_s = ahora.strftime("%d/%m/%Y")
                hora_s = ahora.strftime("%H:%M:%S")
                link_evidencia = "Sin evidencia"

                if archivo:
                    # Procesar imagen con PIL para compatibilidad
                    img = Image.open(archivo)
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG')
                    buf.seek(0)
                    
                    nombre_img = f"evid_{ahora.strftime('%Y%m%d_%H%M%S')}.jpg"
                    res_drive = guardar_evidencia_drive(buf, nombre_img)
                    if res_drive: link_evidencia = res_drive

                # Guardar en Google Sheets
                try:
                    creds = obtener_credenciales()
                    client = gspread.authorize(creds)
                    sheet = client.open(NOMBRE_EXCEL).sheet1
                    sheet.append_row([fecha_s, hora_s, descripcion, link_evidencia])
                    st.success("✅ Registro guardado exitosamente.")
                except Exception as e:
                    st.error(f"Error Sheets: {e}")
        else:
            st.warning("Escribe una descripción.")

# --- TAB DE REPORTES Y CALENDARIO ---
with tab_reportes:
    st.subheader("Consultar Registros")
    # Calendario para filtrar
    fecha_filtro = st.date_input("Filtrar por fecha:", datetime.now())
    
    if st.button("🔍 Ver Actividades"):
        try:
            creds = obtener_credenciales()
            client = gspread.authorize(creds)
            data = client.open(NOMBRE_EXCEL).sheet1.get_all_records()
            df = pd.DataFrame(data)
            
            f_str = fecha_filtro.strftime("%d/%m/%Y")
            df_dia = df[df['Fecha'] == f_str]

            if not df_dia.empty:
                st.dataframe(df_dia, use_container_width=True)
                
                # Generación de Reporte Word
                doc = Document()
                doc.add_heading(f'Bitácora - {f_str}', 0)
                for _, fila in df_dia.iterrows():
                    doc.add_paragraph(f"Hora: {fila['Hora']}\nActividad: {fila['Descripción']}\nLink: {fila['Link']}\n" + "-"*20)
                
                b_word = io.BytesIO()
                doc.save(b_word)
                b_word.seek(0)
                st.download_button("📄 Descargar Reporte Word", b_word, f"Reporte_{f_str.replace('/','-')}.docx")
            else:
                st.info(f"No hay registros para el día {f_str}.")
        except Exception as e:
            st.error(f"Error al cargar datos: {e}")
