import streamlit as st
import pandas as pd
import io
import base64
import re
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
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

# --- FUNKCJE POMOCNICZE (DATY I GANTT) ---
def czy_slot_aktywny(data_str):
    if pd.isna(data_str) or str(data_str).strip() == "": return True 
    match_pl = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(data_str))
    if match_pl:
        try:
            return datetime(int(match_pl.group(3)), int(match_pl.group(2)), int(match_pl.group(1))).date() >= datetime.today().date()
        except: pass
    match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(data_str))
    if match_iso:
        try:
            return datetime(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3))).date() >= datetime.today().date()
        except: pass
    return True

def parse_dates_for_gantt(data_str):
    if pd.isna(data_str): return None, None
    s = str(data_str)
    m2 = re.search(r'(\d{2})\.(\d{2})\.(\d{4})[^\d]*(\d{2}):(\d{2})[^\d]*(\d{2})\.(\d{2})\.(\d{4})[^\d]*(\d{2}):(\d{2})', s)
    if m2:
        try:
            start = datetime(int(m2.group(3)), int(m2.group(2)), int(m2.group(1)), int(m2.group(4)), int(m2.group(5)))
            end = datetime(int(m2.group(8)), int(m2.group(7)), int(m2.group(6)), int(m2.group(9)), int(m2.group(10)))
            return start, end
        except: pass
    m1 = re.search(r'(\d{2})\.(\d{2})\.(\d{4})[^\d]*(\d{2}):(\d{2})[^\d]*(\d{2}):(\d{2})', s)
    if m1:
        try:
            start = datetime(int(m1.group(3)), int(m1.group(2)), int(m1.group(1)), int(m1.group(4)), int(m1.group(5)))
            end = datetime(int(m1.group(3)), int(m1.group(2)), int(m1.group(1)), int(m1.group(6)), int(m1.group(7)))
            if end <= start: end += timedelta(days=1)
            return start, end
        except: pass
    return None, None

# --- GENERATOR PDF (TRYB OFFLINE) ---
def generate_offline_pdf(df_slots, title_text):
    def clean_pl(text):
        pl_chars = {'ą':'a','ć':'c','ę':'e','ł':'l','ń':'n','ó':'o','ś':'s','ź':'z','ż':'z',
                    'Ą':'A','Ć':'C','Ę':'E','Ł':'L','Ń':'N','Ó':'O','Ś':'S','Ź':'Z','Ż':'Z'}
        for k, v in pl_chars.items():
            text = str(text).replace(k, v)
        return text

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, clean_pl(title_text), ln=True, align="C")
    pdf.ln(5)
    
    for index, row in df_slots.iterrows():
        event = row.get('Event', '')
        auto = row.get('Auto', '')
        ref_num = row.get('Nr_Referencyjny', '')
        data_slotu = row.get('Data_Slotu', '')
        notatki = row.get('Notatki', '')
        
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 8, f"Event: {clean_pl(event)}", ln=True)
        pdf.set_font("Helvetica", '', 11)
        pdf.cell(0, 6, f"Termin: {clean_pl(data_slotu)}", ln=True)
        pdf.cell(0, 6, f"Brama / Nr Ref: {clean_pl(ref_num)}", ln=True)
        if str(auto).strip():
            pdf.cell(0, 6, f"Auto: {clean_pl(auto)}", ln=True)
        if str(notatki).strip():
            pdf.multi_cell(0, 6, f"Notatka: {clean_pl(notatki)}")
        
        pdf.ln(5)
        pdf.cell(0, 0, "", "T") 
        pdf.ln(5)
        
    pdf_out = pdf.output(dest='S')
    if isinstance(pdf_out, bytearray): return bytes(pdf_out)
    elif isinstance(pdf_out, str): return pdf_out.encode('latin-1')
    return bytes(pdf_out)

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
        pin_grupy = st.text_input("PIN Ekipy (Podaj hasło):", type="password")
        
        if st.button("OTWÓRZ TABLICĘ ZBIORCZĄ"):
            if wybrany_event != "-- Wybierz --":
                df_konta['Rola_clean'] = df_konta['Rola'].astype(str).str.strip().str.lower()
                df_konta['Login_clean'] = df_konta['Login'].astype(str).str.strip().str.lower()
                df_konta['PIN_clean'] = df_konta['PIN'].astype(str).str.split('.').str[0].str.strip()
                
                # Szukamy pinu ściśle dedykowanego pod wybrany z listy event
                pin_eventu = df_konta[(df_konta['Rola_clean'] == 'ekipa') & (df_konta['Login_clean'] == wybrany_event.strip().lower())]
                
                if not pin_eventu.empty:
                    poprawny_pin = pin_eventu.iloc[0]['PIN_clean']
                    if pin_grupy.strip() == poprawny_pin:
                        cookie_controller.set("sqm_login", wybrany_event, max_age=COOKIE_EXPIRY)
                        cookie_controller.set("sqm_role", "Team_Board", max_age=COOKIE_EXPIRY)
                        st.rerun()
                    else:
                        st.error("Błędny PIN ekipy dla tego wydarzenia.")
                else:
                    st.error(f"Koordynator nie ustalił jeszcze numeru PIN dla eventu: {wybrany_event}.")
            else:
                st.error("Najpierw wybierz wydarzenie z listy.")

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
    col1.success(f"Aktywna sesja: {saved_login}")
    if col2.button("Zamknij widok / Wyloguj"):
        cookie_controller.remove("sqm_login")
        cookie_controller.remove("sqm_role")
        st.rerun()
        
    st.write("---")

    # ------------------------------------------
    # WIDOK: TABLICA ZBIORCZA EVENTU (PRO KARTY)
    # ------------------------------------------
    if saved_role == "Team_Board":
        st.write(f"### 📋 Harmonogram: {saved_login}")
        
        df_event = df_sloty[df_sloty['Event'] == saved_login].copy()
        
        if df_event.empty:
            st.info("Brak przypisanych aut i slotów do tego wydarzenia.")
        else:
            df_event['Czy_Aktywny'] = df_event['Data_Slotu'].apply(czy_slot_aktywny)
            pokaz_archiwalne = st.checkbox("Pokaż archiwalne (wczorajsze) sloty", value=False)
            
            if not pokaz_archiwalne:
                df_event = df_event[df_event['Czy_Aktywny'] == True]
                
            if not df_event.empty:
                df_event = df_event.fillna("")
                
                # ZBIORCZY PDF DLA EKIPY (Tylko dane z harmonogramu, bez linków do załączników)
                pdf_bytes = generate_offline_pdf(df_event, f"Harmonogram SQM - {saved_login}")
                st.download_button(
                    label="📥 Pobierz plan offline (PDF - Brak Zasięgu)",
                    data=pdf_bytes,
                    file_name=f"Harmonogram_{str(saved_login).replace(' ','_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.write("") 
                
                for index, row in df_event.sort_values(by='Data_Slotu').iterrows():
                    kierowca = row.get('Nazwisko', 'Nieprzypisany')
                    auto = row.get('Auto', '')
                    ref_num = row.get('Nr_Referencyjny', '')
                    data_slotu = row.get('Data_Slotu', 'Do ustalenia')
                    notatki = row.get('Notatki', '')
                    
                    with st.container():
                        st.markdown(f"### 🗓️ {data_slotu}")
                        colA, colB = st.columns(2)
                        with colA:
                            st.markdown(f"**👨‍🔧 Kto jedzie:** `{kierowca}`")
                            st.markdown(f"**🔑 Brama/Ref:** `{ref_num if ref_num else 'Brak'}`")
                        with colB:
                            st.markdown(f"**🚐 Auto:** `{auto if auto else 'Nie podano'}`")
                                
                        if str(notatki).strip():
                            st.info(f"**Ważne info:** {notatki}")
                        st.divider()
            else:
                st.success("Wszystkie sloty dla tego eventu zostały już zrealizowane!")

    # ------------------------------------------
    # WIDOK ADMINA (CMS + GANTT)
    # ------------------------------------------
    elif saved_role == "Admin":
        tryb_admina = st.radio("Wybierz moduł:", ["📊 Wykres Gantta", "➕ Dodaj nowy slot", "✏️ Edytuj / Usuń istniejący"], horizontal=True)
        st.write("---")
        
        if tryb_admina == "📊 Wykres Gantta":
            st.write("### 📈 Harmonogram operacyjny (Gantt)")
            if df_sloty.empty:
                st.info("Baza jest pusta.")
            else:
                lista_wydarzen = df_sloty['Event'].dropna().unique().tolist()
                event_gantt = st.selectbox("Wybierz wydarzenie do analizy czasowej:", lista_wydarzen)
                
                df_g = df_sloty[df_sloty['Event'] == event_gantt].copy()
                gantt_data = []
                
                for i, row in df_g.iterrows():
                    start, end = parse_dates_for_gantt(row.get('Data_Slotu', ''))
                    if start and end:
                        nazw = row.get('Nazwisko', 'Nieznany')
                        auto = row.get('Auto', '')
                        label = f"{nazw} ({auto})" if str(auto).strip() else nazw
                        gantt_data.append(dict(Task=label, Start=start, Finish=end, Ref=row.get('Nr_Referencyjny','')))
                
                if gantt_data:
                    df_plot = pd.DataFrame(gantt_data)
                    fig = px.timeline(df_plot, x_start="Start", x_end="Finish", y="Task", color="Task", hover_data=["Ref"])
                    fig.update_yaxes(autorange="reversed")
                    fig.update_layout(
                        showlegend=False, 
                        height=200 + (len(gantt_data)*35),
                        paper_bgcolor='rgba(0,0,0,0)', 
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    fig.update_xaxes(tickfont=dict(color='gray'))
                    fig.update_yaxes(tickfont=dict(color='black'))
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Nie znaleziono odpowiednio sformatowanych dat dla tego eventu (wymagany format to np. '24.08.2026, 08:00 - 11:00').")

        elif tryb_admina == "➕ Dodaj nowy slot":
            with st.form("add_form", clear_on_submit=True):
                new_event = st.text_input("Nazwa Eventu")
                lista_pracownikow = df_konta[df_konta['Rola'].isin(['Technik', 'Kierowca'])]['Login'].tolist()
                new_nazwisko = st.selectbox("Przypisz pracownika", ["-- Wpisz ręcznie poniżej --"] + lista_pracownikow)
                new_nazwisko_reczne = st.text_input("...lub wpisz nazwisko ręcznie")
                
                new_auto = st.text_input("Auto / Rejestracja")
                new_data = st.text_input("Data i godzina (np. 15.09.2026, 14:00 - 17:00)")
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
                df_sloty = df_sloty.fillna("")
                opcje_wyboru = df_sloty.index.tolist()
                def format_opcji(i):
                    auto_info = df_sloty.loc[i, 'Auto'] if 'Auto' in df_sloty.columns and df_sloty.loc[i, 'Auto'] else 'Brak'
                    return f"{df_sloty.loc[i, 'Event']} | {df_sloty.loc[i, 'Nazwisko']} | Auto: {auto_info} | {df_sloty.loc[i, 'Data_Slotu']}"
                
                wybrany_index = st.selectbox("Wybierz wpis:", opcje_wyboru, format_func=format_opcji)
                
                if wybrany_index is not None:
                    row = df_sloty.loc[wybrany_index]
                    with st.form("edit_form"):
                        ed_event = st.text_input("Event", value=str(row.get('Event', '')))
                        ed_nazw = st.text_input("Nazwisko", value=str(row.get('Nazwisko', '')))
                        ed_auto = st.text_input("Auto / Rejestracja", value=str(row.get('Auto', '')))
                        ed_data = st.text_input("Data i godzina (np. 15.09.2026, 14:00 - 17:00)", value=str(row.get('Data_Slotu', '')))
                        ed_ref = st.text_input("Nr Ref / Brama", value=str(row.get('Nr_Referencyjny', '')))
                        ed_notatki = st.text_area("Notatki", value=str(row.get('Notatki', '')))
                        
                        obecny_link = row.get('Link_PDF', '')
                        usun_plik = False
                        if str(obecny_link).strip() != "":
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
        df_sloty = df_sloty.fillna("")
        df_sloty['Nazwisko_clean'] = df_sloty['Nazwisko'].astype(str).str.strip().str.lower()
        moje_sloty = df_sloty[df_sloty['Nazwisko_clean'] == str(saved_login).lower().strip()].copy()
        
        if moje_sloty.empty:
            st.info("Nie masz aktualnie przypisanych żadnych slotów.")
        else:
            moje_sloty['Czy_Aktywny'] = moje_sloty['Data_Slotu'].apply(czy_slot_aktywny)
            pokaz_archiwalne_moje = st.checkbox("Pokaż moje archiwalne (zakończone) wyjazdy", value=False)
            
            if not pokaz_archiwalne_moje:
                moje_sloty = moje_sloty[moje_sloty['Czy_Aktywny'] == True]
                
            if not moje_sloty.empty:
                pdf_bytes = generate_offline_pdf(moje_sloty, f"Harmonogram - {saved_login}")
                st.download_button(
                    label="📥 Pobierz plan offline (PDF - Brak Zasięgu)",
                    data=pdf_bytes,
                    file_name=f"Harmonogram_{str(saved_login).replace(' ','_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.write("") 
                
                for index, row in moje_sloty.sort_values(by='Data_Slotu').iterrows():
                    event_name = row.get('Event', 'Nieznany Event')
                    auto = row.get('Auto', '')
                    ref_num = row.get('Nr_Referencyjny', '')
                    data_slotu = row.get('Data_Slotu', 'Do ustalenia')
                    notatki = row.get('Notatki', '')
                    link_pdf = row.get('Link_PDF', '')
                    
                    with st.container():
                        st.markdown(f"### 📍 {event_name}")
                        st.markdown(f"**🗓 Termin:** `{data_slotu}`")
                        st.markdown(f"**🔑 Brama / Nr Ref:** `{ref_num if ref_num else 'Brak'}`")
                        if auto:
                            st.markdown(f"**🚐 Auto:** `{auto}`")
                        
                        if notatki:
                            st.info(f"**Notatka:** {notatki}")
                        
                        if str(link_pdf).strip():
                            st.link_button(f"📄 Pobierz wjazdówkę", str(link_pdf))
                        st.markdown("---")
            else:
                 st.success("Wszystkie Twoje zadania zostały już zrealizowane.")
