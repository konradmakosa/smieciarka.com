import json, re, os

OUT_DIR = "seo"
BASE_URL = "https://www.smieciarka.com"

with open(f"{OUT_DIR}/addresses.json", encoding="utf-8") as f:
    all_addresses = json.load(f)

print(f"Wczytano {len(all_addresses)} adresow")

unique_streets = {}
for addr_id, full_name in all_addresses.items():
    parts = full_name.strip().split()
    postcode_idx = next((i for i, p in enumerate(parts) if re.match(r'^\d{2}-\d{3}$', p)), None)
    if postcode_idx is None:
        continue
    postcode = parts[postcode_idx]
    district = " ".join(parts[postcode_idx+1:])
    name_parts = parts[:postcode_idx]
    while name_parts and any(c.isdigit() for c in name_parts[-1]):
        name_parts.pop()
    if not name_parts:
        continue
    street = " ".join(name_parts)
    slug = f"{street}-{postcode}-{district}".lower().replace(" ", "-")
    if slug not in unique_streets:
        unique_streets[slug] = {"street": street, "district": district, "postcode": postcode}

print(f"Unikalnych ulic: {len(unique_streets)}")

with open(f"{OUT_DIR}/streets.json", "w", encoding="utf-8") as f:
    json.dump(unique_streets, f, ensure_ascii=False, indent=2)
print(f"Zapisano {OUT_DIR}/streets.json")

urls = [f'<url><loc>{BASE_URL}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>']
for slug in unique_streets:
    urls.append(f'<url><loc>{BASE_URL}/ulica/{slug}</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>')
xml = ('<?xml version="1.0" encoding="UTF-8"?>'
       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
       + "".join(urls) + "</urlset>")
with open(f"{OUT_DIR}/sitemap.xml", "w", encoding="utf-8") as f:
    f.write(xml)
print(f"Zapisano {OUT_DIR}/sitemap.xml ({len(urls)} URL-i)")

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
