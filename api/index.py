"""
Śmieciarka.com - API dla harmonogramu wywozu odpadów (Warszawa)
FastAPI + Vercel Serverless
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import Response, HTMLResponse
import sys

# Dodaj root projektu do path (dla importów z parent dir)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from scraper import WarsawWasteScraper
    from ics_generator import ICSGenerator
except ImportError:
    # Fallback dla Vercel
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scraper import WarsawWasteScraper
    from ics_generator import ICSGenerator

app = FastAPI(title="Śmieciarka.com", description="Harmonogram wywozu odpadów dla Warszawy")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
CACHE_TTL_HOURS = 168  # 7 dni

# Upewnij się, że katalog cache istnieje
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(key: str) -> str:
    """Generuje ścieżkę do pliku cache na podstawie klucza"""
    safe_key = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{safe_key}.json")


def get_from_cache(key: str) -> Optional[list]:
    """Pobiera dane z cache jeśli nie wygasły"""
    cache_path = get_cache_path(key)
    if not os.path.exists(cache_path):
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        
        cached_time = datetime.fromisoformat(cached['cached_at'])
        if datetime.now() - cached_time > timedelta(hours=CACHE_TTL_HOURS):
            os.remove(cache_path)
            return None
        
        return cached['data']
    except Exception:
        return None


def save_to_cache(key: str, data: list):
    """Zapisuje dane do cache"""
    cache_path = get_cache_path(key)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({
                'cached_at': datetime.now().isoformat(),
                'data': data
            }, f, default=str)
    except Exception:
        pass


@app.get("/", response_class=HTMLResponse)
def index():
    """Zwraca stronę główną"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "index.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    # Fallback jeśli nie ma index.html
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Śmieciarka.com</title></head>
    <body>
        <h1>Śmieciarka.com</h1>
        <p>Harmonogram wywozu odpadów dla Warszawy</p>
        <p>API: /search?q=ulica numer | /ical/{adres}.ics</p>
    </body>
    </html>
    """


@app.get("/api/search")
def search_addresses(q: str = Query(..., min_length=3, description="Fragment adresu (ulica numer)")):
    """
    Wyszukuje adresy w Warszawie.
    Przykład: /api/search?q=platnicza+65
    """
    try:
        scraper = WarsawWasteScraper(street_address=q)
        geolocation_id = scraper.get_geolocation_id(q)
        
        # Format odpowiedzi: adres i jego ID
        return {
            "results": [{
                "address": q,
                "geolocation_id": geolocation_id,
                "url": f"/ical/{q.replace(' ', '-').lower()}.ics"
            }]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd wyszukiwania: {str(e)}")


@app.get("/ical/{address_path:path}.ics")
def generate_ical(address_path: str):
    """
    Generuje plik .ics dla podanego adresu.
    Przykład: /ical/platnicza-65.ics lub /ical/ulica-platnicza-65.ics
    """
    # Normalizacja adresu
    address = address_path.replace("-", " ").replace("_", " ")
    
    # Sprawdź cache
    cache_key = f"schedule_{address}"
    cached_data = get_from_cache(cache_key)
    
    if cached_data:
        # Odtwórz obiekty z cache
        collections = []
        for item in cached_data:
            from scraper import WasteCollection
            from datetime import datetime
            date_obj = datetime.strptime(item['date'], '%Y-%m-%d').date()
            collections.append(WasteCollection(date_obj, item['waste_type']))
    else:
        # Pobierz z API Warszawy
        try:
            scraper = WarsawWasteScraper(street_address=address)
            collections = scraper.fetch_schedule()
            
            # Zapisz do cache
            cache_data = [{'date': c.date.isoformat(), 'waste_type': c.waste_type} for c in collections]
            save_to_cache(cache_key, cache_data)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Błąd pobierania danych: {str(e)}")
    
    if not collections:
        raise HTTPException(status_code=404, detail="Brak danych w harmonogramie dla tego adresu")
    
    # Generuj .ics
    ics_gen = ICSGenerator()
    ics_gen.add_collections(collections)
    ics_content = ics_gen.generate()
    
    # Zmień nazwę kalendarza w nagłówku
    ics_content = ics_content.replace(
        "X-WR-CALNAME:Harmonogram Wywozu Odpadów",
        f"X-WR-CALNAME:Wywóz śmieci - {address.title()}"
    )
    
    # Dodaj refresh-interval (ważne dla Google Calendar)
    ics_content = ics_content.replace(
        "X-WR-TIMEZONE:Europe/Warsaw",
        f"X-WR-TIMEZONE:Europe/Warsaw\nX-PUBLISHED-TTL:PT{CACHE_TTL_HOURS}H"
    )
    
    safe_filename = address.replace(" ", "_").replace("/", "_")
    
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}.ics"',
            "Cache-Control": f"public, max-age={CACHE_TTL_HOURS * 3600}"
        }
    )


# Dla lokalnego developmentu
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
