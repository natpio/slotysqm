import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Konfiguracja strony
st.set_page_config(page_title="Portal Technika", page_icon="📦", layout="centered")

# Pobranie danych z Google Sheets
# Upewnij się, że w secrets.toml masz skonfigurowane połączenie GSheets
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(worksheet="Dostep", ttl=60) # ttl=60 odświeża cache co minutę

# Interfejs logowania
st.title("📦 Panel Technika")
st.write("Wybierz event i podaj swoje dane, aby uzyskać dostęp do slotów i notatek.")

# Pobranie unikalnej listy eventów (pomijanie pustych)
lista_eventow = df['Event'].dropna().unique().tolist()
lista_eventow.insert(0, "--- Wybierz ---")

# Formularz logowania
with st.container():
    event = st.selectbox("Wybierz event", lista_eventow)
    nazwisko = st.text_input("Nazwisko")
    # type="password" ukrywa wpisywane znaki
    pin = st.text_input("6-cyfrowe hasło", type="password", max_chars=6)
    
    zaloguj = st.button("Zaloguj", type="primary", use_container_width=True)

# Logika weryfikacji
if zaloguj:
    if event == "--- Wybierz ---" or not nazwisko or not pin:
        st.warning("Proszę wypełnić wszystkie pola.")
    else:
        # Filtrowanie DataFrame (case-insensitive dla nazwiska, traktowanie PINu jako string)
        user_data = df[
            (df['Event'] == event) & 
            (df['Nazwisko'].astype(str).str.lower() == nazwisko.lower()) & 
            (df['PIN'].astype(str) == pin)
        ]
        
        if not user_data.empty:
            st.success(f"Witaj, {nazwisko.title()}! Zalogowano pomyślnie.")
            st.divider()
            
            # Ekstrakcja danych dla zalogowanego technika
            notatki = user_data.iloc[0]['Notatki']
            link_pdf = user_data.iloc[0]['Link_PDF']
            
            st.subheader("📝 Notatki operacyjne")
            st.info(notatki if pd.notna(notatki) else "Brak dodatkowych notatek do tego eventu.")
            
            st.subheader("📄 Pliki do pobrania (Sloty)")
            if pd.notna(link_pdf):
                # Nowoczesny przycisk linkujący (dostępny w nowszych wersjach Streamlit)
                st.link_button("Otwórz / Pobierz PDF (Google Drive)", link_pdf)
            else:
                st.warning("Brak przypisanego pliku PDF.")
                
        else:
            st.error("Nieprawidłowe dane. Sprawdź wybrany event, nazwisko oraz PIN.")
