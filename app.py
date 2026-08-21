import streamlit as st
import pandas as pd
import io
import base64
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from fpdf import FPDF

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="SQM Hub", page_icon="📱", layout="centered", initial_sidebar_state="collapsed")

# --- ŁADOWANIE TŁA GRAFICZNEGO ---
def set_bg_from_local(image_file):
    try:
        with open(image_file, "rb") as file:
            encoded_string = base64.b64encode(file.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url(data:image/png;base64,{encoded_string});
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    except FileNotFoundError:
        st.warning("Nie znaleziono pliku tła (tlosloty.png).")

set_bg_from_local("tlosloty.png")

# --- ŁADOWANIE CSS ---
def load_css(file_name):
    try:
        with open(file_name, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css("style.css")

# ID folderu na Google Drive (Pamiętaj o podmianie na swój docelowy folder)
DRIVE_FOLDER_ID = "TWÓJ_ID_FOLDERU_NA_DRIVE" 

# --- FUNKCJA DO GENEROWANIA CMR (Z ŁATKĄ DLA STREAMLIT) ---
def create_cmr_pdf(event_name, technician_name):
    def clean_pl(text):
        pl_chars = {'ą':'a','ć':'c','ę':'e','ł':'l','ń':'n','ó':'o','ś':'s','ź':'z','ż':'z',
                    'Ą':'A','Ć':'C','Ę':'E','Ł':'L','Ń':'N','Ó':'O','Ś':'S','Ź':'Z','Ż':'Z'}
        for k, v in pl_chars.items():
            text = text.replace(k, v)
        return text

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "LIST PRZEWOZOWY CMR (ZWROT)", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Helvetica", '', 12)
    pdf.cell(0, 8, f"Event: {clean_pl(event_name)}", ln=True)
    pdf.cell(0, 8, f"Technik / Kierowca: {clean_pl(technician_name).upper()}", ln=True)
    pdf.ln(10)
    pdf.cell(0, 8, "ODBIORCA: SQM Multimedia Solutions, ul. Wiosenna, Komorniki", ln=True)
    
    # Zabezpieczenie typu pliku dla Streamlita
    pdf_out = pdf.output(dest='S')
    
    if isinstance(pdf_out, bytearray):
        return bytes(pdf_out)
    elif isinstance(pdf_out, str):
        return pdf_out.encode('latin-1')
    
    return bytes(pdf_out)

# --- POŁĄCZENIE Z BAZĄ GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(worksheet="Dostep", ttl=60)

# --- HEADER APLIKACJI MOBILNEJ ---
st.markdown("<div class='title-sqm'>SQM SOLUTIONS</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Event Logistics Hub</div>", unsafe_allow_html=True)

# Pobranie listy eventów
lista_eventow = df['Event'].dropna().unique().tolist()
lista_eventow.insert(0, "Wybierz z listy...")

# --- FORMULARZ LOGOWANIA ---
event = st.selectbox("1. Wydarzenie", lista_eventow)
nazwisko = st.text_input("2. Nazwisko")
pin = st.text_input("3. Hasło (PIN)", type="password", max_chars=6)
    
zaloguj = st.button("ZALOGUJ SIĘ")

# --- LOGIKA PO ZALOGOWANIU ---
if zaloguj:
    if event == "Wybierz z listy..." or not nazwisko or not pin:
        st.error("Wypełnij wszystkie pola, aby uzyskać dostęp.")
    else:
        # Oczyszczanie danych zapobiegające błędom spacji i typów liczbowych
        df['Event_clean'] = df['Event'].astype(str).str.strip()
        df['Nazwisko_clean'] = df['Nazwisko'].astype(str).str.strip().str.lower()
        df['PIN_clean'] = df['PIN'].astype(str).str.split('.').str[0].str.strip()
        
        user_data = df[
            (df['Event_clean'] == event.strip()) & 
            (df['Nazwisko_clean'] == nazwisko.strip().lower()) & 
            (df['PIN_clean'] == pin.strip())
        ]
        
        if not user_data.empty:
            st.success(f"Cześć, {nazwisko.title()}!")
            
            notatki = user_data.iloc[0]['Notatki']
            link_pdf = user_data.iloc[0]['Link_PDF']
            
            # GŁÓWNY WIDOK: Notatki
            st.write("### Notatki operacyjne")
            st.info(notatki if pd.notna(notatki) else "Brak dodatkowych instrukcji.")
            
            # GŁÓWNY WIDOK: Przycisk do pobrania
            st.write("") # Odstęp
            if pd.notna(link_pdf) and str(link_pdf).strip() != "":
                st.link_button("📄 POBIERZ SLOT / PLAN HALI", str(link_pdf))
            else:
                st.warning("Brak pliku do pobrania.")
            
            st.write("---")
            
            # ROZWIJANA SEKCJA 1: Check-in / Statusy
            with st.expander("📍 Zgłoś swój status"):
                st.write("Wybierz aktualny etap prac:")
                if st.button("🚛 Jestem na miejscu"):
                    st.success("Zgłoszono przyjazd.")
                if st.button("📦 Rozładunek zakończony"):
                    st.success("Zgłoszono rozładunek.")
                if st.button("🏁 Wyjazd z hali"):
                    st.success("Zgłoszono wyjazd.")

            # ROZWIJANA SEKCJA 2: Dokumenty zwrotne (CMR)
            with st.expander("🖨️ Wygeneruj dokument zwrotny"):
                st.write("Pobierz gotowy list przewozowy na drogę powrotną do Komornik.")
                pdf_bytes = create_cmr_pdf(event, nazwisko)
                st.download_button(
                    label="Pobierz CMR (PDF)",
                    data=pdf_bytes,
                    file_name=f"CMR_Zwrot_{event.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )

            # ROZWIJANA SEKCJA 3: Upload zdjęć
            with st.expander("📸 Dodaj zdjęcie lub skan"):
                st.write("Zrób zdjęcie telefonem lub załącz plik z urządzenia.")
                uploaded_file = st.file_uploader("", type=['jpg', 'jpeg', 'png', 'pdf'])
                
                if uploaded_file is not None:
                    if st.button("Wyślij plik"):
                        with st.spinner("Wysyłanie..."):
                            try:
                                creds_dict = st.secrets["connections"]["gsheets"]
                                creds = service_account.Credentials.from_service_account_info(
                                    creds_dict, scopes=["https://www.googleapis.com/auth/drive"]
                                )
                                drive_service = build('drive', 'v3', credentials=creds)
                                file_name_drive = f"{event}_{nazwisko}_{uploaded_file.name}"
                                media = MediaIoBaseUpload(io.BytesIO(uploaded_file.read()), mimetype=uploaded_file.type, resumable=True)
                                file_metadata = {'name': file_name_drive, 'parents': [DRIVE_FOLDER_ID]}
                                drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                                st.success("Plik wysłany do centrali!")
                            except Exception as e:
                                st.error("Wystąpił problem z wysyłaniem. Sprawdź połączenie z dyskiem.")
        else:
            st.error("Błędne dane autoryzacyjne. Spróbuj ponownie.")
