"""
Enhanced headless browser fetch module with JSON extraction capabilities
"""

import logging
import re
import json
import time
from typing import Optional, List, Dict, Tuple
import demjson3  # For more forgiving JSON parsing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("headless_fetcher")

# Try to import Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    HAS_SELENIUM = True
    logger.info("Using Selenium for headless browsing")
except ImportError:
    HAS_SELENIUM = False
    logger.error("Selenium is not installed. Headless fetching will not work.")

def fetch_dynamic_page(url: str, wait_selector: Optional[str] = None, 
                      click_selectors: Optional[List[str]] = None,
                      timeout: int = 30, debug: bool = False) -> str:
    """
    Fetch a page with enhanced JSON extraction, falling back to browser interaction
    
    Args:
        url: URL to fetch
        wait_selector: Optional CSS selector to wait for before considering page loaded
        click_selectors: Optional list of CSS selectors to click after page load
        timeout: Maximum seconds to wait for page load or selectors
        debug: Whether to enable debug output and save screenshots
        
    Returns:
        String containing the fully rendered HTML
    """
    if debug:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"🌐 Enhanced fetching of page: {url}")
    
    if not HAS_SELENIUM:
        import requests
        logger.warning("Selenium not available, using basic requests")
        response = requests.get(url)
        return response.text
    
    # Set up Selenium options
    options = webdriver.ChromeOptions()
    if not debug:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Navigate to the URL
        logger.info(f"Navigating to {url}")
        driver.get(url)
        
        # Wait for page to fully load
        if wait_selector:
            try:
                logger.info(f"Waiting for selector: {wait_selector}")
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for {wait_selector}, continuing anyway")
        
        # Default wait - let page load completely
        logger.info("Waiting for page load complete")
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        time.sleep(3)  # Additional wait for any JS to run
        
        # Get the initial HTML
        html = driver.page_source
        
        # First, attempt to extract credits from JSON in page source
        json_data = extract_json_data(html)
        
        # If we found credits in the JSON data, we can skip interaction
        if json_data and 'credits_found' in json_data and json_data['credits_found']:
            logger.info("✅ Successfully extracted credits from embedded JSON")
            # No need to click tabs, but we might want to enhance the HTML with our findings
            enhanced_html = inject_extracted_credits(html, json_data)
            return enhanced_html
        
        # If we didn't find credits in JSON, try clicking tabs
        logger.info("No credits found in JSON, attempting UI interaction")
        
        # Take screenshot if debugging
        if debug:
            driver.save_screenshot("before_interactions.png")
            logger.debug(f"Screenshot saved: before_interactions.png")
        
        # Scan page for LBB credits tabs
        tab_xpath_patterns = [
            "//a[contains(text(), 'Credit')]",
            "//button[contains(text(), 'Credit')]",
            "//span[contains(text(), 'Credit')]",
            "//div[contains(@class, 'tab')][contains(text(), 'Credit')]",
            "//li[contains(text(), 'Credit')]"
        ]
        
        clicked_something = False
        for xpath in tab_xpath_patterns:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                if elements:
                    logger.info(f"Found {len(elements)} elements matching {xpath}")
                    for element in elements:
                        try:
                            logger.info(f"Clicking element: {element.text}")
                            driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            driver.execute_script("arguments[0].click();", element)
                            clicked_something = True
                            time.sleep(2)  # Wait for any content to load
                        except Exception as e:
                            logger.warning(f"Failed to click element: {e}")
            except Exception as e:
                logger.warning(f"Error with XPath {xpath}: {e}")
        
        # If still no luck, try the provided click selectors
        if not clicked_something and click_selectors:
            for selector in click_selectors:
                try:
                    logger.info(f"Attempting to click: {selector}")
                    
                    # Special handling for :contains pseudo selector
                    if ":contains" in selector:
                        text = selector.split(":contains('")[1].split("')")[0]
                        elements = driver.find_elements(By.XPATH, f"//*[contains(text(),'{text}')]")
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    logger.info(f"Found {len(elements)} elements matching {selector}")
                    
                    for element in elements:
                        try:
                            logger.info(f"Clicking element: {selector}")
                            driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            driver.execute_script("arguments[0].click();", element)
                            time.sleep(1)  # Wait for any animations/transitions
                        except Exception as e:
                            logger.warning(f"Couldn't click element {selector}: {e}")
                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
        
        # Wait for any content changes after clicks
        time.sleep(3)
        
        # Take another screenshot if debugging
        if debug:
            driver.save_screenshot("after_interactions.png")
            logger.debug(f"Screenshot saved: after_interactions.png")
        
        # Get the final HTML
        html = driver.page_source
        logger.info(f"Fetched HTML content (length: {len(html)})")
        
        # Save HTML to a local file for inspection
        if debug:
            with open('fetched_page.html', 'w', encoding='utf-8') as f:
                f.write(html)
            logger.debug("Saved HTML to fetched_page.html")
        
        return html
        
    except Exception as e:
        logger.error(f"Error fetching with Selenium: {str(e)}")
        return ""
    finally:
        driver.quit()

def extract_json_data(html: str) -> Dict:
    """
    Extract credits data from embedded JSON in the page HTML
    
    Args:
        html: HTML content of the page
        
    Returns:
        Dictionary with extracted credits data and flags
    """
    result = {
        'credits_found': False,
        'credits_data': None,
        'old_credits': None
    }
    
    # Try to extract lbb_credits
    credits_match = re.search(r'"lbb_credits":"((?:\\.|[^"\\])*)"', html)
    if credits_match:
        credits_str = credits_match.group(1)
        if credits_str:
            # Unescape the string
            credits_str = credits_str.replace('\\"', '"').replace('\\\\', '\\').replace('\\/', '/')
            try:
                credits_str = credits_str.encode('utf-8').decode('unicode_escape')
            except Exception as e:
                logger.debug(f"Unicode escape decoding failed: {e}")
            
            try:
                credits_data = json.loads(credits_str)
                result['credits_data'] = credits_data
                result['credits_found'] = True
                logger.info("Successfully extracted lbb_credits JSON")
            except json.JSONDecodeError:
                try:
                    # Try with demjson for more forgiving parsing
                    credits_data = demjson3.decode(credits_str)
                    result['credits_data'] = credits_data
                    result['credits_found'] = True
                    logger.info("Successfully extracted lbb_credits JSON using demjson")
                except Exception as e:
                    logger.error(f"Failed to parse lbb_credits JSON: {e}")
    
    # Also check for old_credits
    old_credits_match = re.search(r'"old_credits":"([^"]*)"', html)
    if old_credits_match:
        old_credits = old_credits_match.group(1)
        if old_credits:
            result['old_credits'] = old_credits.replace('\\n', '\n')
            result['credits_found'] = True
            logger.info("Successfully extracted old_credits")
    
    # Extract video information
    notube_match = re.search(r'"notube_id":"([^"]+)"', html)
    if notube_match:
        notube_id = notube_match.group(1)
        result['video_url'] = f"https://notube.lbbonline.com/v/{notube_id}"
        logger.debug(f"Extracted video URL: {result['video_url']}")
    
    # Extract image information
    img_match = re.search(r'"image":"([^"]+)"', html)
    if img_match:
        image_path = img_match.group(1)
        result['image_url'] = f"https://d3q27bh1u24u2o.cloudfront.net/{image_path}"
        logger.debug(f"Extracted image URL: {result['image_url']}")
    
    return result

def inject_extracted_credits(html: str, json_data: Dict) -> str:
    """
    Inject extracted credits data into the HTML to make it visible to the scraper
    
    Args:
        html: Original HTML
        json_data: Extracted credits data
        
    Returns:
        Enhanced HTML with credits data
    """
    # Find where to inject our content (before closing body tag)
    if '</body>' not in html:
        # If no closing body tag, just append to the end
        return html + '<div id="injected-credits" style="display:none;">' + json.dumps(json_data) + '</div>'
    
    # Inject before closing body tag
    return html.replace('</body>', '<div id="injected-credits" style="display:none;">' + json.dumps(json_data) + '</div></body>')