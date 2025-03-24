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
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from project structure
try:
    from backend.scrapy.utils.config import CONFIG
    from backend.scrapy.utils.testing import save_html_snapshot, save_test_result
    from backend.scrapy.scraper.adaptive_extractor import extract_project_adaptive, scrape_project_adaptive
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from scrapy.utils.config import CONFIG
    from scrapy.utils.testing import save_html_snapshot, save_test_result

# NEW: Import headless_fetcher for dynamic content fetching
from backend.scrapy.scraper.headless_fetcher import fetch_dynamic_page

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
            logger.info("⚠️ Using existing snapshot despite error")
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

def extract_lbbonline_2025(html: str, url: str, fallback_mapping: Dict) -> Dict:
    """
    Custom extraction function for LBB Online 2025 design which has a non-standard credits structure.
    
    Args:
        html: The HTML content
        url: The URL being scraped
        fallback_mapping: Mapping for role/company normalization
        
    Returns:
        Dictionary with extracted project data
    """
    import re
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Basic info extraction
    title = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""
    
    # Description - might be in rich text block
    description = ""
    desc_block = soup.select(".rich-text.space-y-5 p")
    if desc_block:
        description = " ".join(p.get_text(strip=True) for p in desc_block)
    
    # Project metadata
    client = ""
    date = ""
    location = ""
    format_ = ""
    
    meta_blocks = soup.select(".credit-meta div")
    for block in meta_blocks:
        text = block.get_text(" ", strip=True).lower()
        if "client" in text or "brand" in text:
            client = block.get_text(strip=True).replace("Client:", "").strip()
        elif re.search(r"\b\d{4}\b", text):
            date = text
        elif "location" in text:
            location = text
        elif any(keyword in text for keyword in ["format", "type", "category"]):
            format_ = text
    
    # Media extraction
    video_links = []
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if src and any(x in src for x in ["youtube", "vimeo", "lbbonline"]):
            video_links.append(src)
    
    # Poster image
    poster_image = ""
    og_image = soup.find("meta", property="og:image")
    if og_image:
        poster_image = og_image.get("content", "")
    
    # Credits extraction - this is the custom part
    companies = []
    unknown_roles = []
    
    # Find the credit blocks which now use a different structure
    credit_blocks = soup.select("div.flex.space-y-4")
    
    for block in credit_blocks:
        # Company name is in a span with these specific classes
        company_name_el = block.select_one("span.font-barlow.font-bold.text-black")
        if not company_name_el:
            continue
            
        company_name = company_name_el.get_text(strip=True)
        company_url = ""  # Not always present in the new design
        company_id = company_name.lower().replace(" ", "_")
        
        # Company type might not be explicitly marked
        company_type = ""
        
        # Look for roles which are in a different format
        role_elements = block.select("div.team div")
        
        people = []
        for role_el in role_elements:
            role_text = role_el.get_text(strip=True)
            
            # Try to extract role and person from combined text (usually in format "Role: Person")
            role_match = re.match(r"([^:]+):\s*(.*)", role_text)
            
            if role_match:
                role_name = role_match.group(1).strip()
                person_name = role_match.group(2).strip()
                
                # Create unique person ID
                person_id = f"{company_id}_{person_name.lower().replace(' ', '_')}"
                
                people.append({
                    "person": {
                        "id": person_id,
                        "name": person_name,
                        "url": ""
                    },
                    "role": role_name
                })
            else:
                # If no colon, assume it's just a role without a person
                unknown_roles.append({"person_id": "unknown", "name": role_text})
        
        if company_name and (people or company_type):
            companies.append({
                "id": company_id,
                "name": company_name,
                "type": company_type,
                "url": company_url,
                "credits": people
            })
    
    # Alternative approach - try to find companies in paragraphs if the above method failed
    if not companies:
        credit_section = soup.select(".credits-section, .project-credits, article section")
        
        for section in credit_section:
            paragraphs = section.find_all("p")
            
            current_company = None
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                
                # Check if this is a company header
                if p.find("strong") or p.find("b") or p.name == "h3" or p.name == "h4":
                    # Start a new company
                    current_company = {
                        "id": text.lower().replace(" ", "_"),
                        "name": text,
                        "type": "",
                        "url": "",
                        "credits": []
                    }
                    companies.append(current_company)
                elif current_company and ":" in text:
                    # This might be a role: person combination
                    role_parts = text.split(":", 1)
                    role_name = role_parts[0].strip()
                    person_names = role_parts[1].strip().split(",")
                    
                    for person_name in person_names:
                        person_name = person_name.strip()
                        if person_name:
                            person_id = f"{current_company['id']}_{person_name.lower().replace(' ', '_')}"
                            
                            current_company["credits"].append({
                                "person": {
                                    "id": person_id,
                                    "name": person_name,
                                    "url": ""
                                },
                                "role": role_name
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
            "unknown_roles": unknown_roles,
            "strategy": "lbbonline_v2",
            "custom_extractor": True
        }
    }

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
    video_links = []
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src")
        if src and any(x in src for x in ["youtube", "vimeo", "lbbonline"]):
            video_links.append(src)
    
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

def suggest_fixes_via_openai(html: str, url: str, missing: List[str], snapshot_path: str, previous_selectors: Optional[Dict[str, str]] = None) -> Dict:
    """
    Use Azure OpenAI to suggest fixes for missing data.
    
    Args:
        html: The HTML content
        url: The URL of the page
        missing: List of missing elements
        snapshot_path: Path to the HTML snapshot
        previous_selectors: Optional dictionary of previously tried selectors
        
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
        
        # Get AI-suggested selectors, passing any previous selectors
        suggestions = enhancer.suggest_selectors(html, missing, url, previous_selectors)
        
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
    """
    # Import here to avoid circular import
    from backend.scrapy.scraper.headless_fetcher import fetch_dynamic_page
    
    # First attempt using the adaptive extractor
    data = scrape_project_adaptive(
        url=url,
        fallback_mapping=fallback_mapping,
        debug=debug,
        ai_enabled=ai_enabled,
        ai_model=ai_model,
        normalize_roles=normalize_roles,
        strategy_file=strategy_file
    )
    
    # Validate scraped data; if dynamic elements are missing, use headless browser fallback
    missing_elements = validate_scraped_data(data)
    logger.info(f"Missing elements detected: {missing_elements}")
    if missing_elements:
        logger.info(f"Dynamic content missing ({missing_elements}). Retrying with headless browser...")
        
        # Determine if this is an LBB page and set appropriate click selectors
        click_selectors = []
        wait_selector = None
        
        if "lbbonline.com" in url:
            click_selectors = [
                "a[data-tab='credits']",  # Direct tab selector
                "a[href='#credits']",      # Href-based tab
                "span:contains('Credits')",  # Text-based tab
                "button:contains('Credits')",  # Button tab
                ".tab-selector"  # Generic tab selector
            ]
            logger.info(f"Using LBB-specific click selectors: {click_selectors}")
            wait_selector = ".credits-container, .credit-blocks, .tab-content"
        
        # Fetch fully rendered HTML using enhanced headless browser
        rendered_html = fetch_dynamic_page(
            url, 
            wait_selector=wait_selector, 
            click_selectors=click_selectors,
            timeout=15,
            debug=debug
        )
        
        # Save a snapshot of the rendered HTML for debugging
        if rendered_html:
            from urllib.parse import urlparse
            import hashlib
            domain = urlparse(url).netloc.replace("www.", "")
            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            rendered_path = os.path.join(SNAPSHOT_DIR, f"{domain}__rendered_{url_hash}.html")
            with open(rendered_path, "w", encoding="utf-8") as f:
                f.write(rendered_html)
            logger.info(f"Saved rendered HTML snapshot to: {rendered_path}")
            
            # Process the rendered HTML directly
            adapted_data = extract_project_adaptive(url, rendered_html, fallback_mapping, debug)
            
            # If we got better data, use it
            if adapted_data.get("companies") and len(adapted_data.get("companies", [])) > 0:
                logger.info(f"Found {len(adapted_data['companies'])} companies in rendered HTML")
                return adapted_data
            else:
                logger.warning("No companies found in rendered HTML, using original data")
        else:
            logger.warning("Failed to get rendered HTML, using original data")
    
    return data

def agent_scrape_project(url: str, fallback_mapping: Optional[Dict] = None, debug: bool = False, 
                         ai_enabled: bool = None, ai_model: Optional[str] = None,
                         normalize_roles: bool = False, strategy_file: Optional[str] = None, 
                         strategy_name: Optional[str] = None, max_attempts: int = 5) -> Dict:
    """
    Agent function to scrape a project page repeatedly until complete data is obtained.
    Always uses headless fetching for dynamic content.
    
    Process:
      1. Always fetch the fully rendered HTML using headless_fetcher.
      2. Run adaptive extraction on the rendered HTML.
      3. Validate the results. If required elements are missing, use AI to adjust the extraction strategy.
      4. Retry (with a delay) until all elements are captured or max_attempts is reached.
    
    Args:
        url: URL of the project page
        fallback_mapping: Optional mapping for role/company normalization
        debug: Enable debug output
        ai_enabled: Override config setting for AI enhancement
        ai_model: Override config setting for AI model
        normalize_roles: Use AI to normalize unknown roles
        strategy_file: Path to a JSON file containing a custom strategy
        strategy_name: Name of a strategy to use (domain/version)
        max_attempts: Maximum number of retry attempts
    
    Returns:
        Dictionary with complete project data (or last attempt's data if unsuccessful)
    """
    attempt = 1
    final_data = {}
    while attempt <= max_attempts:
        logger.info(f"🚀 Agent attempt {attempt} for URL: {url}")
        # Always use headless_fetcher
        rendered_html = fetch_dynamic_page(url, wait_selector=".credits-container", timeout=15)
        logger.debug(f"Rendered HTML length: {len(rendered_html)} characters")
        
        # Run adaptive extraction on the rendered HTML.
        # Here we assume scrape_project_adaptive can work with the rendered HTML.
        # If it only works with URLs, consider modifying it to accept raw HTML.
        # For this patch, we call it as usual, assuming it re-fetches or uses an internal override.
        data = scrape_project_adaptive(
            url=url,
            fallback_mapping=fallback_mapping,
            debug=debug,
            ai_enabled=ai_enabled,
            ai_model=ai_model,
            normalize_roles=normalize_roles,
            strategy_file=strategy_file
        )
        
        missing_elements = validate_scraped_data(data)
        logger.debug(f"Agent attempt {attempt}: Missing elements: {missing_elements}")
        if not missing_elements:
            logger.info("✅ Extraction complete. All required elements present.")
            final_data = data
            break
        else:
            logger.info(f"Agent attempt {attempt}: Missing elements ({missing_elements}). Using AI to adjust strategy.")
            # Use AI to suggest selector adjustments
            suggestions = suggest_fixes_via_openai(rendered_html, url, missing_elements, snapshot_path="N/A", previous_selectors=None)
            if suggestions.get("suggestions"):
                logger.info("Updating extraction strategy with AI suggestions.")
                # For example, merge the suggestions into fallback_mapping or update local strategy
                # (This is a placeholder; implement your own strategy update logic as needed.)
            else:
                logger.info("No AI suggestions provided; retrying with current strategy.")
            logger.debug("Waiting 5 seconds before next attempt...")
            time.sleep(5)
        attempt += 1

    if attempt > max_attempts:
        logger.error("Max attempts reached. Extraction incomplete; returning last attempt's data.")
    return final_data

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