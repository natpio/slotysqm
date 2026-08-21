import streamlit as st
import pandas as pd
import io
from streamlit_gsheets import GSheetsConnection
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Konfiguracja strony
st.set_page_config(page_title="SYSTEM 64", page_icon="💾", layout="centered")

# --- WCZYTYWANIE CSS ---
def load_css(file_name):
    try:
        with open(file_name, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("Nie znaleziono pliku style.css")

load_css("style.css")

# --- DANE KONFIGURACYJNE ---
# ID folderu na Google Drive, do którego mają trafiać skany/CMR
# Znajdziesz je w URL folderu: drive.google.com/drive/folders/TUTAJ_JEST_ID
DRIVE_FOLDER_ID = "TWÓJ_ID_FOLDERU_NA_DRIVE" 

# Pobranie danych z Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(worksheet="Dostep", ttl=60)

# --- INTERFEJS RETRO ---
st.markdown("<h1>**** TERMINAL TECHNIKA ****<br><br>64K RAM SYSTEM  38911 BYTES FREE<br><br>READY.</h1>", unsafe_allow_html=True)

# Pobranie listy eventów
lista_eventow = df['Event'].dropna().unique().tolist()
lista_eventow.insert(0, "--- WYBIERZ ---")

with st.container():
    event = st.selectbox("EVENT:", lista_eventow)
    nazwisko = st.text_input("NAZWISKO:")
    pin = st.text_input("PIN (6 CYFR):", type="password", max_chars=6)
    
    zaloguj = st.button("RUN")

if zaloguj:
    if event == "--- WYBIERZ ---" or not nazwisko or not pin:
        st.error("SYNTAX ERROR WPROWADZ DANE")
    else:
        user_data = df[
            (df['Event'] == event) & 
            (df['Nazwisko'].astype(str).str.lower() == nazwisko.lower()) & 
            (df['PIN'].astype(str) == pin)
        ]
        
        if not user_data.empty:
            st.success(f"WITAJ {nazwisko.upper()}. LOGOWANIE OK.")
            st.divider()
            
            notatki = user_data.iloc[0]['Notatki']
            link_pdf = user_data.iloc[0]['Link_PDF']
            
            st.write(">> NOTATKI OPERACYJNE:")
            st.info(notatki if pd.notna(notatki) else "BRAK NOTATEK")
            
            st.write(">> PLIKI SLOTOW:")
            if pd.notna(link_pdf):
                st.link_button("LOAD \"SLOT_PDF\",8,1", link_pdf)
            else:
                st.warning("FILE NOT FOUND")
            
            st.divider()
            
            # --- SEKCJA UPLOADU (NP. CMR) ---
            st.write(">> UPLOAD DOKUMENTOW (CMR/ZDJECIA):")
            uploaded_file = st.file_uploader("WYBIERZ PLIK DO PRZESLANIA", type=['pdf', 'jpg', 'jpeg', 'png'])
            
            if uploaded_file is not None:
                upload_btn = st.button("WYSLIJ NA DYSK")
                
                if upload_btn:
                    with st.spinner("TRWA PRZESYLANIE..."):
                        try:
                            # Połączenie z Google Drive API używając tych samych kluczy co st-gsheets
                            creds_dict = st.secrets["connections"]["gsheets"]
                            creds = service_account.Credentials.from_service_account_info(
                                creds_dict, scopes=["https://www.googleapis.com/auth/drive"]
                            )
                            drive_service = build('drive', 'v3', credentials=creds)
                            
                            # Budowa nazwy pliku: Event_Nazwisko_OryginalnaNazwa
                            file_name_drive = f"{event}_{nazwisko}_{uploaded_file.name}"
                            
                            media = MediaIoBaseUpload(io.BytesIO(uploaded_file.read()), mimetype=uploaded_file.type, resumable=True)
                            file_metadata = {
                                'name': file_name_drive,
                                'parents': [DRIVE_FOLDER_ID]
                            }
                            
                            request = drive_service.files().create(body=file_metadata, media_body=media, fields='id')
                            response = request.execute()
                            
                            st.success("PRZESYLANIE ZAKONCZONE SUKCESEM.")
                        except Exception as e:
                            st.error(f"ERROR: {e}")
        else:
            st.error("ACCESS DENIED. BLEDNE DANE.")
