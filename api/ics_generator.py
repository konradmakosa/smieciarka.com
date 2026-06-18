"""
Generator pliku .ics (iCalendar) dla harmonogramu odpadów
"""

from datetime import datetime, timedelta
from typing import List
from scraper import WasteCollection


class ICSGenerator:
    def __init__(self):
        self.events = []

    def add_collections(self, collections: List[WasteCollection]):
        """Dodaje terminy wywozu odpadów do kalendarza"""
        for collection in collections:
            self._add_event(
                summary=f'Wywóz odpadów: {collection.waste_type}',
                description=f'Frakcja: {collection.waste_type}',
                date=collection.date
            )

    def _add_event(self, summary: str, description: str, date):
        """Tworzy pojedynczy event w formacie iCalendar"""
        uid = f'{date.isoformat()}-{summary.replace(" ", "-")}@odpady-scraper'
        created = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

        event = f"""BEGIN:VEVENT
DTSTAMP:{created}
UID:{uid}
SUMMARY:{summary}
DESCRIPTION:{description}
DTSTART;VALUE=DATE:{date.strftime('%Y%m%d')}
DTEND;VALUE=DATE:{(date + timedelta(days=1)).strftime('%Y%m%d')}
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Wywóz odpadów za 2 dni
TRIGGER:-P2DT15H
END:VALARM
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Wywóz odpadów jutro
TRIGGER:-P1DT15H
END:VALARM
END:VEVENT"""

        self.events.append(event)

    def generate(self) -> str:
        """Generuje pełny plik .ics"""
        header = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Odpady Scraper//PL
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:Harmonogram Wywozu Odpadów
X-WR-TIMEZONE:Europe/Warsaw"""

        footer = "END:VCALENDAR"

        return f"{header}\n" + "\n".join(self.events) + f"\n{footer}"

    def save_to_file(self, filename: str = "harmonogram_odpadow.ics"):
        """Zapisuje plik .ics do pliku"""
        content = self.generate()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return filename
