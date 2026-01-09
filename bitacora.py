import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import json
from PIL import Image

# --- LIBRERÍAS DE GOOGLE ---
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
except ImportError:
    pass

# --- Configuración ---
st.set_page_config(page_title="Bitácora Servicios", page_icon="☁️", layout="centered")

# --- CONEXIÓN CON GOOGLE ---
def obtener_credenciales():
    # Leemos el secreto desde la configuración de Streamlit
    if "gcp_service_account" in st.secrets:
        try:
            info_dict = json.loads(st.secrets["gcp_service_account"]["payload"])
            scope = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_info(info_dict, scopes=scope)
            return creds
        except Exception as e:
            st.error(f"Error leyendo secretos: {e}")
            return None
    return None

def guardar_en_drive(imagen_bytes, nombre_archivo):
    """Sube la imagen a la carpeta FOTOS_BITACORA en Drive"""
    creds = obtener_credenciales()
    if not creds: return None
    
    service = build('drive', 'v3', credentials=creds)
    
    # 1. Buscar el ID de la carpeta
    results = service.files().list(
        q="name = 'FOTOS_BITACORA' and mimeType = 'application/vnd.google-apps.folder'",
        fields="files(id, name)").execute()
    items = results.get('files', [])
    
    if not items:
        st.error("⚠️ No encuentro la carpeta 'FOTOS_BITACORA' en Drive. ¿La compartiste con el robot?")
        return None
    
    folder_id = items[0]['id']
    
    # 2. Subir el archivo
    file_metadata = {'name': nombre_archivo, 'parents': [folder_id]}
    media = MediaIoBaseUpload(imagen_bytes, mimetype='image/jpeg')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    
    # Retornamos un enlace para ver la imagen
    return f"https://drive.google.com/file/d/{file.get('id')}/view"

def guardar_en_sheets(fecha, hora, actividad, link_imagen):
    """Guarda una nueva fila en DB_BITACORA"""
    creds = obtener_credenciales()
    if not creds: return False
    
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open("DB_BITACORA").sheet1
        # Si está vacía, ponemos encabezados
        if not sheet.get_all_values():
            sheet.append_row(["Fecha", "Hora", "Actividad", "RutaImagen"])
            
        sheet.append_row([str(fecha), str(hora), actividad, link_imagen])
        return True
    except Exception as e:
        st.error(f"Error accediendo a Google Sheets: {e}")
        return False

def leer_de_sheets():
    """Lee los datos para el historial"""
    creds = obtener_credenciales()
    if not creds: return pd.DataFrame()
    
    client = gspread.authorize(creds)
    try:
        sheet = client.open("DB_BITACORA").sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# --- INTERFAZ GRÁFICA ---
st.title("☁️ Bitácora en la Nube")

# Verificación de seguridad
if "gcp_service_account" not in st.secrets:
    st.warning("⚠️ Faltan los Secretos de configuración.")
    st.info("Por favor configura 'gcp_service_account' en el panel de Streamlit Cloud.")
    st.stop()

tab_registro, tab_historial = st.tabs(["📝 Nuevo Registro", "📋 Ver Historial"])

# --- PESTAÑA 1: REGISTRO ---
with tab_registro:
    st.markdown("### Ingresar Actividad")
    
    with st.form("form_nube", clear_on_submit=True):
        fecha = st.date_input("Fecha", date.today())
        hora = st.time_input("Hora", datetime.now().time())
        actividad = st.text_area("Descripción de la labor")
        foto = st.file_uploader("Evidencia Fotográfica", type=['jpg','png','jpeg'])
        
        btn = st.form_submit_button("☁️ Guardar en Google Drive", type="primary", use_container_width=True)
        
        if btn:
            if not actividad:
                st.error("⚠️ Falta la descripción.")
            else:
                with st.spinner("Subiendo foto y guardando datos..."):
                    link_foto = "Sin evidencia"
                    
                    # Proceso de imagen (si existe)
                    if foto:
                        img_byte_arr = io.BytesIO()
                        image = Image.open(foto)
                        if image.mode in ("RGBA", "P"): image = image.convert("RGB")
                        image.save(img_byte_arr, format='JPEG')
                        img_byte_arr.seek(0)
                        
                        nombre_archivo = f"evidencia_{fecha}_{datetime.now().strftime('%H%M%S')}.jpg"
                        link_result = guardar_en_drive(img_byte_arr, nombre_archivo)
                        if link_result: link_foto = link_result

                    # Guardar datos en Sheets
                    if guardar_en_sheets(fecha, hora, actividad, link_foto):
                        st.success("✅ ¡Registro exitoso! Guardado en la nube.")
                        st.balloons()

# --- PESTAÑA 2: HISTORIAL ---
with tab_historial:
    if st.button("🔄 Actualizar lista"):
        st.rerun()
        
    df = leer_de_sheets()
    
    if not df.empty:
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha']).dt.date
            df = df.sort_values(by="Fecha", ascending=False)
            
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        st.caption("Últimos registros detallados:")
        for i, row in df.head(5).iterrows():
            with st.expander(f"{row.get('Fecha')} - {str(row.get('Actividad'))[:30]}..."):
                st.write(f"**Detalle:** {row.get('Actividad')}")
                ruta = row.get('RutaImagen', '')
                if "http" in str(ruta):
                    st.markdown(f"[📷 Ver foto en Drive]({ruta})")
    else:
        st.info("No hay registros en la hoja 'DB_BITACORA'.")
