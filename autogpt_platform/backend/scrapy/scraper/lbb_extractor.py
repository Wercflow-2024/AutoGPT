"""
LBB Credits Extractor - Specialized module to extract credits from LBB website
using the embedded JSON data approach that works reliably.
"""

import re
import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
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
    
    def extract_credits(self, html: str, url: str) -> Dict:
        """
        Extract credits and other data from LBB page HTML
        
        Args:
            html: The HTML content of the page
            url: The URL of the page
            
        Returns:
            Dictionary with structured credits data
        """
        # Start with basic result structure
        result = {
            'url': url,
            'title': '',
            'brand': '',
            'description': '',
            'video_url': '',
            'image_url': '',
            'companies': [],
            'meta': {
                'extraction_method': 'lbb_json_extractor',
                'credits_found': False
            }
        }
        
        # Extract basic metadata
        self._extract_basic_metadata(html, result)
        
        # Try to extract credits from embedded JSON
        found_credits = self._extract_from_lbb_credits(html, result)
        
        # If that fails, try old_credits format
        if not found_credits:
            found_credits = self._extract_from_old_credits(html, result)
            
        # Set credits_found flag
        result['meta']['credits_found'] = found_credits
            
        return result
    
    def _extract_basic_metadata(self, html: str, result: Dict) -> None:
        """Extract basic metadata like title, description, etc."""
        # Extract brand_and_name
        brand_name_match = re.search(r'"brand_and_name":"([^"]+)"', html)
        if brand_name_match:
            full_title = brand_name_match.group(1).strip()
            if " - " in full_title:
                brand, title = full_title.split(" - ", 1)
                result['brand'] = brand.strip()
                result['title'] = title.strip()
            else:
                result['title'] = full_title
        
        # Fallback title extraction
        if not result['title']:
            title_tag = re.search(r'<title>(.*?)</title>', html)
            if title_tag:
                title_text = title_tag.group(1)
                # Remove common suffixes
                title_text = re.sub(r'\s+\|\s+LBBOnline$', '', title_text)
                result['title'] = title_text.strip()
        
        # Extract description
        meta_desc = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        if meta_desc:
            result['description'] = meta_desc.group(1).strip()
        
        # Extract video URL
        notube_match = re.search(r'"notube_id":"([^"]+)"', html)
        if notube_match:
            notube_id = notube_match.group(1)
            result['video_url'] = f"https://notube.lbbonline.com/v/{notube_id}"
            logger.debug(f"Extracted video URL: {result['video_url']}")
        
        # Extract image URL
        img_match = re.search(r'"image":"([^"]+)"', html)
        if img_match:
            image_path = img_match.group(1)
            result['image_url'] = f"https://d3q27bh1u24u2o.cloudfront.net/{image_path}"
            logger.debug(f"Extracted image URL: {result['image_url']}")
    
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
        credits_str = credits_str.replace('\\"', '"').replace('\\\\', '\\').replace('\\/', '/')
        try:
            credits_str = credits_str.encode('utf-8').decode('unicode_escape')
        except Exception as e:
            logger.debug(f"Unicode escape decoding failed: {e}")
        
        # Parse the JSON
        try:
            credits_data = json.loads(credits_str)
            logger.info(f"Successfully parsed lbb_credits JSON with {len(credits_data)} sections")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse lbb_credits JSON: {e}")
            logger.debug(f"lbb_credits JSON string: {credits_str[:200]}...")
            return False
        
        # Process each section (company)
        companies = []
        for section in credits_data:
            if 'cat_value' in section and len(section['cat_value']) >= 2:
                company_id, company_name = section['cat_value']
                cat_id = str(section.get("cat_id", ""))
                
                # Get company type from mapping if available
                company_type = ""
                if cat_id in self.fallback_mapping["company_types"]:
                    company_type = self.fallback_mapping["company_types"][cat_id]
                
                # Create company object
                company = {
                    "id": company_id,
                    "name": company_name,
                    "type": company_type,
                    "url": f"https://lbbonline.com/companies/{company_id}",
                    "credits": []
                }
                
                # Process roles for this company
                for field in section.get('fields', []):
                    if 'field_value' in field and field['field_value'] is not None and len(field['field_value']) >= 2:
                        person_id, person_name = field['field_value']
                        field_id = str(field.get("field_id", ""))
                        
                        # Get role name from mapping if available
                        role_name = ""
                        if field_id in self.fallback_mapping["role_mappings"]:
                            role_name = self.fallback_mapping["role_mappings"][field_id]
                        
                        # Add role to company
                        company["credits"].append({
                            "person": {
                                "id": person_id,
                                "name": person_name,
                                "url": f"https://lbbonline.com/people/{person_id}"
                            },
                            "role": role_name
                        })
                
                companies.append(company)
        
        # Update result with companies data
        if companies:
            result["companies"] = companies
            result["meta"]["extraction_method"] = "lbb_credits_json"
            logger.info(f"Extracted {len(companies)} companies with {sum(len(c['credits']) for c in companies)} credits")
            return True
        
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
        old_credits = old_credits.replace('\\n', '\n')
        lines = old_credits.split('\n')
        
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
                companies.append(current_company)
            elif current_company and key and value:
                # This is a role: person pair
                sanitized_name = value.lower().replace(' ', '-')
                person_id = f"oldcredits_{sanitized_name}"
                
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
            logger.info(f"Extracted {len(companies)} companies with {sum(len(c['credits']) for c in companies)} credits")
            return True
        
        return False

# Simple function to use the extractor
def extract_lbb_credits(html: str, url: str, fallback_mapping: Optional[Dict] = None, debug: bool = False) -> Dict:
    """
    Extract credits from an LBB page
    
    Args:
        html: HTML content of the page
        url: URL of the page
        fallback_mapping: Optional mapping for company types and roles
        debug: Enable debug logging
        
    Returns:
        Dictionary with extracted credits data
    """
    extractor = LBBCreditsExtractor(fallback_mapping, debug)
    return extractor.extract_credits(html, url)