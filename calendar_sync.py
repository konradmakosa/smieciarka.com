"""
Synchronizacja z Google Calendar
"""

import logging
from datetime import datetime, timedelta
from typing import List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from scraper import WasteCollection

_LOGGER = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']


class CalendarSync:
    def __init__(self, credentials_json: str, calendar_ids: List[str]):
        """
        credentials_json: ścieżka do pliku z credentials lub zawartość jako string
        calendar_ids: lista ID kalendarzy (Twój i żony)
        """
        self.calendar_ids = calendar_ids
        self.service = self._authenticate(credentials_json)

    def _authenticate(self, credentials_json: str):
        """Autentykacja z Google Calendar API"""
        import json
        import tempfile
        import os

        # Sprawdź czy to ścieżka do pliku czy zawartość
        if os.path.exists(credentials_json):
            creds_path = credentials_json
        else:
            # Zapisz credentials do tymczasowego pliku
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(credentials_json)
                creds_path = f.name

        credentials = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES
        )

        # Cleanup temp file
        if not os.path.exists(credentials_json):
            os.unlink(creds_path)

        return build('calendar', 'v3', credentials=credentials, cache_discovery=False)

    def sync_collections(self, collections: List[WasteCollection], days_ahead: int = 30):
        """
        Synchronizuje terminy wywozu odpadów z kalendarzem
        Usuwa stare eventy i dodaje nowe z harmonogramu
        """
        now = datetime.utcnow()
        time_min = now.isoformat() + 'Z'
        time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'

        for calendar_id in self.calendar_ids:
            _LOGGER.info(f"Synchronizacja kalendarza: {calendar_id}")

            # Usuń stare eventy o odpadach
            self._delete_old_waste_events(calendar_id, time_min, time_max)

            # Dodaj nowe eventy
            self._add_collection_events(calendar_id, collections)

    def _delete_old_waste_events(self, calendar_id: str, time_min: str, time_max: str):
        """Usuwa istniejące eventy o odpadach z kalendarza"""
        events_result = self.service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            q='Wywóz odpadów',
            singleEvents=True
        ).execute()

        events = events_result.get('items', [])
        for event in events:
            try:
                self.service.events().delete(
                    calendarId=calendar_id,
                    eventId=event['id']
                ).execute()
                _LOGGER.info(f"Usunięto event: {event.get('summary', 'unknown')}")
            except Exception as e:
                _LOGGER.error(f"Błąd usuwania eventu: {e}")

    def _add_collection_events(self, calendar_id: str, collections: List[WasteCollection]):
        """Dodaje eventy z harmonogramu wywozu odpadów"""
        for collection in collections:
            event = {
                'summary': f'Wywóz odpadów: {collection.waste_type}',
                'description': f'Frakcja: {collection.waste_type}\nAutomatycznie dodane przez scraper',
                'start': {
                    'date': collection.date.isoformat(),
                    'timeZone': 'Europe/Warsaw',
                },
                'end': {
                    'date': collection.date.isoformat(),
                    'timeZone': 'Europe/Warsaw',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 60 * 24},  # dzień wcześniej
                        {'method': 'popup', 'minutes': 60 * 2},   # 2h przed
                    ],
                },
            }

            try:
                event = self.service.events().insert(calendarId=calendar_id, body=event).execute()
                _LOGGER.info(f'Dodano event: {event.get("summary")} na {collection.date}')
            except Exception as e:
                _LOGGER.error(f"Błąd dodawania eventu: {e}")
