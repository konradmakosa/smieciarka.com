# Harmonogram Wywozu Odpadów - Warszawa → Google Calendar

Automatyczna synchronizacja harmonogramu wywozu odpadów z [warszawa19115.pl](https://warszawa19115.pl) do Google Calendar.

## Funkcjonalność

- **Scrapowanie**: Pobiera dane o wywozie odpadów z oficjalnej platformy MPO Warszawa
- **Synchronizacja**: Dodaje terminy do Google Calendar przez API lub wysyła plik `.ics` emailem
- **Wielokalendarzowość**: Obsługa kilku kalendarzy (np. Twój i żony)
- **Email z .ics**: Alternatywna metoda - wysyła plik kalendarza do dodania ręcznie
- **Przypomnienia**: Dwa przypomnienia w pliku .ics (2 dni przed i dzień przed o 9:00)
- **Automatyzacja**: Uruchamia się raz na tydzień w poniedziałek o 6:00 przez GitHub Actions

## Wymagane typy odpadów

- Bio restauracyjne (BG)
- Bio (BK)
- Metale i tworzywa sztuczne (MT)
- Papier (OP)
- Szkło (OS)
- Zielone (OZ)
- Odpady wielkogabarytowe (WG)
- Odpady zmieszane (ZM)

## Konfiguracja

### 1. Uzyskaj geolocation_id dla swojego adresu

Możesz użyć adresu ulicy lub bezpośrednio `geolocation_id`:

```bash
# Instalacja zależności
pip install requests

# Testowe sprawdzenie ID
python -c "
import requests
url = 'https://warszawa19115.pl/harmonogramy-wywozu-odpadow'
params = {
    'p_p_id': 'portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ',
    'p_p_lifecycle': '2',
    'p_p_resource_id': 'autocompleteResource',
    '_portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ_name': 'TWÓJ ADRES, np. MARSZAŁKOWSKA 84/92'
}
session = requests.Session()
session.get(url)
resp = session.get(url, params=params)
print(resp.json())
"
```

### 2. Skonfiguruj Google Calendar API

1. Wejdź w [Google Cloud Console](https://console.cloud.google.com/)
2. Utwórz nowy projekt
3. Włącz **Google Calendar API**
4. Utwórz **Service Account** (Konto usługi):
   - IAM i administracja → Konta usług → Utwórz
   - Nadaj rolę "Edytor" dla Calendar API
5. Wygeneruj klucz JSON dla konta usługi
6. **Udostępnij kalendarze**:
   - Wejdź w ustawienia swojego kalendarza Google → "Udostępnij dla konkretnych osób"
   - Dodaj email konta usługi (wygląda jak: `nazwa@projekt.iam.gserviceaccount.com`)
   - Nadaj uprawnienia do wprowadzania zmian
   - Powtórz dla kalendarza żony

### 3. Dodaj sekrety do GitHub

W repozytorium: **Settings → Secrets and variables → Actions → New repository secret**

| Nazwa sekretu | Wartość |
|--------------|---------|
| `STREET_ADDRESS` | Twój adres (opcjonalnie, np. `MARSZAŁKOWSKA 84/92, 00-514 Śródmieście`) |
| `GEOLOCATION_ID` | ID geolokacji (opcjonalnie, np. `3830963`) |
| `GOOGLE_CREDENTIALS_JSON` | Cała zawartość pliku JSON z kluczem service account |
| `CALENDAR_IDS` | ID kalendarzy oddzielone przecinkami (np. `primary,abc123@group.calendar.google.com`) |

**Uwaga**: Użyj `STREET_ADDRESS` LUB `GEOLOCATION_ID` (nie obu na raz). Jeśli masz już geolocation_id, użyj go - będzie szybciej.

### Opcjonalnie: Wysyłka email z plikiem .ics

Jako dodatkowa metoda (backup), możesz otrzymywać email z plikiem `.ics`, który można dodać do dowolnego kalendarza:

| Nazwa sekretu | Wartość |
|--------------|---------|
| `EMAIL_RECIPIENTS` | Adresy email oddzielone przecinkami (np. `konrad.makosa@gmail.com,makosa.kasia@gmail.com`) |
| `SMTP_USERNAME` | Email nadawcy (np. `konrad.makosa@gmail.com`) |
| `SMTP_PASSWORD` | Hasło aplikacji Gmail (nie zwykłe hasło!) - [jak wygenerować](https://support.google.com/accounts/answer/185833) |
| `SMTP_SERVER` | `smtp.gmail.com` (domyślnie) |
| `SMTP_PORT` | `587` (domyślnie) |

**Jak wygenerować hasło aplikacji Gmail:**
1. Wejdź w [Google Account](https://myaccount.google.com/) → Security
2. Włącz 2-Step Verification
3. Wygeneruj App Password dla "Mail"
4. Użyj tego hasła jako `SMTP_PASSWORD`

### 4. Ręczne uruchomienie (test)

```bash
# Lokalne uruchomienie (wymaga ustawionych zmiennych środowiskowych)
export STREET_ADDRESS="MARSZAŁKOWSKA 84/92, 00-514 Śródmieście"
export GOOGLE_CREDENTIALS_JSON='{zawartość pliku json}'
export CALENDAR_IDS="primary,xyz@group.calendar.google.com"

python main.py
```

### 5. Ręczne uruchomienie w GitHub Actions

Wejdź w: **Actions → Scrape Warsaw Waste Schedule → Run workflow**

## Struktura projektu

```
.
├── .github/
│   └── workflows/
│       └── scrape.yml      # Workflow GitHub Actions
├── scraper.py              # Logika scrapowania warszawa19115.pl
├── calendar_sync.py        # Synchronizacja z Google Calendar
├── main.py                 # Główny skrypt
├── requirements.txt        # Zależności Python
└── README.md              # Ta instrukcja
```

## Rozwiązywanie problemów

### Nie znaleziono adresu
- Sprawdź czy adres jest wpisany dokładnie jak na stronie warszawa19115.pl
- Użyj pełnego adresu z kodem pocztowym

### Błąd autentykacji Google
- Upewnij się, że Google Calendar API jest włączone w projekcie
- Sprawdź czy konto usługi ma uprawnienia do edycji kalendarzy
- Zweryfikuj czy email konta usługi został dodany do udostępnionych kalendarzy

### Brak uprawnień do kalendarza
- Kalendarz musi być udostępniony kontu usługi z uprawnieniami "wprowadzanie zmian"
- Sprawdź czy ID kalendarza jest poprawne (dla głównego kalendarza użyj `primary`)

## Źródła

- Scraper oparty na kodzie z [hacs_waste_collection_schedule](https://github.com/mampfes/hacs_waste_collection_schedule)
- Alternatywny projekt: [warsaw_garbage_collection_schedule](https://github.com/srozb/warsaw_garbage_collection_schedule)
