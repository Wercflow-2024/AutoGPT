"""
AI enhancement module for web scraping using Azure OpenAI API.
Improves extraction quality by suggesting selectors and normalizing data.
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Any
import requests
from dotenv import load_dotenv

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
    """Extract valid JSON from an OpenAI response string"""
    import re

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
    except json.JSONDecodeError:
        pass

    # Try extracting from triple-backtick block
    match = re.search(r"```(?:json)?\s*({.*?})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(clean_json_string(match.group(1)))
        except json.JSONDecodeError:
            pass

    # Try first {...} block
    match = re.search(r"({.*})", text, re.DOTALL)
    if match:
        try:
            return json.loads(clean_json_string(match.group(1)))
        except json.JSONDecodeError:
            pass

    raise ValueError("❌ Could not parse AI response as valid JSON")

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
    
    def suggest_selectors(self, html_snippet: str, missing_elements: List[str], site_url: str, previous_selectors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Analyze HTML and suggest CSS selectors for missing elements
        
        Args:
            html_snippet: The HTML content to analyze
            missing_elements: List of missing element types
            site_url: URL of the page being scraped
            
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
            
            # Parse response
            suggestions = self._parse_selector_response(response, missing_elements)
            logger.info(f"✅ AI suggestions generated for: {', '.join(missing_elements)}")
            
            # Check if new selectors differ from previous selectors
            if previous_selectors is not None:
                prev = previous_selectors if isinstance(previous_selectors, dict) else {}
                new = suggestions.get("selectors", {})
                if new != prev:
                    logger.info("New selectors differ from previous selectors.")
                else:
                    logger.info("AI suggestions did not change from previous selectors.")
                    
            return suggestions
            
        except Exception as e:
            logger.error(f"❌ Error generating AI suggestions: {str(e)}")
            return self._generate_placeholder_suggestions(missing_elements)
    
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
            from backend.scrapy.utils.config import CONFIG, get_next_version
            import slugify
            
            domain = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
            version = get_next_version(domain, CONFIG["STRATEGIES_DIR"])
            strategy_path = os.path.join(CONFIG["STRATEGIES_DIR"], domain, f"{version}.json")
            
            try:
                os.makedirs(os.path.dirname(strategy_path), exist_ok=True)
                with open(strategy_path, "w") as f:
                    json.dump(strategy, f, indent=2)
                logger.info(f"💾 Strategy saved to: {strategy_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save strategy: {e}")
            
            return strategy
            
        except Exception as e:
            logger.error(f"❌ Error analyzing HTML structure: {str(e)}")
            return {"strategy": "unknown", "selectors": {}}
    
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
        logger.debug(f"Raw AI response: {response_data['choices'][0]['message']['content']}")
        return response_data["choices"][0]["message"]["content"]
    
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
                    "You are an expert web scraper and front-end engineer. "
                    "Your job is to find the best CSS selectors to extract elements from a webpage based on its raw HTML. "
                    "You are especially good at tracing elements based on visible text and structure."
                )
            },
            {
                "role": "user",
                "content": f"""
I’m scraping this page: {site_url}
I already have the HTML below. I'm trying to extract the following missing elements:
- {', '.join(missing_elements)}
{prior_context}

Please scan the HTML, and for each missing element:
1. Suggest a **precise CSS selector** that targets that data
2. Explain why that selector works
3. List any obvious patterns or fallback selectors

Only return a JSON object with this structure:
{{
  "selectors": {{
    "element_name": "css selector"
  }},
  "explanations": {{
    "element_name": "explanation"
  }},
  "alternatives": {{
    "element_name": ["alt1", "alt2"]
  }}
}}

Here’s the HTML:
```html
{html}
```"""
            }
        ]
    
    def _create_role_prompt(self, unknown_roles: List[Dict], known_roles: Dict, html_snippet: str) -> List[Dict]:
        """Create prompt for role normalization"""
        # Format the unknown roles
        unknown_roles_str = json.dumps(unknown_roles, indent=2)
        
        # Format a sample of known roles (max 20)
        known_roles_sample = {k: v for i, (k, v) in enumerate(known_roles.items()) if i < 20}
        known_roles_str = json.dumps(known_roles_sample, indent=2)
        
        html_context = f"\nHere's some HTML context:\n```html\n{html_snippet[:5000]}\n```" if html_snippet else ""
        
        return [
            {"role": "system", "content": "You are an expert in creative industry roles and job titles. Your task is to normalize inconsistent or missing role names to standard industry terms."},
            {"role": "user", "content": f"""
I need to normalize these unknown roles from a creative project/company database:
{unknown_roles_str}

For reference, here are some examples of known roles and their IDs:
{known_roles_str}
{html_context}

For each unknown role, determine the most likely standard job title based on the person's name, ID, and any context available.

Return your response as a JSON object with person_id as keys and normalized role names as values:
{{
  "person_id1": "Normalized Role",
  "person_id2": "Normalized Role",
  ...
}}

If you can't determine a role, use "Contributor" as the default.
"""}
        ]
    
    def _create_structure_prompt(self, html: str, url: str) -> List[Dict]:
        """Create prompt for HTML structure analysis"""
        return [
            {"role": "system", "content": "You are an expert web scraper who can analyze HTML structure and create accurate extraction strategies. You can identify patterns in HTML and suggest robust CSS selectors for extracting structured data."},
            {"role": "user", "content": f"""
I need to create a scraping strategy for this page: {url}

Please analyze the HTML structure and create a complete scraping strategy with CSS selectors for:
1. Title
2. Description
3. Project information (client, date, location, format)
4. Credit blocks (companies, people, roles)
5. Media (videos, images)

Return your response as a JSON object with this structure:
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
    
    def _parse_selector_response(self, response: str, missing_elements: List[str]) -> Dict:
        """Parse the response for selector suggestions"""
        try:
            # Extract JSON from response
            suggestions = extract_json_from_response(response)
            
            # Ensure we have the expected structure
            if "selectors" not in suggestions:
                suggestions["selectors"] = {}
            
            # Make sure we have entries for all missing elements
            for element in missing_elements:
                if element not in suggestions["selectors"]:
                    suggestions["selectors"][element] = ""
            
            return suggestions
            
        except Exception as e:
            logger.error(f"❌ Error parsing selector response: {str(e)}")
            return self._generate_placeholder_suggestions(missing_elements)
    
    def _parse_role_response(self, response: str) -> Dict[str, str]:
        """Parse the response for role normalization"""
        try:
            # Extract JSON from response
            normalized_roles = extract_json_from_response(response)
            return normalized_roles
            
        except Exception as e:
            logger.error(f"❌ Error parsing role response: {str(e)}")
            return {}
    
    def _parse_structure_response(self, response: str) -> Dict:
        """Parse the response for HTML structure analysis"""
        try:
            return extract_json_from_response(response)
        except Exception as e:
            logger.error(f"Raw response that failed to parse:\n{response}")
            return {
                "strategy": "unknown",
                "selectors": {},
                "raw_response": response
            }
    
    def _generate_placeholder_suggestions(self, missing_elements: List[str]) -> Dict:
        """Generate placeholder suggestions when AI is disabled"""
        suggestions = {
            "selectors": {},
            "explanations": {},
            "alternatives": {}
        }
        
        default_selectors = {
            "title": "h1, .title, header h2",
            "description": ".description, .content p:first-of-type, article p",
            "companies": ".company, .credit-company, .partner",
            "company_credits": ".team, .credit-person, .member",
            "roles": ".role, .job-title, .position",
            "media": "iframe[src*=video], .main-image, .hero img"
        }
        
        for element in missing_elements:
            suggestions["selectors"][element] = default_selectors.get(element, ".unknown")
            suggestions["explanations"][element] = "Placeholder suggestion (AI disabled)"
            suggestions["alternatives"][element] = [".alt1", ".alt2"]
        
        return suggestions


# Example usage:
if __name__ == "__main__":
    # Test the AI enhancer
    enhancer = AzureOpenAIEnhancer(model="gpt-4o-mini")
    
    # Test if properly configured
    print(f"AI enhancer enabled: {enhancer.enabled}")
    
    if enhancer.enabled:
        # Test a simple HTML snippet
        html = "<div class='project'><h1>Project Title</h1><p class='description'>Description here</p></div>"
        missing = ["companies", "roles"]
        suggestions = enhancer.suggest_selectors(html, missing, "https://example.com")
        print(json.dumps(suggestions, indent=2))