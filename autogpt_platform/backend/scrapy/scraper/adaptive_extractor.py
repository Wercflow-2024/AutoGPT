"""
Adaptive extraction framework that uses pattern detection, multiple strategies,
and intelligent fallbacks to handle a wide variety of site structures.
"""

import os
import re
import json
import hashlib
import datetime
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("adaptive_extractor")

# Import from project structure - with better error handling
try:
    from backend.scrapy.utils.config import CONFIG
    from backend.scrapy.scraper.project_scraper import (
        SNAPSHOT_DIR, fetch_html_and_snapshot, normalize_roles_with_ai, 
        suggest_fixes_via_openai, validate_scraped_data
    )
except ImportError:
    try:
        from autogpt_platform.backend.scrapy.utils.config import CONFIG
        from autogpt_platform.backend.scrapy.scraper.project_scraper import (
            SNAPSHOT_DIR, fetch_html_and_snapshot, normalize_roles_with_ai, 
            suggest_fixes_via_openai, validate_scraped_data
        )
    except ImportError:
        # Fallback with minimal functionality for standalone use
        logger.warning("⚠️ Unable to import from project structure. Using minimal fallbacks.")
        
        # Define basic CONFIG
        CONFIG = {
            "AI_ENABLED": False,
            "AI_MODEL": "",
            "FORCE_REFRESH": False,
            "REQUEST_TIMEOUT": 30,
        }
        
        # Define SNAPSHOT_DIR
        SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "snapshots")
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        
        # Placeholder functions
        def fetch_html_and_snapshot(url, force_refresh=False):
            """Minimal fallback for fetch_html_and_snapshot"""
            import requests
            response = requests.get(url, timeout=30)
            html = response.text
            return html, False
            
        def validate_scraped_data(data):
            """Minimal fallback for validate_scraped_data"""
            missing = []
            if not data.get("title"):
                missing.append("title")
            if not data.get("companies"):
                missing.append("companies")
            return missing
            
        def suggest_fixes_via_openai(html, url, missing, snapshot_path, previous_selectors=None):
            """Minimal fallback for suggest_fixes_via_openai"""
            return {"suggestions": {}}
            
        def normalize_roles_with_ai(data, html):
            """Minimal fallback for normalize_roles_with_ai"""
            return data

# Constants for extraction patterns
PATTERNS = {
    "role_person_split": re.compile(r"([^:]+):\s*(.+)"),  # Pattern for "Role: Person"
    "year": re.compile(r"\b(20\d{2})\b"),                 # Pattern for year (2000-2099)
    "client_brand": re.compile(r"\b(?:client|brand)\b", re.IGNORECASE)  # Pattern for client/brand indicators
}

class AdaptiveExtractor:
    """
    Flexible extraction system that can adapt to different website structures
    """
    
    def __init__(self, html: str, url: str, fallback_mapping: Dict = None, debug: bool = False):
        """Initialize with HTML content and URL"""
        self.html = html
        self.url = url
        self.fallback_mapping = fallback_mapping or {}
        self.debug = debug
        
        # Try to parse HTML with error handling
        try:
            self.soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.error(f"❌ Error parsing HTML: {str(e)}")
            self.soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        
        self.domain = urlparse(url).netloc.lower()
        
        # Set up logging
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # Detection results
        self.structure_type = self._detect_structure()
        logger.info(f"Detected structure type: {self.structure_type}")
        
        # Extraction results
        self.data = {
            "title": "",
            "description": "",
            "client": "",
            "date": "",
            "location": "",
            "format": "",
            "video_links": [],
            "poster_image": "",
            "companies": [],
            "assets": {"image_url": ""},
            "meta": {
                "url": url,
                "scraped_at": datetime.datetime.now().isoformat(),
                "unknown_roles": [],
                "structure_type": self.structure_type,
            }
        }
    
    def extract(self) -> Dict:
        """Main extraction method that coordinates the process"""
        logger.info(f"Extracting data using structure type: {self.structure_type}")
        
        try:
            # Extract basic metadata that's common across most structures
            self._extract_basic_metadata()
            
            # Extract media elements (videos, images)
            self._extract_media()
            
            # Special case for LBB sites
            if self.structure_type == "lbbonline_specialized":
                logger.info("Using specialized LBB extractor")
            
            if self._extract_credits_lbb_specialized():
                # Successfully extracted credits, skip to finalization
                self._finalize_data()
                return self.data
            
            # Extract company and credit information using the appropriate method
            if self.structure_type == "lbbonline_v2":
                logger.info("Using LBB Online v2 extractor")
                self._extract_credits_lbbonline_v2()
            elif self.structure_type == "lbbonline_v1":
                logger.info("Using LBB Online v1 extractor")
                self._extract_credits_lbbonline_v1()
            elif self.structure_type == "dandad":
                logger.info("Using D&AD extractor")
                self._extract_credits_dandad()
            else:
                # Generic extraction as fallback
                logger.info("Using generic extractor")
                self._extract_credits_generic()
            
            # If companies extraction failed, try alternative methods
            if not self.data["companies"]:
                logger.info("Primary credit extraction failed, trying alternatives")
                self._extract_credits_alternative()
            
            # Finalize the extracted data
            self._finalize_data()
            
        except Exception as e:
            logger.error(f"❌ Error during extraction: {str(e)}")
            # Don't re-raise, allow returning partial data
        
        return self.data
    
    def _detect_structure(self) -> str:
        """Detect the structure type of the page"""
        try:
            # Debug output for structure detection
            if self.debug:
                logger.debug(f"Domain: {self.domain}")
                logger.debug(f"Title: {self.soup.title.string if self.soup.title else 'No title'}")
                
                # Log key structural elements presence
                for selector in ['span.font-barlow', 'div.flex.space-y-4', '.rich-text.space-y-5', '.credit-entry']:
                    logger.debug(f"Has {selector}: {bool(self.soup.select(selector))}")
                
                # Add additional logging for credits tab structure
                for selector in ['.credits-tab', '.tab-selector', '.credits-container']:
                    logger.debug(f"Has {selector}: {bool(self.soup.select(selector))}")
            
            
            if "lbbonline.com" in self.domain:
                return "lbbonline_specialized"
            
            # LBB Online 2025 design detection
            if "lbbonline.com" in self.domain:
                # Look for credit tab structures
                has_credits_tab = bool(self.soup.select('.credits-tab, .tab-selector, [data-tab="credits"]'))
                
                if has_credits_tab:
                    logger.info("Detected LBB Online with credits in tabs - needs JavaScript interaction")
                    return "lbbonline_js_v2"
                
                # Check for LBB v2 first (new design)
                if (self.soup.select("span.font-barlow.font-bold.text-black") or 
                    self.soup.select("div.flex.space-y-4") or 
                    self.soup.select(".rich-text.space-y-5")):
                    return "lbbonline_v2"
                
                # Then check for LBB v1 (old design)
                if (self.soup.select(".credit-entry") or 
                    self.soup.select(".company-name") or 
                    self.soup.select(".field--name-field-basic-info")):
                    return "lbbonline_v1"
                
                # Define structure indicators for confidence scoring
                structure_indicators = [
                    bool(self.soup.select("span.font-barlow.font-bold.text-black")),
                    bool(self.soup.select("div.flex.space-y-4")),
                    bool(self.soup.select(".rich-text.space-y-5"))
                ]
                confidence_score = sum(structure_indicators)
                
                if confidence_score >= 2:
                    # Check for JavaScript-rendered content hints
                    script_patterns = [
                        "window.__INITIAL_STATE__",
                        "react", "vue", "angular",
                        "fetch(", ".json()"
                    ]
                    
                    scripts = self.soup.find_all('script')
                    js_hints = sum(1 for script in scripts if any(pattern in (script.string or '') for pattern in script_patterns))
                    
                    if js_hints > 0:
                        # Mark as potentially JavaScript-rendered
                        logger.info("Detected potential JavaScript-rendered content")
                        return "lbbonline_js_v2"
                    
                    return "lbbonline_v2"
            
            # Fallback detection logic remains the same
            return super()._detect_structure()  # Call parent method if available
        
        except Exception as e:
            logger.error(f"❌ Error in structure detection: {str(e)}")
            return "unknown"
    
    def _extract_basic_metadata(self):
        """Extract basic metadata like title, description, etc."""
        try:
            # Title - try multiple selectors
            for selector in ["h1", ".title", "header h2", ".main-title", "article h1"]:
                title_elem = self.soup.select_one(selector)
                if title_elem and title_elem.get_text(strip=True):
                    self.data["title"] = title_elem.get_text(strip=True)
                    break
            
            # Description - try multiple approaches
            description = ""
            
            # Approach 1: Structured description elements
            for selector in [".description", ".field--name-field-description", 
                            ".rich-text.space-y-5 p", ".award-content-intro", 
                            ".content p:first-of-type", "article p"]:
                desc_elems = self.soup.select(selector)
                if desc_elems:
                    description = " ".join(elem.get_text(strip=True) for elem in desc_elems if elem.get_text(strip=True))
                    break
            
            # Approach 2: First paragraph after title
            if not description and self.data["title"]:
                title_elem = self.soup.find(string=re.compile(re.escape(self.data["title"])))
                if title_elem and title_elem.parent:
                    next_p = title_elem.parent.find_next("p")
                    if next_p:
                        description = next_p.get_text(strip=True)
            
            self.data["description"] = description
            
            # Project metadata (client, date, etc.)
            self._extract_project_metadata()
        except Exception as e:
            logger.error(f"❌ Error extracting basic metadata: {str(e)}")
    
    def _extract_project_metadata(self):
        """Extract project metadata like client, date, location, format"""
        try:
            # Try structured metadata first
            metadata_selectors = [
                ".field--name-field-basic-info .field__item",
                ".credit-meta div",
                ".award-meta-details",
                ".project-info li",
                ".metadata li",
                ".details div"
            ]
            
            metadata_elements = []
            for selector in metadata_selectors:
                elements = self.soup.select(selector)
                if elements:
                    metadata_elements = elements
                    break
            
            # Process structured metadata
            for elem in metadata_elements:
                text = elem.get_text(" ", strip=True).lower()
                
                # Check for client/brand
                if PATTERNS["client_brand"].search(text):
                    self.data["client"] = text.split(":", 1)[-1].strip() if ":" in text else text
                
                # Check for year
                year_match = PATTERNS["year"].search(text)
                if year_match and not self.data["date"]:
                    self.data["date"] = year_match.group(1)
                
                # Check for location
                if "location" in text.lower() and ":" in text:
                    self.data["location"] = text.split(":", 1)[-1].strip()
                
                # Check for format
                if any(keyword in text.lower() for keyword in ["format", "type", "category"]):
                    self.data["format"] = text.split(":", 1)[-1].strip() if ":" in text else text
            
            # If client is still missing, try alternative approaches
            if not self.data["client"]:
                # Look for metadata in HTML meta tags
                meta_desc = self.soup.find("meta", attrs={"name": "description"})
                if meta_desc:
                    desc_text = meta_desc.get("content", "")
                    client_match = re.search(r"(?:client|brand):\s*([^,\.]+)", desc_text, re.IGNORECASE)
                    if client_match:
                        self.data["client"] = client_match.group(1).strip()
                
                # Extract from title if it contains "for" or similar patterns
                if self.data["title"]:
                    title = self.data["title"]
                    for_match = re.search(r"\s+(?:for|by|client:)\s+([^-\|]+)", title, re.IGNORECASE)
                    if for_match:
                        self.data["client"] = for_match.group(1).strip()
            
            # If date is still missing, look for it in the page
            if not self.data["date"]:
                # Try to find year in the title
                if self.data["title"]:
                    year_match = PATTERNS["year"].search(self.data["title"])
                    if year_match:
                        self.data["date"] = year_match.group(1)
                
                # Look for a date element
                date_elements = self.soup.select(".date, .year, .publish-date")
                if date_elements:
                    for elem in date_elements:
                        year_match = PATTERNS["year"].search(elem.get_text())
                        if year_match:
                            self.data["date"] = year_match.group(1)
                            break
        except Exception as e:
            logger.error(f"❌ Error extracting project metadata: {str(e)}")
    
    def _extract_media(self):
        """Extract media elements like videos and images"""
        try:
            # Find video embeds
            video_links = []
            
            # Look for iframes with video URLs
            for iframe in self.soup.find_all("iframe"):
                src = iframe.get("src", "")
                if src and any(provider in src for provider in [
                    "youtube", "vimeo", "lbbonline", "player", "video"
                ]):
                    video_links.append(src)
            
            # Look for video elements
            for video in self.soup.find_all("video"):
                src = video.get("src", "")
                if src:
                    video_links.append(src)
                
                # Check for source elements inside video
                for source in video.find_all("source"):
                    src = source.get("src", "")
                    if src:
                        video_links.append(src)
            
            # Look for links to videos
            for a in self.soup.find_all("a", href=True):
                href = a.get("href", "")
                if any(provider in href for provider in ["youtube", "vimeo", "player"]):
                    if href not in video_links:
                        video_links.append(href)
            
            self.data["video_links"] = video_links
            
            # Find poster image
            poster_image = ""
            
            # Try OpenGraph image first
            og_image = self.soup.find("meta", property="og:image")
            if og_image:
                poster_image = og_image.get("content", "")
            
            # If no OG image, look for a hero/main image
            if not poster_image:
                for selector in [".hero img", ".main-image img", ".featured-image img", 
                                ".thumbnail img", "article > img"]:
                    img = self.soup.select_one(selector)
                    if img and img.get("src"):
                        poster_image = img.get("src")
                        break
            
            # If still no image, try first large image
            if not poster_image:
                for img in self.soup.find_all("img"):
                    src = img.get("src", "")
                    if src and not src.endswith((".ico", ".svg", "logo")):
                        width = img.get("width", "0")
                        height = img.get("height", "0")
                        try:
                            if int(width) > 400 or int(height) > 300:
                                poster_image = src
                                break
                        except (ValueError, TypeError):
                            # If dimensions aren't specified or valid, still consider the image
                            poster_image = src
                            break
            
            self.data["poster_image"] = poster_image
            
            # Also set in assets dict for compatibility
            self.data["assets"] = {"image_url": poster_image}
        except Exception as e:
            logger.error(f"❌ Error extracting media: {str(e)}")
    
    def _extract_credits_lbbonline_v2(self):
        """Extract credits using LBB Online 2025 structure with JSON fallback"""
        try:
            # First try to extract from embedded JSON
            if self._extract_credits_from_json():
                logger.info("Successfully extracted credits from embedded JSON")
                return
            
            # If JSON extraction failed, continue with the original method
            companies = []
            unknown_roles = []
            
            # Find credit blocks with the new structure
            credit_blocks = self.soup.select("div.flex.space-y-4")
            
            logger.info(f"Found {len(credit_blocks)} credit blocks in LBB v2 format")
            
            # Process each block
            for block in credit_blocks:
                # Extract company name
                company_name_el = block.select_one("span.font-barlow.font-bold.text-black")
                if not company_name_el:
                    continue
                    
                company_name = company_name_el.get_text(strip=True)
                company_id = f"company_{len(companies) + 1}"
                
                # Determine company type
                company_type = self._guess_company_type(company_name)
                
                # Look for roles and people
                role_elements = block.select("div.team div")
                
                people = []
                for role_el in role_elements:
                    role_text = role_el.get_text(strip=True)
                    
                    # Try to extract role and person from combined text
                    role_match = PATTERNS["role_person_split"].match(role_text)
                    
                    if role_match:
                        role_name = role_match.group(1).strip()
                        person_name = role_match.group(2).strip()
                        
                        # Create unique person ID
                        person_id = f"{company_id}_person_{len(people) + 1}"
                        
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
                        "url": "",
                        "credits": people
                    })
            
            # Set the data if we found any companies
            if companies:
                self.data["companies"] = companies
                self.data["meta"]["unknown_roles"] = unknown_roles
                logger.info(f"Extracted {len(companies)} companies using DOM parsing")
        except Exception as e:
            logger.error(f"❌ Error in LBB v2 credit extraction: {str(e)}")
    
    def _extract_credits_lbbonline_v1(self):
        """Extract credits using LBB Online traditional structure"""
        try:
            companies = []
            unknown_roles = []
            
            # Find credit blocks
            credit_blocks = self.soup.select(".credit-entry")
            
            for block in credit_blocks:
                # Extract company info
                company_link = block.select_one(".company-name a")
                if not company_link:
                    continue
                    
                company_name = company_link.get_text(strip=True)
                company_url = urljoin(self.url, company_link["href"]) if "href" in company_link.attrs else ""
                company_id = self._extract_id_from_url(company_url) or f"company_{len(companies) + 1}"
                
                # Extract company type
                company_type_el = block.select_one(".company-type")
                company_type = company_type_el.get_text(strip=True) if company_type_el else ""
                
                if not company_type and company_id in self.fallback_mapping.get("company_types", {}):
                    company_type = self.fallback_mapping["company_types"][company_id]
                
                # Extract roles and people
                people = []
                role_blocks = block.select(".roles .role")
                
                for role_block in role_blocks:
                    role_name_el = role_block.select_one(".role-name")
                    role = role_name_el.get_text(strip=True) if role_name_el else ""
                    
                    for person_el in role_block.select(".person"):
                        person_link = person_el.select_one("a")
                        person_name_el = person_el.select_one("a") or person_el
                        person_name = person_name_el.get_text(strip=True)
                        
                        person_url = ""
                        if person_link and "href" in person_link.attrs:
                            person_url = urljoin(self.url, person_link["href"])
                        
                        person_id = self._extract_id_from_url(person_url) or f"{company_id}_person_{len(people) + 1}"
                        
                        if not role and person_id in self.fallback_mapping.get("role_mappings", {}):
                            role = self.fallback_mapping["role_mappings"][person_id]
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
            
            self.data["companies"] = companies
            self.data["meta"]["unknown_roles"] = unknown_roles
        except Exception as e:
            logger.error(f"❌ Error in LBB v1 credit extraction: {str(e)}")
    
    def _extract_credits_dandad(self):
        """Extract credits using D&AD structure"""
        try:
            companies = []
            unknown_roles = []
            
            # Find credit blocks
            credit_blocks = self.soup.select(".award-credits-list")
            
            for block in credit_blocks:
                # Extract company info
                company_name_el = block.select_one(".company-name")
                if not company_name_el:
                    continue
                    
                company_name = company_name_el.get_text(strip=True)
                company_id = f"company_{len(companies) + 1}"
                
                # Extract company type
                company_type_el = block.select_one(".company-role")
                company_type = company_type_el.get_text(strip=True) if company_type_el else ""
                
                # Extract roles and people
                people = []
                role_blocks = block.select(".award-credits-role")
                
                for role_block in role_blocks:
                    role_name_el = role_block.select_one(".role-title")
                    role = role_name_el.get_text(strip=True) if role_name_el else ""
                    
                    for person_el in role_block.select(".person-name"):
                        person_name_el = person_el.select_one("span") or person_el
                        person_name = person_name_el.get_text(strip=True)
                        person_id = f"{company_id}_person_{len(people) + 1}"
                        
                        if not role:
                            unknown_roles.append({"person_id": person_id, "name": person_name})
                        
                        people.append({
                            "person": {
                                "id": person_id,
                                "name": person_name,
                                "url": ""
                            },
                            "role": role
                        })
                
                companies.append({
                    "id": company_id,
                    "name": company_name,
                    "type": company_type,
                    "url": "",
                    "credits": people
                })
            
            self.data["companies"] = companies
            self.data["meta"]["unknown_roles"] = unknown_roles
        except Exception as e:
            logger.error(f"❌ Error in D&AD credit extraction: {str(e)}")
    
    def _extract_credits_generic(self):
        """Extract credits using generic pattern recognition"""
        try:
            companies = []
            unknown_roles = []
            
            # First approach: Look for company sections with clear headers
            company_sections = []
            
            # Try to find headers that might introduce companies
            for header in self.soup.find_all(['h2', 'h3', 'h4', 'strong', 'b']):
                header_text = header.get_text(strip=True)
                
                # Skip if it's not a company header
                if len(header_text) < 2 or len(header_text) > 50:
                    continue
                    
                if re.search(r'(prod|agenc|studio|post|director|brand)', header_text, re.IGNORECASE):
                    # This might be a company header
                    company_sections.append({
                        'header': header,
                        'name': header_text,
                        'type': self._guess_company_type(header_text)
                    })
            
            # Process each potential company section
            for section in company_sections:
                header = section['header']
                company_name = section['name']
                company_type = section['type']
                company_id = f"company_{len(companies) + 1}"
                
                # Look for role/person pairs in the elements following this header
                people = []
                current = header.next_sibling
                
                # Process until we hit the next header or run out of siblings
                while current and current.name not in ['h2', 'h3', 'h4']:
                    if isinstance(current, Tag):
                        text = current.get_text(strip=True)
                        
                        # Check for "Role: Person" pattern
                        role_match = PATTERNS["role_person_split"].match(text)
                        
                        if role_match:
                            role_name = role_match.group(1).strip()
                            person_name = role_match.group(2).strip()
                            
                            person_id = f"{company_id}_person_{len(people) + 1}"
                            
                            people.append({
                                "person": {
                                    "id": person_id,
                                    "name": person_name,
                                    "url": ""
                                },
                                "role": role_name
                            })
                        elif text and len(text) > 2:
                            # This might be plain text content
                            # Check for roles/people in other formats
                            lines = text.split('\n')
                            for line in lines:
                                if ':' in line:
                                    parts = line.split(':', 1)
                                    if len(parts) == 2:
                                        role_name = parts[0].strip()
                                        person_name = parts[1].strip()
                                        
                                        if role_name and person_name:
                                            person_id = f"{company_id}_person_{len(people) + 1}"
                                            
                                            people.append({
                                                "person": {
                                                    "id": person_id,
                                                    "name": person_name,
                                                    "url": ""
                                                },
                                                "role": role_name
                                            })
                    
                    current = current.next_sibling
                
                # Only add the company if we found people
                if people:
                    companies.append({
                        "id": company_id,
                        "name": company_name,
                        "type": company_type,
                        "url": "",
                        "credits": people
                    })
            
            # If we didn't find companies with the structured approach, try a paragraph-based approach
            if not companies:
                self._extract_credits_from_paragraphs()
            else:
                self.data["companies"] = companies
                self.data["meta"]["unknown_roles"] = unknown_roles
        except Exception as e:
            logger.error(f"❌ Error in generic credit extraction: {str(e)}")
    
    def _extract_credits_from_paragraphs(self):
        """Extract credits from paragraphs - a more aggressive approach"""
        try:
            companies = []
            unknown_roles = []
            
            # Look for paragraphs that might contain credits
            credit_paragraphs = []
            
            # Potential containing sections
            credit_sections = self.soup.select(".credits, .team, .crew, .credit, article, section")
            
            if not credit_sections:
                # If no specific sections found, use the whole body
                credit_sections = [self.soup.find('body')]
            
            # Extract paragraphs from these sections
            for section in credit_sections:
                if not section:
                    continue
                    
                paragraphs = section.find_all(['p', 'div', 'li'])
                credit_paragraphs.extend(paragraphs)
            
            # Process paragraphs looking for company headers and role/person info
            current_company = None
            
            for p in credit_paragraphs:
                text = p.get_text(strip=True)
                
                # Skip empty paragraphs
                if not text:
                    continue
                
                # Check if this might be a company header
                if p.find('strong') or p.find('b') or p.name == 'h3' or p.name == 'h4' or len(text) < 40:
                    company_type = self._guess_company_type(text)
                    
                    if company_type or re.search(r'(prod|agenc|studio|post|director|brand)', text, re.IGNORECASE):
                        # This looks like a company header
                        current_company = {
                            "id": f"company_{len(companies) + 1}",
                            "name": text,
                            "type": company_type,
                            "url": "",
                            "credits": []
                        }
                        companies.append(current_company)
                        continue
                
                # If we have a current company, look for role/person info
                if current_company and ':' in text:
                    # This might be role: person format
                    lines = text.split('\n')
                    
                    for line in lines:
                        if ':' not in line:
                            continue
                            
                        parts = line.split(':', 1)
                        role_name = parts[0].strip()
                        person_text = parts[1].strip()
                        
                        # Person text might contain multiple names
                        person_names = re.split(r',\s*(?:and\s+)?|\s+and\s+', person_text)
                        
                        for person_name in person_names:
                            person_name = person_name.strip()
                            if not person_name:
                                continue
                                
                            person_id = f"{current_company['id']}_person_{len(current_company['credits']) + 1}"
                            
                            current_company["credits"].append({
                                "person": {
                                    "id": person_id,
                                    "name": person_name,
                                    "url": ""
                                },
                                "role": role_name
                            })
            
            # If we found companies, update the data
            if companies:
                # Filter out companies without credits
                self.data["companies"] = [c for c in companies if c["credits"]]
                self.data["meta"]["unknown_roles"] = unknown_roles
        except Exception as e:
            logger.error(f"❌ Error in paragraph-based credit extraction: {str(e)}")
    
    def _extract_credits_alternative(self):
        """
        Enhanced alternative extraction with more sophisticated methods
        
        Additional strategies:
        1. Look for potential company elements using advanced selectors
        2. Use AI-assisted extraction with more context
        3. Implement multiple extraction fallbacks
        """
        try:
            # If no companies found, try advanced selectors
            advanced_selectors = [
                "div[class*='company']",
                "section[class*='credits']",
                "[data-testid*='company']",
                "article div[class*='team']"
            ]
            
            potential_companies = []
            for selector in advanced_selectors:
                matches = self.soup.select(selector)
                if matches:
                    potential_companies.extend(matches)
                    break
            
            # If no matches, try AI-assisted extraction
            if not potential_companies and self.debug:
                try:
                    # Import AI enhancer
                    from backend.scrapy.scraper.ai_enhancer import AzureOpenAIEnhancer
                    
                    ai_enhancer = AzureOpenAIEnhancer(model="gpt-4o-mini")
                    if ai_enhancer.enabled:
                        # More specific prompt for company extraction
                        ai_suggestions = ai_enhancer.suggest_selectors(
                            str(self.soup), 
                            ["companies"], 
                            self.url, 
                            {"context": "Creative industry project page"}
                        )
                        
                        # Use AI-suggested selectors
                        ai_selector = ai_suggestions.get('selectors', {}).get('companies')
                        if ai_selector:
                            potential_companies = self.soup.select(ai_selector)
                except ImportError:
                    logger.warning("Could not import AI enhancer for advanced extraction")
            
            # Refine potential companies
            companies = self._improve_company_detection(self.soup, potential_companies)
            
            # If still no companies, try last-resort methods
            if not companies:
                # Extract from paragraphs or headings that might contain company names
                text_selectors = [
                    "p", "h2", "h3", "div[class*='name']", 
                    "span[class*='company']"
                ]
                
                for selector in text_selectors:
                    text_elements = self.soup.select(selector)
                    companies = self._improve_company_detection(self.soup, text_elements)
                    if companies:
                        break
            
            # Final sanity check
            if companies:
                self.data["companies"] = companies
                self.data["meta"]["used_alternative_extraction"] = True
        
        except Exception as e:
            logger.error(f"❌ Error in alternative credit extraction: {str(e)}")
    
    def _extract_credits_from_tables(self):
        """Extract credits from tables"""
        try:
            companies = []
            
            # Find tables that might contain credits
            tables = self.soup.find_all('table')
            
            for table in tables:
                # Check if this table has enough rows to be a credits table
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # Try to determine if this is a credits table
                headers = [h.get_text(strip=True).lower() for h in rows[0].find_all(['th', 'td'])]
                if not any(term in ' '.join(headers) for term in ['company', 'role', 'name', 'credit']):
                    continue
                
                # This looks like a credits table
                company_name = "Unknown Company"
                company_type = ""
                company_id = f"company_{len(companies) + 1}"
                people = []
                
                # Try to find a company name in a caption or nearby heading
                caption = table.find('caption')
                if caption:
                    company_name = caption.get_text(strip=True)
                    company_type = self._guess_company_type(company_name)
                else:
                    # Look for a heading before the table
                    prev = table.previous_sibling
                    while prev and not (isinstance(prev, Tag) and prev.name in ['h1', 'h2', 'h3', 'h4', 'h5']):
                        prev = prev.previous_sibling
                    
                    if prev and isinstance(prev, Tag):
                        company_name = prev.get_text(strip=True)
                        company_type = self._guess_company_type(company_name)
                
                # Process data rows
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 2:
                        continue
                    
                    # Try to identify role and person columns
                    role_col = 0
                    person_col = 1
                    
                    # If we have headers, use them to guess the columns
                    if headers:
                        for i, header in enumerate(headers):
                            if any(term in header for term in ['role', 'position', 'job']):
                                role_col = i
                            elif any(term in header for term in ['name', 'person', 'who']):
                                person_col = i
                    
                    # Extract role and person
                    if role_col < len(cells) and person_col < len(cells):
                        role_name = cells[role_col].get_text(strip=True)
                        person_name = cells[person_col].get_text(strip=True)
                        
                        if role_name and person_name:
                            person_id = f"{company_id}_person_{len(people) + 1}"
                            
                            people.append({
                                "person": {
                                    "id": person_id,
                                    "name": person_name,
                                    "url": ""
                                },
                                "role": role_name
                            })
                
                # Add the company if we found people
                if people:
                    companies.append({
                        "id": company_id,
                        "name": company_name,
                        "type": company_type,
                        "url": "",
                        "credits": people
                    })
            
            if companies:
                self.data["companies"] = companies
        except Exception as e:
            logger.error(f"❌ Error in table-based credit extraction: {str(e)}")
    
    def _extract_credits_from_lists(self):
        """Extract credits from list items"""
        try:
            companies = []
            
            # Find lists that might contain credits
            lists = self.soup.find_all(['ul', 'ol'])
            
            for list_elem in lists:
                # Check if this list has enough items
                items = list_elem.find_all('li')
                if len(items) < 2:
                    continue
                
                # Check if items look like credits (contain colons or credit-like terms)
                credit_items = [item for item in items if ':' in item.get_text() or
                               any(term in item.get_text().lower() for term in 
                                   ['director', 'producer', 'editor', 'creative'])]
                
                if len(credit_items) < 2:
                    continue
                
                # This looks like a credits list
                company_name = "Unknown Company"
                company_type = ""
                company_id = f"company_{len(companies) + 1}"
                people = []
                
                # Try to find a company name in a heading before the list
                prev = list_elem.previous_sibling
                while prev and not (isinstance(prev, Tag) and prev.name in ['h1', 'h2', 'h3', 'h4', 'h5']):
                    prev = prev.previous_sibling
                
                if prev and isinstance(prev, Tag):
                    company_name = prev.get_text(strip=True)
                    company_type = self._guess_company_type(company_name)
                
                # Process list items
                for item in credit_items:
                    text = item.get_text(strip=True)
                    
                    # Try to extract role and person
                    if ':' in text:
                        parts = text.split(':', 1)
                        role_name = parts[0].strip()
                        person_text = parts[1].strip()
                        
                        # Person text might contain multiple names
                        person_names = re.split(r',\s*(?:and\s+)?|\s+and\s+', person_text)
                        
                        for person_name in person_names:
                            person_name = person_name.strip()
                            if not person_name:
                                continue
                                
                            person_id = f"{company_id}_person_{len(people) + 1}"
                            
                            people.append({
                                "person": {
                                    "id": person_id,
                                    "name": person_name,
                                    "url": ""
                                },
                                "role": role_name
                            })
                    else:
                        # Try to guess role and person
                        match = re.match(r'(.*?)\s+-\s+(.*)', text)
                        if match:
                            role_name = match.group(1).strip()
                            person_name = match.group(2).strip()
                            
                            if role_name and person_name:
                                person_id = f"{company_id}_person_{len(people) + 1}"
                                
                                people.append({
                                    "person": {
                                        "id": person_id,
                                        "name": person_name,
                                        "url": ""
                                    },
                                    "role": role_name
                                })
                
                # Add the company if we found people
                if people:
                    companies.append({
                        "id": company_id,
                        "name": company_name,
                        "type": company_type,
                        "url": "",
                        "credits": people
                    })
            
            if companies:
                self.data["companies"] = companies
        except Exception as e:
            logger.error(f"❌ Error in list-based credit extraction: {str(e)}")

    def _extract_credits_from_json(self):
        """
        Extract credits from embedded JSON in the page
        """
        try:
            companies = []
            unknown_roles = []
        
            # Try to find the lbb_credits JSON
            credits_match = re.search(r'"lbb_credits":"((?:\\.|[^"\\])*)"', self.html)
            if credits_match:
                credits_str = credits_match.group(1)
                if credits_str:
                    # Unescape
                    credits_str = credits_str.replace('\\"', '"').replace('\\\\', '\\').replace('\\/', '/')
                    try:
                        credits_str = credits_str.encode('utf-8').decode('unicode_escape')
                    except Exception as e:
                        logger.debug(f"Unicode escape decoding failed: {e}")
                    
                    try:
                        credits_data = json.loads(credits_str)
                        logger.info(f"Found JSON credits data with {len(credits_data)} sections")
                        
                        # Process the credits data
                        for section in credits_data:
                            if 'cat_value' in section and len(section['cat_value']) >= 2:
                                company_id, company_name = section['cat_value']
                                cat_id = str(section.get("cat_id", ""))
                                
                                # Determine company type from mapping
                                company_type = ""
                                if hasattr(self, 'fallback_mapping') and self.fallback_mapping:
                                    if cat_id in self.fallback_mapping.get("company_types", {}):
                                        company_type = self.fallback_mapping["company_types"][cat_id]
                                
                                # If type is still empty, try to guess from name
                                if not company_type:
                                    company_type = self._guess_company_type(company_name)
                                
                                # Create company credit
                                company_credit = {
                                    "id": company_id,
                                    "name": company_name,
                                    "type": company_type,
                                    "url": f"https://lbbonline.com/companies/{company_id}",
                                    "credits": []
                                }
                                
                                # Process roles
                                for field in section.get('fields', []):
                                    if 'field_value' in field and field['field_value'] is not None and len(field['field_value']) >= 2:
                                        person_id, person_name = field['field_value']
                                        field_id = str(field.get("field_id", ""))
                                        
                                        # Get role from mapping
                                        role_name = ""
                                        if hasattr(self, 'fallback_mapping') and self.fallback_mapping:
                                            if field_id in self.fallback_mapping.get("role_mappings", {}):
                                                role_name = self.fallback_mapping["role_mappings"][field_id]
                                        
                                        # Add role to company
                                        company_credit["credits"].append({
                                            "person": {
                                                "id": person_id,
                                                "name": person_name,
                                                "url": f"https://lbbonline.com/people/{person_id}"
                                            },
                                            "role": role_name
                                        })
                                        
                                        # If no role, add to unknown roles for potential AI enrichment
                                        if not role_name:
                                            unknown_roles.append({
                                                "person_id": person_id,
                                                "name": person_name
                                            })
                                
                                companies.append(company_credit)
                        
                        logger.info(f"Extracted {len(companies)} companies from JSON with {sum(len(c['credits']) for c in companies)} credits")
                        self.data["companies"] = companies
                        self.data["meta"]["unknown_roles"] = unknown_roles
                        self.data["meta"]["extraction_method"] = "lbbonline_json"
                        return True
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing credits JSON: {e}")
            
            # If lbb_credits fails, try old_credits
            old_credits_match = re.search(r'"old_credits":"([^"]*)"', self.html)
            if old_credits_match:
                old_credits = old_credits_match.group(1).replace('\\n', '\n')
                if old_credits:
                    logger.info("Found old_credits data, attempting to parse")
                    result = self._parse_old_credits_text(old_credits)
                    if result:
                        return True
            
            return False
        except Exception as e:
            logger.error(f"Error extracting credits from JSON: {e}")
            return False

    def _parse_old_credits_text(self, old_credits: str) -> bool:
        """
        Parse old_credits text format into structured credits
        """
        try:
            companies = []
            current_company = None
            current_section = ""
        
            lines = old_credits.split('\n')
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
                    # New company block
                    company_id = self._clean_text(value).lower().replace(' ', '-')
                    current_company = {
                        "id": company_id,
                        "name": value,
                        "type": current_section,
                        "url": f"https://lbbonline.com/companies/{company_id}",
                        "credits": []
                    }
                    companies.append(current_company)
                elif current_company and key and value:
                    # Role and person
                    person_id = self._clean_text(value).lower().replace(' ', '-')
                    current_company["credits"].append({
                        "person": {
                            "id": person_id,
                            "name": value,
                            "url": f"https://lbbonline.com/people/{person_id}"
                        },
                        "role": key
                    })
            
            if companies:
                logger.info(f"Extracted {len(companies)} companies from old_credits with {sum(len(c['credits']) for c in companies)} credits")
                self.data["companies"] = companies
                self.data["meta"]["extraction_method"] = "lbbonline_oldcredits"
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error parsing old_credits text: {e}")
            return False

    def _extract_credits_desperate(self):
        """Most aggressive credit extraction approach"""
        try:
            # Create a single default company
            company = {
                "id": "company_1",
                "name": self.data.get("client", "Unknown Company"),
                "type": "Unknown",
                "url": "",
                "credits": []
            }
            
            # Look for any text that matches role patterns
            role_patterns = [
                r'(\w+[\w\s]+):\s+([\w\s]+)',  # Role: Person
                r'(director|producer|editor|creative director|cinematographer|dop)\s+(?:is|was|:)?\s+([\w\s]+)',  # Role is Person
                r'([\w\s]+)\s+\((\w+[\w\s]+)\)'  # Person (Role)
            ]
            
            # Get all text from the page
            all_text = self.soup.get_text()
            
            # Find all potential matches
            for pattern in role_patterns:
                matches = re.finditer(pattern, all_text, re.IGNORECASE)
                for match in matches:
                    if pattern.startswith(r'([\w\s]+)\s+\('):
                        # Person (Role) format
                        person_name = match.group(1).strip()
                        role_name = match.group(2).strip()
                    else:
                        # Role: Person format
                        role_name = match.group(1).strip()
                        person_name = match.group(2).strip()
                    
                    # Skip if either field is missing
                    if not role_name or not person_name:
                        continue
                    
                    person_id = f"company_1_person_{len(company['credits']) + 1}"
                    
                    # Check if this person is already in our list
                    duplicate = False
                    for credit in company["credits"]:
                        if credit["person"]["name"].lower() == person_name.lower():
                            duplicate = True
                            break
                    
                    if not duplicate:
                        company["credits"].append({
                            "person": {
                                "id": person_id,
                                "name": person_name,
                                "url": ""
                            },
                            "role": role_name
                        })
            
            # Add the company if we found people
            if company["credits"]:
                self.data["companies"] = [company]
                
                # Special case for LBB Online - add client as a brand for desperate extraction
                if "lbbonline.com" in self.domain and self.data.get("client"):
                    self.data["companies"].append({
                        "id": "client_company",
                        "name": self.data["client"],
                        "type": "Brand",
                        "url": "",
                        "credits": []
                    })
        except Exception as e:
            logger.error(f"❌ Error in desperate credit extraction: {str(e)}")
    
    def _finalize_data(self):
        """Finalize the extracted data and clean it up"""
        try:
            # Add extraction metadata
            self.data["meta"]["extraction_method"] = self.structure_type
            
            # Make sure we have the basic fields, even if empty
            if not self.data.get("assets"):
                self.data["assets"] = {"image_url": self.data.get("poster_image", "")}
            
            # Clean up companies list
            if self.data.get("companies"):
                # Remove companies without credits or names
                self.data["companies"] = [
                    company for company in self.data["companies"] 
                    if company.get("name") and company.get("credits")
                ]
                
                # Clean up company names
                for company in self.data["companies"]:
                    company["name"] = self._clean_text(company["name"])
                    
                    # Clean up credits
                    if company.get("credits"):
                        for credit in company["credits"]:
                            if credit.get("person") and credit["person"].get("name"):
                                credit["person"]["name"] = self._clean_text(credit["person"]["name"])
                            
                            if credit.get("role"):
                                credit["role"] = self._clean_text(credit["role"])
            
            # Try to derive company type if missing
            for company in self.data.get("companies", []):
                if not company.get("type"):
                    company["type"] = self._guess_company_type(company["name"])
                    
            # Special case for LBB Online - if we still have no companies but have a client, add it as a brand
            if not self.data.get("companies") and "lbbonline.com" in self.domain and self.data.get("client"):
                self.data["companies"] = [{
                    "id": "client_company",
                    "name": self.data["client"],
                    "type": "Brand",
                    "url": "",
                    "credits": []
                }]
                
            # Set the data structure as credits_enriched if there are companies
            if self.data.get("companies"):
                self.data["meta"]["credits_enriched"] = True
            else:
                self.data["meta"]["credits_enriched"] = False
                
            # Log extraction results
            if self.debug:
                companies_count = len(self.data.get("companies", []))
                credits_count = sum(len(c.get("credits", [])) for c in self.data.get("companies", []))
                logger.debug(f"Extraction completed with {companies_count} companies and {credits_count} credits")
        except Exception as e:
            logger.error(f"❌ Error in data finalization: {str(e)}")
    
    def _extract_credits_lbb_specialized(self):
            """
            Use the specialized LBB credits extractor for more reliable extraction
            """
            try:
                # Import the specialized extractor for LBB sites
                from backend.scrapy.scraper.lbb_extractor import extract_lbb_credits
                
                # Use it to extract credits
                lbb_data = extract_lbb_credits(self.html, self.url, self.fallback_mapping, self.debug)
                
                if lbb_data.get('companies'):
                    logger.info(f"Specialized LBB extractor found {len(lbb_data['companies'])} companies")
                    
                    # Copy over the relevant data
                    self.data['companies'] = lbb_data['companies']
                    self.data['title'] = lbb_data.get('title', self.data['title'])
                    self.data['client'] = lbb_data.get('brand', self.data['client'])
                    self.data['video_links'] = [lbb_data['video_url']] if lbb_data.get('video_url') else self.data['video_links']
                    self.data['poster_image'] = lbb_data.get('image_url', self.data['poster_image'])
                    self.data['meta']['extraction_method'] = lbb_data['meta']['extraction_method']
                    
                    return True
                    
                return False
            except Exception as e:
                logger.error(f"Error in specialized LBB extractor: {e}")
                return False

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        """Extract ID from URL like /12345/ or similar patterns"""
        if not url:
            return None
            
        match = re.search(r"/(\d+)/?$", url)
        return match.group(1) if match else None

    def _improve_company_detection(self, soup, potential_companies: List[Tag]) -> List[Dict]:
        """
        Enhance company detection with more sophisticated filtering
        
        Args:
            soup: BeautifulSoup object
            potential_companies: List of potential company elements
        
        Returns:
            List of refined company dictionaries
        """
        refined_companies = []
        
        # Advanced filtering criteria
        def is_valid_company(element):
            # Text-based filters
            text = element.get_text(strip=True).lower()
            
            # Exclude clearly non-company text
            exclude_patterns = [
                'subscribe', 'newsletter', 'follow us', 'edition', 
                'credits', '→', 'arrow', 'page', 'menu', 
                'login', 'signup', 'sign up'
            ]
            if any(pattern in text for pattern in exclude_patterns):
                return False
            
            # Length-based filter
            if len(text) < 2 or len(text) > 100:
                return False
            
            # Capitalization check (most company names have significant capitalization)
            capitalized_words = sum(1 for word in text.split() if word and word[0].isupper())
            if capitalized_words < 1:
                return False
            
            return True
        
        for element in potential_companies:
            # Try to get meaningful text
            text = element.get_text(strip=True)
            
            if is_valid_company(element):
                # Try to find additional context
                company_type = self._guess_company_type(text)
                
                refined_companies.append({
                    "id": f"company_{len(refined_companies) + 1}",
                    "name": text,
                    "type": company_type,
                    "url": "",
                    "credits": []
                })
        
        return refined_companies

    def _guess_company_type(self, name: str) -> str:
        """Guess company type based on name or patterns"""
        if not name:
            return ""
            
        name_lower = name.lower()
        
        # Define type mapping with likely keywords
        type_mapping = {
            "Production": ["production", "films", "pictures", "studios"],
            "Agency": ["agency", "creative", "advertising", "digital"],
            "Brand": ["brand", "client"],
            "Post Production": ["post", "vfx", "effects", "post-production"],
            "Sound": ["sound", "audio", "music", "studio"],
            "Editorial": ["editorial", "edit", "editing"],
        }
        
        # Check each type
        for company_type, keywords in type_mapping.items():
            if any(keyword in name_lower for keyword in keywords):
                return company_type
        
        # If no match, return empty string
        return ""
    
    def _clean_text(self, text: str) -> str:
        """Clean up text fields by removing extra whitespace, etc."""
        if not text:
            return ""
            
        # Replace multiple whitespace with a single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text

def extract_project_adaptive(url: str, html: str, fallback_mapping: Dict = None, debug: bool = False) -> Dict:
    """
    Main extraction function that uses the adaptive extractor
    
    Args:
        url: The URL being scraped
        html: The HTML content
        fallback_mapping: Optional mapping for fallbacks
        debug: Whether to enable debug output
        
    Returns:
        Dictionary with extracted project data
    """
    logger.info(f"Starting adaptive extraction for {url}")
    extractor = AdaptiveExtractor(html, url, fallback_mapping, debug)
    data = extractor.extract()
    logger.info(f"Completed adaptive extraction: found {len(data.get('companies', []))} companies")
    return data

#   Integration with scrape_project
def scrape_project_adaptive(url: str, fallback_mapping: Optional[Dict] = None, debug: bool = False, 
                  ai_enabled: bool = None, ai_model: Optional[str] = None,
                  normalize_roles: bool = False, strategy_file: Optional[str] = None) -> Dict:
    """
    Main function to scrape a project page with adaptive extraction.

    Args:
        url: URL of the project page
        fallback_mapping: Optional mapping for role/company normalization
        debug: Enable debug output
        ai_enabled: Override config setting for AI enhancement
        ai_model: Override config setting for AI model
        normalize_roles: Use AI to normalize unknown roles
        strategy_file: Path to a JSON file containing a custom strategy

    Returns:
        Dictionary with project data
    """
    # Override config settings if specified
    global CONFIG
    if ai_enabled is not None:
        CONFIG["AI_ENABLED"] = ai_enabled

    if ai_model:
        CONFIG["AI_MODEL"] = ai_model

    # Set up enhanced logging if in debug mode
    if debug:
        logger.setLevel(logging.DEBUG)
        # Add a file handler to capture all debug logs
        try:
            debug_handler = logging.FileHandler('adaptive_extractor_debug.log')
            debug_handler.setLevel(logging.DEBUG)
            logger.addHandler(debug_handler)
        except:
            pass

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
        html, from_cache = fetch_html_and_snapshot(url, force_refresh=CONFIG.get("FORCE_REFRESH", False))
    except Exception as e:
        logger.error(f"❌ Failed to fetch page: {e}")
        return {}

    # Step 2: Use the adaptive extractor to extract data
    logger.info(f"📊 Using adaptive extraction for {url}")
    data = extract_project_adaptive(url, html, fallback_mapping, debug)
    
    # Step 3: Check for missing elements
    missing_elements = validate_scraped_data(data)
    
    # Step 4: If validation failed and AI is enabled, use AI suggestions to enhance
    if missing_elements and CONFIG.get("AI_ENABLED", False):
        try:
            # Try AI enhancement for missing elements
            snapshot_path = os.path.join(SNAPSHOT_DIR, f"{urlparse(url).netloc.replace('www.', '')}_{hashlib.md5(url.encode()).hexdigest()[:10]}.html")
            logger.info(f"🤖 Using AI to enhance extraction for missing elements: {', '.join(missing_elements)}")
            
            # Get AI-suggested selectors
            fix_suggestions = suggest_fixes_via_openai(html, url, missing_elements, snapshot_path)
            
            # Record AI suggestions in metadata
            data["meta"]["missing_elements"] = missing_elements
            data["meta"]["ai_suggestions"] = fix_suggestions.get("suggestions", {})
            
            # Try to reextract with the AI suggestions if we're still missing companies
            if "companies" in missing_elements and fix_suggestions.get("suggestions", {}).get("companies"):
                logger.info("🔄 Re-extracting with AI suggestions for companies")
                # Create a soup from the HTML
                soup = BeautifulSoup(html, "html.parser")
                
                # Try the AI-suggested companies selector
                companies_selector = fix_suggestions["suggestions"]["companies"]
                company_elements = soup.select(companies_selector)
                
                if company_elements:
                    logger.info(f"✅ Found {len(company_elements)} potential company elements with AI selector")
                    
                    # Create a dummy company for each element found
                    companies = []
                    for i, element in enumerate(company_elements):
                        company_name = element.get_text(strip=True)
                        if not company_name:
                            continue
                            
                        companies.append({
                            "id": f"ai_company_{i+1}",
                            "name": company_name,
                            "type": "",
                            "url": "",
                            "credits": []
                        })
                    
                    if companies:
                        data["companies"] = companies
                        logger.info(f"✅ Added {len(companies)} companies from AI suggestions")
                        
                        # Update missing elements
                        missing_elements.remove("companies")
        except Exception as e:
            logger.error(f"❌ Error in AI enhancement: {e}")
    
    # Step 5: Normalize roles with AI if requested
    if normalize_roles and CONFIG.get("AI_ENABLED", False) and data.get("meta", {}).get("unknown_roles"):
        try:
            data = normalize_roles_with_ai(data, html)
        except Exception as e:
            logger.error(f"❌ Error in role normalization: {e}")

    # Step 6: Return the structured data
    if debug:
        try:
            logger.debug(json.dumps(data, indent=2))
        except:
            logger.debug("Unable to log data as JSON")

    return data

# For command-line testing
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Test the adaptive extractor")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--output", help="Save output to file")
    parser.add_argument("--ai", action="store_true", help="Enable AI enhancement")
    
    args = parser.parse_args()
    
    try:
        # Fetch HTML
        try:
            from backend.scrapy.scraper.project_scraper import fetch_html_and_snapshot
        except ImportError:
            from requests import get
            def fetch_html_and_snapshot(url, **kwargs):
                response = get(url)
                return response.text, False
                
        html, _ = fetch_html_and_snapshot(args.url)
        
        # Extract data
        if args.ai:
            CONFIG["AI_ENABLED"] = True
            data = scrape_project_adaptive(args.url, debug=args.debug)
        else:
            data = extract_project_adaptive(args.url, html, debug=args.debug)
        
        # Output results
        print(f"\nExtracted Data:")
        print(f"Title: {data.get('title')}")
        print(f"Companies: {len(data.get('companies', []))}")
        
        for i, company in enumerate(data.get('companies', [])):
            print(f"\nCompany {i+1}: {company.get('name')}")
            print(f"  Type: {company.get('type')}")
            print(f"  Credits: {len(company.get('credits', []))}")
            
            for credit in company.get('credits', [])[:3]:  # Show first 3 credits
                person = credit.get('person', {})
                print(f"    {credit.get('role')}: {person.get('name')}")
            
            if len(company.get('credits', [])) > 3:
                print(f"    ... and {len(company.get('credits', [])) - 3} more")
        
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"\nSaved to {args.output}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)