"""
Headless browser fetch module for JavaScript-rendered content
Uses Playwright or Selenium to interact with dynamic websites
"""

import logging
import os
import time
from typing import Optional, List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("headless_fetcher")

# Try to import Playwright (preferred) or fall back to Selenium
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
    logger.info("Using Playwright for headless browsing")
except ImportError:
    HAS_PLAYWRIGHT = False
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        logger.info("Using Selenium for headless browsing")
    except ImportError:
        logger.error("Neither Playwright nor Selenium is installed. Headless fetching will not work.")

def fetch_dynamic_page(url: str, wait_selector: Optional[str] = None, 
                       click_selectors: Optional[List[str]] = None,
                       timeout: int = 30, debug: bool = False) -> str:
    """
    Fetch a page using a headless browser, with support for waiting and clicking
    
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
    
    logger.info(f"🌐 Fetching dynamic page: {url}")
    
    # Default click selectors for LBB if none provided
    if url and "lbbonline.com" in url and not click_selectors:
        click_selectors = [
            ".tab-selector", 
            ".credits-tab",
            "button:contains('Credits')",
            "button:contains('View All')"
        ]
        logger.info(f"Using default LBB click selectors: {click_selectors}")
    
    if HAS_PLAYWRIGHT:
        return _fetch_with_playwright(url, wait_selector, click_selectors, timeout, debug)
    else:
        return _fetch_with_selenium(url, wait_selector, click_selectors, timeout, debug)

def _fetch_with_playwright(url, wait_selector, click_selectors, timeout, debug):
    """Fetch page using Playwright"""
    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not debug)
        page = browser.new_page()
        
        try:
            # Navigate to the URL
            logger.info(f"Navigating to {url}")
            page.goto(url, timeout=timeout * 1000)
            
            # Wait for selector if specified
            if wait_selector:
                logger.info(f"Waiting for selector: {wait_selector}")
                page.wait_for_selector(wait_selector, timeout=timeout * 1000)
            else:
                # Default wait for page load
                page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            
            # Take screenshot if debugging
            if debug:
                page.screenshot(path="before_interactions.png")
                logger.debug(f"Screenshot saved: before_interactions.png")
            
            # Click on selectors if specified
            if click_selectors:
                for selector in click_selectors:
                    try:
                        logger.info(f"Attempting to click: {selector}")
                        elements = page.query_selector_all(selector)
                        logger.info(f"Found {len(elements)} elements matching {selector}")
                        
                        for element in elements:
                            try:
                                element.click()
                                logger.info(f"Clicked element: {selector}")
                                # Wait a moment for any animations/transitions
                                page.wait_for_timeout(1000)
                            except Exception as e:
                                logger.warning(f"Couldn't click element {selector}: {e}")
                    except Exception as e:
                        logger.warning(f"Error with selector {selector}: {e}")
            
            # Wait for any content changes after clicks
            page.wait_for_timeout(2000)
            
            # Take another screenshot if debugging
            if debug:
                page.screenshot(path="after_interactions.png")
                logger.debug(f"Screenshot saved: after_interactions.png")
            
            # Get the final HTML
            html = page.content()
            logger.info(f"Fetched HTML content (length: {len(html)})")
            
        except Exception as e:
            logger.error(f"Error fetching with Playwright: {str(e)}")
        finally:
            browser.close()
    
    return html

def _fetch_with_selenium(url, wait_selector, click_selectors, timeout, debug):
    """Fetch page using Selenium"""
    html = ""
    
    # Set up Selenium options
    options = webdriver.ChromeOptions()
    if not debug:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Navigate to the URL
        logger.info(f"Navigating to {url}")
        driver.get(url)
        
        # Wait for selector if specified
        if wait_selector:
            logger.info(f"Waiting for selector: {wait_selector}")
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        else:
            # Default wait
            time.sleep(5)
        
        # Take screenshot if debugging
        if debug:
            driver.save_screenshot("before_interactions.png")
            logger.debug(f"Screenshot saved: before_interactions.png")
        
        # Click on selectors if specified
        if click_selectors:
            for selector in click_selectors:
                try:
                    logger.info(f"Attempting to click: {selector}")
                    
                    # Special handling for :contains pseudo selector (Selenium doesn't support it)
                    if ":contains" in selector:
                        text = selector.split(":contains('")[1].split("')")[0]
                        elements = driver.find_elements(By.XPATH, f"//*[contains(text(),'{text}')]")
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    logger.info(f"Found {len(elements)} elements matching {selector}")
                    
                    for element in elements:
                        try:
                            element.click()
                            logger.info(f"Clicked element: {selector}")
                            # Wait a moment for any animations/transitions
                            time.sleep(1)
                        except Exception as e:
                            logger.warning(f"Couldn't click element {selector}: {e}")
                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
        
        # Wait for any content changes after clicks
        time.sleep(2)
        
        # Take another screenshot if debugging
        if debug:
            driver.save_screenshot("after_interactions.png")
            logger.debug(f"Screenshot saved: after_interactions.png")
        
        # Get the final HTML
        html = driver.page_source
        logger.info(f"Fetched HTML content (length: {len(html)})")
        
    except Exception as e:
        logger.error(f"Error fetching with Selenium: {str(e)}")
    finally:
        driver.quit()
    
    return html