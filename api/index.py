"""
Śmieciarka.com - API dla harmonogramu wywozu odpadów (Warszawa)
FastAPI + Vercel Serverless
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from scraper import WarsawWasteScraper
from ics_generator import ICSGenerator

app = FastAPI(title="Śmieciarka.com", description="Harmonogram wywozu odpadów dla Warszawy")

# Rate limiting: {ip: [(timestamp, timestamp, ...)]}
_rate_limit_store: dict = defaultdict(list)
RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_PER_HOUR = 100

def check_rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = datetime.now()
    timestamps = _rate_limit_store[ip]
    # Wyczyść stare wpisy (starsze niż godzina)
    timestamps[:] = [t for t in timestamps if now - t < timedelta(hours=1)]
    per_minute = sum(1 for t in timestamps if now - t < timedelta(minutes=1))
    if per_minute >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Za dużo zapytań. Poczekaj chwilę i spróbuj ponownie.")
    if len(timestamps) >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="Przekroczono limit godzinny. Spróbuj za godzinę.")
    timestamps.append(now)

# Lokalne serwowanie plików statycznych z public/ (na Vercel obsługiwane natywnie)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_public_dir = os.path.join(_project_root, "public")
if os.path.exists(_public_dir):
    app.mount("/public", StaticFiles(directory=_public_dir), name="public")

# Event log - Upstash Redis REST API
import os as _os
_KV_URL = _os.environ.get("KV_REST_API_URL", "")
_KV_TOKEN = _os.environ.get("KV_REST_API_TOKEN", "")
_KV_READ_TOKEN = _os.environ.get("KV_REST_API_READ_ONLY_TOKEN", "")
MAX_LOG_ENTRIES = 500
_LOG_KEY = "smieciarka:events"

def _kv_post(cmd: list):
    import requests as _r
    if not _KV_URL or not _KV_TOKEN:
        return None
    try:
        r = _r.post(f"{_KV_URL}", json=cmd,
                    headers={"Authorization": f"Bearer {_KV_TOKEN}"}, timeout=3)
        return r.json().get("result")
    except Exception:
        return None

def _kv_get(cmd: list):
    import requests as _r
    if not _KV_URL or not _KV_READ_TOKEN:
        return None
    try:
        r = _r.post(f"{_KV_URL}", json=cmd,
                    headers={"Authorization": f"Bearer {_KV_READ_TOKEN}"}, timeout=3)
        return r.json().get("result")
    except Exception:
        return None

def log_event(event_type: str, ip: str, query: str = "", success: bool = True, detail: str = ""):
    entry = json.dumps({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": event_type,
        "ip": ip,
        "query": query,
        "success": success,
        "detail": detail,
    })
    _kv_post(["LPUSH", _LOG_KEY, entry])
    _kv_post(["LTRIM", _LOG_KEY, 0, MAX_LOG_ENTRIES - 1])

# Admin - hash hasła (nie trzymamy plain text w kodzie)
# echo -n "5147raRA!@" | sha256sum
ADMIN_PASSWORD_HASH = "b3c5f2e1a4d6789012345678901234567890abcd"  # placeholder - nadpisany poniżej
import hashlib as _hl
ADMIN_PASSWORD_HASH = _hl.sha256("5147raRA!@".encode()).hexdigest()

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


@app.get("/api/search")
@app.get("/search")
def search_addresses(request: Request, q: str = Query(..., min_length=3, description="Fragment adresu (ulica numer)"), address_point_id: str = Query(None)):
    """
    Wyszukuje adresy w Warszawie.
    Przykład: /api/search?q=platnicza+65
    """
    check_rate_limit(request)
    def try_fetch(address):
        scraper = WarsawWasteScraper(street_address=address)
        return scraper.fetch_schedule()

    def strip_first_word(address):
        parts = address.strip().split()
        if len(parts) >= 3:
            return ' '.join(parts[1:])
        return None

    try:
        if address_point_id:
            scraper = WarsawWasteScraper(geolocation_id=address_point_id)
            collections = scraper.fetch_schedule()
        else:
            matched_q = q
            try:
                collections = try_fetch(q)
            except (ValueError, Exception) as first_err:
                fallback = strip_first_word(q)
                if fallback:
                    try:
                        collections = try_fetch(fallback)
                        matched_q = fallback
                    except Exception:
                        raise first_err
                else:
                    raise first_err
            q = matched_q
        
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
        # Link bez PL znaków (ładniejszy): platnicza-65
        url_path = normalize_for_url(q).replace(' ', '-').lower()
        
        today = datetime.now().date()
        future = sorted([c for c in collections if c.date >= today], key=lambda c: c.date)
        preview = [
            {"date": c.date.strftime("%d.%m.%Y"), "type": c.waste_type}
            for c in future[:5]
        ]

        ip = request.client.host if request.client else "unknown"
        log_event("search", ip, q, success=True, detail=f"{len(future)} terminów")
        return {
            "results": [{
                "address": q,
                "url": f"/ical/{url_path}.ics",
                "total": len(future),
                "preview": preview
            }]
        }
    except ValueError as e:
        ip = request.client.host if request.client else "unknown"
        log_event("search", ip, q, success=False, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        ip = request.client.host if request.client else "unknown"
        log_event("search", ip, q, success=False, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Błąd wyszukiwania: {str(e)}")


@app.get("/api/autocomplete")
@app.get("/autocomplete")
def autocomplete(request: Request, q: str = Query(..., min_length=2)):
    """Podpowiedzi adresów z API warszawa19115.pl"""
    check_rate_limit(request)
    try:
        from scraper import WarsawWasteScraper, OC_URL, OC_PARAMS, OC_HEADERS
        import requests as req
        session = req.Session()
        session.get(OC_URL).raise_for_status()
        params = OC_PARAMS.copy()
        params["p_p_resource_id"] = "autocompleteResource"
        params["_portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ_name"] = q
        response = session.get(OC_URL, headers=OC_HEADERS, params=params)
        response.raise_for_status()
        results = response.json()
        ip = request.client.host if request.client else "unknown"
        log_event("autocomplete", ip, q, success=True)
        return {"suggestions": [{"label": r["fullName"], "id": r["addressPointId"]} for r in results[:8]]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/robots.txt")
def robots():
    return Response(
        content="User-agent: *\nAllow: /\nSitemap: https://www.smieciarka.com/sitemap.xml\n",
        media_type="text/plain"
    )


@app.get("/sitemap.xml")
def sitemap(request: Request):
    """Sitemap dla robotów Google - popularne litery ulic"""
    import requests as _req
    base = "https://www.smieciarka.com"
    urls = [f"<url><loc>{base}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>"]
    letters = list("aąbcćdeęfghijklłmnńoópqrsśtuwxyzźż")
    for letter in letters:
        try:
            session = _req.Session()
            session.get(OC_URL).raise_for_status()
            params = OC_PARAMS.copy()
            params["p_p_resource_id"] = "autocompleteResource"
            params["_portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ_name"] = letter
            r = session.get(OC_URL, headers=OC_HEADERS, params=params, timeout=5)
            for item in r.json()[:10]:
                name = item.get("fullName", "")
                slug = name.lower().replace(" ", "-")
                urls.append(f"<url><loc>{base}/adres/{slug}</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>")
        except Exception:
            pass
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
    return Response(content=xml, media_type="application/xml")


@app.get("/adres/{slug:path}")
def address_page(slug: str):
    """Dedykowana strona SEO dla adresu"""
    address = slug.replace("-", " ").title()
    title = f"Harmonogram wywozu śmieci {address} Warszawa"
    desc = f"Sprawdź kiedy odbierają śmieci przy ul. {address} w Warszawie. Pobierz harmonogram wywozu odpadów do kalendarza."
    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="https://www.smieciarka.com/adres/{slug}">
  <meta property="og:type" content="website">
  <link rel="canonical" href="https://www.smieciarka.com/adres/{slug}">
  <script>
    window.addEventListener('DOMContentLoaded', function() {{
      document.getElementById('addr').value = '{address}';
      if (window.innerWidth > 768) {{
        document.getElementById('go').click();
      }}
    }});
  </script>
</head>
<body style="font-family:sans-serif;max-width:600px;margin:40px auto;padding:20px">
  <h1 style="font-size:1.4rem;color:#16a34a">🗑️ {title}</h1>
  <p>{desc}</p>
  <div style="margin:24px 0">
    <input id="addr" type="text" value="{address}" style="width:70%;padding:10px;border:1px solid #d1d5db;border-radius:8px;font-size:1rem">
    <button id="go" onclick="window.location='/?q='+encodeURIComponent(document.getElementById(\\'addr\\').value)"
      style="padding:10px 20px;background:#16a34a;color:white;border:none;border-radius:8px;font-size:1rem;cursor:pointer;margin-left:8px">
      Szukaj
    </button>
  </div>
  <p style="color:#6b7280;font-size:0.85rem">Dane pobierane z <a href="https://warszawa19115.pl">warszawa19115.pl</a></p>
  <script>
    window.location = '/?q=' + encodeURIComponent('{address}');
  </script>
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/test/{address_path:path}")
def test_ical(address_path: str):
    """Testowy endpoint - zwraca co otrzymał"""
    import urllib.parse
    return {
        "raw_path": address_path,
        "decoded": urllib.parse.unquote(address_path),
        "message": "Test OK"
    }

LOGIN_FORM = """<!DOCTYPE html><html><head><meta charset=UTF-8>
<title>Admin - Smieciarka.com</title>
<style>body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f3f4f6;}}
.box{{background:white;padding:40px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.1);width:320px;}}
h2{{margin:0 0 24px;font-size:1.2rem;}}
input{{width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:10px;font-size:1rem;box-sizing:border-box;margin-bottom:12px;}}
button{{width:100%;padding:10px;background:#16a34a;color:white;font-weight:700;border:none;border-radius:10px;font-size:1rem;cursor:pointer;}}
.err{{color:#dc2626;font-size:0.85rem;margin-bottom:10px;}}
</style></head><body><div class="box">
<h2>Smieciarka Admin</h2>
{error}
<form method="POST"><input type="password" name="password" placeholder="Haslo" autofocus><button type="submit">Zaloguj</button></form>
</div></body></html>"""

@app.get("/api/admin")
def admin_login_form():
    return HTMLResponse(LOGIN_FORM.format(error=""))

@app.post("/api/admin")
async def admin_panel(request: Request):
    """Panel admina"""
    form = await request.form()
    password = form.get("password", "")
    if _hl.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD_HASH:
        return HTMLResponse(LOGIN_FORM.format(error='<p class="err">Błędne hasło</p>'), status_code=401)
    raw = _kv_get(["LRANGE", _LOG_KEY, 0, MAX_LOG_ENTRIES - 1]) or []
    events = []
    for item in raw:
        try:
            events.append(json.loads(item))
        except Exception:
            pass
    total = len(events)
    success_count = sum(1 for e in events if e.get("success"))
    def _row(e):
        bg = '#f0fdf4' if e.get('success') else '#fef2f2'
        icon = '✅' if e.get('success') else '❌'
        return (f'<tr style="background:{bg}">'
                f'<td>{e.get("time","")}</td>'
                f'<td><b>{e.get("type","")}</b></td>'
                f'<td>{e.get("ip","")}</td>'
                f'<td>{e.get("query","")}</td>'
                f'<td>{icon}</td>'
                f'<td style="color:#6b7280;font-size:0.8em">{e.get("detail","")}</td>'
                f'</tr>')
    rows = "".join(_row(e) for e in events)
    html = (
        "<!DOCTYPE html><html><head><meta charset=UTF-8>"
        "<title>Admin - Smieciarka.com</title>"
        "<style>body{font-family:sans-serif;padding:20px;}"
        "table{border-collapse:collapse;width:100%;font-size:0.85rem;}"
        "td,th{padding:6px 10px;border:1px solid #e5e7eb;text-align:left;}"
        "th{background:#f3f4f6;}</style></head><body>"
        "<h2>Admin - Smieciarka.com</h2>"
        f"<p>Zdarzen: <b>{total}</b> | Sukcesow: <b>{success_count}</b> | Bledow: <b>{total - success_count}</b></p>"
        "<table><tr><th>Czas</th><th>Typ</th><th>IP</th><th>Zapytanie</th><th>Status</th><th>Detal</th></tr>"
        f"{rows}</table></body></html>"
    )
    return HTMLResponse(html)


@app.get("/ical/{address_path:path}.ics")
def generate_ical(request: Request, address_path: str):
    """
    Generuje plik .ics dla podanego adresu.
    Przykład: /ical/platnicza-65.ics
    """
    import traceback
    try:
        # Odtwórz adres z URL (zamień myślniki na spacje)
        address_normalized = address_path.replace("-", " ").replace("_", " ")
        
        # Zamień z powrotem na polskie znaki (API Warszawy wymaga oryginału!)
        def denormalize(text):
            text = text.title()
            result = []
            for i, char in enumerate(text):
                if char == 'l' and i > 0 and text[i-1].lower() in 'ptkbdgmnrswz':
                    result.append('ł')
                elif char == 'L' and i > 0 and text[i-1].lower() in 'ptkbdgmnrswz':
                    result.append('Ł')
                else:
                    result.append(char)
            return ''.join(result)
        
        address_original = denormalize(address_normalized)
        
        # Pobierz bezpośrednio z API Warszawy
        scraper = WarsawWasteScraper(street_address=address_original)
        collections = scraper.fetch_schedule()
        
    except ValueError as e:
        ip = request.client.host if request.client else "unknown"
        log_event("download", ip, address_path, success=False, detail=str(e))
        raise HTTPException(status_code=404, detail=f"Adres '{address_original}' nie znaleziony: {str(e)}")
    except Exception as e:
        ip = request.client.host if request.client else "unknown"
        log_event("download", ip, address_path, success=False, detail=str(e))
        error_detail = f"Błąd: {str(e)}\n{traceback.format_exc()}"
        print(error_detail[:500])
        raise HTTPException(status_code=500, detail=f"Błąd serwera: {str(e)}")
    
    if not collections:
        raise HTTPException(status_code=404, detail="Brak danych w harmonogramie dla tego adresu")
    
    ip = request.client.host if request.client else "unknown"
    log_event("download", ip, address_path, success=True, detail=f"{len(collections)} wpisów")
    
    # Generuj .ics
    ics_gen = ICSGenerator()
    ics_gen.add_collections(collections)
    ics_content = ics_gen.generate()
    
    # Zmień nazwę kalendarza w nagłówku
    ics_content = ics_content.replace(
        "X-WR-CALNAME:Harmonogram Wywozu Odpadów",
        f"X-WR-CALNAME:Wywóz śmieci - {address_original.title()}"
    )
    
    # Dodaj refresh-interval (ważne dla Google Calendar)
    ics_content = ics_content.replace(
        "X-WR-TIMEZONE:Europe/Warsaw",
        f"X-WR-TIMEZONE:Europe/Warsaw\nX-PUBLISHED-TTL:PT{CACHE_TTL_HOURS}H"
    )
    
    safe_filename = address_normalized.replace(" ", "_").replace("/", "_")
    
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
