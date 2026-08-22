import streamlit as st
import pandas as pd
import io
import base64
from streamlit_gsheets import GSheetsConnection
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from streamlit_cookies_controller import CookieController

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="SQM Hub", page_icon="📱", layout="centered", initial_sidebar_state="collapsed")

# --- INICJALIZACJA CIASTECZEK (Na 30 dni) ---
cookie_controller = CookieController()
COOKIE_EXPIRY = 30 * 24 * 60 * 60  # 30 dni w sekundach

# --- ŁADOWANIE TŁA I CSS ---
def set_bg_from_local(image_file):
    try:
        with open(image_file, "rb") as file:
            encoded_string = base64.b64encode(file.read()).decode()
        st.markdown(
            f"<style>.stApp {{ background-image: url(data:image/png;base64,{encoded_string}); background-size: cover; background-position: center; background-attachment: fixed; }}</style>",
            unsafe_allow_html=True
        )
    except FileNotFoundError:
        pass

set_bg_from_local("tlosloty.png")

def load_css(file_name):
    try:
        with open(file_name, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css("style.css")

# --- KONFIGURACJA DYSKU ---
DRIVE_FOLDER_ID = "TWÓJ_ID_FOLDERU_NA_DRIVE" 

def upload_to_drive(uploaded_file, event_name, tech_name):
    creds_dict = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/drive"])
    drive_service = build('drive', 'v3', credentials=creds)
    file_metadata = {'name': f"SLOT_{event_name}_{tech_name}_{uploaded_file.name}", 'parents': [DRIVE_FOLDER_ID]}
    media = MediaIoBaseUpload(io.BytesIO(uploaded_file.read()), mimetype=uploaded_file.type, resumable=True)
    file_drive = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file_drive.get('id')
    drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
    return f"https://drive.google.com/file/d/{file_id}/view"

# --- POŁĄCZENIE Z BAZĄ ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(worksheet="Dostep", ttl=60)

# --- HEADER APLIKACJI ---
st.markdown("<div class='title-sqm'>SQM SOLUTIONS</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Event Logistics Hub</div>", unsafe_allow_html=True)

# --- ODCZYT ZAPISANYCH SESJI (CIASTECZEK) ---
saved_role = cookie_controller.get("sqm_role")
saved_nazw = cookie_controller.get("sqm_nazw")
saved_pin = cookie_controller.get("sqm_pin")

# ==========================================
# EKRAN 1: JEŚLI UŻYTKOWNIK NIE JEST ZALOGOWANY
# ==========================================
if not saved_role:
    rola = st.radio("Wybierz profil autoryzacji:", ["👨‍🔧 Technik / Kierowca", "⚙️ Koordynator (CMS)"], horizontal=True)
    st.write("---")
    
    # EKRAN LOGOWANIA TECHNIKA (Tylko Nazwisko i PIN, bez eventów)
    if rola == "👨‍🔧 Technik / Kierowca":
        st.write("Wpisz swoje dane, aby sprawdzić przypisane sloty.")
        nazwisko = st.text_input("1. Nazwisko")
        pin = st.text_input("2. Hasło (PIN)", type="password", max_chars=6)
            
        if st.button("ZALOGUJ SIĘ"):
            if not nazwisko or not pin:
                st.error("Wypełnij wszystkie pola.")
            else:
                df['Nazwisko_clean'] = df['Nazwisko'].astype(str).str.strip().str.lower()
                df['PIN_clean'] = df['PIN'].astype(str).str.split('.').str[0].str.strip()
                
                # Sprawdzamy czy technik w ogóle figuruje w bazie
                user_rows = df[(df['Nazwisko_clean'] == nazwisko.strip().lower()) & (df['PIN_clean'] == pin.strip())]
                
                if not user_rows.empty:
                    # Zapisujemy logowanie na 30 dni i odświeżamy apkę
                    cookie_controller.set("sqm_role", "tech", max_age=COOKIE_EXPIRY)
                    cookie_controller.set("sqm_nazw", nazwisko.strip().lower(), max_age=COOKIE_EXPIRY)
                    cookie_controller.set("sqm_pin", pin.strip(), max_age=COOKIE_EXPIRY)
                    st.rerun()
                else:
                    st.error("Błędne dane lub brak przypisanych slotów w systemie.")

    # EKRAN LOGOWANIA ADMINA
    elif rola == "⚙️ Koordynator (CMS)":
        admin_pass = st.text_input("Hasło Koordynatora:", type="password")
        if st.button("ZALOGUJ JAKO ADMIN"):
            if admin_pass == st.secrets.get("admin_password", "brak_hasla"):
                cookie_controller.set("sqm_role", "admin", max_age=COOKIE_EXPIRY)
                st.rerun()
            else:
                st.error("Błędne hasło główne.")

# ==========================================
# EKRAN 2: WIDOK DLA ZALOGOWANEGO TECHNIKA
# ==========================================
elif saved_role == "tech":
    col1, col2 = st.columns([3, 1])
    col1.success(f"Zalogowano jako: {str(saved_nazw).title()}")
    if col2.button("Wyloguj"):
        cookie_controller.remove("sqm_role")
        cookie_controller.remove("sqm_nazw")
        cookie_controller.remove("sqm_pin")
        st.rerun()
        
    st.write("---")
    
    # Pobieranie tylko tych slotów, które należą do niego
    df['Nazwisko_clean'] = df['Nazwisko'].astype(str).str.strip().str.lower()
    df['PIN_clean'] = df['PIN'].astype(str).str.split('.').str[0].str.strip()
    
    moje_sloty = df[(df['Nazwisko_clean'] == saved_nazw) & (df['PIN_clean'] == saved_pin)]
    
    if moje_sloty.empty:
        st.info("Aktualnie nie masz żadnych przypisanych zadań lub eventów w bazie.")
    else:
        for index, row in moje_sloty.iterrows():
            event_name = row.get('Event', 'Nieznany Event')
            ref_num = row.get('Nr_Referencyjny', 'Brak')
            data_slotu = row.get('Data_Slotu', 'Do ustalenia')
            notatki = row.get('Notatki', '')
            link_pdf = row.get('Link_PDF', '')
            
            with st.container():
                st.markdown(f"### 📍 {event_name}")
                st.markdown(f"**📅 Termin:** `{data_slotu}`")
                st.markdown(f"**🔑 Nr Ref / Brama:** `{ref_num}`")
                
                if pd.notna(notatki) and str(notatki).strip():
                    st.info(f"**Notatka:** {notatki}")
                
                if pd.notna(link_pdf) and str(link_pdf).strip() != "":
                    st.link_button(f"📄 Pobierz dokumentację (PDF)", str(link_pdf))
                st.markdown("---")

# ==========================================
# EKRAN 3: WIDOK DLA ZALOGOWANEGO ADMINA (CMS)
# ==========================================
elif saved_role == "admin":
    col1, col2 = st.columns([3, 1])
    col1.success("Jesteś w trybie Koordynatora (CMS).")
    if col2.button("Wyloguj"):
        cookie_controller.remove("sqm_role")
        st.rerun()
        
    st.divider()
    tryb_admina = st.radio("Wybierz akcję:", ["➕ Dodaj nowy slot", "✏️ Edytuj / Usuń istniejący"], horizontal=True)
    
    # --- DODAWANIE ---
    if tryb_admina == "➕ Dodaj nowy slot":
        with st.form("add_form", clear_on_submit=True):
            new_event = st.text_input("Nazwa Eventu (np. IBC Amsterdam 2026)")
            new_nazwisko = st.text_input("Nazwisko Technika")
            new_pin = st.text_input("PIN dla Technika (np. 123456)")
            new_data = st.text_input("Data i godzina (np. 15.09.2026, 14:00)")
            new_ref = st.text_input("Numer Referencyjny / Brama")
            new_notatki = st.text_area("Notatki operacyjne")
            new_file = st.file_uploader("Załącz plik (Opcjonalnie)", type=['pdf', 'jpg', 'png'], key="file_add")
            
            submitted = st.form_submit_button("ZAPISZ SLOT W BAZIE")
            
            if submitted:
                if not new_event or not new_nazwisko or not new_pin:
                    st.error("Event, Nazwisko i PIN są obowiązkowe!")
                else:
                    with st.spinner("Przetwarzanie..."):
                        final_link = ""
                        if new_file is not None:
                            try:
                                final_link = upload_to_drive(new_file, new_event, new_nazwisko)
                            except Exception as e:
                                st.error(f"Błąd dysku: {e}")
                        try:
                            nowy_wiersz = pd.DataFrame([{
                                "Event": new_event, "Nazwisko": new_nazwisko, "PIN": new_pin,
                                "Data_Slotu": new_data, "Nr_Referencyjny": new_ref,
                                "Notatki": new_notatki, "Link_PDF": final_link
                            }])
                            zaktualizowana_baza = pd.concat([df, nowy_wiersz], ignore_index=True)
                            conn.update(worksheet="Dostep", data=zaktualizowana_baza)
                            st.cache_data.clear()
                            st.success(f"Dodano slot dla: {new_nazwisko}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Błąd bazy: {e}")

    # --- EDYCJA ---
    elif tryb_admina == "✏️ Edytuj / Usuń istniejący":
        if df.empty:
            st.warning("Baza jest pusta.")
        else:
            opcje_wyboru = df.index.tolist()
            def format_opcji(i):
                return f"{df.loc[i, 'Event']} | {df.loc[i, 'Nazwisko']} | {df.loc[i, 'Data_Slotu']}"
            
            wybrany_index = st.selectbox("Wybierz wpis:", opcje_wyboru, format_func=format_opcji)
            
            if wybrany_index is not None:
                row = df.loc[wybrany_index]
                with st.form("edit_form"):
                    ed_event = st.text_input("Event", value=str(row.get('Event', '')))
                    ed_nazw = st.text_input("Nazwisko", value=str(row.get('Nazwisko', '')))
                    ed_pin = st.text_input("PIN", value=str(row.get('PIN', '')))
                    ed_data = st.text_input("Data i godzina", value=str(row.get('Data_Slotu', '')))
                    ed_ref = st.text_input("Nr Ref", value=str(row.get('Nr_Referencyjny', '')))
                    ed_notatki = st.text_area("Notatki", value=str(row.get('Notatki', '')))
                    
                    obecny_link = row.get('Link_PDF', '')
                    usun_plik = False
                    if pd.notna(obecny_link) and str(obecny_link).strip() != "":
                        st.info("Zapisany plik PDF jest aktywny.")
                        usun_plik = st.checkbox("Usuń obecny plik")
                        
                    ed_file = st.file_uploader("Nadpisz nowym plikiem", type=['pdf', 'jpg', 'png'])
                    zapisz_edycje = st.form_submit_button("💾 ZAPISZ ZMIANY")
                    
                    if zapisz_edycje:
                        with st.spinner("Zapisywanie..."):
                            nowy_link = "" if usun_plik else obecny_link
                            if ed_file is not None:
                                try:
                                    nowy_link = upload_to_drive(ed_file, ed_event, ed_nazw)
                                except: pass
                            
                            df.at[wybrany_index, 'Event'] = ed_event
                            df.at[wybrany_index, 'Nazwisko'] = ed_nazw
                            df.at[wybrany_index, 'PIN'] = ed_pin
                            df.at[wybrany_index, 'Data_Slotu'] = ed_data
                            df.at[wybrany_index, 'Nr_Referencyjny'] = ed_ref
                            df.at[wybrany_index, 'Notatki'] = ed_notatki
                            df.at[wybrany_index, 'Link_PDF'] = nowy_link
                            
                            conn.update(worksheet="Dostep", data=df)
                            st.cache_data.clear()
                            st.success("Zapisano!")
                            st.rerun()

                if st.button("🗑️ USUŃ TRWALE SLOT", type="primary"):
                    df = df.drop(index=wybrany_index).reset_index(drop=True)
                    conn.update(worksheet="Dostep", data=df)
                    st.cache_data.clear()
                    st.success("Usunięto.")
                    st.rerun()
