import os
import requests
from urllib.parse import urlparse
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SNAPSHOT_DIR = "html_snapshots"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Add your links and optional labels here
URLS = [
    ("https://lbbonline.com/work?edition=international", "lbb_listing"),
    ("https://lbbonline.com/work/132158", "lbb_project"),
    ("https://lbbonline.com/companies/droga5-new-york", "lbb_company"),
    ("https://lbbonline.com/awards/immortals/entry/11490", "lbb_award"),
    ("https://eyecannndy.com/", "eyecanddy_home"),
    ("https://eyecannndy.com/technique/mixed-media", "eyecanddy_technique"),
    ("https://www.dandad.org/en/d-ad-awards-pencil-winners/", "dandad_categories"),
    ("https://www.dandad.org/search/archive/?q=&programmes=D%26AD+Awards&years=2024&categories=Animation&sort_order=newest&page=1&show_result=true", "dandad_category_listing"),
    ("https://www.dandad.org/awards/professional/2024/238864/up-in-smoke/", "dandad_project")
]

def sanitize_filename(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)

def snapshot_site(url: str, label: str):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()

        domain = urlparse(url).netloc.replace("www.", "")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{sanitize_filename(domain)}__{label}__{timestamp}.html"

        path = os.path.join(SNAPSHOT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(res.text)

        print(f"✅ Saved: {filename}")
    except Exception as e:
        print(f"❌ Failed to snapshot {url}: {e}")

if __name__ == "__main__":
    for url, label in URLS:
        snapshot_site(url, label)
