import streamlit as st
import pandas as pd
import io
import base64
from streamlit_gsheets import GSheetsConnection
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

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
        pass

set_bg_from_local("tlosloty.png")

# --- ŁADOWANIE CSS ---
def load_css(file_name):
    try:
        with open(file_name, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css("style.css")

# --- KONFIGURACJA DYSKU ---
# Pamiętaj o podmianie na swój docelowy folder na Google Drive
DRIVE_FOLDER_ID = "TWÓJ_ID_FOLDERU_NA_DRIVE" 

# --- FUNKCJA: WGRYWANIE NA DRIVE ---
def upload_to_drive(uploaded_file, event_name, tech_name):
    """Wgrywa plik na Dysk Google i zwraca publiczny link."""
    creds_dict = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/drive"]
    )
    drive_service = build('drive', 'v3', credentials=creds)
    
    file_metadata = {'name': f"SLOT_{event_name}_{tech_name}_{uploaded_file.name}", 'parents': [DRIVE_FOLDER_ID]}
    media = MediaIoBaseUpload(io.BytesIO(uploaded_file.read()), mimetype=uploaded_file.type, resumable=True)
    
    file_drive = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file_drive.get('id')
    
    # Nadajemy uprawnienia "Każda osoba mająca link (odczyt)"
    drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
    
    return f"https://drive.google.com/file/d/{file_id}/view"

# --- POŁĄCZENIE Z BAZĄ GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(worksheet="Dostep", ttl=60)

# --- HEADER APLIKACJI ---
st.markdown("<div class='title-sqm'>SQM SOLUTIONS</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Event Logistics Hub</div>", unsafe_allow_html=True)

# --- WYBÓR PROFILU LOGOWANIA ---
rola = st.radio("Wybierz profil autoryzacji:", ["👨‍🔧 Technik / Kierowca", "⚙️ Koordynator (CMS)"], horizontal=True)
st.write("---")

# ==========================================
# PROFIL 1: TECHNIK / KIEROWCA (TYLKO ODCZYT)
# ==========================================
if rola == "👨‍🔧 Technik / Kierowca":
    lista_eventow = df['Event'].dropna().unique().tolist()
    lista_eventow_wybor = ["Wybierz z listy..."] + lista_eventow
    
    event = st.selectbox("1. Wydarzenie", lista_eventow_wybor, key="tech_event")
    nazwisko = st.text_input("2. Nazwisko", key="tech_nazw")
    pin = st.text_input("3. Hasło (PIN)", type="password", max_chars=6, key="tech_pin")
        
    if st.button("ZALOGUJ SIĘ", key="btn_login_tech"):
        if event == "Wybierz z listy..." or not nazwisko or not pin:
            st.error("Wypełnij wszystkie pola, aby uzyskać dostęp.")
        else:
            # Oczyszczanie danych
            df['Event_clean'] = df['Event'].astype(str).str.strip()
            df['Nazwisko_clean'] = df['Nazwisko'].astype(str).str.strip().str.lower()
            df['PIN_clean'] = df['PIN'].astype(str).str.split('.').str[0].str.strip()
            
            user_rows = df[
                (df['Event_clean'] == event.strip()) & 
                (df['Nazwisko_clean'] == nazwisko.strip().lower()) & 
                (df['PIN_clean'] == pin.strip())
            ]
            
            if not user_rows.empty:
                st.success(f"Cześć, {nazwisko.title()}! Znaleziono sloty dla: {event}")
                st.write("---")
                
                # Wyświetlanie przypisanych slotów w formie kart
                for index, row in user_rows.iterrows():
                    ref_num = row.get('Nr_Referencyjny', 'Brak numeru ref.')
                    data_slotu = row.get('Data_Slotu', 'Do ustalenia')
                    notatki = row.get('Notatki', 'Brak dodatkowych instrukcji.')
                    link_pdf = row.get('Link_PDF', None)
                    
                    with st.container():
                        st.markdown(f"### 🎟️ Slot / Zgłoszenie")
                        st.markdown(f"**📅 Termin:** `{data_slotu}`")
                        st.markdown(f"**🔑 Nr Ref / Brama:** `{ref_num}`")
                        st.info(f"**Notatka:** {notatki}")
                        
                        if pd.notna(link_pdf) and str(link_pdf).strip() != "":
                            st.link_button(f"📄 Pobierz plik / slot", str(link_pdf))
                        st.markdown("---")
            else:
                st.error("Błędne dane autoryzacyjne lub brak przypisanych slotów.")


# ==========================================
# PROFIL 2: KOORDYNATOR (PEŁNY CMS)
# ==========================================
elif rola == "⚙️ Koordynator (CMS)":
    # Inicjalizacja stanu sesji dla bezpiecznego logowania
    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"] = False

    if not st.session_state["admin_logged_in"]:
        st.write("Podaj hasło główne, aby zarządzać bazą danych.")
        admin_pass = st.text_input("Hasło Koordynatora:", type="password", key="admin_pass")
        
        if st.button("ZALOGUJ JAKO ADMIN"):
            if admin_pass == st.secrets.get("admin_password", "brak_hasla"):
                st.session_state["admin_logged_in"] = True
                st.rerun()
            else:
                st.error("Błędne hasło główne.")
                
    # Ekran CMS (widoczny tylko po poprawnym zalogowaniu admina)
    if st.session_state["admin_logged_in"]:
        st.success("Autoryzacja pomyślna. Tryb zarządzania aktywny.")
        if st.button("Wyloguj"):
            st.session_state["admin_logged_in"] = False
            st.rerun()
            
        st.divider()
        
        # Przełącznik trybu (Dodawanie vs Edycja)
        tryb_admina = st.radio("Wybierz akcję:", ["➕ Dodaj nowy slot", "✏️ Edytuj / Usuń istniejący"], horizontal=True)
        
        # --- TRYB: DODAWANIE ---
        if tryb_admina == "➕ Dodaj nowy slot":
            with st.form("add_form", clear_on_submit=True):
                st.write("### Dodawanie nowego slotu do bazy")
                new_event = st.text_input("Nazwa Eventu (np. IBC Amsterdam 2026)")
                new_nazwisko = st.text_input("Nazwisko Technika")
                new_pin = st.text_input("PIN dla Technika (np. 123456)")
                new_data = st.text_input("Data i godzina (np. 15.09.2026, 14:00)")
                new_ref = st.text_input("Numer Referencyjny / Brama")
                new_notatki = st.text_area("Notatki operacyjne")
                
                st.write("Opcjonalnie: Załącz plik (możesz to zrobić również później)")
                new_file = st.file_uploader("", type=['pdf', 'jpg', 'png'], key="file_add")
                
                submitted = st.form_submit_button("ZAPISZ SLOT W BAZIE")
                
                if submitted:
                    if not new_event or not new_nazwisko or not new_pin:
                        st.error("Event, Nazwisko i PIN są obowiązkowe!")
                    else:
                        with st.spinner("Przetwarzanie danych..."):
                            final_link = ""
                            if new_file is not None:
                                try:
                                    final_link = upload_to_drive(new_file, new_event, new_nazwisko)
                                except Exception as e:
                                    st.error(f"Błąd wgrywania pliku na dysk: {e}")
                            
                            try:
                                nowy_wiersz = pd.DataFrame([{
                                    "Event": new_event, "Nazwisko": new_nazwisko, "PIN": new_pin,
                                    "Data_Slotu": new_data, "Nr_Referencyjny": new_ref,
                                    "Notatki": new_notatki, "Link_PDF": final_link
                                }])
                                zaktualizowana_baza = pd.concat([df, nowy_wiersz], ignore_index=True)
                                conn.update(worksheet="Dostep", data=zaktualizowana_baza)
                                st.cache_data.clear()
                                st.success(f"✅ Slot dla {new_nazwisko} został pomyślnie dodany!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Błąd zapisu w Arkuszu Google: {e}")

        # --- TRYB: EDYCJA I KASOWANIE ---
        elif tryb_admina == "✏️ Edytuj / Usuń istniejący":
            if df.empty:
                st.warning("Baza jest aktualnie pusta.")
            else:
                opcje_wyboru = df.index.tolist()
                def format_opcji(i):
                    return f"ID: {i} | {df.loc[i, 'Event']} | {df.loc[i, 'Nazwisko']} | {df.loc[i, 'Data_Slotu']}"
                
                wybrany_index = st.selectbox("Wybierz wpis do modyfikacji:", opcje_wyboru, format_func=format_opcji)
                
                if wybrany_index is not None:
                    row = df.loc[wybrany_index]
                    st.divider()
                    
                    with st.form("edit_form"):
                        st.write("### Edycja danych slotu")
                        ed_event = st.text_input("Event", value=str(row.get('Event', '')))
                        ed_nazw = st.text_input("Nazwisko", value=str(row.get('Nazwisko', '')))
                        ed_pin = st.text_input("PIN", value=str(row.get('PIN', '')))
                        ed_data = st.text_input("Data i godzina", value=str(row.get('Data_Slotu', '')))
                        ed_ref = st.text_input("Nr Ref / Brama", value=str(row.get('Nr_Referencyjny', '')))
                        ed_notatki = st.text_area("Notatki", value=str(row.get('Notatki', '')))
                        
                        obecny_link = row.get('Link_PDF', '')
                        if pd.notna(obecny_link) and str(obecny_link).strip() != "":
                            st.info("Ten slot ma obecnie przypisany plik na dysku.")
                            usun_plik = st.checkbox("Zaznacz, aby całkowicie usunąć link do obecnego pliku")
                        else:
                            usun_plik = False
                            st.info("Ten slot nie ma obecnie przypisanego pliku.")
                        
                        st.write("Wgraj nowy plik (jeśli go dodasz, zastąpi on obecny link):")
                        ed_file = st.file_uploader("", type=['pdf', 'jpg', 'png'], key="file_ed")
                        
                        zapisz_edycje = st.form_submit_button("💾 ZAPISZ ZMIANY")
                        
                        if zapisz_edycje:
                            with st.spinner("Zapisywanie zmian w bazie..."):
                                nowy_link = obecny_link
                                
                                if usun_plik:
                                    nowy_link = ""
                                
                                if ed_file is not None:
                                    try:
                                        nowy_link = upload_to_drive(ed_file, ed_event, ed_nazw)
                                    except Exception as e:
                                        st.error(f"Błąd wgrywania nowego pliku: {e}")
                                
                                df.at[wybrany_index, 'Event'] = ed_event
                                df.at[wybrany_index, 'Nazwisko'] = ed_nazw
                                df.at[wybrany_index, 'PIN'] = ed_pin
                                df.at[wybrany_index, 'Data_Slotu'] = ed_data
                                df.at[wybrany_index, 'Nr_Referencyjny'] = ed_ref
                                df.at[wybrany_index, 'Notatki'] = ed_notatki
                                df.at[wybrany_index, 'Link_PDF'] = nowy_link
                                
                                conn.update(worksheet="Dostep", data=df)
                                st.cache_data.clear()
                                st.success("✅ Zmiany zostały pomyślnie zapisane!")
                                st.rerun()

                    st.write("### Opcje destrukcyjne")
                    st.write("Skasowanie slotu usunie wiersz z bazy trwale.")
                    if st.button("🗑️ USUŃ TEN SLOT Z BAZY", type="primary"):
                        df = df.drop(index=wybrany_index).reset_index(drop=True)
                        conn.update(worksheet="Dostep", data=df)
                        st.cache_data.clear()
                        st.success("Slot został usunięty.")
                        st.rerun()
