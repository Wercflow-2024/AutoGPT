from .scraper.domain_scanner import scan_domain
from .scraper.project_scraper import scrape_project
from .scraper.company_scraper import scrape_company
from .scraper.validator import validate_data
from .sql.db_writer import write_to_db
from .blob.uploader import upload_assets
from .scraper.site_analyzer import analyze_site


def run_scrapy_mission(task: dict) -> dict:
    url = task.get("url")
    instructions = task.get("instructions", "default")
    debug = task.get("debug", False)

    # 🔍 Analyze site
    from .scraper.site_analyzer import analyze_site
    analysis = analyze_site(url)

    strategy = analysis.get("strategy", {}).get("recommended", "unknown")
    agents = analysis.get("routing", {}).get("agents", [
        "domain_scanner", "project_scraper", "entity_scraper", "validator", "db_writer"
    ])
    print(f"📊 Site strategy: {strategy}")
    print(f"🧠 Agent plan: {agents}")

    if debug:
        input("🔍 Pause after site analysis. Press Enter to continue...")

    # 🧭 Domain scan
    project_links = run_domain_scanner(url, agents)
    scraped = 0

    for link in project_links:
        raw_data = run_project_scraper(link, url, agents)
        if not raw_data:
            print("⚠️ No data returned, skipping.")
            continue

        if debug:
            input("📦 Pause after project scrape. Press Enter to continue...")

        raw_data = run_entity_scraper(raw_data, agents)

        if debug:
            input("🏢 Pause after company scrape. Press Enter to continue...")

        uploaded_links = run_asset_upload(raw_data, agents)
        validated_data = run_validator(raw_data, uploaded_links, agents)

        if debug:
            input("✅ Pause before DB insert. Press Enter to continue...")

        run_db_writer(validated_data, agents)
        scraped += 1

    print(f"🎯 Mission complete. {scraped} projects scraped.")
    return {"status": "success", "projects_scraped": scraped}


def run_domain_scanner(url: str, agents: list[str]) -> list[str]:
    if "domain_scanner" not in agents:
        return []
    return scan_domain(url)


def run_project_scraper(link: str, base_url: str, agents: list[str]) -> dict | None:
    if "project_scraper" not in agents:
        return None
    if not link.startswith("http"):
        link = base_url.rstrip("/") + "/" + link.lstrip("/")
    print(f"🔗 Scraping project: {link}")
    return scrape_project(link)


def run_entity_scraper(raw_data: dict, agents: list[str]) -> dict:
    if "entity_scraper" not in agents or not raw_data:
        return raw_data
    raw_data["company_details"] = []
    for company_url in raw_data.get("companies", []):
        print(f"🏢 Scraping company: {company_url}")
        company_data = scrape_company(company_url)
        if company_data:
            raw_data["company_details"].append(company_data)
    return raw_data


def run_asset_upload(raw_data: dict, agents: list[str]) -> dict:
    return upload_assets(raw_data) if raw_data else {}


def run_validator(raw_data: dict, uploaded_links: dict, agents: list[str]) -> dict:
    if "validator" in agents:
        return validate_data(raw_data, uploaded_links)
    return raw_data


def run_db_writer(validated_data: dict, agents: list[str]) -> None:
    if "db_writer" in agents:
        write_to_db(validated_data)


if __name__ == "__main__":
    import argparse
    from pprint import pprint

    parser = argparse.ArgumentParser(description="Run a Werc Scrapy Mission manually.")
    parser.add_argument("url", help="The base URL to scrape")
    parser.add_argument("--instructions", default="default", help="Optional instructions")
    parser.add_argument("--debug", action="store_true", help="Enable debug pauses between steps")

    args = parser.parse_args()

    task = {
        "url": args.url,
        "instructions": args.instructions,
        "debug": args.debug
    }

    print(f"🚀 Starting mission for: {args.url}")
    result = run_scrapy_mission(task)
    print("\n✅ Result:")
    pprint(result)