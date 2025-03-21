from .scraper.domain_scanner import scan_domain
from .scraper.project_scraper import scrape_project
from .scraper.company_scraper import scrape_company
from .scraper.validator import validate_data
from .sql.db_writer import write_to_db
from .blob.uploader import upload_assets
from .scraper.site_analyzer import analyze_site
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("mission_runner")

# Try to import the AI enhancer
try:
    from .scraper.ai_enhancer import AzureOpenAIEnhancer
    AI_AVAILABLE = True
except ImportError:
    logger.warning("AI enhancer not available. Some features will be disabled.")
    AI_AVAILABLE = False

def run_scrapy_mission(task: dict) -> dict:
    """
    Run a complete scraping mission with AI enhancement.
    
    Args:
        task: Dictionary containing mission parameters:
            - url: Base URL to scrape
            - instructions: Optional instructions
            - debug: Enable debug pauses
            - ai_enhanced: Enable AI enhancement
            - ai_model: Model to use for AI (gpt-4o, gpt-4o-mini, etc.)
            - normalize_roles: Use AI to normalize unknown roles
            
    Returns:
        Dictionary with mission results
    """
    url = task.get("url")
    instructions = task.get("instructions", "default")
    debug = task.get("debug", False)
    ai_enhanced = task.get("ai_enhanced", AI_AVAILABLE)
    ai_model = task.get("ai_model", os.getenv("AI_MODEL", "gpt-4o-mini"))
    normalize_roles = task.get("normalize_roles", False)
    
    # Log mission start
    mission_id = f"mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🚀 Starting mission {mission_id} for: {url}")
    logger.info(f"AI enhancement: {'✅ Enabled' if ai_enhanced else '❌ Disabled'}")
    
    if ai_enhanced and not AI_AVAILABLE:
        logger.warning("⚠️ AI enhancement requested but not available. Falling back to standard scraping.")
        ai_enhanced = False

    # 🔍 Analyze site
    logger.info(f"🔍 Analyzing site: {url}")
    analysis = analyze_site(url)

    strategy = analysis.get("strategy", {}).get("recommended", "unknown")
    agents = analysis.get("routing", {}).get("agents", [
        "domain_scanner", "project_scraper", "entity_scraper", "validator", "db_writer"
    ])
    logger.info(f"📊 Site strategy: {strategy}")
    logger.info(f"🧠 Agent plan: {agents}")

    # Initialize AI enhancer if enabled
    ai_enhancer = None
    if ai_enhanced and AI_AVAILABLE:
        try:
            ai_enhancer = AzureOpenAIEnhancer(model=ai_model)
            if ai_enhancer.enabled:
                logger.info(f"🤖 AI enhancer initialized with model: {ai_model}")
                
                # Try to improve the strategy using AI
                if strategy == "unknown":
                    logger.info("🧠 Attempting to generate strategy with AI...")
                    # Mock a simple HTML snippet for analysis
                    html_snippet = f"<html><body><h1>{url}</h1></body></html>"
                    ai_strategy = ai_enhancer.analyze_html_structure(html_snippet, url)
                    if ai_strategy and ai_strategy.get("strategy") != "unknown":
                        logger.info(f"✅ AI suggested strategy: {ai_strategy.get('strategy')}")
                        strategy = ai_strategy.get("strategy")
            else:
                logger.warning("⚠️ AI enhancer initialization failed. Using standard scraping.")
                ai_enhanced = False
        except Exception as e:
            logger.error(f"❌ Error initializing AI enhancer: {e}")
            ai_enhanced = False

    if debug:
        input("🔍 Pause after site analysis. Press Enter to continue...")

    # Save mission metadata
    mission_metadata = {
        "mission_id": mission_id,
        "url": url,
        "strategy": strategy,
        "agents": agents,
        "ai_enhanced": ai_enhanced,
        "ai_model": ai_model if ai_enhanced else None,
        "started_at": datetime.now().isoformat(),
        "instructions": instructions
    }
    
    # Create results directory if it doesn't exist
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mission_results")
    os.makedirs(results_dir, exist_ok=True)
    
    # Save mission metadata
    metadata_file = os.path.join(results_dir, f"{mission_id}_metadata.json")
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(mission_metadata, f, indent=2)

    # 🧭 Domain scan
    project_links = run_domain_scanner(url, agents)
    scraped = 0
    failed = 0
    
    # Track all project results
    project_results = []

    for link in project_links:
        logger.info(f"\n🔗 Processing project link: {link}")
        
        # 📝 Project scraping
        raw_data = run_project_scraper(link, url, agents, ai_enhanced, ai_model, normalize_roles)
        if not raw_data:
            logger.warning(f"⚠️ No data returned for {link}, skipping.")
            failed += 1
            continue

        # Save raw data
        project_id = raw_data.get("meta", {}).get("project_id", 
                    f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{scraped}")
        raw_file = os.path.join(results_dir, f"{mission_id}_{project_id}_raw.json")
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2)
        
        if debug:
            input("📦 Pause after project scrape. Press Enter to continue...")

        # 🏢 Entity scraping
        raw_data = run_entity_scraper(raw_data, agents, ai_enhanced, ai_model)

        if debug:
            input("🏢 Pause after company scrape. Press Enter to continue...")

        # 🖼️ Asset upload
        uploaded_links = run_asset_upload(raw_data, agents)
        
        # ✅ Validation
        validated_data = run_validator(raw_data, uploaded_links, agents)
        
        # Save validated data
        validated_file = os.path.join(results_dir, f"{mission_id}_{project_id}_validated.json")
        with open(validated_file, "w", encoding="utf-8") as f:
            json.dump(validated_data, f, indent=2)

        if debug:
            input("✅ Pause before DB insert. Press Enter to continue...")

        # 💾 DB writing
        run_db_writer(validated_data, agents)
        
        # Track result
        project_results.append({
            "project_id": project_id,
            "url": link,
            "title": raw_data.get("title", "Unknown"),
            "companies": len(raw_data.get("companies", [])),
            "credits": sum(len(c.get("credits", [])) for c in raw_data.get("companies", [])),
            "ai_enhanced": ai_enhanced,
            "validated": bool(validated_data)
        })
        
        scraped += 1
        logger.info(f"✅ Project {scraped} processed: {raw_data.get('title', 'Unknown')}")

    # Complete mission metadata
    mission_metadata["completed_at"] = datetime.now().isoformat()
    mission_metadata["projects_scraped"] = scraped
    mission_metadata["projects_failed"] = failed
    mission_metadata["projects"] = project_results
    
    # Update mission metadata file
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(mission_metadata, f, indent=2)

    logger.info(f"\n🎯 Mission complete. {scraped} projects scraped, {failed} failed.")
    return {
        "status": "success", 
        "mission_id": mission_id,
        "projects_scraped": scraped,
        "projects_failed": failed,
        "metadata_file": metadata_file
    }


def run_domain_scanner(url: str, agents: list[str]) -> list[str]:
    """Run the domain scanner agent to find project links"""
    if "domain_scanner" not in agents:
        return []
    
    logger.info("🧭 Running domain scanner")
    return scan_domain(url)


def run_project_scraper(link: str, base_url: str, agents: list[str], 
                       ai_enhanced: bool = False, ai_model: str = None,
                       normalize_roles: bool = False) -> Optional[Dict]:
    """Run the project scraper agent to extract project data"""
    if "project_scraper" not in agents:
        return None
    
    if not link.startswith("http"):
        link = base_url.rstrip("/") + "/" + link.lstrip("/")
    
    logger.info(f"📄 Scraping project: {link}")
    
    try:
        # Call the enhanced project scraper with AI options
        return scrape_project(
            link, 
            ai_enabled=ai_enhanced, 
            ai_model=ai_model,
            normalize_roles=normalize_roles,
            debug=False  # We handle debugging at the mission level
        )
    except Exception as e:
        logger.error(f"❌ Error scraping project {link}: {e}")
        return None


def run_entity_scraper(raw_data: dict, agents: list[str], 
                      ai_enhanced: bool = False, ai_model: str = None) -> dict:
    """Run the entity scraper agent to extract company data"""
    if "entity_scraper" not in agents or not raw_data:
        return raw_data
    
    raw_data["company_details"] = []
    for company in raw_data.get("companies", []):
        company_url = company.get("url")
        if not company_url:
            continue
            
        logger.info(f"🏢 Scraping company: {company_url}")
        try:
            company_data = scrape_company(company_url)
            if company_data:
                # Include the original company ID for reference
                company_data["original_id"] = company.get("id")
                raw_data["company_details"].append(company_data)
        except Exception as e:
            logger.error(f"❌ Error scraping company {company_url}: {e}")
    
    return raw_data


def run_asset_upload(raw_data: dict, agents: list[str]) -> dict:
    """Run the asset uploader agent to upload media assets"""
    logger.info("🖼️ Running asset uploader")
    return upload_assets(raw_data) if raw_data else {}


def run_validator(raw_data: dict, uploaded_links: dict, agents: list[str]) -> dict:
    """Run the validator agent to validate extracted data"""
    if "validator" in agents:
        logger.info("✅ Running validator")
        return validate_data(raw_data, uploaded_links)
    return raw_data


def run_db_writer(validated_data: dict, agents: list[str]) -> None:
    """Run the DB writer agent to store data in the database"""
    if "db_writer" in agents:
        logger.info("💾 Running DB writer")
        write_to_db(validated_data)


if __name__ == "__main__":
    import argparse
    from pprint import pprint

    parser = argparse.ArgumentParser(description="Run a Werc Scrapy Mission manually.")
    parser.add_argument("url", help="The base URL to scrape")
    parser.add_argument("--instructions", default="default", help="Optional instructions")
    parser.add_argument("--debug", action="store_true", help="Enable debug pauses between steps")
    parser.add_argument("--ai", action="store_true", help="Enable AI enhancement")
    parser.add_argument("--ai-model", choices=["gpt-4o", "gpt-4o-mini", "o1-mini", "o3-mini"], 
                        help="AI model to use")
    parser.add_argument("--normalize-roles", action="store_true", help="Use AI to normalize unknown roles")

    args = parser.parse_args()

    task = {
        "url": args.url,
        "instructions": args.instructions,
        "debug": args.debug,
        "ai_enhanced": args.ai,
        "ai_model": args.ai_model,
        "normalize_roles": args.normalize_roles
    }

    print(f"🚀 Starting mission for: {args.url}")
    result = run_scrapy_mission(task)
    print("\n✅ Result:")
    pprint(result)  