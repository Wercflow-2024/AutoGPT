# backend/scrapy/scraper/domain_scanner.py

from bs4 import BeautifulSoup
import requests

from bs4 import BeautifulSoup
import requests

def scan_domain(base_url: str) -> list[str]:
    print(f"🔍 Scanning domain: {base_url}")
    res = requests.get(base_url)
    soup = BeautifulSoup(res.text, "html.parser")
    
    project_links = list(set(
        a["href"] for a in soup.find_all("a", href=True)
        if "/work/" in a["href"]
    ))

    # 💡 Inspect links
    print("🧵 Found project links:")
    for link in project_links:
        print(f" - {link}")

    return project_links
