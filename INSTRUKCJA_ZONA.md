# Instrukcja dla żony - udostępnienie kalendarza

## Co zrobić (gdy będziesz miał dostęp do komputera żony):

### Krok 1: Wejdź w Google Calendar
1. Otwórz przeglądarkę na komputerze żony
2. Wejdź na: https://calendar.google.com
3. Zaloguj się na konto: **makosa.kasia@gmail.com**

### Krok 2: Udostępnij kalendarz dla Ciebie (Konrad)
1. Z lewej strony znajdź główny kalendarz (zazwyczaj "Mój kalendarz" lub "makosa.kasia@gmail.com")
2. Kliknij **trzy kropki** obok nazwy kalendarza
3. Wybierz **"Ustawienia i udostępnianie"**
4. Przewiń do sekcji **"Udostępnij dla konkretnych osób"**
5. Kliknij **"Dodaj osoby"**
6. Wpisz email: **konrad.makosa@gmail.com**
7. Nadaj uprawnienia: **"Wprowadzanie zmian w wydarzeniach i zarządzanie udostępnianiem"**
8. Kliknij **"Wyślij"**

### Krok 3: Udostępnij kalendarz dla konta usługi (scraper)
1. W tym samym oknie (w sekcji "Udostępnij dla konkretnych osób")
2. Kliknij **"Dodaj osoby"**
3. Wpisz email: **odpady-scraper@odpady-499810.iam.gserviceaccount.com**
4. Nadaj uprawnienia: **"Wprowadzanie zmian w wydarzeniach i zarządzanie udostępnianiem"**
5. Kliknij **"Wyślij"**

### Krok 4: Pobierz ID kalendarza (dla Ciebie - Konrad)
1. W tym samym oknie ustawień kalendarza
2. Przewiń do góry - sekcja **"Integracja kalendarza"**
3. Skopiuj **"Identyfikator kalendarza"**
   - Wygląda jak: `abc123def456@group.calendar.google.com`
   - LUB dla głównego kalendarza: `makosa.kasia@gmail.com`
4. Prześlij ten ID na Slack/email do Konrada

---

## Podsumowanie - kto ma dostęp do kalendarza żony:

| Osoba | Email | Uprawnienia |
|-------|-------|-------------|
| Konrad (Ty) | konrad.makosa@gmail.com | Wprowadzanie zmian |
| Scraper (automat) | odpady-scraper@odpady-499810.iam.gserviceaccount.com | Wprowadzanie zmian |

## Co dalej (po udostępnieniu):

Konrad musi:
1. Dodać do GitHub Secrets: `CALENDAR_IDS=primary,ID_KALENDARZA_ZONY`
2. Uruchomić workflow w GitHub Actions

---

**Notatka:** Jeśli żona nie chce udostępniać Ci swojego głównego kalendarza, możecie:
- Utworzyć **nowy kalendarz** tylko dla odpadów
- Udostępnić tylko ten nowy kalendarz
