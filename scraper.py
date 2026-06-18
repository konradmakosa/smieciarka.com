"""
Scraper dla harmonogramu wywozu odpadów z warszawa19115.pl
Na podstawie kodu z hacs_waste_collection_schedule
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
import requests

_LOGGER = logging.getLogger(__name__)

OC_URL = "https://warszawa19115.pl/harmonogramy-wywozu-odpadow"
OC_PARAMS = {
    "p_p_id": "portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ",
    "p_p_lifecycle": "2",
    "p_p_resource_id": "ajaxResource",
}
OC_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

NAME_MAP = {
    "BG": "Bio restauracyjne",
    "BK": "Bio",
    "MT": "Metale i tworzywa sztuczne",
    "OP": "Papier",
    "OS": "Szkło",
    "OZ": "Zielone",
    "WG": "Odpady wielkogabarytowe",
    "ZM": "Odpady zmieszane",
}


class WasteCollection:
    def __init__(self, date: datetime.date, waste_type: str):
        self.date = date
        self.waste_type = waste_type

    def __repr__(self):
        return f"WasteCollection(date={self.date}, type={self.waste_type})"


class WarsawWasteScraper:
    def __init__(self, street_address: Optional[str] = None, geolocation_id: Optional[str] = None):
        if street_address is None and geolocation_id is None:
            raise ValueError("Wymagany jest adres lub geolocation_id")
        self._street_address = street_address
        self._geolocation_id = geolocation_id

    def get_geolocation_id(self, street_address: str) -> str:
        """Wyszukuje geolocation_id na podstawie adresu"""
        session = requests.Session()
        session.get(OC_URL).raise_for_status()

        params = OC_PARAMS.copy()
        params["p_p_resource_id"] = "autocompleteResource"
        params[
            "_portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ_name"
        ] = street_address

        response = session.get(OC_URL, headers=OC_HEADERS, params=params)
        response.raise_for_status()

        result = response.json()
        _LOGGER.debug(f"Search response: {result}")

        if not result:
            raise ValueError("Nie znaleziono adresu")

        geolocation_id = result[0]["addressPointId"]
        _LOGGER.info(f"Adres {street_address} -> geolocation_id {geolocation_id}")

        return geolocation_id

    def fetch_schedule(self) -> List[WasteCollection]:
        """Pobiera harmonogram wywozu odpadów"""
        if self._geolocation_id is None:
            self._geolocation_id = self.get_geolocation_id(self._street_address)

        session = requests.Session()
        session.get(OC_URL).raise_for_status()

        params = OC_PARAMS.copy()
        params["p_p_resource_id"] = "ajaxResource"
        params[
            "_portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ_addressPointId"
        ] = self._geolocation_id

        response = session.get(OC_URL, headers=OC_HEADERS, params=params)
        response.raise_for_status()

        result = response.json()
        _LOGGER.debug(f"Calendar response: {result}")

        if not result or "harmonogramyZ" not in result[0] or not result[0]["harmonogramyZ"]:
            raise ValueError("Brak danych w harmonogramie")

        entries = []
        for item in result:
            for entry in item["harmonogramyZ"]:
                if entry["data"]:
                    original_type = entry["frakcja"]["id_frakcja"]
                    waste_type = NAME_MAP.get(original_type, original_type)
                    waste_date = datetime.strptime(entry["data"], "%Y-%m-%d").date()
                    entries.append(WasteCollection(waste_date, waste_type))

        return entries
