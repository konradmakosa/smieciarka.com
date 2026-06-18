#!/usr/bin/env python3
"""
Główny skrypt scrapujący i synchronizujący harmonogram odpadów z Google Calendar
"""

import os
import sys
import json
import logging
from datetime import datetime
from scraper import WarsawWasteScraper
from calendar_sync import CalendarSync
from ics_generator import ICSGenerator
from email_sender import EmailSender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)


def main():
    # Konfiguracja z zmiennych środowiskowych
    street_address = os.environ.get('STREET_ADDRESS')
    geolocation_id = os.environ.get('GEOLOCATION_ID')
    credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    calendar_ids_str = os.environ.get('CALENDAR_IDS', '')

    if not credentials_json:
        _LOGGER.error("Brak GOOGLE_CREDENTIALS_JSON w zmiennych środowiskowych")
        sys.exit(1)

    if not calendar_ids_str:
        _LOGGER.error("Brak CALENDAR_IDS w zmiennych środowiskowych")
        sys.exit(1)

    calendar_ids = [id.strip() for id in calendar_ids_str.split(',') if id.strip()]

    if not calendar_ids:
        _LOGGER.error("CALENDAR_IDS jest pusty")
        sys.exit(1)

    try:
        # Scrapowanie danych
        _LOGGER.info("Rozpoczynam scrapowanie harmonogramu odpadów...")

        if geolocation_id:
            _LOGGER.info(f"Używam geolocation_id: {geolocation_id}")
            scraper = WarsawWasteScraper(geolocation_id=geolocation_id)
        elif street_address:
            _LOGGER.info(f"Wyszukiwanie geolocation_id dla adresu: {street_address}")
            scraper = WarsawWasteScraper(street_address=street_address)
        else:
            _LOGGER.error("Wymagany jest STREET_ADDRESS lub GEOLOCATION_ID")
            sys.exit(1)

        collections = scraper.fetch_schedule()
        _LOGGER.info(f"Znaleziono {len(collections)} terminów wywozu odpadów")

        for col in collections:
            _LOGGER.info(f"  - {col.date}: {col.waste_type}")

        # Synchronizacja z kalendarzem
        _LOGGER.info("Synchronizacja z Google Calendar...")
        sync = CalendarSync(credentials_json, calendar_ids)
        sync.sync_collections(collections)

        _LOGGER.info("Synchronizacja zakończona pomyślnie!")

        # Wysyłka email z plikiem .ics (backup/alternatywa)
        email_recipients_str = os.environ.get('EMAIL_RECIPIENTS', '')
        smtp_server = os.environ.get('SMTP_SERVER', '') or 'smtp.gmail.com'
        smtp_port_str = os.environ.get('SMTP_PORT', '')
        smtp_port = int(smtp_port_str) if smtp_port_str and smtp_port_str.strip() else 587
        smtp_username = os.environ.get('SMTP_USERNAME')
        smtp_password = os.environ.get('SMTP_PASSWORD')

        if email_recipients_str and smtp_username and smtp_password:
            _LOGGER.info("Generowanie i wysyłka pliku .ics...")

            # Generowanie pliku .ics
            ics_gen = ICSGenerator()
            ics_gen.add_collections(collections)
            ics_content = ics_gen.generate()

            # Wysyłka email
            recipients = [r.strip() for r in email_recipients_str.split(',') if r.strip()]
            sender = EmailSender(smtp_server, smtp_port, smtp_username, smtp_password)

            month_name = datetime.now().strftime('%B %Y')
            sender.send_ics_calendar(recipients, ics_content, month_name)

            _LOGGER.info("Wysyłka email zakończona!")
        else:
            _LOGGER.info("Brak konfiguracji email - pominięto wysyłkę .ics")

    except Exception as e:
        _LOGGER.error(f"Błąd: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
