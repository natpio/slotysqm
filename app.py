import streamlit as st
import pandas as pd
import io
import base64
import re
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from streamlit_cookies_controller import CookieController

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="SQM Hub", page_icon="📱", layout="wide", initial_sidebar_state="collapsed")

# --- INICJALIZACJA CIASTECZEK (Na 30 dni) ---
cookie_controller = CookieController()
COOKIE_EXPIRY = 30 * 24 * 60 * 60

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

# --- SYSTEM SPRAWDZANIA DAT (UKRYWANIE ZAKOŃCZONYCH) ---
def czy_slot_aktywny(data_str):
    if pd.isna(data_str) or str(data_str).strip() == "":
        return True # Jeśli nie ma daty, zostawiamy slot jako aktywny
    
    # Szukamy polskiego formatu DD.MM.YYYY w ciągu znaków
    match_pl = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(data_str))
    if match_pl:
        try:
            slot_date = datetime(int(match_pl.group(3)), int(match_pl.group(2)), int(match_pl.group(1))).date()
            return slot_date >= datetime.today().date()
        except: pass
        
    # Szukamy formatu YYYY-MM-DD
    match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(data_str))
    if match_iso:
        try:
            slot_date = datetime(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3))).date()
            return slot_date >= datetime.today().date()
        except: pass

    # Jeśli nie udało się odczytać formatu daty, domyślnie pokazujemy slot
    return True

# --- POŁĄCZENIE Z BAZĄ GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_konta = conn.read(worksheet="Uzytkownicy", ttl=60)
    df_sloty = conn.read(worksheet="Dostep", ttl=60)
except Exception as e:
    st.error("Błąd połączenia z bazą. Upewnij się, że masz zakładki: 'Dostep' oraz 'Uzytkownicy'.")
    st.stop()

# --- HEADER APLIKACJI ---
st.markdown("<div class='title-sqm'>SQM SOLUTIONS</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Event Logistics Hub</div>", unsafe_allow_html=True)

saved_login = cookie_controller.get("sqm_login")
saved_role = cookie_controller.get("sqm_role")

# ==========================================
# EKRAN 1: WYBÓR WIDOKU I LOGOWANIE
# ==========================================
if not saved_login:
    st.write("### Gdzie chcesz wejść?")
    rola_wybor = st.radio("Wybierz profil:", ["👨‍🔧 Moje prywatne sloty", "📋 Tablica Eventu (Dla Ekipy)", "⚙️ Panel Koordynatora"], horizontal=False)
    st.write("---")
    
    if rola_wybor == "👨‍🔧 Moje prywatne sloty":
        st.write("Podaj swoje dane, aby zobaczyć tylko swoje wyjazdy.")
        login_input = st.text_input("Login / Nazwisko")
        pin_input = st.text_input("Hasło (PIN)", type="password")
            
        if st.button("ZALOGUJ SIĘ"):
            if not login_input or not pin_input:
                st.error("Wypełnij wszystkie pola.")
            else:
                df_konta['Login_clean'] = df_konta['Login'].astype(str).str.strip().str.lower()
                df_konta['PIN_clean'] = df_konta['PIN'].astype(str).str.split('.').str[0].str.strip()
                user_row = df_konta[(df_konta['Login_clean'] == login_input.strip().lower()) & (df_konta['PIN_clean'] == pin_input.strip())]
                
                if not user_row.empty:
                    znaleziona_rola = str(user_row.iloc[0]['Rola']).strip()
                    rzeczywisty_login = str(user_row.iloc[0]['Login']).strip()
                    cookie_controller.set("sqm_login", rzeczywisty_login, max_age=COOKIE_EXPIRY)
                    cookie_controller.set("sqm_role", znaleziona_rola, max_age=COOKIE_EXPIRY)
                    st.rerun()
                else:
                    st.error("Błędny login lub hasło.")

    elif rola_wybor == "📋 Tablica Eventu (Dla Ekipy)":
        lista_wydarzen = df_sloty['Event'].dropna().unique().tolist()
        wybrany_event = st.selectbox("Wybierz wydarzenie, na które jedziesz:", ["-- Wybierz --"] + lista_wydarzen)
        pin_grupy = st.text_input("PIN Ekipy (Otrzymany na WhatsApp):", type="password")
        
        if st.button("OTWÓRZ TABLICĘ ZBIORCZĄ"):
            if wybrany_event != "-- Wybierz --" and pin_grupy == st.secrets.get("team_pin", "1234"):
                cookie_controller.set("sqm_login", wybrany_event, max_age=COOKIE_EXPIRY)
                cookie_controller.set("sqm_role", "Team_Board", max_age=COOKIE_EXPIRY)
                st.rerun()
            else:
                st.error("Błędny PIN ekipy lub nie wybrano wydarzenia.")

    elif rola_wybor == "⚙️ Panel Koordynatora":
        admin_pass = st.text_input("Hasło Główne:", type="password")
        if st.button("WEJDŹ DO CMS"):
            if admin_pass == st.secrets.get("admin_password", "brak_hasla"):
                cookie_controller.set("sqm_login", "Administrator", max_age=COOKIE_EXPIRY)
                cookie_controller.set("sqm_role", "Admin", max_age=COOKIE_EXPIRY)
                st.rerun()
            else:
                st.error("Błędne hasło główne.")

# ==========================================
# EKRAN 2: ZALOGOWANY UŻYTKOWNIK
# ==========================================
else:
    col1, col2 = st.columns([3, 1])
    col1.success(f"Aktywna sesja: {saved_login} ({saved_role})")
    if col2.button("Zamknij widok / Wyloguj"):
        cookie_controller.remove("sqm_login")
        cookie_controller.remove("sqm_role")
        st.rerun()
        
    st.write("---")

    # ------------------------------------------
    # WIDOK: TABLICA ZBIORCZA EVENTU (PRO TABLE)
    # ------------------------------------------
    if saved_role == "Team_Board":
        st.write(f"### 📋 Harmonogram wyjazdowy: {saved_login}")
        
        df_event = df_sloty[df_sloty['Event'] == saved_login].copy()
        
        if df_event.empty:
            st.info("Brak przypisanych aut i slotów do tego wydarzenia.")
        else:
            # Filtrowanie archiwalnych slotów
            df_event['Czy_Aktywny'] = df_event['Data_Slotu'].apply(czy_slot_aktywny)
            pokaz_archiwalne = st.checkbox("Pokaż archiwalne (zakończone) sloty z poprzednich dni", value=False)
            
            if not pokaz_archiwalne:
                df_event = df_event[df_event['Czy_Aktywny'] == True]
                if df_event.empty:
                    st.success("Wszystkie sloty dla tego eventu zostały już zrealizowane w minionych dniach.")

            if not df_event.empty:
                # Zabezpieczenie przed brakiem kolumn
                oczekiwane_kolumny = ['Data_Slotu', 'Auto', 'Nazwisko', 'Nr_Referencyjny', 'Notatki', 'Link_PDF']
                for kol in oczekiwane_kolumny:
                    if kol not in df_event.columns:
                        df_event[kol] = ""  
                
                df_tabela = df_event[oczekiwane_kolumny].copy()
                df_tabela.columns = ['🗓️ Termin', '🚐 Auto', '👨‍🔧 Kierowca / Technik', '🔑 Brama / Nr Ref', '📝 Notatki / Info', 'PDF']
                
                # Wyświetlanie PRO Tabeli Streamlita
                st.dataframe(
                    df_tabela,
                    column_config={
                        "PDF": st.column_config.LinkColumn(
                            "📄 Dokument", display_text="Otwórz plik"
                        )
                    },
                    hide_index=True,
                    use_container_width=True
                )
                st.caption("Przesuń tabelę w prawo, aby zobaczyć notatki i linki do dokumentów. Kliknij nagłówek kolumny, aby posortować.")

    # ------------------------------------------
    # WIDOK ADMINA (CMS)
    # ------------------------------------------
    elif saved_role == "Admin":
        tryb_admina = st.radio("Wybierz akcję:", ["➕ Dodaj nowy slot", "✏️ Edytuj / Usuń istniejący"], horizontal=True)
        
        if tryb_admina == "➕ Dodaj nowy slot":
            with st.form("add_form", clear_on_submit=True):
                new_event = st.text_input("Nazwa Eventu")
                lista_pracownikow = df_konta[df_konta['Rola'].isin(['Technik', 'Kierowca'])]['Login'].tolist()
                new_nazwisko = st.selectbox("Przypisz pracownika", ["-- Wpisz ręcznie poniżej --"] + lista_pracownikow)
                new_nazwisko_reczne = st.text_input("...lub wpisz nazwisko ręcznie")
                
                new_auto = st.text_input("Auto / Rejestracja (np. Sprinter PO 12345)")
                new_data = st.text_input("Data i godzina (np. 15.09.2026, 14:00)")
                new_ref = st.text_input("Numer Referencyjny / Brama")
                new_notatki = st.text_area("Notatki operacyjne")
                new_file = st.file_uploader("Załącz plik (Opcjonalnie)", type=['pdf', 'jpg', 'png'])
                
                submitted = st.form_submit_button("ZAPISZ SLOT W BAZIE")
                
                if submitted:
                    docelowe_nazwisko = new_nazwisko_reczne if new_nazwisko_reczne else new_nazwisko
                    if not new_event or docelowe_nazwisko == "-- Wpisz ręcznie poniżej --":
                        st.error("Event oraz przypisany pracownik są obowiązkowe!")
                    else:
                        with st.spinner("Przetwarzanie..."):
                            final_link = ""
                            if new_file is not None:
                                try: final_link = upload_to_drive(new_file, new_event, docelowe_nazwisko)
                                except Exception as e: st.error(f"Błąd dysku: {e}")
                            try:
                                nowy_wiersz = pd.DataFrame([{
                                    "Event": new_event, "Nazwisko": docelowe_nazwisko, 
                                    "Auto": new_auto, "Data_Slotu": new_data, "Nr_Referencyjny": new_ref,
                                    "Notatki": new_notatki, "Link_PDF": final_link
                                }])
                                zaktualizowana_baza = pd.concat([df_sloty, nowy_wiersz], ignore_index=True)
                                conn.update(worksheet="Dostep", data=zaktualizowana_baza)
                                st.cache_data.clear()
                                st.success("Dodano slot!")
                                st.rerun()
                            except Exception as e: st.error(f"Błąd bazy: {e}")

        elif tryb_admina == "✏️ Edytuj / Usuń istniejący":
            if df_sloty.empty:
                st.warning("Baza slotów jest pusta.")
            else:
                opcje_wyboru = df_sloty.index.tolist()
                def format_opcji(i):
                    auto_info = df_sloty.loc[i, 'Auto'] if 'Auto' in df_sloty.columns else 'Brak'
                    return f"{df_sloty.loc[i, 'Event']} | {df_sloty.loc[i, 'Nazwisko']} | Auto: {auto_info} | {df_sloty.loc[i, 'Data_Slotu']}"
                
                wybrany_index = st.selectbox("Wybierz wpis:", opcje_wyboru, format_func=format_opcji)
                
                if wybrany_index is not None:
                    row = df_sloty.loc[wybrany_index]
                    with st.form("edit_form"):
                        ed_event = st.text_input("Event", value=str(row.get('Event', '')))
                        ed_nazw = st.text_input("Nazwisko", value=str(row.get('Nazwisko', '')))
                        ed_auto = st.text_input("Auto / Rejestracja", value=str(row.get('Auto', '')))
                        ed_data = st.text_input("Data i godzina", value=str(row.get('Data_Slotu', '')))
                        ed_ref = st.text_input("Nr Ref / Brama", value=str(row.get('Nr_Referencyjny', '')))
                        ed_notatki = st.text_area("Notatki", value=str(row.get('Notatki', '')))
                        
                        obecny_link = row.get('Link_PDF', '')
                        usun_plik = False
                        if pd.notna(obecny_link) and str(obecny_link).strip() != "":
                            st.info("Zapisany plik PDF jest aktywny.")
                            usun_plik = st.checkbox("Usuń obecny plik z rekordu")
                            
                        ed_file = st.file_uploader("Nadpisz nowym plikiem", type=['pdf', 'jpg', 'png'])
                        zapisz_edycje = st.form_submit_button("💾 ZAPISZ ZMIANY")
                        
                        if zapisz_edycje:
                            with st.spinner("Zapisywanie..."):
                                nowy_link = "" if usun_plik else obecny_link
                                if ed_file is not None:
                                    try: nowy_link = upload_to_drive(ed_file, ed_event, ed_nazw)
                                    except: pass
                                
                                df_sloty.at[wybrany_index, 'Event'] = ed_event
                                df_sloty.at[wybrany_index, 'Nazwisko'] = ed_nazw
                                df_sloty.at[wybrany_index, 'Auto'] = ed_auto
                                df_sloty.at[wybrany_index, 'Data_Slotu'] = ed_data
                                df_sloty.at[wybrany_index, 'Nr_Referencyjny'] = ed_ref
                                df_sloty.at[wybrany_index, 'Notatki'] = ed_notatki
                                df_sloty.at[wybrany_index, 'Link_PDF'] = nowy_link
                                
                                conn.update(worksheet="Dostep", data=df_sloty)
                                st.cache_data.clear()
                                st.success("Zapisano!")
                                st.rerun()

                    if st.button("🗑️ USUŃ TRWALE SLOT", type="primary"):
                        df_sloty = df_sloty.drop(index=wybrany_index).reset_index(drop=True)
                        conn.update(worksheet="Dostep", data=df_sloty)
                        st.cache_data.clear()
                        st.success("Usunięto.")
                        st.rerun()

    # ------------------------------------------
    # WIDOK TECHNIKA / KIEROWCY (TYLKO OSOBISTE SLOTY)
    # ------------------------------------------
    elif saved_role in ["Technik", "Kierowca"]:
        df_sloty['Nazwisko_clean'] = df_sloty['Nazwisko'].astype(str).str.strip().str.lower()
        moje_sloty = df_sloty[df_sloty['Nazwisko_clean'] == str(saved_login).lower().strip()].copy()
        
        if moje_sloty.empty:
            st.info("Nie masz aktualnie przypisanych żadnych slotów.")
        else:
            # Filtrowanie archiwalnych dla prywatnego widoku
            moje_sloty['Czy_Aktywny'] = moje_sloty['Data_Slotu'].apply(czy_slot_aktywny)
            pokaz_archiwalne_moje = st.checkbox("Pokaż moje archiwalne (zakończone) wyjazdy", value=False)
            
            if not pokaz_archiwalne_moje:
                moje_sloty = moje_sloty[moje_sloty['Czy_Aktywny'] == True]
                
            if moje_sloty.empty:
                 st.success("Wszystkie Twoje zadania zostały już zrealizowane.")
            else:
                for index, row in moje_sloty.iterrows():
                    event_name = row.get('Event', 'Nieznany Event')
                    auto = row.get('Auto', '')
                    ref_num = row.get('Nr_Referencyjny', 'Brak numeru ref.')
                    data_slotu = row.get('Data_Slotu', 'Do ustalenia')
                    notatki = row.get('Notatki', '')
                    link_pdf = row.get('Link_PDF', None)
                    
                    with st.container():
                        st.markdown(f"### 📍 {event_name}")
                        st.markdown(f"**🗓 Termin:** `{data_slotu}`")
                        st.markdown(f"**🔑 Brama / Nr Ref:** `{ref_num}`")
                        if pd.notna(auto) and str(auto).strip():
                            st.markdown(f"**🚐 Auto:** `{auto}`")
                        
                        if pd.notna(notatki) and str(notatki).strip():
                            st.info(f"**Notatka:** {notatki}")
                        
                        if pd.notna(link_pdf) and str(link_pdf).strip() != "":
                            st.link_button(f"📄 Pobierz dokumentację", str(link_pdf))
                        st.markdown("---")
