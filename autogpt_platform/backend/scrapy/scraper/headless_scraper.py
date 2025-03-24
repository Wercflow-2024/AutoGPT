# headless_fetcher.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def fetch_dynamic_page(url, wait_selector=".credits-container", timeout=10):
    """
    Launches a headless Chrome browser to load the given URL, waits for the
    dynamic element specified by wait_selector to appear, then returns the
    fully rendered HTML.
    
    Parameters:
        url (str): The URL to fetch.
        wait_selector (str): A CSS selector for an element that indicates
                             dynamic content has loaded. Default is ".credits-container".
        timeout (int): Maximum time in seconds to wait for the element. Default is 10.
        
    Returns:
        str: The rendered page source (HTML).
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Initialize the Chrome driver (ensure chromedriver is installed and in PATH)
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        # Wait until the target element is present
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
        )
    except Exception as e:
        print(f"Warning: dynamic content may not have loaded properly: {e}")
    finally:
        # Capture the page source after waiting
        rendered_html = driver.page_source
        driver.quit()
    
    return rendered_html

if __name__ == "__main__":
    # Example usage: fetch and print rendered HTML for a sample URL
    test_url = "https://lbbonline.com/work/132229"
    html = fetch_dynamic_page(test_url)
    print(html)