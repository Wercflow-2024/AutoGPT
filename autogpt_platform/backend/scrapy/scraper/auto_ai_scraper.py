# python -m backend.scrapy.scraper.auto_ai_scraper https://lbbonline.com/work/132273 --debug

#!/usr/bin/env python3
"""
Autonomous AI-Powered Scraper Agent
This agent will run continuously, learning from failures until it succeeds.
"""

import requests
import re
import json
import os
import time
import logging
import random
import importlib
import sys
import traceback
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("ai_scraper.log"),
        logging.StreamHandler()
    ],
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("autonomous_scraper")

from dotenv import load_dotenv
import os

load_dotenv()  # This loads variables from your .env file

azure_key = os.getenv("AZURE_OPENAI_API_KEY1")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

print("Azure OpenAI Key:", azure_key)
print("Azure OpenAI Endpoint:", azure_endpoint)

class AutonomousScraper:
    """Self-improving AI scraper that will retry until successful"""

    def __init__(self, api_key=None, model="gpt-4o", debug=False, max_retries=20):
        """Initialize the autonomous scraper"""
        self.debug = debug
        self.max_retries = max_retries

        if debug:
            logger.setLevel(logging.DEBUG)

        # API configuration
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY1")
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")

        if not self.api_key:
            logger.warning("No OpenAI API key found. Set OPENAI_API_KEY environment variable.")

        self.model = model

        # Session history - track all attempts
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = f"scraper_session_{self.session_id}"
        os.makedirs(self.session_dir, exist_ok=True)

        # Knowledge base
        self.knowledge_base_path = os.path.join(self.session_dir, "knowledge_base.json")
        self.knowledge_base = self.load_knowledge_base()

        # Required libraries - attempt to import
        self.ensure_dependencies()

        logger.info(f"Autonomous Scraper initialized (Session: {self.session_id})")

    def ensure_dependencies(self):
        """Make sure all required dependencies are installed"""
        required_packages = [
            "requests", "bs4", "openai", "pandas", "lxml", "html5lib"
        ]

        for package in required_packages:
            try:
                importlib.import_module(package)
            except ImportError:
                logger.warning(f"Package {package} not found. Attempting to install...")
                try:
                    import subprocess
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    logger.info(f"Successfully installed {package}")
                except Exception as e:
                    logger.error(f"Failed to install {package}: {e}")

    def load_knowledge_base(self) -> Dict:
        """Load knowledge base from disk or initialize a new one"""
        if os.path.exists(self.knowledge_base_path):
            try:
                with open(self.knowledge_base_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading knowledge base: {e}")

        # Initialize new knowledge base
        knowledge_base = {
            "domains": {},
            "global_patterns": {
                "title": [
                    {"type": "meta", "selector": "title"},
                    {"type": "regex", "pattern": r'<title>(.*?)</title>'},
                    {"type": "regex", "pattern": r'"title":"([^"]+)"'}
                ],
                "description": [
                    {"type": "meta", "selector": "meta[name='description']", "attribute": "content"},
                    {"type": "regex", "pattern": r'<meta\s+name="description"\s+content="([^"]+)"'}
                ],
                "json_blocks": [
                    {"type": "regex", "pattern": r'<script[^>]*type="application/json"[^>]*>(.*?)</script>'},
                    {"type": "regex", "pattern": r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>'},
                    {"type": "regex", "pattern": r'"lbb_credits":"((?:\\.|[^"\\])*)"'},
                    {"type": "regex", "pattern": r'"old_credits":"([^"]*)"'}
                ]
            },
            "attempts": {},
            "successes": {}
        }

        # Add specific LBB knowledge since we already know it
        knowledge_base["domains"]["lbbonline.com"] = {
            "patterns": {
                "lbb_credits": {"type": "regex", "pattern": r'"lbb_credits":"((?:\\.|[^"\\])*)"'},
                "title": {"type": "regex", "pattern": r'"brand_and_name":"([^"]+)"'},
                "video_url": {"type": "regex", "pattern": r'"notube_id":"([^"]+)"'}
            },
            "extraction_methods": [
                "extract_from_lbb_credits_json",
                "extract_from_old_credits",
                "extract_from_dom"
            ]
        }

        return knowledge_base

    def save_knowledge_base(self):
        """Save knowledge base to disk"""
        try:
            with open(self.knowledge_base_path, 'w') as f:
                json.dump(self.knowledge_base, f, indent=2)
            logger.info(f"Knowledge base saved to {self.knowledge_base_path}")
        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")

    def scrape_until_success(self, url: str, success_criteria: Optional[Dict] = None) -> Dict:
        """
        Continuously attempt to scrape a URL until successful
        
        Args:
            url: The URL to scrape
            success_criteria: Dictionary defining what makes a successful scrape
                e.g. {"min_companies": 1, "min_credits": 5}
        
        Returns:
            The final result dictionary
        """
        if not success_criteria:
            success_criteria = {"min_companies": 1}

        domain = self.extract_domain(url)
        logger.info(f"Starting scraping session for {url} (domain: {domain})")

        # Create attempt tracking
        attempt_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.knowledge_base["attempts"][attempt_id] = {
            "url": url,
            "domain": domain,
            "started_at": datetime.now().isoformat(),
            "success": False,
            "iterations": []
        }

        html = None
        result = None
        success = False

        for iteration in range(1, self.max_retries + 1):
            logger.info(f"Attempt {iteration}/{self.max_retries} for {url}")

            # Record this iteration
            iteration_data = {
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
                "methods_tried": [],
                "success": False
            }

            try:
                # Fetch HTML (only on first attempt or if we need fresh content)
                if html is None or iteration % 5 == 0:  # Refresh every 5 attempts
                    html = self.fetch_html(url)
                    if not html:
                        logger.error(f"Failed to fetch HTML from {url}, retrying...")
                        time.sleep(random.uniform(2, 5))
                        continue

                    # Save HTML for debugging
                    html_path = os.path.join(self.session_dir, f"html_{domain}_{iteration}.html")
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    logger.debug(f"HTML saved to {html_path}")

                # Try different scraping strategies
                if domain in self.knowledge_base["domains"]:
                    # Use domain-specific methods first
                    domain_methods = self.knowledge_base["domains"][domain].get("extraction_methods", [])

                    for method_name in domain_methods:
                        iteration_data["methods_tried"].append(method_name)

                        try:
                            # Get the method from this class
                            method = getattr(self, method_name)
                            result = method(html, url)

                            # Check if this result meets success criteria
                            if self.is_successful(result, success_criteria):
                                success = True
                                logger.info(f"Successfully extracted data using {method_name}")
                                break
                        except Exception as e:
                            logger.error(f"Error with method {method_name}: {e}")
                            traceback.print_exc()

                # If domain-specific methods failed, try generic methods
                if not success:
                    generic_methods = [
                        "extract_generic",
                        "extract_with_ai_analysis"
                    ]

                    for method_name in generic_methods:
                        if method_name in iteration_data["methods_tried"]:
                            continue

                        iteration_data["methods_tried"].append(method_name)

                        try:
                            method = getattr(self, method_name)
                            result = method(html, url)

                            # Check if this result meets success criteria
                            if self.is_successful(result, success_criteria):
                                success = True
                                logger.info(f"Successfully extracted data using {method_name}")

                                # If this was AI analysis, learn from it
                                if method_name == "extract_with_ai_analysis" and "patterns" in result.get("meta", {}):
                                    self.learn_from_ai_analysis(domain, result["meta"]["patterns"])

                                break
                        except Exception as e:
                            logger.error(f"Error with method {method_name}: {e}")
                            traceback.print_exc()

                # Record results for this iteration
                iteration_data["success"] = success
                if result:
                    result_path = os.path.join(self.session_dir, f"result_{domain}_{iteration}.json")
                    with open(result_path, 'w') as f:
                        json.dump(result, f, indent=2)
                    iteration_data["result_path"] = result_path

                self.knowledge_base["attempts"][attempt_id]["iterations"].append(iteration_data)
                self.save_knowledge_base()

                # If successful, break out of the loop
                if success:
                    self.knowledge_base["attempts"][attempt_id]["success"] = True
                    self.knowledge_base["successes"][attempt_id] = {
                        "url": url,
                        "domain": domain,
                        "completed_at": datetime.now().isoformat(),
                        "iterations_required": iteration,
                        "final_method": iteration_data["methods_tried"][-1]
                    }
                    self.save_knowledge_base()
                    break

                # Wait before next attempt
                time.sleep(random.uniform(2, 5))

            except Exception as e:
                logger.error(f"Error in iteration {iteration}: {e}")
                traceback.print_exc()

                # Still record this iteration
                iteration_data["error"] = str(e)
                self.knowledge_base["attempts"][attempt_id]["iterations"].append(iteration_data)
                self.save_knowledge_base()

                # Wait before retry
                time.sleep(random.uniform(3, 7))

        # Final result
        if success:
            logger.info(f"Successfully scraped {url} after {iteration} attempts")
            return result
        else:
            logger.warning(f"Failed to scrape {url} after {self.max_retries} attempts")
            return {"error": "Failed to scrape after maximum retries", "url": url}

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        return match.group(1) if match else "unknown"

    def fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML from URL with retries"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        for attempt in range(3):  # 3 retries
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.text
            except Exception as e:
                logger.error(f"Error fetching {url} (attempt {attempt+1}/3): {e}")
                time.sleep(random.uniform(2, 5))

        return None

    def is_successful(self, result: Dict, criteria: Dict) -> bool:
        """Check if the result meets the success criteria"""
        if not result or "error" in result:
            return False

        # Check companies
        if "min_companies" in criteria:
            companies = result.get("companies", [])
            if len(companies) < criteria["min_companies"]:
                return False

        # Check credits
        if "min_credits" in criteria:
            total_credits = sum(len(company.get("credits", [])) for company in result.get("companies", []))
            if total_credits < criteria["min_credits"]:
                return False

        # Add more criteria checks as needed

        return True

    # Add the following methods inside the AutonomousScraper class
    def load_gold_standard(self, url: str) -> Optional[Dict]:
        """
        Load a gold standard JSON for the given URL if available.
        Assumes the file is stored in a folder named 'golden_data/<domain>/<project_id>.json'
        """
        match = re.search(r'lbbonline\.com/work/(\d+)', url)
        if match:
            project_id = match.group(1)
            domain = "lbbonline.com"
            path = os.path.join("golden_data", domain, f"{project_id}.json")
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        gold = json.load(f)
                    logger.info(f"Gold standard loaded from {path}")
                    return gold
                except Exception as e:
                    logger.error(f"Error loading gold standard: {e}")
        return None

    def compare_against_gold(self, extracted: Dict, gold: Dict) -> bool:
        """
        Compare the extracted data against the gold standard.
        Checks title, client, and total number of credits.
        """
        # Compare title if gold has it
        if gold.get("title") and extracted.get("title") != gold["title"]:
            logger.debug(f"Title mismatch: expected '{gold['title']}', got '{extracted.get('title','')}'")
            return False

        # Compare client if present
        if gold.get("client") and extracted.get("client") != gold["client"]:
            logger.debug(f"Client mismatch: expected '{gold['client']}', got '{extracted.get('client','')}'")
            return False

        # Compare total credits if specified in gold's meta
        expected_credits = gold.get("meta", {}).get("expected_credits")
        if expected_credits:
            total_extracted_credits = sum(len(c.get("credits", [])) for c in extracted.get("companies", []))
            if total_extracted_credits < expected_credits:
                logger.debug(f"Credit count mismatch: expected at least {expected_credits}, got {total_extracted_credits}")
                return False

        logger.info("Extracted data matches the gold standard.")
        return True

    def is_successful(self, result: Dict, criteria: Dict) -> bool:
        """Check if the result meets the success criteria, including matching a gold standard if available"""
        if not result or "error" in result:
            return False

        # Check minimal criteria first
        if "min_companies" in criteria:
            companies = result.get("companies", [])
            if len(companies) < criteria["min_companies"]:
                return False

        if "min_credits" in criteria:
            total_credits = sum(len(c.get("credits", [])) for c in result.get("companies", []))
            if total_credits < criteria["min_credits"]:
                return False

        # Now, if a gold standard exists for this URL, perform a detailed comparison
        gold = self.load_gold_standard(result.get("url", ""))
        if gold:
            if not self.compare_against_gold(result, gold):
                return False

        return True

    # In the scrape_until_success method, update the loop as follows:
    def scrape_until_success(self, url: str, success_criteria: Optional[Dict] = None) -> Dict:
        """
        Continuously attempt to scrape a URL until successful.
        Records each iteration as an artifact and learns the winning strategy.
        
        Args:
            url: The URL to scrape
            success_criteria: Dictionary defining success (e.g., {"min_companies": 1, "min_credits": 5})
        
        Returns:
            The final result dictionary
        """
        if not success_criteria:
            success_criteria = {"min_companies": 1}

        domain = self.extract_domain(url)
        logger.info(f"Starting scraping session for {url} (domain: {domain})")

        # Create attempt tracking
        attempt_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.knowledge_base["attempts"][attempt_id] = {
            "url": url,
            "domain": domain,
            "started_at": datetime.now().isoformat(),
            "success": False,
            "iterations": []
        }

        html = None
        result = None
        success = False

        for iteration in range(1, self.max_retries + 1):
            logger.info(f"Attempt {iteration}/{self.max_retries} for {url}")

            iteration_data = {
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
                "methods_tried": [],
                "success": False
            }

            try:
                if html is None or iteration % 5 == 0:  # Refresh every 5 attempts
                    html = self.fetch_html(url)
                    if not html:
                        logger.error(f"Failed to fetch HTML from {url}, retrying...")
                        time.sleep(random.uniform(2, 5))
                        continue

                    # Save HTML snapshot for debugging
                    html_path = os.path.join(self.session_dir, f"html_{domain}_{iteration}.html")
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    logger.debug(f"HTML saved to {html_path}")

                # Try extraction methods as before...
                if domain in self.knowledge_base["domains"]:
                    domain_methods = self.knowledge_base["domains"][domain].get("extraction_methods", [])
                    for method_name in domain_methods:
                        iteration_data["methods_tried"].append(method_name)
                        try:
                            method = getattr(self, method_name)
                            result = method(html, url)
                            if self.is_successful(result, success_criteria):
                                success = True
                                logger.info(f"Successfully extracted data using {method_name}")
                                break
                        except Exception as e:
                            logger.error(f"Error with method {method_name}: {e}")
                            traceback.print_exc()

                if not success:
                    generic_methods = [
                        "extract_generic",
                        "extract_with_ai_analysis"
                    ]
                    for method_name in generic_methods:
                        if method_name in iteration_data["methods_tried"]:
                            continue
                        iteration_data["methods_tried"].append(method_name)
                        try:
                            method = getattr(self, method_name)
                            result = method(html, url)
                            if self.is_successful(result, success_criteria):
                                success = True
                                logger.info(f"Successfully extracted data using {method_name}")
                                if method_name == "extract_with_ai_analysis" and "patterns" in result.get("meta", {}):
                                    self.learn_from_ai_analysis(domain, result["meta"]["patterns"])
                                break
                        except Exception as e:
                            logger.error(f"Error with method {method_name}: {e}")
                            traceback.print_exc()

                # Record extraction counts
                companies = result.get("companies", [])
                iteration_data["extracted_companies"] = len(companies)
                iteration_data["extracted_credits"] = sum(len(c.get("credits", [])) for c in companies)

                # Save iteration artifact
                artifact_path = os.path.join(self.session_dir, f"attempt_{attempt_id}_iter_{iteration}.json")
                with open(artifact_path, 'w', encoding='utf-8') as f:
                    json.dump(iteration_data, f, indent=2)
                iteration_data["artifact_path"] = artifact_path

                self.knowledge_base["attempts"][attempt_id]["iterations"].append(iteration_data)
                self.save_knowledge_base()

                if success:
                    # Record the winning extraction method in the knowledge base for this domain
                    final_method = iteration_data["methods_tried"][-1]
                    if domain not in self.knowledge_base["domains"]:
                        self.knowledge_base["domains"][domain] = {"patterns": {}, "extraction_methods": []}
                    if final_method not in self.knowledge_base["domains"][domain]["extraction_methods"]:
                        self.knowledge_base["domains"][domain]["extraction_methods"].insert(0, final_method)
                    self.knowledge_base["attempts"][attempt_id]["success"] = True
                    self.knowledge_base["successes"][attempt_id] = {
                        "url": url,
                        "domain": domain,
                        "completed_at": datetime.now().isoformat(),
                        "iterations_required": iteration,
                        "final_method": final_method
                    }
                    self.save_knowledge_base()
                    logger.info(f"Successfully scraped {url} after {iteration} attempts")
                    break

                time.sleep(random.uniform(2, 5))

            except Exception as e:
                logger.error(f"Error in iteration {iteration}: {e}")
                iteration_data["error"] = str(e)
                self.knowledge_base["attempts"][attempt_id]["iterations"].append(iteration_data)
                self.save_knowledge_base()
                time.sleep(random.uniform(3, 7))

        if not success:
            logger.warning(f"Failed to scrape {url} after {self.max_retries} attempts")
            return {"error": "Failed to scrape after maximum retries", "url": url}
        return result

    def extract_with_heuristics(self, html: str, url: str, fallback_mapping: Optional[Dict] = None) -> Dict:
        """
        Extract company and credit information using heuristics and fallback mapping.

        This method assumes that on the page, a company type is presented as a heading
        (e.g., h2, h3, or h4) which is immediately followed by the company name, and that the next sibling
        contains a list (or container) of people/roles associated with that company.

        Args:
            html: The HTML content of the page.
            url: The URL being scraped.
            fallback_mapping: A dictionary with keys 'company_types' and 'role_mappings' to provide known
                              company types and role names.

        Returns:
            A dictionary containing the extracted project data.
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        result = {
            "url": url,
            "title": "",
            "companies": [],
            "meta": {
                "extraction_method": "heuristics",
                "scraped_at": datetime.now().isoformat()
            }
        }

        # Extract title from <title> tag
        title_tag = soup.find('title')
        if title_tag:
            result["title"] = title_tag.get_text(strip=True)

        # Use fallback mapping if provided; otherwise, an empty dict
        fallback = fallback_mapping if fallback_mapping else {}
        # Get a set of known company types (assume fallback["company_types"] is a dict mapping keys to type names)
        known_company_types = set(val.lower() for val in fallback.get("company_types", {}).values())

        companies = []

        # Heuristic: Look for headings (h2, h3, h4) whose text matches one of the known company types.
        headings = soup.find_all(['h2', 'h3', 'h4'])
        for heading in headings:
            heading_text = heading.get_text(strip=True).lower()
            if heading_text in known_company_types:
                company_type = heading_text
                # The next sibling is expected to contain the company name.
                company_name_elem = heading.find_next_sibling()
                if not company_name_elem:
                    continue
                company_name = company_name_elem.get_text(strip=True)

                # Optionally, you can check if the fallback mapping has a standardized name for this company type.
                # (This example doesn't change the company name, but you could add that logic here.)

                # Now, assume that the following sibling (after the company name element) contains the list of people/roles.
                credits = []
                credits_container = company_name_elem.find_next_sibling()
                if credits_container:
                    # Search for list items or divs that likely represent role: person pairs.
                    credit_items = credits_container.find_all(['li', 'div'])
                    for item in credit_items:
                        text = item.get_text(strip=True)
                        if ':' in text:
                            role, person = text.split(':', 1)
                            role = role.strip()
                            person = person.strip()
                        else:
                            role = ""
                            person = text.strip()
                        if person:
                            credits.append({
                                "person": {
                                    "id": f"{company_name.lower().replace(' ', '_')}_{len(credits)+1}",
                                    "name": person,
                                    "url": ""
                                },
                                "role": role
                            })

                company_obj = {
                    "id": company_name.lower().replace(' ', '_'),
                    "name": company_name,
                    "type": company_type,
                    "url": "",
                    "credits": credits
                }
                companies.append(company_obj)

        if not companies:
            logger.warning("Heuristics extraction found no companies")
            raise ValueError("Heuristics extraction found no companies")

        result["companies"] = companies
        return result

    def extract_from_lbb_credits_json(self, html: str, url: str) -> Dict:
        """Extract credits from LBB credits JSON"""
        logger.info("Attempting to extract from lbb_credits JSON")

        # Initialize result
        result = {
            "url": url,
            "title": "",
            "companies": [],
            "meta": {
                "extraction_method": "lbb_credits_json",
                "scraped_at": datetime.now().isoformat()
            }
        }

        # Try to find the lbb_credits JSON
        credits_match = re.search(r'"lbb_credits":"((?:\\.|[^"\\])*)"', html)
        if not credits_match:
            logger.warning("No lbb_credits found in HTML")
            raise ValueError("No lbb_credits JSON found")

        credits_str = credits_match.group(1)
        if not credits_str:
            logger.warning("Empty lbb_credits string")
            raise ValueError("Empty lbb_credits JSON")

        # Unescape the JSON string
        credits_str = credits_str.replace('\\"', '"').replace('\\\\', '\\').replace('\\/', '/')
        try:
            credits_str = credits_str.encode('utf-8').decode('unicode_escape')
        except Exception as e:
            logger.debug(f"Unicode escape decoding failed: {e}")

        # Save raw JSON for debugging
        raw_json_path = os.path.join(self.session_dir, f"raw_lbb_credits_{self.extract_domain(url)}.json")
        with open(raw_json_path, 'w', encoding='utf-8') as f:
            f.write(credits_str)

        # Parse JSON
        try:
            credits_data = json.loads(credits_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse lbb_credits JSON: {e}")

            # Try demjson or ast if available
            try:
                import ast
                credits_data = ast.literal_eval(credits_str)
                logger.info("Parsed lbb_credits using ast.literal_eval")
            except (ImportError, SyntaxError) as e:
                try:
                    import demjson3
                    credits_data = demjson3.decode(credits_str)
                    logger.info("Parsed lbb_credits using demjson3")
                except ImportError:
                    raise ValueError(f"Failed to parse lbb_credits JSON: {e}")

        # Extract basic metadata
        title_match = re.search(r'"brand_and_name":"([^"]+)"', html)
        if title_match:
            result["title"] = title_match.group(1)

        # Extract video URL
        video_match = re.search(r'"notube_id":"([^"]+)"', html)
        if video_match:
            result["video_url"] = f"https://notube.lbbonline.com/v/{video_match.group(1)}"

        # Process each section (company)
        companies = []

        for section in credits_data:
            if 'cat_value' in section and isinstance(section['cat_value'], list) and len(section['cat_value']) >= 2:
                company_id, company_name = section['cat_value']
                cat_id = str(section.get("cat_id", ""))

                # Get company type from knowledge base if available
                company_type = ""
                if "company_types" in self.knowledge_base.get("mappings", {}):
                    company_type = self.knowledge_base["mappings"]["company_types"].get(cat_id, "")

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
                    if 'field_value' in field and field['field_value'] is not None and isinstance(field['field_value'], list) and len(field['field_value']) >= 2:
                        person_id, person_name = field['field_value']
                        field_id = str(field.get("field_id", ""))

                        # Get role name from knowledge base if available
                        role_name = ""
                        if "role_mappings" in self.knowledge_base.get("mappings", {}):
                            role_name = self.knowledge_base["mappings"]["role_mappings"].get(field_id, "")

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

        if not companies:
            logger.warning("No companies found in lbb_credits JSON")
            raise ValueError("No companies found in lbb_credits JSON")

        result["companies"] = companies
        logger.info(f"Extracted {len(companies)} companies with {sum(len(c['credits']) for c in companies)} credits from lbb_credits")

        return result

    def extract_from_old_credits(self, html: str, url: str) -> Dict:
        """Extract from old_credits format"""
        logger.info("Attempting to extract from old_credits")

        # Initialize result
        result = {
            "url": url,
            "title": "",
            "companies": [],
            "meta": {
                "extraction_method": "old_credits",
                "scraped_at": datetime.now().isoformat()
            }
        }

        # Try to find old_credits
        old_credits_match = re.search(r'"old_credits":"([^"]*)"', html)
        if not old_credits_match:
            logger.warning("No old_credits found in HTML")
            raise ValueError("No old_credits found")

        old_credits = old_credits_match.group(1)
        if not old_credits:
            logger.warning("Empty old_credits string")
            raise ValueError("Empty old_credits")

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

        if not companies:
            logger.warning("No companies found in old_credits")
            raise ValueError("No companies found in old_credits")

        result["companies"] = companies
        logger.info(f"Extracted {len(companies)} companies with {sum(len(c['credits']) for c in companies)} credits from old_credits")

        # Extract title and other metadata
        title_match = re.search(r'"title":"([^"]+)"', html) or re.search(r'<title>(.*?)</title>', html)
        if title_match:
            result["title"] = title_match.group(1)

        return result

    def extract_from_dom(self, html: str, url: str) -> Dict:
        """Extract credits from DOM structure"""
        logger.info("Attempting to extract from DOM structure")

        # Initialize result
        result = {
            "url": url,
            "title": "",
            "companies": [],
            "meta": {
                "extraction_method": "dom",
                "scraped_at": datetime.now().isoformat()
            }
        }

        try:
            # Try to use BeautifulSoup for more intelligent parsing
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                result["title"] = title_tag.text.strip()

            # Try to find credit sections
            credit_sections = soup.select('.credits, .team, .crew, .credit-section, .credit-entry')

            if not credit_sections:
                # Try alternative selectors
                credit_sections = soup.select('div[class*="credit"], div[class*="team"], section[class*="credit"]')

            companies = []

            for section in credit_sections:
                # Try to find company name
                company_name_tag = section.select_one('.company-name, .company, h2, h3')
                if not company_name_tag:
                    continue

                company_name = company_name_tag.text.strip()
                company_id = f"dom_{len(companies) + 1}"

                # Try to find company type
                company_type_tag = section.select_one('.company-type, .type')
                company_type = company_type_tag.text.strip() if company_type_tag else ""

                # Create company
                company = {
                    "id": company_id,
                    "name": company_name,
                    "type": company_type,
                    "url": "",
                    "credits": []
                }

                # Try to find role-person pairs
                role_blocks = section.select('.role, .credit, .member, div[class*="role"]')

                for role_block in role_blocks:
                    # Try different patterns for role and person
                    role_name_tag = role_block.select_one('.role-name, .title')
                    person_tag = role_block.select_one('.person, .name')

                    role_name = role_name_tag.text.strip() if role_name_tag else ""
                    person_name = person_tag.text.strip() if person_tag else ""

                    # If we couldn't find with selectors, try text patterns
                    if not role_name or not person_name:
                        text = role_block.text.strip()
                        if ':' in text:
                            parts = text.split(':', 1)
                            if not role_name:
                                role_name = parts[0].strip()
                            if not person_name and len(parts) > 1:
                                person_name = parts[1].strip()

                    if person_name:
                        person_id = f"{company_id}_person_{len(company['credits']) + 1}"

                        company["credits"].append({
                            "person": {
                                "id": person_id,
                                "name": person_name,
                                "url": ""
                            },
                            "role": role_name
                        })

                if company["credits"]:
                    companies.append(company)

            if not companies:
                logger.warning("No companies found in DOM")
                raise ValueError("No companies found in DOM")

            result["companies"] = companies
            logger.info(f"Extracted {len(companies)} companies with {sum(len(c['credits']) for c in companies)} credits from DOM")

            return result

        except ImportError:
            logger.warning("BeautifulSoup not available, using regex-based extraction")

            # Fallback to regex-based extraction
            # This will be less reliable but can work in a pinch
            company_matches = re.findall(r'<(?:div|span)[^>]*class="[^"]*company[^"]*"[^>]*>([^<]+)</(?:div|span)>', html)

            if not company_matches:
                logger.warning("No company elements found with regex")
                raise ValueError("No companies found with regex")

            logger.info(f"Found {len(company_matches)} potential company elements with regex")

            # Find potential role-person pairs
            role_matches = re.findall(r'<(?:div|span)[^>]*class="[^"]*role[^"]*"[^>]*>([^:]+):\s*([^<]+)</(?:div|span)>', html)

            logger.info(f"Found {len(role_matches)} potential role-person pairs with regex")

            if not role_matches:
                logger.warning("No role elements found with regex")
                raise ValueError("No roles found with regex")

            # Create companies with the credits
            companies = []
            for i, company_name in enumerate(company_matches):
                company_name = company_name.strip()
                company_id = f"regex_company_{i+1}"

                company = {
                    "id": company_id,
                    "name": company_name,
                    "type": "",
                    "url": "",
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
                            "url": ""
                        },
                        "role": role_name
                    })

                if company["credits"]:
                    companies.append(company)

            result["companies"] = companies
            logger.info(f"Extracted {len(companies)} companies with {sum(len(c['credits']) for c in companies)} credits with regex")

            # Extract title with regex
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                result["title"] = title_match.group(1).strip()

            return result

    def extract_generic(self, html: str, url: str) -> Dict:
        """Generic extraction using common patterns"""
        logger.info("Attempting generic extraction")

        # Initialize result
        result = {
            "url": url,
            "title": "",
            "companies": [],
            "meta": {
                "extraction_method": "generic",
                "scraped_at": datetime.now().isoformat()
            }
        }

        # Try to use BeautifulSoup for better parsing
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                result["title"] = title_tag.text.strip()

            # Try to find any JSON data that might contain credits
            script_tags = soup.find_all('script', type="application/json")

            for script in script_tags:
                try:
                    json_data = json.loads(script.string)
                    # Look for any credit-like structures
                    self._extract_from_json_data(json_data, result)
                except:
                    pass

            # Try to find any hidden JSON in attributes
            data_attrs = soup.find_all(attrs=lambda x: x and hasattr(x, 'attrs') and any(a.startswith('data-') for a in x.attrs))


            for elem in data_attrs:
                for attr, value in elem.attrs.items():
                    if attr.startswith('data-') and value and ('{' in value or '[' in value):
                        try:
                            json_data = json.loads(value)
                            self._extract_from_json_data(json_data, result)
                        except:
                            pass

        except ImportError:
            logger.warning("BeautifulSoup not available")

            # Extract title with regex
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                result["title"] = title_match.group(1).strip()

            # Try to find JSON data with regex
            json_blocks = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)

            for block in json_blocks:
                try:
                    json_data = json.loads(block)
                    self._extract_from_json_data(json_data, result)
                except:
                    pass

        # If no companies found, this method failed
        if not result.get("companies"):
            raise ValueError("No companies found with generic extraction")

        return result

    def _extract_from_json_data(self, json_data: Any, result: Dict) -> None:
        """Recursively examine JSON data for credit-like structures"""
        if isinstance(json_data, dict):
            # Look for company-like keys
            company_keys = ['company', 'agency', 'studio', 'production', 'credit', 'team']
            for key in company_keys:
                if key in json_data and isinstance(json_data[key], (dict, list)):
                    self._process_potential_company(json_data[key], result)

            # Look for credits array
            if 'credits' in json_data and isinstance(json_data['credits'], list):
                self._process_credits_array(json_data['credits'], result)

            # Look for companies array
            if 'companies' in json_data and isinstance(json_data['companies'], list):
                for company_data in json_data['companies']:
                    self._process_potential_company(company_data, result)

            # Recurse into all dictionary values
            for value in json_data.values():
                self._extract_from_json_data(value, result)

        elif isinstance(json_data, list):
            # Recurse into all list items
            for item in json_data:
                self._extract_from_json_data(item, result)

    def _process_potential_company(self, data: Any, result: Dict) -> None:
        """Process a potential company object from JSON data"""
        if not isinstance(data, dict):
            return

        # Check if this looks like a company
        name_field = next((data[k] for k in ['name', 'company_name', 'title'] if k in data and isinstance(data[k], str)), None)

        if name_field:
            company = {
                "id": data.get('id', f"json_company_{len(result.get('companies', []))+1}"),
                "name": name_field,
                "type": data.get('type', data.get('company_type', '')),
                "url": data.get('url', data.get('company_url', '')),
                "credits": []
            }

            # Look for credits/people
            if 'credits' in data and isinstance(data['credits'], list):
                for credit in data['credits']:
                    self._process_credit(credit, company)
            elif 'people' in data and isinstance(data['people'], list):
                for person in data['people']:
                    self._process_credit(person, company)
            elif 'staff' in data and isinstance(data['staff'], list):
                for staff in data['staff']:
                    self._process_credit(staff, company)

            # Only add if we have some credits
            if company['credits']:
                if 'companies' not in result:
                    result['companies'] = []
                result['companies'].append(company)

    def _process_credits_array(self, credits: List, result: Dict) -> None:
        """Process an array of credits"""
        # Group by company if possible
        company_groups = {}

        for credit in credits:
            if not isinstance(credit, dict):
                continue

            company_name = credit.get('company', credit.get('agency', 'Unknown'))
            if company_name not in company_groups:
                company_groups[company_name] = {
                    "id": f"json_company_{len(company_groups)+1}",
                    "name": company_name,
                    "type": credit.get('company_type', ''),
                    "url": credit.get('company_url', ''),
                    "credits": []
                }

            self._process_credit(credit, company_groups[company_name])

        # Add all company groups to result
        if company_groups:
            if 'companies' not in result:
                result['companies'] = []

            for company in company_groups.values():
                if company['credits']:
                    result['companies'].append(company)

    def _process_credit(self, credit: Any, company: Dict) -> None:
        """Process a credit/person object and add to company"""
        if not isinstance(credit, dict):
            return

        person_name = credit.get('name', credit.get('person_name', credit.get('person', {}).get('name', '')))
        if not person_name:
            return

        role_name = credit.get('role', credit.get('title', credit.get('position', '')))

        person = {
            "id": credit.get('id', f"{company['id']}_person_{len(company['credits'])+1}"),
            "name": person_name,
            "url": credit.get('url', credit.get('person_url', ''))
        }

        company['credits'].append({
            "person": person,
            "role": role_name
        })

    def extract_with_ai_analysis(self, html: str, url: str) -> Dict:
        """Use AI to analyze the HTML and extract data using the Azure OpenAI endpoint only"""
        logger.info("Attempting extraction with AI analysis")
        # Create the prompt for AI analysis
        domain = self.extract_domain(url)
        prompt = self._create_extraction_prompt(domain, html)

        # Use direct API call to Azure OpenAI via requests
        try:
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key
            }

            payload = {
                "messages": [
                    {"role": "system", "content": "You are an expert web scraper assistant."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 4000,
                "temperature": 0.2
            }

            # Call the Azure OpenAI endpoint directly
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )
            if response.status_code != 200:
                raise ValueError(f"OpenAI API error: {response.status_code} - {response.text}")
            response_data = response.json()
            ai_response = response_data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            raise ValueError(f"AI analysis failed: {e}")

        # Save the raw AI response
        ai_response_path = os.path.join(self.session_dir, f"ai_response_{domain}.txt")
        with open(ai_response_path, "w", encoding="utf-8") as f:
            f.write(ai_response)
        logger.debug(f"AI response saved to {ai_response_path}")

        # Parse the AI response
        ai_data = self._parse_ai_response(ai_response)

        # Update result with AI-extracted data
        result = {}
        if 'data' in ai_data:
            for key, value in ai_data['data'].items():
                if key == 'companies' and isinstance(value, list):
                    result['companies'] = value
                else:
                    result[key] = value

        # Store patterns for learning
        if 'patterns' in ai_data:
            if "meta" not in result:
                result["meta"] = {}
            result['meta']['patterns'] = ai_data['patterns']

        # If we didn't get companies, this method failed
        if not result.get('companies'):
            raise ValueError("AI analysis did not yield company data")

        logger.info(f"Successfully extracted data with AI: {len(result.get('companies', []))} companies")
        return result

    def _create_extraction_prompt(self, domain: str, html: str) -> str:
        """Create a prompt for the AI to extract data"""
        return f"""
I need your help extracting structured data from this HTML from {domain}.

I specifically need to extract:
1. Title or name of the creative project
2. Companies involved in the project (production companies, agencies, studios, etc.)
3. Credits (the people who worked on the project and their roles)
4. Any media links (videos, images)

The HTML might contain embedded JSON data with keys like "lbb_credits" or "old_credits" that hold structured information.

Please analyze this HTML and extract the data in the following JSON format:

```json
{{
  "data": {{
    "title": "The extracted title",
    "description": "The extracted description if available",
    "companies": [
      {{
        "name": "Company name",
        "type": "Company type if available",
        "credits": [
          {{
            "person": {{
              "name": "Person name"
            }},
            "role": "Person's role"
          }}
        ]
      }}
    ],
    "media": [
      {{
        "type": "video/image",
        "url": "URL of media"
      }}
    ]
  }},
  "patterns": {{
    "title": {{
      "type": "regex",
      "pattern": "The regex pattern to extract the title"
    }},
    "companies": {{
      "type": "regex/json_path",
      "pattern": "The pattern to extract companies"
    }}
  }}
}}

Here's the HTML:
{html}
If the HTML is truncated, focus on identifying patterns in the available content.
"""

    def _parse_ai_response(self, response: str) -> Dict:
        """Parse the AI response to extract structured data"""
        # Try to find JSON block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON from code block")

        # Try to parse the entire response as JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Failed to parse entire response as JSON")

        # Try to extract JSON object with regex
        json_obj_match = re.search(r'({[\s\S]*})', response)
        if json_obj_match:
            try:
                return json.loads(json_obj_match.group(1))
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON object from response")

        # Create a minimal result if all parsing fails
        logger.warning("Creating fallback result from AI response")
        return {
            "data": {
                "title": "",
                "companies": []
            },
            "patterns": {}
        }

    def learn_from_ai_analysis(self, domain: str, patterns: Dict) -> None:
        """Learn patterns from AI analysis"""
        if domain not in self.knowledge_base["domains"]:
            self.knowledge_base["domains"][domain] = {
                "patterns": {},
                "extraction_methods": []
            }

        # Add new patterns
        for key, pattern_info in patterns.items():
            self.knowledge_base["domains"][domain]["patterns"][key] = pattern_info

        # Save knowledge base
        self.save_knowledge_base()
        logger.info(f"Learned {len(patterns)} new patterns for domain: {domain}")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous AI-powered web scraper")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model to use")
    parser.add_argument("--retries", type=int, default=20, help="Maximum number of retries")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    # Initialize scraper
    scraper = AutonomousScraper(
        api_key=args.api_key, 
        model=args.model, 
        debug=args.debug,
        max_retries=args.retries
    )

    # Define success criteria
    success_criteria = {
        "min_companies": 1,
        "min_credits": 3
    }

    print(f"Starting autonomous scraping of {args.url}")
    print(f"Will attempt up to {args.retries} times until success")
    print(f"Results will be saved to the session directory: {scraper.session_dir}")

    result = scraper.scrape_until_success(args.url, success_criteria)

    # Save final result
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(scraper.session_dir, "final_result.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nScraping completed!\nFinal result saved to: {output_path}")

    # Print summary
    if "error" in result:
        print(f"\nError: {result['error']}")
    else:
        print(f"\nTitle: {result.get('title', '')}")
        companies = result.get('companies', [])
        total_credits = sum(len(company.get('credits', [])) for company in companies)
        print(f"Companies: {len(companies)}")
        print(f"Total credits: {total_credits}")
        print(f"Extraction method: {result.get('meta', {}).get('extraction_method', 'unknown')}")
