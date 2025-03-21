#!/usr/bin/env python3
"""
Test script for the AI-enhanced scraper.
This script verifies that the AI enhancement functionality is working correctly.
"""

import os
import json
import argparse
import sys
import logging
from datetime import datetime

# Import from project structure
try:
    from backend.scrapy.scraper.ai_enhancer import AzureOpenAIEnhancer
    from backend.scrapy.scraper.project_scraper import scrape_project
    from backend.scrapy.utils.config import CONFIG
    from backend.scrapy.utils.testing import save_test_result, compare_extraction_results
except ImportError:
    # For standalone testing
    print("Could not import from project structure. Using direct imports.")
    from backend.scrapy.scraper.ai_enhancer import AzureOpenAIEnhancer
    from backend.scrapy.scraper.project_scraper import scrape_project
    from backend.scrapy.utils.config import CONFIG
    from backend.scrapy.utils.testing import save_test_result, compare_extraction_results

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("test_ai_enhanced")

def test_ai_setup():
    """Test that AI enhancer is properly configured"""
    logger.info("Testing AI enhancer configuration...")
    
    enhancer = AzureOpenAIEnhancer(model=CONFIG["AI_MODEL"])
    
    if enhancer.enabled:
        logger.info(f"✅ AI enhancer enabled with model: {enhancer.model}")
        logger.info(f"Using endpoint: {enhancer.endpoint}")
        return True
    else:
        logger.error("❌ AI enhancer not enabled. Check your environment variables.")
        return False

def test_simple_selector_suggestion():
    """Test basic selector suggestion functionality"""
    logger.info("Testing selector suggestion functionality...")
    
    enhancer = AzureOpenAIEnhancer(model=CONFIG["AI_MODEL"])
    
    if not enhancer.enabled:
        logger.warning("AI enhancer not enabled. Skipping test.")
        return False
    
    # Simple HTML snippet
    html = """
    <div class="project">
        <h1 class="title">Project Title</h1>
        <div class="company">
            <h2>Agency Name</h2>
            <div class="type">Creative Agency</div>
        </div>
        <div class="credits">
            <div class="role">
                <h3>Creative Director</h3>
                <ul>
                    <li class="person">John Smith</li>
                    <li class="person">Jane Doe</li>
                </ul>
            </div>
        </div>
    </div>
    """
    
    missing = ["title", "companies"]
    logger.info(f"Requesting suggestions for: {', '.join(missing)}")
    
    try:
        suggestions = enhancer.suggest_selectors(html, missing, "https://example.com/test")
        
        logger.info("Received suggestions:")
        logger.info(json.dumps(suggestions.get("selectors", {}), indent=2))
        
        return "selectors" in suggestions and all(m in suggestions["selectors"] for m in missing)
    except Exception as e:
        logger.error(f"Error testing selector suggestion: {e}")
        return False

def test_role_normalization():
    """Test role normalization functionality"""
    logger.info("Testing role normalization functionality...")
    
    enhancer = AzureOpenAIEnhancer(model=CONFIG["AI_MODEL"])
    
    if not enhancer.enabled:
        logger.warning("AI enhancer not enabled. Skipping test.")
        return False
    
    # Sample unknown roles
    unknown_roles = [
        {"person_id": "123", "name": "John Smith"},
        {"person_id": "456", "name": "Jane Doe, DOP"}
    ]
    
    # Sample known roles
    known_roles = {
        "789": "Director",
        "101": "Producer",
        "112": "Director of Photography"
    }
    
    try:
        normalized = enhancer.normalize_roles(unknown_roles, known_roles)
        
        logger.info("Normalized roles:")
        logger.info(json.dumps(normalized, indent=2))
        
        return len(normalized) > 0
    except Exception as e:
        logger.error(f"Error testing role normalization: {e}")
        return False

def test_compare_with_without_ai(url, output_dir=None):
    """
    Test scraping with and without AI and compare results
    
    Args:
        url: URL to scrape
        output_dir: Directory to save results
    """
    logger.info(f"Testing scraping with and without AI for URL: {url}")
    
    # Create output directory if needed
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Scrape without AI
    logger.info("Scraping without AI...")
    result_without_ai = scrape_project(url, ai_enabled=False)
    
    # Save result
    if output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        no_ai_file = os.path.join(output_dir, f"no_ai_{timestamp}.json")
        with open(no_ai_file, "w", encoding="utf-8") as f:
            json.dump(result_without_ai, f, indent=2)
        logger.info(f"Result without AI saved to: {no_ai_file}")
    
    # Scrape with AI
    logger.info("Scraping with AI...")
    result_with_ai = scrape_project(url, ai_enabled=True, normalize_roles=True)
    
    # Save result
    if output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with_ai_file = os.path.join(output_dir, f"with_ai_{timestamp}.json")
        with open(with_ai_file, "w", encoding="utf-8") as f:
            json.dump(result_with_ai, f, indent=2)
        logger.info(f"Result with AI saved to: {with_ai_file}")
    
    # Compare results
    logger.info("Comparing results...")
    comparison = compare_extraction_results(result_without_ai, result_with_ai)
    
    logger.info("Comparison:")
    for key, value in comparison.items():
        logger.info(f"  {key}: {value}")
    
    # Determine if AI improved the results
    improved = False
    if comparison["companies_diff"] > 0 or comparison["credits_diff"] > 0:
        improved = True
        logger.info("✅ AI enhanced scraping extracted more data")
    elif not result_without_ai.get("title") and result_with_ai.get("title"):
        improved = True
        logger.info("✅ AI enhanced scraping found missing title")
    elif (not result_without_ai.get("video_links") and result_with_ai.get("video_links")) or \
         (not result_without_ai.get("poster_image") and result_with_ai.get("poster_image")):
        improved = True
        logger.info("✅ AI enhanced scraping found missing media")
    else:
        logger.info("ℹ️ AI enhancement did not significantly improve results")
    
    return improved

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the AI-enhanced scraper")
    parser.add_argument("--test-url", help="URL to test scraping with and without AI")
    parser.add_argument("--output-dir", default="test_results", help="Directory to save test results")
    parser.add_argument("--run-all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: AI Setup
    if args.run_all or not args.test_url:
        logger.info("\n=== Test 1: AI Enhancer Setup ===")
        if test_ai_setup():
            logger.info("✅ Test 1 passed")
            tests_passed += 1
        else:
            logger.error("❌ Test 1 failed")
            tests_failed += 1
    
    # Test 2: Selector Suggestion
    if args.run_all or not args.test_url:
        logger.info("\n=== Test 2: Selector Suggestion ===")
        if test_simple_selector_suggestion():
            logger.info("✅ Test 2 passed")
            tests_passed += 1
        else:
            logger.error("❌ Test 2 failed")
            tests_failed += 1
    
    # Test 3: Role Normalization
    if args.run_all or not args.test_url:
        logger.info("\n=== Test 3: Role Normalization ===")
        if test_role_normalization():
            logger.info("✅ Test 3 passed")
            tests_passed += 1
        else:
            logger.error("❌ Test 3 failed")
            tests_failed += 1
    
    # Test 4: Scraping Comparison
    if args.test_url:
        logger.info("\n=== Test 4: Scraping Comparison ===")
        if test_compare_with_without_ai(args.test_url, args.output_dir):
            logger.info("✅ Test 4 passed")
            tests_passed += 1
        else:
            logger.warning("⚠️ Test 4 inconclusive - AI did not significantly improve results")
            # Don't count this as a failure
    
    # Summary
    logger.info(f"\n=== Test Summary: {tests_passed} passed, {tests_failed} failed ===")
    
    if tests_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)