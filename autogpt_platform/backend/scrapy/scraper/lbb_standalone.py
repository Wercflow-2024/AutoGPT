#!/usr/bin/env python3
"""
Standalone LBB Credits Extractor

This script focuses solely on extracting credits from LBB pages using the embedded JSON data approach.
Run this directly to test extraction from a specific URL or HTML file.

Usage:
  python lbb_standalone.py --url https://lbbonline.com/work/132158
  python lbb_standalone.py --file lbbonline.com__950813dc8f.html
  python lbb_standalone.py --file lbbonline.com__950813dc8f.html --fallback fallback_mapping.json
"""

import re
import json
import os
import argparse
import requests
import logging
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin
import time
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("lbb_extractor.log"),
        logging.StreamHandler()
    ],
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("lbb_extractor")

class LBBCreditsExtractor:
    """Specialized extractor for LBB website credits"""
    
    def __init__(self, fallback_mapping: Optional[Dict] = None, debug: bool = False):
        self.fallback_mapping = fallback_mapping or {
            "company_types": {},
            "role_mappings": {}
        }
        self.debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)
        
        logger.info("LBB Credits Extractor initialized")
        if fallback_mapping:
            logger.info(f"Using fallback mapping with {len(fallback_mapping.get('company_types', {}))} company types and {len(fallback_mapping.get('role_mappings', {}))} role mappings")
    
    def extract_credits(self, html: str, url: str) -> Dict:
        """
        Extract credits and other data from LBB page HTML
        
        Args:
            html: The HTML content of the page
            url: The URL of the page
            
        Returns:
            Dictionary with structured credits data
        """
        logger.info(f"Starting extraction for URL: {url}")
        logger.info(f"HTML length: {len(html)} characters")
        
        # Start with basic result structure
        result = {
            'url': url,
            'title': '',
            'brand': '',
            'description': '',
            'video_links': [],
            'poster_image': '',
            'companies': [],
            'meta': {
                'extraction_method': 'lbb_json_extractor',
                'credits_found': False
            }
        }
        
        # Extract basic metadata
        self._extract_basic_metadata(html, result)
        
        # Try to extract credits from embedded JSON
        found_credits = False
        
        logger.info("Attempting to extract credits from lbb_credits JSON...")
        lbb_credits_found = self._extract_from_lbb_credits(html, result)
        
        # If that fails, try old_credits format
        if not lbb_credits_found:
            logger.info("lbb_credits extraction failed, trying old_credits format...")
            old_credits_found = self._extract_from_old_credits(html, result)
            found_credits = old_credits_found
        else:
            found_credits = True
        
        # If still no credits, look for structured DOM elements that might contain credits
        if not found_credits:
            logger.info("JSON credits extraction failed, trying DOM-based extraction...")
            dom_credits_found = self._extract_from_dom(html, result)
            found_credits = dom_credits_found
            
        # Set credits_found flag
        result['meta']['credits_found'] = found_credits
        
        # Set a default "credits not found" message if needed
        if not found_credits:
            logger.warning("No credits found using any extraction method")
            result['meta']['error'] = "No credits found using any extraction method"
        
        return result
    
    def _extract_basic_metadata(self, html: str, result: Dict) -> None:
        """Extract basic metadata like title, description, etc."""
        logger.info("Extracting basic metadata...")
        
        # Extract brand_and_name
        brand_name_match = re.search(r'"brand_and_name":"([^"]+)"', html)
        if brand_name_match:
            full_title = brand_name_match.group(1).strip()
            logger.debug(f"Found brand_and_name: {full_title}")
            
            if " - " in full_title:
                brand, title = full_title.split(" - ", 1)
                result['brand'] = brand.strip()
                result['title'] = title.strip()
                logger.info(f"Extracted brand: '{brand.strip()}' and title: '{title.strip()}'")
            else:
                result['title'] = full_title
                logger.info(f"Extracted title: '{full_title}'")
        
        # Fallback title extraction
        if not result['title']:
            title_tag = re.search(r'<title>(.*?)</title>', html)
            if title_tag:
                title_text = title_tag.group(1)
                # Remove common suffixes
                title_text = re.sub(r'\s+\|\s+LBBOnline$', '', title_text)
                result['title'] = title_text.strip()
                logger.info(f"Extracted title from <title> tag: '{title_text.strip()}'")
        
        # Extract description
        meta_desc = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        if meta_desc:
            result['description'] = meta_desc.group(1).strip()
            logger.info(f"Extracted description: '{meta_desc.group(1).strip()[:100]}...'")
        
        # Extract video URL
        notube_match = re.search(r'"notube_id":"([^"]+)"', html)
        if notube_match:
            notube_id = notube_match.group(1)
            video_url = f"https://notube.lbbonline.com/v/{notube_id}"
            result['video_links'].append(video_url)
            logger.info(f"Extracted video URL: {video_url}")
        
        # Extract image URL
        img_match = re.search(r'"image":"([^"]+)"', html)
        if img_match:
            image_path = img_match.group(1)
            image_url = f"https://d3q27bh1u24u2o.cloudfront.net/{image_path}"
            result['poster_image'] = image_url
            logger.info(f"Extracted image URL: {image_url}")
        
        # Extract media_thumbnail (alternative image source)
        thumbnail_match = re.search(r'"media_thumbnail":"([^"]+)"', html)
        if thumbnail_match and not result['poster_image']:
            thumbnail_url = thumbnail_match.group(1)
            if thumbnail_url.startswith("//"):
                thumbnail_url = "https:" + thumbnail_url
            elif not thumbnail_url.startswith("http"):
                thumbnail_url = "https://" + thumbnail_url
                
            result['poster_image'] = thumbnail_url
            logger.info(f"Extracted thumbnail URL: {thumbnail_url}")
    
    def _extract_from_lbb_credits(self, html: str, result: Dict) -> bool:
        """
        Extract from lbb_credits JSON data - this is the primary method that works reliably
        
        Returns True if credits were found and extracted
        """
        # Try to find the lbb_credits JSON
        credits_match = re.search(r'"lbb_credits":"((?:\\.|[^"\\])*)"', html)
        if not credits_match:
            logger.debug("No lbb_credits found in HTML")
            return False
            
        credits_str = credits_match.group(1)
        if not credits_str:
            logger.debug("Empty lbb_credits string")
            return False
        
        # Unescape the JSON string
        logger.debug(f"Raw lbb_credits string preview: {credits_str[:100]}...")
        credits_str = credits_str.replace('\\"', '"').replace('\\\\', '\\').replace('\\/', '/')
        try:
            credits_str = credits_str.encode('utf-8').decode('unicode_escape')
        except Exception as e:
            logger.debug(f"Unicode escape decoding failed: {e}")
        
        # Save the raw JSON for debugging if needed
        if self.debug:
            with open("lbb_credits_raw.json", "w", encoding="utf-8") as f:
                f.write(credits_str)
            logger.debug("Saved raw lbb_credits to lbb_credits_raw.json")
        
        # Parse the JSON
        try:
            credits_data = json.loads(credits_str)
            logger.info(f"Successfully parsed lbb_credits JSON with {len(credits_data)} sections")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse lbb_credits JSON: {e}")
            logger.debug(f"lbb_credits JSON string preview: {credits_str[:200]}...")
            
            # Try to parse the JSON with a more forgiving approach
            try:
                # Simple "eval" approach (dangerous in production but OK for testing)
                import ast
                credits_data = ast.literal_eval(credits_str)
                logger.info(f"Successfully parsed lbb_credits JSON using ast.literal_eval with {len(credits_data)} sections")
            except Exception as e2:
                logger.error(f"Second attempt to parse JSON failed: {e2}")
                return False
        
        # Process each section (company)
        companies = []
        for section in credits_data:
            if 'cat_value' in section and isinstance(section['cat_value'], list) and len(section['cat_value']) >= 2:
                company_id, company_name = section['cat_value']
                cat_id = str(section.get("cat_id", ""))
                
                logger.debug(f"Processing company: {company_name} (ID: {company_id}, cat_id: {cat_id})")
                
                # Get company type from mapping if available
                company_type = ""
                if cat_id in self.fallback_mapping.get("company_types", {}):
                    company_type = self.fallback_mapping["company_types"][cat_id]
                    logger.debug(f"Found company type in fallback mapping: {company_type}")
                
                # Create company object
                company = {
                    "id": company_id,
                    "name": company_name,
                    "type": company_type,
                    "url": f"https://lbbonline.com/companies/{company_id}",
                    "credits": []
                }
                
                # Process roles for this company
                credits_count = 0
                for field in section.get('fields', []):
                    if 'field_value' in field and field['field_value'] is not None and isinstance(field['field_value'], list) and len(field['field_value']) >= 2:
                        person_id, person_name = field['field_value']
                        field_id = str(field.get("field_id", ""))
                        
                        # Get role name from mapping if available
                        role_name = ""
                        if field_id in self.fallback_mapping.get("role_mappings", {}):
                            role_name = self.fallback_mapping["role_mappings"][field_id]
                            logger.debug(f"Found role in fallback mapping: {role_name} for ID {field_id}")
                        
                        # Add role to company
                        company["credits"].append({
                            "person": {
                                "id": person_id,
                                "name": person_name,
                                "url": f"https://lbbonline.com/people/{person_id}"
                            },
                            "role": role_name
                        })
                        credits_count += 1
                
                logger.info(f"Company '{company_name}' has {credits_count} credits")
                companies.append(company)
        
        # Update result with companies data
        if companies:
            result["companies"] = companies
            result["meta"]["extraction_method"] = "lbb_credits_json"
            logger.info(f"Extracted {len(companies)} companies with {sum(len(c['credits']) for c in companies)} credits")
            return True
        
        logger.warning("No valid companies found in lbb_credits JSON")
        return False
    
    def _extract_from_old_credits(self, html: str, result: Dict) -> bool:
        """
        Extract from old_credits format as a fallback
        
        Returns True if credits were found and extracted
        """
        # Try to find old_credits
        old_credits_match = re.search(r'"old_credits":"([^"]*)"', html)
        if not old_credits_match:
            logger.debug("No old_credits found in HTML")
            return False
            
        old_credits = old_credits_match.group(1)
        if not old_credits:
            logger.debug("Empty old_credits string")
            return False
        
        # Process the old_credits format
        logger.debug(f"old_credits preview: {old_credits[:100]}...")
        old_credits = old_credits.replace('\\n', '\n')
        lines = old_credits.split('\n')
        
        logger.info(f"Parsing old_credits with {len(lines)} lines")
        
        companies = []
        current_company = None
        current_section = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if ':' not in line:
                # This is a section header (company type)
                current_section = line
                logger.debug(f"Found section header: '{current_section}'")
                continue
            
            parts = line.split(':', 1)
            key = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ""
            
            if key.lower() == 'company name':
                # Start a new company
                sanitized_name = value.lower().replace(' ', '-')
                company_id = f"oldcredits_{sanitized_name}"
                current_company = {
                    "id": company_id,
                    "name": value,
                    "type": current_section,
                    "url": f"https://lbbonline.com/companies/{sanitized_name}",
                    "credits": []
                }
                logger.debug(f"Found company: '{value}' (type: '{current_section}')")
                companies.append(current_company)
            elif current_company and key and value:
                # This is a role: person pair
                sanitized_name = value.lower().replace(' ', '-')
                person_id = f"oldcredits_{sanitized_name}"
                
                logger.debug(f"Found credit: {key}: {value}")
                
                current_company["credits"].append({
                    "person": {
                        "id": person_id,
                        "name": value,
                        "url": f"https://lbbonline.com/people/{sanitized_name}"
                    },
                    "role": key
                })
        
        # Update result with companies data
        if companies:
            result["companies"] = companies
            result["meta"]["extraction_method"] = "old_credits_text"
            total_credits = sum(len(c["credits"]) for c in companies)
            logger.info(f"Extracted {len(companies)} companies with {total_credits} credits from old_credits")
            return True
        
        logger.warning("No valid companies found in old_credits")
        return False
    
    def _extract_from_dom(self, html: str, result: Dict) -> bool:
        """
        Extract credits from DOM structure as a last resort
        
        Returns True if credits were found and extracted
        """
        try:
            # Basic regex-based extraction - we're looking for patterns like:
            # <div class="company">Company Name</div>
            # <div class="role">Role: Person</div>
            
            # Simplified approach - just look for common patterns
            company_matches = re.findall(r'<(?:div|span)[^>]*class="[^"]*company[^"]*"[^>]*>([^<]+)</(?:div|span)>', html)
            
            if not company_matches:
                logger.debug("No company elements found in DOM")
                return False
                
            logger.info(f"Found {len(company_matches)} potential company elements in DOM")
            
            # Find potential role-person pairs
            role_matches = re.findall(r'<(?:div|span)[^>]*class="[^"]*role[^"]*"[^>]*>([^:]+):\s*([^<]+)</(?:div|span)>', html)
            
            logger.info(f"Found {len(role_matches)} potential role-person pairs in DOM")
            
            if not role_matches:
                logger.debug("No role elements found in DOM")
                return False
            
            # Create a basic company with the credits
            companies = []
            for i, company_name in enumerate(company_matches):
                company_name = company_name.strip()
                company_id = f"dom_company_{i+1}"
                
                company = {
                    "id": company_id,
                    "name": company_name,
                    "type": "",  # No way to know from DOM
                    "url": f"https://lbbonline.com/companies/{company_name.lower().replace(' ', '-')}",
                    "credits": []
                }
                
                # Add all roles to this company (imperfect but better than nothing)
                for role_name, person_name in role_matches:
                    role_name = role_name.strip()
                    person_name = person_name.strip()
                    
                    person_id = f"{company_id}_person_{len(company['credits'])+1}"
                    
                    company["credits"].append({
                        "person": {
                            "id": person_id,
                            "name": person_name,
                            "url": f"https://lbbonline.com/people/{person_name.lower().replace(' ', '-')}"
                        },
                        "role": role_name
                    })
                
                if company["credits"]:
                    companies.append(company)
            
            # Update result with companies data
            if companies:
                result["companies"] = companies
                result["meta"]["extraction_method"] = "dom_fallback"
                total_credits = sum(len(c["credits"]) for c in companies)
                logger.info(f"Extracted {len(companies)} companies with {total_credits} credits from DOM")
                return True
            
            logger.warning("No valid companies with credits found in DOM")
            return False
        except Exception as e:
            logger.error(f"Error extracting from DOM: {e}")
            return False

def load_fallback_mapping(file_path: str) -> Dict:
    """Load fallback mapping from a JSON file"""
    if not os.path.exists(file_path):
        logger.warning(f"Fallback mapping file not found: {file_path}")
        return {"company_types": {}, "role_mappings": {}}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        logger.info(f"Loaded fallback mapping from {file_path}")
        return mapping
    except Exception as e:
        logger.error(f"Error loading fallback mapping: {e}")
        return {"company_types": {}, "role_mappings": {}}

def fetch_html(url: str) -> str:
    """Fetch HTML from a URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return ""

def read_html_file(file_path: str) -> str:
    """Read HTML from a file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return ""

def save_results(results: Dict, output_file: str = None) -> None:
    """Save results to a JSON file"""
    if not output_file:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_file = f"lbb_results_{timestamp}.json"
    
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")

def print_summary(results: Dict) -> None:
    """Print a summary of the extraction results"""
    print("\n" + "="*80)
    print("LBB CREDITS EXTRACTION SUMMARY")
    print("="*80)
    
    print(f"\nURL: {results['url']}")
    print(f"Title: {results['title']}")
    if results.get('brand'):
        print(f"Brand: {results['brand']}")
    
    print(f"\nExtraction method: {results['meta']['extraction_method']}")
    print(f"Credits found: {results['meta']['credits_found']}")
    
    companies = results.get('companies', [])
    print(f"\nCompanies found: {len(companies)}")
    
    total_credits = sum(len(company.get('credits', [])) for company in companies)
    print(f"Total credits: {total_credits}")
    
    if companies:
        print("\nCompany details:")
        for i, company in enumerate(companies):
            print(f"  {i+1}. {company['name']} ({company['type'] or 'Unknown type'})")
            print(f"     Credits: {len(company.get('credits', []))}")
            
            # Print first 3 credits as samples
            for j, credit in enumerate(company.get('credits', [])[:3]):
                role = credit.get('role', 'Unknown role')
                person_name = credit.get('person', {}).get('name', 'Unknown person')
                print(f"       - {role}: {person_name}")
            
            # If there are more credits, show count
            if len(company.get('credits', [])) > 3:
                print(f"       ... and {len(company.get('credits', [])) - 3} more credits")
    
    print("\n" + "="*80)

def main():
    """Main function to run the script"""
    parser = argparse.ArgumentParser(description="Standalone LBB Credits Extractor")
    parser.add_argument("--url", help="URL to process")
    parser.add_argument("--file", help="HTML file to process")
    parser.add_argument("--fallback", help="Path to fallback mapping JSON file")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    if not args.url and not args.file:
        parser.error("Either --url or --file must be provided")
    
    # Set debug level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Load fallback mapping if provided
    fallback_mapping = None
    if args.fallback:
        fallback_mapping = load_fallback_mapping(args.fallback)
    
    # Get HTML content
    html = ""
    url = args.url or "file://" + os.path.abspath(args.file)
    
    if args.url:
        logger.info(f"Fetching HTML from URL: {args.url}")
        html = fetch_html(args.url)
    elif args.file:
        logger.info(f"Reading HTML from file: {args.file}")
        html = read_html_file(args.file)
    
    if not html:
        logger.error("Failed to get HTML content")
        return
    
    # Create extractor and process HTML
    extractor = LBBCreditsExtractor(fallback_mapping, args.debug)
    results = extractor.extract_credits(html, url)
    
    # Save results
    save_results(results, args.output)
    
    # Print summary
    print_summary(results)

if __name__ == "__main__":
    main()