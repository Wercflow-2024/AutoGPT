"""
Testing utilities for scrapy components.
Provides functions for testing scraper functionality.
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, List, Any, Optional, Union

from backend.scrapy.utils.config import CONFIG

# Configure logging
logger = logging.getLogger("scrapy.testing")

def generate_test_id(url: str) -> str:
    """Generate a unique test ID from a URL"""
    domain = urlparse(url).netloc.replace("www.", "")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{domain}_{url_hash}_{timestamp}"

def save_test_result(data: Dict, url: str, output_dir: Optional[str] = None) -> str:
    """
    Save test result to a JSON file
    
    Args:
        data: Data to save
        url: URL of the test
        output_dir: Directory to save to (defaults to CONFIG["RESULTS_DIR"])
        
    Returns:
        Path to the saved file
    """
    if output_dir is None:
        output_dir = CONFIG["RESULTS_DIR"]
    
    os.makedirs(output_dir, exist_ok=True)
    
    test_id = generate_test_id(url)
    filename = f"{test_id}.json"
    path = os.path.join(output_dir, filename)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved test result to {path}")
    return path

def save_html_snapshot(html: str, url: str, output_dir: Optional[str] = None) -> str:
    """
    Save HTML snapshot to a file
    
    Args:
        html: HTML content
        url: URL of the page
        output_dir: Directory to save to (defaults to CONFIG["SNAPSHOT_DIR"])
        
    Returns:
        Path to the saved file
    """
    if output_dir is None:
        output_dir = CONFIG["SNAPSHOT_DIR"]
    
    os.makedirs(output_dir, exist_ok=True)
    
    domain = urlparse(url).netloc.replace("www.", "")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    filename = f"{domain}__{url_hash}.html"
    path = os.path.join(output_dir, filename)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"Saved HTML snapshot to {path}")
    return path

def compare_extraction_results(result1: Dict, result2: Dict) -> Dict[str, Any]:
    """
    Compare two extraction results and return the differences
    
    Args:
        result1: First extraction result
        result2: Second extraction result
        
    Returns:
        Dictionary with comparison metrics
    """
    def count_credits(result):
        companies = result.get("companies", [])
        total_companies = len(companies)
        total_credits = sum(len(company.get("credits", [])) for company in companies)
        return total_companies, total_credits
    
    companies1, credits1 = count_credits(result1)
    companies2, credits2 = count_credits(result2)
    
    metrics = {
        "title_match": result1.get("title") == result2.get("title"),
        "companies_count_1": companies1,
        "companies_count_2": companies2,
        "credits_count_1": credits1,
        "credits_count_2": credits2,
        "companies_diff": companies2 - companies1,
        "credits_diff": credits2 - credits1,
        "has_video_1": bool(result1.get("video_links")),
        "has_video_2": bool(result2.get("video_links")),
        "has_image_1": bool(result1.get("poster_image")),
        "has_image_2": bool(result2.get("poster_image"))
    }
    
    return metrics

def load_test_results(test_id: Optional[str] = None, output_dir: Optional[str] = None) -> List[Dict]:
    """
    Load test results from JSON files
    
    Args:
        test_id: Test ID to filter by (optional)
        output_dir: Directory to load from (defaults to CONFIG["RESULTS_DIR"])
        
    Returns:
        List of test result dictionaries
    """
    if output_dir is None:
        output_dir = CONFIG["RESULTS_DIR"]
    
    results = []
    
    if not os.path.exists(output_dir):
        logger.warning(f"Results directory {output_dir} does not exist")
        return results
    
    for filename in os.listdir(output_dir):
        if not filename.endswith(".json"):
            continue
        
        if test_id and test_id not in filename:
            continue
        
        path = os.path.join(output_dir, filename)
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["_filename"] = filename
                results.append(data)
        except Exception as e:
            logger.error(f"Failed to load test result {path}: {e}")
    
    return results

def evaluate_scraping_performance(results: List[Dict]) -> Dict[str, Any]:
    """
    Evaluate scraping performance metrics across multiple results
    
    Args:
        results: List of test result dictionaries
        
    Returns:
        Dictionary with performance metrics
    """
    if not results:
        return {"success_rate": 0, "total_tests": 0}
    
    total = len(results)
    success = sum(1 for r in results if r.get("title") and r.get("companies"))
    
    avg_companies = sum(len(r.get("companies", [])) for r in results) / total
    
    total_credits = 0
    total_companies = 0
    
    for result in results:
        companies = result.get("companies", [])
        total_companies += len(companies)
        for company in companies:
            total_credits += len(company.get("credits", []))
    
    avg_credits_per_company = total_credits / total_companies if total_companies else 0
    
    return {
        "total_tests": total,
        "success_rate": success / total,
        "avg_companies_per_project": avg_companies,
        "avg_credits_per_company": avg_credits_per_company,
        "total_companies": total_companies,
        "total_credits": total_credits
    }

if __name__ == "__main__":
    # Test functionality
    test_result = {
        "title": "Test Project",
        "companies": [
            {
                "name": "Company 1",
                "credits": [{"person": {"name": "Person 1"}, "role": "Role 1"}]
            }
        ]
    }
    
    save_test_result(test_result, "https://example.com/test")
    
    html = "<html><body><h1>Test</h1></body></html>"
    save_html_snapshot(html, "https://example.com/test")
    
    results = load_test_results()
    print(f"Loaded {len(results)} test results")
    
    if results:
        metrics = evaluate_scraping_performance(results)
        print(f"Success rate: {metrics['success_rate']:.2%}")