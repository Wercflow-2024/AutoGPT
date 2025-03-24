"""
AI enhancement module for web scraping using Azure OpenAI API.
Improves extraction quality by suggesting selectors and normalizing data.
"""

import os
import json
import logging
import re
import requests
from typing import Dict, List, Optional, Any
import urllib.parse
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ai_enhancer")

def extract_json_from_response(text: str) -> dict:
    """Extract valid JSON from an OpenAI response string with improved debugging"""
    import re
    import json
    
    # Log the raw response for debugging
    logger.debug(f"Raw response from AI: {text[:500]}..." if len(text) > 500 else text)

    def clean_json_string(json_str):
        # Remove inline JS-style comments
        json_str = re.sub(r"//.*", "", json_str)
        # Replace single quotes with double quotes
        json_str = json_str.replace("'", '"')
        # Remove trailing commas
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
        return json_str

    # Try full response as-is
    try:
        return json.loads(clean_json_string(text))
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse full response: {str(e)}")

    # Try extracting from triple-backtick code block (common format in AI responses)
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if match:
        try:
            content = match.group(1).strip()
            logger.debug(f"Extracted content from code block: {content[:200]}...")
            return json.loads(clean_json_string(content))
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse code block content: {str(e)}")

    # Try to find any JSON-like structure with curly braces
    match = re.search(r"({[\s\S]*?})", text)
    if match:
        try:
            content = match.group(1).strip()
            logger.debug(f"Extracted content from braces: {content[:200]}...")
            return json.loads(clean_json_string(content))
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse braces content: {str(e)}")
    
    # If all else fails, create a basic structure
    logger.warning("Could not parse AI response as valid JSON. Creating a fallback structure.")
    
    # Try to extract individual selectors as a last resort
    selectors = {}
    selector_matches = re.finditer(r'"([^"]+)":\s*"([^"]+)"', text)
    for match in selector_matches:
        key, value = match.groups()
        if key and value:
            selectors[key] = value
    
    if selectors:
        logger.info(f"Extracted {len(selectors)} selectors using regex fallback")
        return {"selectors": selectors}
    
    # Force reasonable defaults if all extraction methods fail
    logger.error(f"All JSON extraction methods failed. Response was: {text[:300]}...")
    return {
        "selectors": {
            "companies": ".credit-entry, .company-block, .team-section", 
            "title": "h1, .title",
            "description": ".description, .summary, p.intro",
            "roles": ".role, .position, .job-title"
        },
        "extraction_failed": True
    }

class AzureOpenAIEnhancer:
    """
    Enhances scraping capabilities using Azure OpenAI APIs.
    Features:
    - AI-assisted element detection
    - Selector suggestion for failed extractions
    - HTML structure analysis
    - Role and credit normalization
    """
    
    def __init__(self, model="gpt-4o-mini"):
        """Initialize the AI enhancer with Azure OpenAI credentials"""
        # API credentials from environment variables
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY1")
        
        # Select the right endpoint based on model
        if model == "gpt-4o":
            self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        elif model == "gpt-4o-mini":
            self.endpoint = os.getenv("AZURE_OPENAI_4OM_ENDPOINT")
        elif model == "o1-mini":
            self.endpoint = os.getenv("AZURE_OPENAI_O1_ENDPOINT")
        elif model == "o3-mini":
            self.endpoint = os.getenv("AZURE_OPENAI_O3_ENDPOINT")
        else:
            # Default to GPT-4o Mini
            self.endpoint = os.getenv("AZURE_OPENAI_4OM_ENDPOINT")
            
        self.model = model
        
        # Validate configuration
        if not self.api_key or not self.endpoint:
            logger.warning("⚠️ Azure OpenAI API key or endpoint not found. AI enhancement disabled.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"✅ AI enhancer initialized with model: {model}")
    
    def _validate_css_selector(self, selector: str) -> bool:
        """
        Validate a CSS selector for basic correctness
        
        Args:
            selector: CSS selector to validate
        
        Returns:
            Boolean indicating if the selector is valid
        """
        if not selector or not isinstance(selector, str):
            return False
        
        # Basic CSS selector validation rules
        try:
            # Check for basic syntax
            if not re.match(r'^[.#]?[a-zA-Z0-9\-_]+(?:\s*[.#][a-zA-Z0-9\-_]+)*(?:\s*>\s*[a-zA-Z0-9\-_]+)?$', selector):
                return False
            
            # Ensure no malicious content
            if any(char in selector for char in ['<', '>', '&', '"', "'"]):
                return False
            
            return True
        except Exception:
            return False

    def _generate_fallback_selectors(self, html_content: str, missing_elements: List[str]) -> Dict:
        """
        Generate fallback selectors using multiple heuristics
        
        Args:
            html_content: HTML to analyze
            missing_elements: List of missing elements to find selectors for
        
        Returns:
            Dictionary of potential selectors
        """
        soup = BeautifulSoup(html_content, "html.parser")
        fallback_selectors = {}
        
        # Common selector patterns for different elements
        selector_patterns = {
            "companies": [
                ".company", ".company-name", ".credit-company", 
                "[class*='company']", "[class*='brand']",
                "div.flex > span.font-bold", "section.credits > div"
            ],
            "credits": [
                ".credits", ".team", ".crew", ".collaborators",
                "div.flex.space-y-4", "section.people > div"
            ],
            "title": [
                "h1", ".title", ".page-title", "header h2", 
                "[class*='title']"
            ]
        }
        
        for element in missing_elements:
            # Try patterns for this specific element
            patterns = selector_patterns.get(element, [])
            
            for pattern in patterns:
                matches = soup.select(pattern)
                if matches:
                    fallback_selectors[element] = pattern
                    break
            
            # Fallback to generic selector if no specific pattern works
            if element not in fallback_selectors:
                fallback_selectors[element] = f".{element}"
        
        return {
            "selectors": fallback_selectors,
            "explanations": {k: "Automatically generated fallback selector" for k in fallback_selectors}
        }

    def suggest_selectors(self, html_snippet: str, missing_elements: List[str], site_url: str, previous_selectors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Enhanced method for suggesting selectors with multiple validation layers
        
        Args:
            html_snippet: The HTML content to analyze
            missing_elements: List of missing element types
            site_url: URL of the page being scraped
            previous_selectors: Optional dictionary of previously tried selectors
        
        Returns:
            Dictionary with suggested selectors and extraction code
        """
        if not self.enabled:
            logger.warning("⚠️ AI enhancement disabled. Returning placeholder suggestions.")
            return self._generate_placeholder_suggestions(missing_elements)
        
        # Limit HTML size to avoid token limits
        html_preview = html_snippet[:15000] + "..." if len(html_snippet) > 15000 else html_snippet
        
        # Create prompt for OpenAI
        prompt = self._create_selector_prompt(html_preview, missing_elements, site_url, previous_selectors)
        
        try:
            # Call Azure OpenAI API
            response = self._call_azure_openai(prompt)
            
            # Parse response with improved JSON extraction
            suggestions = self._parse_selector_response(response, missing_elements)
            
            # Validate and clean selectors
            final_suggestions = {}
            for element, selector in suggestions.get("selectors", {}).items():
                if self._validate_css_selector(selector):
                    final_suggestions[element] = selector
            
            # If no valid selectors, use fallback method
            if not final_suggestions:
                logger.warning("No valid AI-suggested selectors. Using fallback method.")
                fallback = self._generate_fallback_selectors(html_preview, missing_elements)
                final_suggestions = fallback.get("selectors", {})
            
            # Update suggestions with validated/fallback selectors
            suggestions["selectors"] = final_suggestions
            
            logger.info(f"✅ AI suggestions generated for: {', '.join(missing_elements)}")
            return suggestions
            
        except Exception as e:
            logger.error(f"❌ Error generating AI suggestions: {str(e)}")
            
            # Use fallback method on complete failure
            fallback = self._generate_fallback_selectors(html_preview, missing_elements)
            return fallback

    def _create_selector_prompt(self, html: str, missing_elements: List[str], site_url: str, previous_selectors: Optional[Dict[str, str]] = None) -> List[Dict]:
        """Create prompt for selector suggestions"""
        prior_context = ""
        if previous_selectors:
            formatted = json.dumps(previous_selectors, indent=2)
            prior_context = f"\nPreviously attempted selectors:\n```json\n{formatted}\n```"

        return [
            {
                "role": "system",
                "content": (
                    "You are an expert web scraper and front-end engineer specializing in extracting structured data from HTML. "
                    "Your primary task is to generate VALID CSS SELECTORS for specific page elements."
                )
            },
            {
                "role": "user",
                "content": f"""
I need to extract the following elements from this page: {', '.join(missing_elements)}
URL: {site_url}
{prior_context}

STRICT REQUIREMENTS FOR YOUR RESPONSE:
1. Provide ONLY a valid JSON object
2. Each missing element MUST have a VALID CSS SELECTOR
3. CSS Selectors must:
   - Start with a valid tag or class/ID selector
   - Use only standard CSS selector syntax
   - Be as precise as possible
   - Prefer combining multiple attributes/classes for accuracy

RESPONSE FORMAT (CRITICAL):
```json
{{
  "selectors": {{
    "element_name": "precise.css.selector",
    "another_element": "another.precise.selector"
  }},
  "explanations": {{
    "element_name": "Why this selector works",
    "another_element": "Explanation for this selector"
  }}
}}
```

IMPORTANT: Do NOT include descriptive text outside the JSON. The JSON MUST be the ONLY content in your response.

HTML to analyze:
```html
{html[:20000]}
```"""
            }
        ]

    def _call_azure_openai(self, prompt: List[Dict]) -> str:
        """Call Azure OpenAI API and return the response text"""
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }
        
        payload = {
            "messages": prompt,
            "temperature": 0.2,
            "max_tokens": 4000,
            "top_p": 0.9,
            "stream": False
        }
        
        response = requests.post(
            self.endpoint,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            logger.error(f"❌ OpenAI API error: {response.status_code} - {response.text}")
            raise Exception(f"OpenAI API error: {response.status_code}")
        
        response_data = response.json()
        raw_response = response_data["choices"][0]["message"]["content"]
        
        logger.debug(f"Raw AI response: {raw_response[:300]}...")
        return raw_response

    def normalize_roles(self, unknown_roles: List[Dict], known_roles: Dict, html_snippet: str = "") -> Dict[str, str]:
        """
        Normalize unknown roles using AI
        
        Args:
            unknown_roles: List of unknown roles with person IDs
            known_roles: Dictionary of known role mappings
            html_snippet: Optional HTML snippet for context
            
        Returns:
            Dictionary mapping person_id to normalized role
        """
        if not self.enabled or not unknown_roles:
            return {}
        
        # Create prompt for role normalization
        prompt = self._create_role_prompt(unknown_roles, known_roles, html_snippet)
        
        try:
            # Call Azure OpenAI API
            response = self._call_azure_openai(prompt)
            
            # Parse response
            normalized_roles = self._parse_role_response(response)
            return normalized_roles
            
        except Exception as e:
            logger.error(f"❌ Error normalizing roles: {str(e)}")
            return {}

    def _create_role_prompt(self, unknown_roles: List[Dict], known_roles: Dict, html_snippet: str) -> List[Dict]:
        """Create prompt for role normalization"""
        # Format the unknown roles
        unknown_roles_str = json.dumps(unknown_roles, indent=2)
        
        # Format a sample of known roles (max 20)
        known_roles_sample = {k: v for i, (k, v) in enumerate(known_roles.items()) if i < 20}
        known_roles_str = json.dumps(known_roles_sample, indent=2)
        
        html_context = f"\nHere's some HTML context:\n```html\n{html_snippet[:5000]}\n```" if html_snippet else ""
        
        return [
            {"role": "system", "content": "You are an expert in creative industry roles and job titles. Your task is to normalize inconsistent or missing role names to standard industry terms. You MUST return a valid JSON object with your response."},
            {"role": "user", "content": f"""
I need to normalize these unknown roles from a creative project/company database:
{unknown_roles_str}

For reference, here are some examples of known roles and their IDs:
{known_roles_str}
{html_context}

For each unknown role, determine the most likely standard job title based on the person's name, ID, and any context available.

Return ONLY a valid JSON object with person_id as keys and normalized role names as values:
{{
  "person_id1": "Normalized Role",
  "person_id2": "Normalized Role",
  ...
}}

If you can't determine a role, use "Contributor" as the default.
"""}
        ]

    def _parse_role_response(self, response: str) -> Dict[str, str]:
        """Parse the response for role normalization"""
        try:
            # Extract JSON from response
            normalized_roles = extract_json_from_response(response)
            
            # Ensure we have a dictionary of role mappings
            if not isinstance(normalized_roles, dict):
                logger.warning("Role normalization did not return a dictionary, creating empty one")
                return {}
                
            # Filter out any non-string values
            return {k: str(v) for k, v in normalized_roles.items() if v}
            
        except Exception as e:
            logger.error(f"❌ Error parsing role response: {str(e)}")
            return {}

    def analyze_html_structure(self, html: str, url: str) -> Dict[str, Any]:
        """
        Analyze HTML structure and suggest a complete scraping strategy
        
        Args:
            html: The HTML content to analyze
            url: URL of the page
            
        Returns:
            Dictionary with suggested scraping strategy
        """
        if not self.enabled:
            return {"strategy": "unknown", "selectors": {}}
        
        # Limit HTML size
        html_preview = html[:20000] + "..." if len(html) > 20000 else html
        
        # Create prompt
        prompt = self._create_structure_prompt(html_preview, url)
        
        try:
            # Call Azure OpenAI API
            response = self._call_azure_openai(prompt)
            
            # Parse response
            strategy = self._parse_structure_response(response)
            
            # Try to save the strategy if CONFIG is available
            try:
                from backend.scrapy.utils.config import CONFIG, get_next_version
                
                domain = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
                version = get_next_version(domain, CONFIG["STRATEGIES_DIR"], "v")
                strategy_path = os.path.join(CONFIG["STRATEGIES_DIR"], domain, f"{version}.json")
                
                try:
                    os.makedirs(os.path.dirname(strategy_path), exist_ok=True)
                    with open(strategy_path, "w") as f:
                        json.dump(strategy, f, indent=2)
                    logger.info(f"💾 Strategy saved to: {strategy_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to save strategy: {e}")
            except ImportError:
                logger.debug("Could not import CONFIG to save strategy")
            
            return strategy
            
        except Exception as e:
            logger.error(f"❌ Error analyzing HTML structure: {str(e)}")
            return {"strategy": "unknown", "selectors": {}}

    def _create_structure_prompt(self, html: str, url: str) -> List[Dict]:
        """Create prompt for HTML structure analysis"""
        return [
            {"role": "system", "content": "You are an expert web scraper who can analyze HTML structure and create accurate extraction strategies. You can identify patterns in HTML and suggest robust CSS selectors for extracting structured data. You MUST return a valid JSON object with your response."},
            {"role": "user", "content": f"""
I need to create a scraping strategy for this page: {url}

Please analyze the HTML structure and create a complete scraping strategy with CSS selectors for:
1. Title
2. Description
3. Project information (client, date, location, format)
4. Credit blocks (companies, people, roles)
5. Media (videos, images)

Return ONLY a valid JSON object with this structure, and nothing else before or after:
{{
  "strategy": "domain_name_v1",
  "selectors": {{
    "title": "h1",
    "description": ".description-selector",
    "project_info": ".info-selector",
    "credit_blocks": ".credits-selector",
    "company_name": ".company-selector",
    "company_type": ".company-type-selector",
    "role_blocks": ".role-selector",
    "role_name": ".role-name-selector",
    "person": ".person-selector",
    "person_name": ".person-name-selector"
  }},
  "structure_notes": "Any special notes about the page structure..."
}}

Here's the HTML:
```html
{html}
```
"""}
        ]

    def _parse_structure_response(self, response: str) -> Dict:
        """Parse the response for HTML structure analysis"""
        try:
            strategy = extract_json_from_response(response)
            
            # Ensure we have the basic strategy structure
            if not isinstance(strategy, dict):
                logger.warning("Structure analysis did not return a dictionary")
                strategy = {}
                
            if "strategy" not in strategy:
                strategy["strategy"] = "unknown"
                
            if "selectors" not in strategy:
                strategy["selectors"] = {}
                
            # Validate all selectors are strings
            for key, value in strategy.get("selectors", {}).items():
                if not isinstance(value, str):
                    logger.warning(f"Selector '{key}' is not a string, converting")
                    strategy["selectors"][key] = str(value)
            
            return strategy
            
        except Exception as e:
            logger.error(f"❌ Error parsing structure response: {str(e)}")
            logger.error(f"Raw response that failed to parse:\n{response[:500]}...")
            return {
                "strategy": "unknown",
                "selectors": {},
                "raw_response": response[:1000] if len(response) > 1000 else response
            }

    def _generate_placeholder_suggestions(self, missing_elements: List[str]) -> Dict:
        """Generate placeholder suggestions when AI is disabled or errors occur"""
        selectors = {element: self._get_placeholder_selector(element) for element in missing_elements}
        
        return {
            "selectors": selectors,
            "explanations": {element: "Placeholder suggestion (AI unavailable)" for element in missing_elements},
            "alternatives": {element: [] for element in missing_elements},
            "ai_error": True
        }

    def _get_placeholder_selector(self, element: str) -> str:
        """Get a placeholder selector for a specific element type"""
        placeholders = {
            "title": "h1, .title, header h2",
            "description": ".description, .content p:first-of-type, article p",
            "project_info": ".info, .metadata, .details",
            "credit_blocks": ".credits, .team, .crew",
            "companies": ".company, .partner, .credit-company, .credit-entry",
            "company_credits": ".team-member, .credit-person, .member",
            "company_name": ".company-name, .partner-name, .credit-company-name",
            "company_type": ".company-type, .partner-type",
            "role_blocks": ".role, .job, .position",
            "role_name": ".role-name, .job-title, .position-name",
            "person": ".person, .team-member, .credit-person",
            "person_name": ".person-name, .member-name, a",
            "media": "iframe[src*=video], .main-image, .hero img",
            "video_links": "iframe[src*=youtube], iframe[src*=vimeo], video"
        }
        return placeholders.get(element, f".{element}")

# Example usage:
if __name__ == "__main__":
    # Test the AI enhancer
    enhancer = AzureOpenAIEnhancer(model="gpt-4o-mini")
    
    # Test if properly configured
    print(f"AI enhancer enabled: {enhancer.enabled}")
    
    if enhancer.enabled:
        # Test a simple HTML snippet
        html = """
        <div class='project'>
          <h1>Test Project</h1>
          <div class='credit-entry'>
            <div class='company-name'><a href="/company/123">Test Company</a></div>
            <div class='company-type'>Production</div>
            <div class='roles'>
              <div class='role'>
                <div class='role-name'>Director</div>
                <div class='person'><a href="/person/456">Jane Smith</a></div>
              </div>
            </div>
          </div>
        </div>
        """
        missing = ["companies"]
        suggestions = enhancer.suggest_selectors(html, missing, "https://example.com")
        print(json.dumps(suggestions, indent=2))