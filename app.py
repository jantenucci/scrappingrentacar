import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

st.set_page_config(page_title="Avis Scraper", layout="centered")
st.title("🚗 Avis Argentina - Scraper de precios")

# Google Sheets config
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import json
from io import StringIO

secrets_json = json.dumps(st.secrets["google"])
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(secrets_json), SCOPE)

gc = gspread.authorize(CREDS)
spreadsheet_id = "1aQVNDkl9nTrNvOUuSkCk5wrd_Ox5-cb-etyQBCXRMuM"
sh = gc.open_by_key(spreadsheet_id)

# Lista de lugares para retiro y devolución
ubicaciones = [
    "Aeroparque",
    "Ezeiza",
    "Buenos Aires centro",
    "Mendoza centro",
    "Mendoza aeropuerto",
    "Salta aeropuerto",
    "Bariloche aeropuerto",
    "San martin de los andes aeropuerto",
    "Puerto Madryn aeropuerto",
    "San Juan aeropuerto",
    "San Juan centro",
    "Neuquen aeropuerto"
]

# Inputs del usuario
with st.form("input_form"):
    lugar_retiro = st.selectbox("📍 Lugar de retiro", ubicaciones)
    lugar_devolucion = st.selectbox("📍 Lugar de devolución", ubicaciones)
    fecha_desde = st.date_input("📅 Fecha desde", value=date(2025, 6, 15), min_value=date.today())
    fecha_hasta = st.date_input("📅 Fecha hasta", value=date(2025, 6, 18), min_value=date.today())
    submitted = st.form_submit_button("Abrir navegador para completar búsqueda")

if submitted:
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.maximize_window()
    driver.get("https://www.avis.com.ar/reserva/lugar-fecha")
    st.session_state.driver = driver
    st.session_state.lugar_retiro = lugar_retiro
    st.session_state.lugar_devolucion = lugar_devolucion
    st.session_state.fecha_desde = fecha_desde.strftime("%d/%m/%Y")
    st.session_state.fecha_hasta = fecha_hasta.strftime("%d/%m/%Y")
    st.success("✅ Página abierta. Completá la búsqueda y hacé clic en 'Find my car'. Luego volvé acá y presioná el botón abajo.")

# Segundo paso: Scraping luego de completar la búsqueda
if "driver" in st.session_state:
    if st.button("✅ Ya completé, continuar scraping"):
        driver = st.session_state.driver

        try:
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.CLASS_NAME, "card-body")))
            st.success("✅ Página de resultados detectada")
        except:
            st.error("❌ No se detectó la página de resultados.")
            driver.quit()
            del st.session_state.driver
            st.stop()

        datos = []

        try:
            autos = driver.find_elements(By.CLASS_NAME, "card-body")

            for auto in autos:
                try:
                    modelo_completo = auto.find_element(By.CLASS_NAME, "fw-bold").text
                    if "Group" in modelo_completo:
                        grupo = modelo_completo.split("Group ")[1].split(" - ")[0].strip()
                        modelo = modelo_completo.split(" - ")[1].strip()
                    else:
                        grupo = ""
                        modelo = modelo_completo

                    botones_precio = auto.find_elements(By.TAG_NAME, "button")
                    for btn in botones_precio:
                        texto = btn.text.strip()
                        if "$" in texto:
                            lineas = texto.split("\n")
                            tipo_tarifa = lineas[0].strip().capitalize()
                            precio_linea = [l for l in lineas if "$" in l]
                            if precio_linea:
                                precio = precio_linea[0].replace("$", "").replace(",", "").strip()
                                if "." in precio:
                                    precio = precio.split(".")[0]
                                datos.append({
                                    "Lugar de Retiro": st.session_state.lugar_retiro,
                                    "Lugar de Devolución": st.session_state.lugar_devolucion,
                                    "Fecha Desde": st.session_state.fecha_desde,
                                    "Fecha Hasta": st.session_state.fecha_hasta,
                                    "Grupo": grupo,
                                    "Modelo": modelo,
                                    "Tipo de Tarifa": tipo_tarifa,
                                    "Precio (ARS)": float(precio)
                                })
                except:
                    continue
        except Exception as e:
            st.error(f"❌ Error en scraping: {e}")
            driver.quit()
            del st.session_state.driver
            st.stop()

        driver.quit()
        del st.session_state.driver

        # Guardar en hoja nueva
        nombre_hoja = f"{st.session_state.lugar_retiro[:25]}_{int(time.time())}"  # única
        try:
            worksheet = sh.add_worksheet(title=nombre_hoja, rows="100", cols="20")
        except:
            worksheet = sh.worksheet(nombre_hoja)

        df = pd.DataFrame(datos)
        df["Precio (ARS)"] = df["Precio (ARS)"].apply(lambda x: f"{int(x):,}".replace(",", "."))
        set_with_dataframe(worksheet, df)
        st.success(f"✅ Datos guardados en Google Sheets (hoja '{nombre_hoja}')")
        st.dataframe(df)


