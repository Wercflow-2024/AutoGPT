#!/usr/bin/env python3
"""
Snapshot Analyzer Utility

This script helps analyze and debug HTML snapshots, comparing them with extraction results.
It's useful for diagnosing scraping issues and developing new extraction strategies.

Features:
- List all available snapshots
- Analyze HTML structure of a snapshot
- Test CSS selectors on snapshots
- Compare snapshots with extraction results
- Find missing elements and suggest fixes
- Generate selector suggestions for different site patterns
"""

import os
import json
import re
import argparse
from typing import Dict, List, Optional, Tuple, Any
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging

# Import from project structure
try:
    from backend.scrapy.utils.config import CONFIG
except ImportError:
    # For standalone testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    try:
        from scrapy.utils.config import CONFIG
    except ImportError:
        # Define basic config if cannot import
        CONFIG = {
            "SNAPSHOT_DIR": os.path.join(os.path.dirname(os.path.dirname(__file__)), "snapshots"),
            "RESULTS_DIR": os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_results"),
            "AI_MODEL": "gpt-4o-mini"
        }

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("snapshot_analyzer")

SNAPSHOT_DIR = CONFIG["SNAPSHOT_DIR"]
RESULTS_DIR = CONFIG["RESULTS_DIR"]

def list_snapshots():
    """List all available HTML snapshots"""
    if not os.path.exists(SNAPSHOT_DIR):
        logger.error(f"Snapshot directory not found: {SNAPSHOT_DIR}")
        return []
    
    snapshots = [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".html")]
    
    if not snapshots:
        logger.warning("No snapshots found!")
        return []
    
    logger.info(f"Found {len(snapshots)} snapshots:")
    
    for i, snapshot in enumerate(snapshots):
        domain_match = re.match(r"([^_]+)__", snapshot)
        domain = domain_match.group(1) if domain_match else "unknown"
        
        path = os.path.join(SNAPSHOT_DIR, snapshot)
        size = os.path.getsize(path) / 1024  # KB
        created = os.path.getctime(path)
        
        logger.info(f"{i+1}. {snapshot} ({domain}, {size:.1f} KB)")
    
    return snapshots

def analyze_snapshot(snapshot_file, show_html=False, selector=None):
    """Analyze a specific HTML snapshot"""
    if not os.path.exists(os.path.join(SNAPSHOT_DIR, snapshot_file)):
        logger.error(f"Snapshot file not found: {snapshot_file}")
        return
    
    with open(os.path.join(SNAPSHOT_DIR, snapshot_file), "r", encoding="utf-8") as f:
        html = f.read()
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Basic stats
    title = soup.find("title").get_text() if soup.find("title") else "No title"
    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = meta_desc.get("content") if meta_desc else "No description"
    
    # Count elements
    links = len(soup.find_all("a"))
    images = len(soup.find_all("img"))
    iframes = len(soup.find_all("iframe"))
    
    logger.info(f"\n=== Snapshot: {snapshot_file} ===")
    logger.info(f"Title: {title}")
    logger.info(f"Description: {description}")
    logger.info(f"Elements: {links} links, {images} images, {iframes} iframes")
    
    # If a selector is provided, show matching elements
    if selector:
        matching = soup.select(selector)
        logger.info(f"\nElements matching selector: {selector} ({len(matching)} found)")
        
        for i, elem in enumerate(matching[:5]):  # Show first 5 matches
            logger.info(f"\nMatch #{i+1}:")
            html_str = str(elem)
            logger.info(f"{html_str[:500]}..." if len(html_str) > 500 else html_str)
        
        if len(matching) > 5:
            logger.info(f"...and {len(matching) - 5} more matches")
    
    # Show full HTML if requested
    if show_html:
        logger.info("\nFull HTML:")
        logger.info(f"{html[:5000]}..." if len(html) > 5000 else html)

def find_extraction_results(snapshot_name):
    """Find extraction results that might correspond to this snapshot"""
    if not os.path.exists(RESULTS_DIR):
        logger.warning(f"Results directory not found: {RESULTS_DIR}")
        return []
    
    domain_match = re.match(r"([^_]+)__", snapshot_name)
    domain = domain_match.group(1) if domain_match else None
    
    if not domain:
        return []
    
    results = [f for f in os.listdir(RESULTS_DIR) if f.startswith(domain) and f.endswith(".json")]
    return results

def compare_snapshot_with_extraction(snapshot_file, result_file=None):
    """Compare snapshot with extraction results"""
    if not os.path.exists(os.path.join(SNAPSHOT_DIR, snapshot_file)):
        logger.error(f"Snapshot file not found: {snapshot_file}")
        return
    
    # Find extraction results if not specified
    if not result_file:
        results = find_extraction_results(snapshot_file)
        if not results:
            logger.warning("No matching extraction results found!")
            return
        result_file = results[0]  # Use the first match
    
    # Load the snapshot
    with open(os.path.join(SNAPSHOT_DIR, snapshot_file), "r", encoding="utf-8") as f:
        html = f.read()
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Load the extraction results
    with open(os.path.join(RESULTS_DIR, result_file), "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Print comparison
    logger.info(f"\n=== Comparison: {snapshot_file} ↔ {result_file} ===")
    
    # Basic metadata
    logger.info("\n-- Metadata --")
    logger.info(f"Title: {data.get('title', 'Missing')}")
    logger.info(f"Client: {data.get('client', 'Missing')}")
    logger.info(f"Date: {data.get('date', 'Missing')}")
    logger.info(f"Format: {data.get('format', 'Missing')}")
    
    # Media
    logger.info("\n-- Media --")
    if data.get('poster_image'):
        logger.info(f"Poster: {data.get('poster_image')}")
    else:
        logger.info("No poster image")
    
    if data.get('video_links'):
        logger.info(f"Videos: {len(data.get('video_links', []))}")
        for video in data.get('video_links', [])[:3]:  # Show first 3
            logger.info(f"  {video}")
        if len(data.get('video_links', [])) > 3:
            logger.info(f"  ...and {len(data.get('video_links', [])) - 3} more")
    else:
        logger.info("No video links")
    
    # Companies and credits
    companies = data.get('companies', [])
    logger.info(f"\n-- Companies: {len(companies)} --")
    
    total_credits = 0
    for company in companies[:5]:  # Show first 5 companies
        credits = company.get('credits', [])
        total_credits += len(credits)
        logger.info(f"\n{company.get('name', 'Unknown')} ({company.get('type', 'Unknown')}) - {len(credits)} credits")
        
        # Show first 3 credits for each company
        for credit in credits[:3]:
            person = credit.get('person', {})
            logger.info(f"  {credit.get('role', 'Unknown role')}: {person.get('name', 'Unknown')}")
        
        if len(credits) > 3:
            logger.info(f"  ...and {len(credits) - 3} more credits")
    
    if len(companies) > 5:
        logger.info(f"...and {len(companies) - 5} more companies")
    
    # Missing elements
    missing = data.get('meta', {}).get('missing_elements', [])
    if missing:
        logger.info(f"\n-- Missing Elements: {len(missing)} --")
        for element in missing:
            logger.info(f"  {element}")
        
        # AI suggestions if available
        ai_suggestions = data.get('meta', {}).get('ai_suggestions', {})
        if ai_suggestions:
            logger.info("\n-- AI Suggestions --")
            for element, suggestion in ai_suggestions.items():
                logger.info(f"  {element}: {suggestion}")
    
    # Verification - check if elements found in extraction actually exist in HTML
    logger.info("\n-- Verification --")
    
    # Title verification
    title_in_html = soup.select_one("h1")
    if title_in_html and data.get('title'):
        if title_in_html.get_text(strip=True) == data.get('title'):
            logger.info("✅ Title verified in HTML")
        else:
            logger.info("⚠️ Title mismatch:")
            logger.info(f"  HTML: {title_in_html.get_text(strip=True)}")
            logger.info(f"  Data: {data.get('title')}")
    
    # Company verification - check if first company name exists in HTML
    if companies:
        first_company = companies[0].get('name')
        if first_company:
            # Try to find text in HTML
            company_in_html = False
            for tag in soup.find_all(['span', 'div', 'p', 'h2', 'h3', 'a']):
                if first_company in tag.get_text(strip=True):
                    company_in_html = True
                    break
            
            if company_in_html:
                logger.info(f"✅ Company name '{first_company}' verified in HTML")
            else:
                logger.info(f"⚠️ Company name '{first_company}' not found in HTML")
    
    # Return data for potential further analysis
    return data

def suggest_selectors(html_content, target_element="credits"):
    """
    Suggest CSS selectors that might be useful for extracting specific elements.
    
    Args:
        html_content: HTML content to analyze
        target_element: Type of element to find selectors for (credits, companies, people, etc.)
    
    Returns:
        List of suggested selectors
    """
    soup = BeautifulSoup(html_content, "html.parser")
    suggestions = []
    
    if target_element == "credits" or target_element == "all":
        # Look for credit-like sections
        credit_candidates = []
        
        # Strategy 1: Look for repeated div structures with names/roles
        sections = soup.find_all(['section', 'div'], class_=lambda x: x and any(term in x.lower() for term in 
                                                           ['credit', 'team', 'crew', 'collaborator', 'contributor']))
        if sections:
            for section in sections:
                suggestions.append(f"CSS: {get_css_path(section)}")
        
        # Strategy 2: Look for tables with role/name columns
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) >= 3:  # At least a header row and two data rows
                suggestions.append(f"Table: {get_css_path(table)}")
        
        # Strategy 3: Look for list structures (ul/li) with names
        lists = soup.find_all(['ul', 'ol'], class_=lambda x: x and any(term in (x.lower() if x else '') for term in 
                                                         ['team', 'credit', 'people', 'staff']))
        if lists:
            for lst in lists:
                suggestions.append(f"List: {get_css_path(lst)}")
    
    elif target_element == "companies" or target_element == "all":
        # Look for company references
        company_candidates = []
        
        # Strategy 1: Look for company logos
        logos = soup.find_all(['img'], alt=lambda x: x and any(term in (x.lower() if x else '') for term in 
                                                 ['logo', 'company', 'agency', 'studio']))
        if logos:
            for logo in logos:
                suggestions.append(f"Company logo: {get_css_path(logo)}")
        
        # Strategy 2: Look for company sections
        company_sections = soup.find_all(['div', 'section'], class_=lambda x: x and any(term in (x.lower() if x else '') for term in 
                                                                ['company', 'agency', 'production', 'studio']))
        if company_sections:
            for section in company_sections:
                suggestions.append(f"Company section: {get_css_path(section)}")
    
    elif target_element == "media" or target_element == "all":
        # Video embeds
        iframes = soup.find_all('iframe', src=lambda x: x and any(site in (x.lower() if x else '') for site in 
                                                     ['youtube', 'vimeo', 'player']))
        if iframes:
            for iframe in iframes:
                suggestions.append(f"Video iframe: {get_css_path(iframe)}")
        
        # Main images
        main_images = soup.find_all(['img'], class_=lambda x: x and any(term in (x.lower() if x else '') for term in 
                                                        ['hero', 'main', 'featured', 'poster', 'cover']))
        if main_images:
            for img in main_images:
                suggestions.append(f"Main image: {get_css_path(img)}")
    
    return suggestions

def get_css_path(element):
    """Generate a CSS path for an element"""
    path_parts = []
    
    # Add tag
    tag = element.name
    path_parts.append(tag)
    
    # Add classes (max 2)
    classes = element.get('class', [])
    if classes:
        for cls in classes[:2]:
            path_parts[-1] += f".{cls}"
    
    # Add id if present
    element_id = element.get('id')
    if element_id:
        path_parts[-1] += f"#{element_id}"
    
    return " > ".join(path_parts)

def generate_strategy_suggestions(snapshot_file, use_ai=False, output=None):
    """
    Analyze a snapshot and suggest a complete scraping strategy
    
    Args:
        snapshot_file: Path to the HTML snapshot file
        use_ai: Whether to use AI for strategy generation
        output: Optional output file path to save the strategy
        
    Returns:
        Dictionary with strategy details
    """
    if not os.path.exists(os.path.join(SNAPSHOT_DIR, snapshot_file)):
        logger.error(f"Snapshot file not found: {snapshot_file}")
        return
    
    with open(os.path.join(SNAPSHOT_DIR, snapshot_file), "r", encoding="utf-8") as f:
        html = f.read()
    
    # Extract domain from snapshot filename
    domain_match = re.match(r"([^_]+)__", snapshot_file)
    domain = domain_match.group(1) if domain_match else "unknown"
    
    # Try to use AI if requested
    if use_ai:
        try:
            # Import AI enhancer
            try:
                from backend.scrapy.scraper.ai_enhancer import AzureOpenAIEnhancer
            except ImportError:
                try:
                    from ai_enhancer import AzureOpenAIEnhancer
                except ImportError:
                    logger.warning("Could not import AI enhancer. Using fallback strategy generation.")
                    use_ai = False
            
            if use_ai:
                # Initialize the AI enhancer
                enhancer = AzureOpenAIEnhancer(model=CONFIG.get("AI_MODEL", "gpt-4o-mini"))
                
                if enhancer.enabled:
                    logger.info("Using AI to generate strategy suggestions...")
                    # Mock URL for analysis
                    url = f"https://{domain}/example"
                    
                    strategy = enhancer.analyze_html_structure(html, url)
                    
                    # Ensure the strategy has the correct format
                    if "selectors" in strategy:
                        # Convert any non-string selector values to strings
                        for key, value in strategy["selectors"].items():
                            if not isinstance(value, str):
                                logger.warning(f"Correcting non-string selector for {key}")
                                strategy["selectors"][key] = str(value)
                    
                    # Add domain and version info if not present
                    if "name" not in strategy:
                        strategy["name"] = f"{domain}_v1"
                    
                    logger.info("\nAI-suggested strategy:")
                    logger.info(json.dumps(strategy, indent=2))
                    
                    # Save to file if requested
                    if output:
                        save_strategy_to_file(strategy, domain, output)
                    
                    return strategy
                else:
                    logger.warning("AI enhancement not available. Using fallback strategy generation.")
                    use_ai = False
        except Exception as e:
            logger.error(f"Error using AI for strategy generation: {e}")
            logger.info("Falling back to standard strategy generation.")
            use_ai = False
    
    # Generate suggestions for all types of elements
    credit_suggestions = suggest_selectors(html, "credits")
    company_suggestions = suggest_selectors(html, "companies")
    media_suggestions = suggest_selectors(html, "media")
    
    # Basic structure detection
    soup = BeautifulSoup(html, "html.parser")
    title_selector = "h1"
    if not soup.select_one("h1"):
        # Try alternative title selectors
        for selector in [".title", ".page-title", "header h2", ".main-title"]:
            if soup.select_one(selector):
                title_selector = selector
                break
    
    # Extract a cleaner selector string from suggestions
    def clean_selector(suggestions):
        if not suggestions:
            return ""
        parts = suggestions[0].split(": ")
        return parts[1] if len(parts) > 1 else ""
    
    # Generate strategy
    strategy = {
        "name": f"{domain}_v1",
        "selectors": {
            "title": title_selector,
            "description": ".description, .summary, .abstract, article p:first-of-type",
            "project_info": ".info, .details, .metadata, .meta-info",
            "credit_blocks": clean_selector(credit_suggestions) or ".credits, .team, .crew",
            "company_name": clean_selector(company_suggestions) or ".company, .agency, .studio",
            "company_type": ".type, .category, .company-category",
            "role_blocks": ".role, .position, .job, .title-holder",
            "role_name": ".role-name, .position-name, .job-title",
            "person": ".person, .member, .crew-member, .staff-member",
            "person_name": ".name, a, span",
        }
    }
    
    # Display results
    logger.info("\nGenerated Scraping Strategy:")
    logger.info(json.dumps(strategy, indent=2))
    
    # Save to file if requested
    if output:
        save_strategy_to_file(strategy, domain, output)
    
    return strategy

def save_strategy_to_file(strategy, domain, output=None):
    """
    Save a strategy to a file with sequential versioning
    
    Args:
        strategy: The strategy dictionary
        domain: The domain the strategy is for
        output: Optional specific output path
    """
    try:
        # Import config to get the strategies directory
        try:
            from backend.scrapy.utils.config import CONFIG, get_next_version
        except ImportError:
            from utils.config import CONFIG, get_next_version
            
        if output:
            # Use the specified output path
            output_path = output
        else:
            # Use the structured directory with versioning
            next_version = get_next_version(domain, CONFIG["STRATEGIES_DIR"], "v")
            strategy_name = strategy.get("name", "custom").replace(" ", "_")
            filename = f"{next_version}_{strategy_name}.json"
            domain_dir = os.path.join(CONFIG["STRATEGIES_DIR"], domain)
            os.makedirs(domain_dir, exist_ok=True)
            output_path = os.path.join(domain_dir, filename)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(strategy, f, indent=2)
        logger.info(f"Strategy saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving strategy to file: {e}")
        # Fallback to direct save if structured save fails
        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(strategy, f, indent=2)
            logger.info(f"Strategy saved to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze HTML snapshots and extraction results")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List snapshots command
    list_parser = subparsers.add_parser("list", help="List all available snapshots")
    
    # Analyze snapshot command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a specific snapshot")
    analyze_parser.add_argument("snapshot", help="Snapshot filename to analyze")
    analyze_parser.add_argument("--html", action="store_true", help="Show full HTML")
    analyze_parser.add_argument("--selector", help="Test a specific CSS selector")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare snapshot with extraction results")
    compare_parser.add_argument("snapshot", help="Snapshot filename")
    compare_parser.add_argument("--result", help="Result JSON filename (optional)")
    
    # Suggest command
    suggest_parser = subparsers.add_parser("suggest", help="Suggest CSS selectors for extraction")
    suggest_parser.add_argument("snapshot", help="Snapshot filename")
    suggest_parser.add_argument("--element", choices=["credits", "companies", "media", "all"], 
                              default="all", help="Element type to suggest selectors for")
    
    # Generate strategy command
    strategy_parser = subparsers.add_parser("strategy", help="Generate a complete scraping strategy")
    strategy_parser.add_argument("snapshot", help="Snapshot filename")
    strategy_parser.add_argument("--output", help="Save strategy to JSON file")
    strategy_parser.add_argument("--ai", action="store_true", help="Use AI to generate strategy")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_snapshots()
    
    elif args.command == "analyze":
        analyze_snapshot(args.snapshot, args.html, args.selector)
    
    elif args.command == "compare":
        compare_snapshot_with_extraction(args.snapshot, args.result)
    
    elif args.command == "suggest":
        if not os.path.exists(os.path.join(SNAPSHOT_DIR, args.snapshot)):
            logger.error(f"Snapshot file not found: {args.snapshot}")
        else:
            with open(os.path.join(SNAPSHOT_DIR, args.snapshot), "r", encoding="utf-8") as f:
                html = f.read()
            
            suggestions = suggest_selectors(html, args.element)
            
            logger.info(f"\nSuggested selectors for {args.element}:")
            for i, suggestion in enumerate(suggestions):
                logger.info(f"{i+1}. {suggestion}")
    
    elif args.command == "strategy":
        strategy = generate_strategy_suggestions(args.snapshot, args.ai)
        
        if args.output and strategy:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(strategy, f, indent=2)
            logger.info(f"Strategy saved to: {args.output}")
    
    else:
        parser.print_help()