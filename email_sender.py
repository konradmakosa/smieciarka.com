"""
Wysyłka email z plikiem .ics
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List

_LOGGER = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    def send_ics_calendar(self, recipients: List[str], ics_content: str, month_name: str):
        """
        Wysyła email z załącznikiem .ics
        recipients: lista adresów email
        ics_content: zawartość pliku .ics
        month_name: nazwa miesiąca (do tematu emaila)
        """
        for recipient in recipients:
            try:
                msg = MIMEMultipart()
                msg['From'] = self.username
                msg['To'] = recipient
                msg['Subject'] = f'Harmonogram wywozu odpadów - {month_name}'

                body = f"""Cześć!

W załączniku znajduje się harmonogram wywozu odpadów na najbliższe miesiące.

Aby dodać terminy do swojego kalendarza:
1. Otwórz załącznik harmonogram_odpadow.ics
2. Kliknij "Dodaj do kalendarza" / "Add to calendar"

Terminy zostaną automatycznie dodane z przypomnieniem 2h przed wywozem.

---
Wiadomość wysłana automatycznie przez Odpady Scraper
"""

                msg.attach(MIMEText(body, 'plain', 'utf-8'))

                # Załącznik .ics
                attachment = MIMEBase('text', 'calendar', method='REQUEST', name='harmonogram_odpadow.ics')
                attachment.set_payload(ics_content.encode('utf-8'))
                encoders.encode_base64(attachment)
                attachment.add_header('Content-Disposition', 'attachment', filename='harmonogram_odpadow.ics')
                attachment.add_header('Content-type', 'text/calendar; charset=utf-8; method=REQUEST')
                msg.attach(attachment)

                # Wysyłka
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.username, self.password)
                    server.send_message(msg)

                _LOGGER.info(f'Wysłano email do: {recipient}')

            except Exception as e:
                _LOGGER.error(f'Błąd wysyłki do {recipient}: {e}')
