"""
Enhanced project scraper with AI assistance and snapshot-based debugging.
Implements the 6-step extraction process:
1. Fetch HTML & Snapshot
2. Select Strategy
3. Attempt Extraction
4. Evaluate Results
5. AI Debugging (optional)
6. Return Structured Data
"""

import os
import re
import json
import hashlib
import datetime
import logging
import argparse
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from project structure
try:
    from backend.scrapy.utils.config import CONFIG
    from backend.scrapy.utils.testing import save_html_snapshot, save_test_result
except ImportError:
    # For standalone testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from scrapy.utils.config import CONFIG
    from scrapy.utils.testing import save_html_snapshot, save_test_result

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("project_scraper")

# Constants
SNAPSHOT_DIR = CONFIG["SNAPSHOT_DIR"]
HEADERS = CONFIG["DEFAULT_HEADERS"]

# Strategies registry
STRATEGIES = {
    "lbb_v1": {
        "name": "lbb_v1",
        "selectors": {
            "title": "h1",
            "description": ".field--name-field-description",
            "project_info": ".field--name-field-basic-info .field__item",
            "credit_blocks": ".credit-entry",
            "company_name": ".company-name a",
            "company_type": ".company-type",
            "role_blocks": ".roles .role",
            "role_name": ".role-name",
            "person": ".person",
            "person_name": "a",
        }
    },
    "dandad_v1": {
        "name": "dandad_v1",
        "selectors": {
            "title": "h1",
            "description": ".award-content-intro",
            "project_info": ".award-meta-details",
            "credit_blocks": ".award-credits-list",
            "company_name": ".company-name",
            "company_type": ".company-role",
            "role_blocks": ".award-credits-role",
            "role_name": ".role-title",
            "person": ".person-name",
            "person_name": "span",
        }
    },
    # Add more strategies as needed
}

def fetch_html_and_snapshot(url: str, force_refresh: bool = False) -> Tuple[str, bool]:
    """
    Fetch HTML from a URL and save it to a snapshot file.
    
    Args:
        url: The URL to fetch
        force_refresh: Force refetching even if a snapshot exists
        
    Returns:
        Tuple of (html_content, is_from_cache)
    """
    # Check if this is a file:// URL
    if url.startswith("file://"):
        file_path = url[7:]
        logger.info(f"🔍 Loading from local file: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read(), True
    
    # Create a filename based on the URL
    domain = urlparse(url).netloc.replace("www.", "")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    filename = f"{domain}__{url_hash}.html"
    path = os.path.join(SNAPSHOT_DIR, filename)
    
    # Check if we have a cached snapshot
    if os.path.exists(path) and not force_refresh:
        logger.info(f"🔍 Loading from snapshot: {filename}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), True
    
    # Fetch fresh HTML
    logger.info(f"🔍 Fetching page: {url}")
    try:
        res = requests.get(url, headers=HEADERS, timeout=CONFIG["REQUEST_TIMEOUT"])
        res.raise_for_status()
        html = res.text
        
        # Save snapshot
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        
        logger.info(f"✅ Snapshot saved: {filename}")
        return html, False
    except Exception as e:
        logger.error(f"❌ Failed to fetch {url}: {e}")
        if os.path.exists(path):
            logger.info(f"⚠️ Using existing snapshot despite error")
            with open(path, "r", encoding="utf-8") as f:
                return f.read(), True
        raise

def select_strategy(html: str, url: str) -> Dict:
    """
    Select the appropriate scraping strategy based on the URL and HTML content.
    
    Args:
        html: The HTML content
        url: The URL being scraped
        
    Returns:
        Dictionary with strategy details
    """
    domain = urlparse(url).netloc.lower()
    
    # Domain-based strategy selection
    if "lbbonline.com" in domain:
        return STRATEGIES["lbb_v1"]
    elif "dandad.org" in domain:
        return STRATEGIES["dandad_v1"]
    
    # If no domain match, try to analyze the structure
    soup = BeautifulSoup(html, "html.parser")
    
    # Basic structure detection heuristics
    if soup.select(".credit-entry") or soup.select(".field--name-field-basic-info"):
        return STRATEGIES["lbb_v1"]
    elif soup.select(".award-credits-list") or soup.select(".award-meta-details"):
        return STRATEGIES["dandad_v1"]
    
    # Default fallback - use site_analyzer if available
    try:
        from backend.scrapy.scraper.site_analyzer import analyze_site
        analysis = analyze_site(url)
        if analysis.get("strategy", {}).get("recommended") != "unknown":
            logger.info(f"Using strategy from site_analyzer: {analysis['strategy']['recommended']}")
            strategy_hint = analysis["strategy"]["recommended"]
            if "project_with_credits" in strategy_hint:
                return STRATEGIES["lbb_v1"]
            elif "basic_gallery" in strategy_hint:
                return STRATEGIES["lbb_v1"]
    except Exception as e:
        logger.warning(f"Could not use site_analyzer: {e}")
    
    # Default fallback
    logger.warning(f"⚠️ No specific strategy detected for {domain}, using fallback")
    return STRATEGIES["lbb_v1"]

def extract_project_data(html: str, strategy: Dict, url: str, fallback_mapping: Dict) -> Dict:
    """
    Extract project data using the selected strategy.
    
    Args:
        html: The HTML content
        strategy: The strategy dict with selectors
        url: The URL being scraped
        fallback_mapping: Mapping for role/company normalization
        
    Returns:
        Dictionary with extracted project data
    """
    soup = BeautifulSoup(html, "html.parser")
    selectors = strategy["selectors"]
    
    def safe_text(element):
        return element.get_text(strip=True) if element else ""
    
    def extract_id_from_url(href):
        match = re.search(r"/(\d+)/?$", href)
        return match.group(1) if match else None
    
    # --- Basic Info ---
    title = safe_text(soup.select_one(selectors["title"]))
    description = safe_text(soup.select_one(selectors["description"]))
    
    # --- Project Metadata ---
    project_info = soup.select(selectors["project_info"])
    client = ""
    date = ""
    location = ""
    format_ = ""
    
    for item in project_info:
        text = item.get_text(" ", strip=True).lower()
        if "client" in text or "brand" in text:
            client = item.get_text(strip=True)
        elif re.search(r"\b\d{4}\b", text):
            date = text
        elif "location" in text:
            location = item.get_text(strip=True)
        elif "format" in text or "project type" in text:
            format_ = item.get_text(strip=True)
    
    # --- Media Assets ---
    # Find video embeds
    video_links = []
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src")
        if src and any(x in src for x in ["youtube", "vimeo", "lbbonline"]):
            video_links.append(src)
    
    # Find poster image
    poster_image = ""
    og_image = soup.find("meta", property="og:image")
    if og_image:
        poster_image = og_image.get("content")
    
    # --- Credits Extraction ---
    companies = []
    unknown_roles = []
    
    credit_blocks = soup.select(selectors["credit_blocks"])
    for block in credit_blocks:
        company_link = block.select_one(selectors["company_name"])
        company_name = safe_text(company_link)
        company_url = urljoin(url, company_link["href"]) if company_link and "href" in company_link.attrs else ""
        company_id = extract_id_from_url(company_url) or company_url
        
        company_type_el = block.select_one(selectors["company_type"])
        company_type = safe_text(company_type_el)
        if not company_type and company_id in fallback_mapping.get("company_types", {}):
            company_type = fallback_mapping["company_types"][company_id]
        
        people = []
        role_blocks = block.select(selectors["role_blocks"])
        for role_block in role_blocks:
            role = safe_text(role_block.select_one(selectors["role_name"]))
            for person in role_block.select(selectors["person"]):
                person_name = safe_text(person.select_one(selectors["person_name"])) or safe_text(person)
                person_link = person.select_one("a")
                person_url = urljoin(url, person_link["href"]) if person_link and "href" in person_link.attrs else ""
                person_id = extract_id_from_url(person_url) or person_url
                
                if not role and person_id in fallback_mapping.get("role_mappings", {}):
                    role = fallback_mapping["role_mappings"][person_id]
                elif not role:
                    unknown_roles.append({"person_id": person_id, "name": person_name})
                
                people.append({
                    "person": {
                        "id": person_id,
                        "name": person_name,
                        "url": person_url
                    },
                    "role": role
                })
        
        companies.append({
            "id": company_id,
            "name": company_name,
            "type": company_type,
            "url": company_url,
            "credits": people
        })
    
    return {
        "title": title,
        "client": client,
        "date": date,
        "location": location,
        "format": format_,
        "description": description,
        "video_links": video_links,
        "poster_image": poster_image,
        "companies": companies,
        "assets": {
            "image_url": poster_image
        },
        "meta": {
            "url": url,
            "scraped_at": datetime.datetime.utcnow().isoformat(),
            "unknown_roles": unknown_roles,
            "strategy": strategy.get("name", "unknown")
        }
    }

def validate_scraped_data(data: Dict) -> List[str]:
    """
    Validate the scraped data and return a list of missing or problematic keys.
    
    Args:
        data: The project data dictionary
        
    Returns:
        List of missing or problematic keys
    """
    missing = []
    
    # Required fields
    if not data.get("title"):
        missing.append("title")
        
    # Check companies
    if not data.get("companies"):
        missing.append("companies")
    else:
        # Check if any companies lack people
        companies_without_credits = [c["name"] for c in data["companies"] if not c.get("credits")]
        if companies_without_credits:
            missing.append("company_credits")
            
        # Check if any roles are missing
        missing_roles = False
        for company in data["companies"]:
            for credit in company.get("credits", []):
                if not credit.get("role"):
                    missing_roles = True
                    break
            if missing_roles:
                break
                
        if missing_roles:
            missing.append("roles")
    
    # Media validation
    if not data.get("video_links") and not data.get("poster_image"):
        missing.append("media")
    
    return missing

def suggest_fixes_via_openai(html: str, url: str, missing: List[str], snapshot_path: str) -> Dict:
    """
    Use Azure OpenAI to suggest fixes for missing data.
    
    Args:
        html: The HTML content
        url: The URL of the page
        missing: List of missing elements
        snapshot_path: Path to the HTML snapshot
        
    Returns:
        Dictionary with suggested fixes
    """
    try:
        # Import AI enhancer
        try:
            from backend.scrapy.scraper.ai_enhancer import AzureOpenAIEnhancer
        except ImportError:
            from ai_enhancer import AzureOpenAIEnhancer
        
        # Initialize the AI enhancer with selected model
        enhancer = AzureOpenAIEnhancer(model=CONFIG["AI_MODEL"])
        
        if not enhancer.enabled:
            logger.warning("⚠️ AI enhancement disabled. Returning placeholder suggestions.")
            return _generate_placeholder_suggestions(missing, snapshot_path)
        
        logger.info(f"🤖 Calling Azure OpenAI to fix: {', '.join(missing)}")
        
        # Get AI-suggested selectors
        suggestions = enhancer.suggest_selectors(html, missing, url)
        
        # Format the response
        result = {
            "suggestions": suggestions.get("selectors", {}),
            "explanations": suggestions.get("explanations", {}),
            "alternatives": suggestions.get("alternatives", {}),
            "custom_extraction_code": None,
            "snapshot_analyzed": snapshot_path
        }
        
        logger.info(f"✅ AI suggestions received for {len(result['suggestions'])} elements")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error using AI enhancer: {str(e)}")
        return _generate_placeholder_suggestions(missing, snapshot_path)

def _generate_placeholder_suggestions(missing: List[str], snapshot_path: str) -> Dict:
    """Generate fallback suggestions when AI is not available"""
    suggestions = {
        "title": "h1, .page-title, header h2",
        "companies": ".credits, .partners, .collaborators",
        "company_credits": ".team-member, .credit-person, .collaborator",
        "roles": "[data-role], .job-title, .position",
        "media": "iframe[src*=vimeo], iframe[src*=youtube], .thumbnail img"
    }
    
    return {
        "suggestions": {key: suggestions.get(key, "") for key in missing},
        "explanations": {key: "Fallback suggestion (AI unavailable)" for key in missing},
        "alternatives": {key: [] for key in missing},
        "custom_extraction_code": None,
        "snapshot_analyzed": snapshot_path
    }

def normalize_roles_with_ai(data: Dict, html: str) -> Dict:
    """
    Use AI to normalize unknown roles
    
    Args:
        data: The scraped data
        html: The HTML content
        
    Returns:
        Updated data dictionary
    """
    unknown_roles = data.get("meta", {}).get("unknown_roles", [])
    if not unknown_roles:
        return data
    
    try:
        # Import AI enhancer
        try:
            from backend.scrapy.scraper.ai_enhancer import AzureOpenAIEnhancer
        except ImportError:
            from ai_enhancer import AzureOpenAIEnhancer
        
        # Initialize the AI enhancer
        enhancer = AzureOpenAIEnhancer(model=CONFIG["AI_MODEL"])
        
        if not enhancer.enabled:
            logger.warning("⚠️ AI role normalization not available")
            return data
        
        # Get fallback mappings
        fallback_mapping = {}
        try:
            fallback_path = os.path.join(os.path.dirname(__file__), "fallback_mapping.json")
            with open(fallback_path, "r", encoding="utf-8") as f:
                mapping_data = json.load(f)
                fallback_mapping = mapping_data.get("role_mappings", {})
        except Exception as e:
            logger.warning(f"Could not load fallback_mapping.json: {e}")
        
        logger.info(f"🤖 Normalizing {len(unknown_roles)} unknown roles with AI")
        
        # Get AI-normalized roles
        normalized_roles = enhancer.normalize_roles(unknown_roles, fallback_mapping, html[:10000])
        
        # Update the data
        if normalized_roles:
            # Create a lookup for normalized roles
            role_lookup = {r["person_id"]: normalized_roles.get(r["person_id"]) for r in unknown_roles if r["person_id"] in normalized_roles}
            
            # Update company credits with normalized roles
            for company in data.get("companies", []):
                for credit in company.get("credits", []):
                    person_id = credit.get("person", {}).get("id")
                    if not credit.get("role") and person_id in role_lookup:
                        credit["role"] = role_lookup[person_id]
            
            # Update the meta information
            remaining_unknown = [r for r in unknown_roles if r["person_id"] not in normalized_roles]
            data["meta"]["unknown_roles"] = remaining_unknown
            data["meta"]["normalized_roles"] = normalized_roles
            data["meta"]["credits_enriched"] = True
        
        return data
        
    except Exception as e:
        logger.error(f"❌ Error normalizing roles: {str(e)}")
        return data

def scrape_project(url: str, fallback_mapping: Optional[Dict] = None, debug: bool = False, 
                  ai_enabled: bool = None, ai_model: Optional[str] = None,
                  normalize_roles: bool = False, strategy_file: Optional[str] = None,
                  strategy_name: Optional[str] = None) -> Dict:
    """
    Main function to scrape a project page.
    
    Args:
        url: URL of the project page
        fallback_mapping: Optional mapping for role/company normalization
        debug: Enable debug output
        ai_enabled: Override config setting for AI enhancement
        ai_model: Override config setting for AI model
        normalize_roles: Use AI to normalize unknown roles
        strategy_file: Path to a JSON file containing a custom strategy
        strategy_name: Name of a strategy (domain/version) to use
        
    Returns:
        Dictionary with project data
    """
    # Override config settings if specified
    if ai_enabled is not None:
        CONFIG["AI_ENABLED"] = ai_enabled
    
    if ai_model:
        CONFIG["AI_MODEL"] = ai_model
    
    # Load fallback mapping if not provided
    if fallback_mapping is None:
        try:
            fallback_path = os.path.join(os.path.dirname(__file__), "fallback_mapping.json")
            with open(fallback_path, "r", encoding="utf-8") as f:
                fallback_mapping = json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Failed to load fallback mapping: {e}")
            fallback_mapping = {"company_types": {}, "role_mappings": {}}
    
    # Step 1: Fetch HTML and save snapshot
    try:
        html, from_cache = fetch_html_and_snapshot(url, force_refresh=CONFIG["FORCE_REFRESH"])
    except Exception as e:
        logger.error(f"❌ Failed to fetch page: {e}")
        return {}
    
    # Step 2: Load strategy or select automatically
    strategy = None
    
    # First priority: Specific strategy file
    if strategy_file:
        try:
            logger.info(f"📊 Loading custom strategy from file: {strategy_file}")
            with open(strategy_file, "r", encoding="utf-8") as f:
                strategy = json.load(f)
            
            # Validate the strategy structure
            if not isinstance(strategy, dict):
                raise ValueError("Strategy must be a dictionary")
            
            if "selectors" not in strategy:
                raise ValueError("Strategy must contain a 'selectors' key")
                
            # Ensure all selector values are strings, not nested dictionaries
            for key, value in strategy.get("selectors", {}).items():
                if not isinstance(value, str):
                    logger.warning(f"⚠️ Selector '{key}' is not a string, converting to string representation")
                    strategy["selectors"][key] = str(value)
            
            logger.info(f"✅ Custom strategy loaded from file: {strategy.get('name', 'unknown')}")
        except Exception as e:
            logger.error(f"❌ Failed to load strategy file: {e}")
            strategy = None  # Will fall back to automatic selection
    
    # Second priority: Named strategy from structured directory
    if not strategy and strategy_name:
        try:
            # Extract domain and version from strategy name
            if "/" in strategy_name:
                domain, version = strategy_name.split("/", 1)
            else:
                # If only domain provided, use the latest version
                domain = strategy_name
                version = None
            
            # Find the strategy file
            strategy_dir = os.path.join(CONFIG["STRATEGIES_DIR"], domain)
            if not os.path.exists(strategy_dir):
                raise FileNotFoundError(f"Strategy directory not found: {strategy_dir}")
            
            if version:
                # Look for specific version
                strategy_files = [f for f in os.listdir(strategy_dir) if f.startswith(version)]
                if not strategy_files:
                    raise FileNotFoundError(f"No strategy file found for version {version} in {domain}")
                strategy_file = os.path.join(strategy_dir, strategy_files[0])
            else:
                # Find the latest version
                strategy_files = sorted(os.listdir(strategy_dir))
                if not strategy_files:
                    raise FileNotFoundError(f"No strategy files found in {domain}")
                strategy_file = os.path.join(strategy_dir, strategy_files[-1])
            
            logger.info(f"📊 Loading strategy from: {strategy_file}")
            with open(strategy_file, "r", encoding="utf-8") as f:
                strategy = json.load(f)
            
            # Validate and fix selectors
            if "selectors" in strategy:
                for key, value in strategy.get("selectors", {}).items():
                    if not isinstance(value, str):
                        strategy["selectors"][key] = str(value)
            
            logger.info(f"✅ Strategy loaded: {strategy.get('name', 'unknown')}")
        except Exception as e:
            logger.error(f"❌ Failed to load named strategy: {e}")
            strategy = None  # Will fall back to automatic selection
    
    # Final fallback: Automatic strategy selection
    if not strategy:
        strategy = select_strategy(html, url)
        logger.info(f"📊 Using auto-selected strategy: {strategy.get('name', 'unknown')}")
    
    # Rest of the function remains the same as before
    # Step 3: Extract data using strategy
    data = extract_project_data(html, strategy, url, fallback_mapping)
    
    # Step 4: Validate extracted data
    missing_elements = validate_scraped_data(data)
    
    # Step 5: If validation failed and AI is enabled, attempt AI-powered fix with retries
    if missing_elements and CONFIG["AI_ENABLED"]:
        retry_attempts = 0
        max_retries = 10
        all_suggestions = {}

        while missing_elements and CONFIG["AI_ENABLED"] and retry_attempts < max_retries:
            snapshot_path = os.path.join(SNAPSHOT_DIR, f"{urlparse(url).netloc.replace('www.', '')}_{hashlib.md5(url.encode()).hexdigest()[:10]}.html")
            fix_suggestions = suggest_fixes_via_openai(html, url, missing_elements, snapshot_path, previous_selectors=all_suggestions)
            new_selectors = fix_suggestions.get("suggestions", {})
            if not new_selectors:
                logger.warning("⚠️ No new selectors provided by AI. Breaking retry loop.")
                break
            all_suggestions.update(new_selectors)

            updated_strategy = {
                "name": strategy.get("name", "ai_retry"),
                "selectors": {**strategy.get("selectors", {}), **all_suggestions}
            }

            logger.info(f"🔁 Retry attempt {retry_attempts + 1} with AI-enhanced strategy: {updated_strategy['name']}")
            data = extract_project_data(html, updated_strategy, url, fallback_mapping)
            missing_elements = validate_scraped_data(data)

            data["meta"].update({
                "strategy_used": updated_strategy["name"],
                "ai_retry": True,
                "retry_attempts": retry_attempts + 1,
                "missing_elements_after_retry": missing_elements,
                "ai_suggestions": all_suggestions,
                "snapshot_analyzed": fix_suggestions.get("snapshot_analyzed"),
            })

            retry_attempts += 1

            if not missing_elements:
                break
    elif missing_elements:
        # AI is disabled but we still record missing elements
        data["meta"]["missing_elements"] = missing_elements
        data["meta"]["credits_enriched"] = False
    else:
        data["meta"]["credits_enriched"] = True
    
    # Normalize roles with AI if requested
    if normalize_roles and CONFIG["AI_ENABLED"]:
        data = normalize_roles_with_ai(data, html)
    
    # Record which strategy was used
    data["meta"]["strategy_used"] = strategy.get("name", "unknown")
    
    # Step 6: Return the structured data
    if debug:
        logger.info(json.dumps(data, indent=2))
    
    return data

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Scrape project data with the new architecture")
    parser.add_argument("url", nargs="+", help="URL(s) of the project(s) to scrape")
    parser.add_argument("--fallback", default=None, help="Path to fallback mapping JSON")
    parser.add_argument("--output", default=None, help="Path to save output JSON")
    parser.add_argument("--debug", action="store_true", help="Print debug output")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh HTML snapshot")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI enhancement")
    parser.add_argument("--ai-model", choices=["gpt-4o", "gpt-4o-mini", "o1-mini", "o3-mini"], 
                        help="AI model to use for enhancement")
    parser.add_argument("--normalize-roles", action="store_true", help="Use AI to normalize unknown roles")
    parser.add_argument("--strategy", help="Path to a JSON file containing a custom strategy")
    parser.add_argument("--strategy-name", help="Name of a strategy to use (domain/version)")
    
    args = parser.parse_args()
    
    # Update config based on arguments
    CONFIG["DEBUG_MODE"] = args.debug
    CONFIG["FORCE_REFRESH"] = args.force_refresh
    
    # Load fallback mapping if specified
    fallback_data = None
    if args.fallback:
        try:
            with open(args.fallback, "r", encoding="utf-8") as f:
                fallback_data = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load fallback mapping: {e}")
    
    # Process each URL
    results = []
    for url in args.url:
        logger.info(f"\n🚀 Scraping project: {url}")
        
        data = scrape_project(
            url, 
            fallback_mapping=fallback_data, 
            debug=args.debug,
            ai_enabled=not args.no_ai,
            ai_model=args.ai_model,
            normalize_roles=args.normalize_roles,
            strategy_file=args.strategy,
            strategy_name=args.strategy_name
        )
        
        results.append(data)
    
    # Save output
    if args.output:
        # If more than one result, save as an array
        if len(results) > 1:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
        # If just one result, save as a single object
        elif results:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results[0], f, indent=2)
            
        logger.info(f"\n✅ Saved scraped project(s) to {args.output}")
    else:
        # Use organized directory structure for results
        for i, result in enumerate(results):
            if result:
                try:
                    # Extract domain from URL
                    domain = urlparse(args.url[i]).netloc.replace("www.", "").split(".")[0]
                    
                    # Import the config function
                    try:
                        from backend.scrapy.utils.config import CONFIG, get_next_version
                    except ImportError:
                        from utils.config import CONFIG, get_next_version
                    
                    # Get the next sequential version number
                    next_id = get_next_version(domain, CONFIG["RESULTS_DIR"], "")
                    
                    # Create a clean title for the filename
                    title = result.get("title", "untitled")
                    clean_title = re.sub(r'[^\w\s-]', '', title).strip().lower()
                    clean_title = re.sub(r'[-\s]+', '_', clean_title)
                    
                    # Limit title length
                    if len(clean_title) > 30:
                        clean_title = clean_title[:30]
                    
                    # Create filename
                    filename = f"{next_id}_{clean_title}.json"
                    domain_dir = os.path.join(CONFIG["RESULTS_DIR"], domain)
                    os.makedirs(domain_dir, exist_ok=True)
                    output_path = os.path.join(domain_dir, filename)
                    
                    # Save result
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2)
                    
                    logger.info(f"\n✅ Saved result to {output_path}")
                    
                except Exception as e:
                    # Fall back to old approach if there's an error
                    logger.error(f"Error using structured save: {e}")
                    save_test_result(result, args.url[i])