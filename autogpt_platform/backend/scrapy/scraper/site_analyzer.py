import os
import re
import requests
from bs4 import BeautifulSoup


def analyze_site(path_or_url: str) -> dict:
    print(f"✨ Analyzing: {path_or_url}")

    # --- Load HTML from URL or file ---
    if path_or_url.startswith("http"):
        try:
            res = requests.get(path_or_url, timeout=10)
            res.raise_for_status()
            html = res.text
        except Exception as e:
            print(f"❌ Failed to fetch site: {e}")
            return {
                "strategy": {"recommended": "unknown", "confidence": 0.0},
                "routing": {"agents": []},
            }
        page_source = path_or_url
    else:
        with open(path_or_url, "r", encoding="utf-8") as f:
            html = f.read()
        page_source = os.path.basename(path_or_url)

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True).lower()
    all_links = [a["href"] for a in soup.find_all("a", href=True)]

    # --- Link grouping ---
    project_keywords = ["/work/", "/project", "/case", "/entry"]
    project_links = [link for link in all_links if any(k in link for k in project_keywords)]
    company_links = [link for link in all_links if any(k in link for k in ["/company", "/studio", "/vendor"])]
    person_links = [link for link in all_links if "/profile" in link or any(role in link for role in ["director", "editor", "dop"])]

    # --- Pagination detection ---
    has_pagination = bool(soup.select('a[href*="page="], a[rel="next"], .pagination')) or "next page" in page_text
    pagination_numbers = [int(m.group(1)) for m in re.finditer(r'page=(\d+)', " ".join(all_links)) if m.group(1).isdigit()]
    max_page = max(pagination_numbers) if pagination_numbers else None

    # --- Role info detection ---
    roles = ["director", "producer", "editor", "dop", "client", "agency", "production company"]
    found_roles = [role for role in roles if role in page_text]
    has_role_info = bool(found_roles)

    # --- Headline / title ---
    headline = soup.find("h1") or soup.find("title")
    headline_text = headline.get_text(strip=True) if headline else ""

    # --- Sections (topics, awards, etc) ---
    section_keywords = ["collections", "topics", "awards", "campaigns"]
    has_sections = any(k in page_text for k in section_keywords)

    # --- Strategy scoring ---
    confidence = {
        "project_with_credits": 0.9 if len(project_links) > 10 and has_role_info else 0,
        "basic_gallery": 0.7 if len(project_links) > 10 and not has_role_info else 0,
        "directory_style": 0.6 if company_links or person_links else 0,
        "unknown": 0.3,
    }
    strategy = max(confidence, key=confidence.get)

    # --- Smart agent routing ---
    agents = []
    if strategy in ["project_with_credits", "basic_gallery"]:
        agents.extend(["domain_scanner", "project_scraper"])
    if strategy == "project_with_credits":
        agents.append("entity_scraper")
    if strategy != "unknown":
        agents.extend(["validator", "db_writer"])

    return {
        "meta": {
            "source": page_source,
            "headline": headline_text,
        },
        "structure": {
            "has_project_links": len(project_links) > 0,
            "has_company_links": len(company_links) > 0,
            "has_person_links": len(person_links) > 0,
            "has_pagination": has_pagination,
            "max_page": max_page,
            "has_role_info": has_role_info,
            "roles_detected": found_roles,
            "has_sections": has_sections,
        },
        "strategy": {
            "recommended": strategy,
            "confidence": round(confidence[strategy], 2),
        },
        "routing": {
            "agents": list(set(agents)),
        },
        "samples": {
            "project_links": project_links[:5],
            "company_links": company_links[:3],
            "person_links": person_links[:3],
        },
    }


if __name__ == "__main__":
    from pprint import pprint

    SAMPLE_DIR = "snapshots"
    for file in os.listdir(SAMPLE_DIR):
        if file.endswith(".html"):
            result = analyze_site(os.path.join(SAMPLE_DIR, file))
            pprint(result)
            print("\n" + "+" * 80 + "\n")
