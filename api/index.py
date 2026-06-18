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
from scraper import WarsawWasteScraper
from ics_generator import ICSGenerator

app = FastAPI(title="Śmieciarka.com", description="Harmonogram wywozu odpadów dla Warszawy")

# In-memory cache (działa na Vercel, resetuje się przy cold start)
_memory_cache = {}
CACHE_TTL_HOURS = 168  # 7 dni

def get_from_cache(key: str) -> Optional[list]:
    """Pobiera dane z cache jeśli nie wygasły"""
    if key not in _memory_cache:
        return None
    
    cached = _memory_cache[key]
    cached_time = datetime.fromisoformat(cached['cached_at'])
    if datetime.now() - cached_time > timedelta(hours=CACHE_TTL_HOURS):
        del _memory_cache[key]
        return None
    
    return cached['data']

def save_to_cache(key: str, data: list):
    """Zapisuje dane do cache"""
    _memory_cache[key] = {
        'cached_at': datetime.now().isoformat(),
        'data': data
    }


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


@app.get("/search")
def search_addresses(q: str = Query(..., min_length=3, description="Fragment adresu (ulica numer)")):
    """
    Wyszukuje adresy w Warszawie.
    Przykład: /api/search?q=platnicza+65
    """
    try:
        scraper = WarsawWasteScraper(street_address=q)
        
        # Pobierz od razu cały harmonogram (przy okazji sprawdzamy czy adres istnieje)
        collections = scraper.fetch_schedule()
        
        # Normalizuj PL znaki dla URL (czytelniejszy link)
        def normalize_for_url(text):
            polish_map = {
                'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
                'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
                'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N',
                'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
            }
            return ''.join(polish_map.get(c, c) for c in text)
        
        import urllib.parse
        # Link z polskimi znakami (URL-encoded) - API Warszawy wymaga polskich znaków!
        # np. "Płatnicza 65" -> "P%C5%82atnicza-65"
        url_path = urllib.parse.quote(q.replace(' ', '-'))
        
        return {
            "results": [{
                "address": q,
                "url": f"/ical/{url_path}.ics"
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
    Przykład: /ical/P%C5%82atnicza-65.ics (Płatnicza-65)
    """
    import urllib.parse
    # Dekoduj URL - dostajemy oryginalny adres z polskimi znakami
    address = urllib.parse.unquote(address_path).replace("-", " ")
    
    try:
        # Pobierz bezpośrednio z API Warszawy
        scraper = WarsawWasteScraper(street_address=address)
        collections = scraper.fetch_schedule()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Adres '{address}' nie znaleziony: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd API: {str(e)}")
    
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
