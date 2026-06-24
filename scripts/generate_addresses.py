import requests, json, time, os

OC_URL = "https://warszawa19115.pl/harmonogramy-wywozu-odpadow"
OC_PARAMS = {
    "p_p_id": "portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ",
    "p_p_lifecycle": "2",
    "p_p_resource_id": "autocompleteResource",
}
OC_HEADERS = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
FIELD = "_portalCKMjunkschedules_WAR_portalCKMjunkschedulesportlet_INSTANCE_o5AIb2mimbRJ_name"
BASE_URL = "https://www.smieciarka.com"
OUT_DIR = "seo"
os.makedirs(OUT_DIR, exist_ok=True)

session = requests.Session()
session.get(OC_URL)

def fetch(query):
    params = OC_PARAMS.copy()
    params[FIELD] = query
    r = session.get(OC_URL, headers=OC_HEADERS, params=params, timeout=10)
    return r.json()

all_addresses = {}
letters = list("aąbcćdeęfghijklłmnńoópqrsśtuwxyzźż")
second = list("aąbcćdeęfghijklłmnńoópqrsśtuwxyzźż 0123456789")

for l1 in letters:
    items = fetch(l1)
    for item in items:
        all_addresses[item["addressPointId"]] = item["fullName"]
    if len(items) >= 10:
        for l2 in second:
            prefix = l1 + l2
            try:
                sub = fetch(prefix)
                for item in sub:
                    all_addresses[item["addressPointId"]] = item["fullName"]
                if len(sub) >= 10:
                    for l3 in "0123456789 ":
                        prefix3 = prefix + l3
                        try:
                            sub3 = fetch(prefix3)
                            for item in sub3:
                                all_addresses[item["addressPointId"]] = item["fullName"]
                        except Exception:
                            pass
                        time.sleep(0.1)
                time.sleep(0.1)
            except Exception:
                pass
    print(f"{l1}: lacznie {len(all_addresses)} adresow")
    time.sleep(0.2)

print(f"\nPobrano {len(all_addresses)} unikalnych adresow (z numerami)")

# Deduplikacja do poziomu ulica + kod + dzielnica (bez numerow budynkow)
# Format: "NAZWA NUMER KOD DZIELNICA" -> wyciagamy NAZWA + KOD + DZIELNICA
import re
unique_streets = {}  # slug -> {"street": ..., "district": ..., "postcode": ...}
for addr_id, full_name in all_addresses.items():
    parts = full_name.strip().split()
    # Znajdz kod pocztowy (XX-XXX)
    postcode_idx = next((i for i, p in enumerate(parts) if re.match(r'^\d{2}-\d{3}$', p)), None)
    if postcode_idx is None:
        continue
    postcode = parts[postcode_idx]
    district = " ".join(parts[postcode_idx+1:])
    # Czesc przed kodem to "NAZWA NUMER" - usun numer (ostatni token jesli zawiera cyfre)
    name_parts = parts[:postcode_idx]
    # Usun numer budynku (ostatni element jesli zawiera cyfre)
    while name_parts and any(c.isdigit() for c in name_parts[-1]):
        name_parts.pop()
    if not name_parts:
        continue
    street = " ".join(name_parts)
    slug = f"{street}-{postcode}-{district}".lower().replace(" ", "-")
    if slug not in unique_streets:
        unique_streets[slug] = {"street": street, "district": district, "postcode": postcode}

print(f"Unikalnych ulic: {len(unique_streets)}")

# Zapisz addresses.json (pelna lista z numerami - do uzycia przez autocomplete)
with open(f"{OUT_DIR}/addresses.json", "w", encoding="utf-8") as f:
    json.dump(all_addresses, f, ensure_ascii=False, indent=2)
print(f"Zapisano {OUT_DIR}/addresses.json")

# Zapisz streets.json (unikalne ulice - do SEO)
with open(f"{OUT_DIR}/streets.json", "w", encoding="utf-8") as f:
    json.dump(unique_streets, f, ensure_ascii=False, indent=2)
print(f"Zapisano {OUT_DIR}/streets.json")

# Generuj sitemap.xml tylko z unikalnymi ulicami
urls = [f'<url><loc>{BASE_URL}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>']
for slug in unique_streets:
    urls.append(f'<url><loc>{BASE_URL}/ulica/{slug}</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>')
xml = ('<?xml version="1.0" encoding="UTF-8"?>'
       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
       + "".join(urls) + "</urlset>")
with open(f"{OUT_DIR}/sitemap.xml", "w", encoding="utf-8") as f:
    f.write(xml)
print(f"Zapisano {OUT_DIR}/sitemap.xml ({len(urls)} URL-i)")

# Generuj HTML podstrony per ulica
pages_dir = f"{OUT_DIR}/pages"
os.makedirs(pages_dir, exist_ok=True)
for slug, info in unique_streets.items():
    street = info["street"].title()
    district = info["district"].title()
    postcode = info["postcode"]
    title = f"Harmonogram wywozu smieci ul. {street} {district} Warszawa"
    desc = f"Sprawdz kiedy odbieraja smieci przy ul. {street} w dzielnicy {district} ({postcode}) w Warszawie. Pobierz harmonogram do kalendarza Google lub iPhone."
    html = (f'<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8">'
            f'<title>{title}</title>'
            f'<meta name="description" content="{desc}">'
            f'<link rel="canonical" href="{BASE_URL}/ulica/{slug}">'
            f'</head><body>'
            f'<h1>{title}</h1><p>{desc}</p>'
            f'<p><a href="{BASE_URL}/?q={street}">Sprawdz harmonogram na smieciarka.com</a></p>'
            f'</body></html>')
    safe_slug = slug.replace("/", "_")[:200]
    with open(f"{pages_dir}/{safe_slug}.html", "w", encoding="utf-8") as f:
        f.write(html)

print(f"Zapisano {len(unique_streets)} stron HTML do {pages_dir}/")
print("GOTOWE!")
