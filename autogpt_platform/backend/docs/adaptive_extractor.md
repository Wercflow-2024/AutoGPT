# How to Integrate the Adaptive Extractor

Follow these steps to fix the silent failures and integrate the new adaptive extractor into your existing system:

## 1. Create the Adaptive Extractor Module

1. Create a new file at `backend/scrapy/scraper/adaptive_extractor.py` and paste the full code from the "Fixed Adaptive Extractor Implementation" and "Fixed Adaptive Extractor Implementation (Continued)" files.

## 2. Update Your Project Scraper

1. In your `project_scraper.py` file, add this import at the top:

```python
from backend.scrapy.scraper.adaptive_extractor import extract_project_adaptive, scrape_project_adaptive
```

2. Update your `scrape_project` function to use the adaptive extractor by replacing the original function with:

```python
def scrape_project(url: str, fallback_mapping: Optional[Dict] = None, debug: bool = False, 
                  ai_enabled: bool = None, ai_model: Optional[str] = None,
                  normalize_roles: bool = False, strategy_file: Optional[str] = None,
                  strategy_name: Optional[str] = None) -> Dict:
    """
    Main function to scrape a project page.
    
    Args:
        url: URL of the project page
        fallback_mapping: Optional mapping for role/company normalization
        debug: Enable debug output
        ai_enabled: Override config setting for AI enhancement
        ai_model: Override config setting for AI model
        normalize_roles: Use AI to normalize unknown roles
        strategy_file: Path to a JSON file containing a custom strategy
        strategy_name: Name of a strategy (domain/version) to use
        
    Returns:
        Dictionary with project data
    """
    # Use the adaptive extractor by default
    return scrape_project_adaptive(
        url=url,
        fallback_mapping=fallback_mapping,
        debug=debug,
        ai_enabled=ai_enabled,
        ai_model=ai_model,
        normalize_roles=normalize_roles,
        strategy_file=strategy_file
    )
```

## 3. Ensure the Required Functions Exist

Make sure your `project_scraper.py` still has these functions defined, as they are referenced by the adaptive extractor:

- `fetch_html_and_snapshot`
- `suggest_fixes_via_openai`
- `normalize_roles_with_ai`
- `validate_scraped_data`

## 4. Fix Import Paths

The adaptive extractor needs to import from your project structure. It tries multiple import paths:

```python
try:
    from backend.scrapy.utils.config import CONFIG
    from backend.scrapy.scraper.project_scraper import (
        SNAPSHOT_DIR, fetch_html_and_snapshot, normalize_roles_with_ai, 
        suggest_fixes_via_openai, validate_scraped_data
    )
except ImportError:
    try:
        from autogpt_platform.backend.scrapy.utils.config import CONFIG
        # ...
```

Make sure the import paths match your actual project structure.

## 5. Test the Integration

1. Test with a known problematic LBB Online URL:

```bash
python -m backend.scrapy.scraper.project_scraper https://lbbonline.com/work/132158 --debug
```

2. Check if it correctly extracts companies and credits.

## Key Fixes in the Adaptive Extractor

1. **Better Error Handling**: Every method has robust try/except blocks to catch and log errors instead of failing silently.

2. **Debug Logging**: Comprehensive logging helps identify where extraction fails.

3. **Structure Detection Improvements**: Better detection of LBB Online's v2 design.

4. **Multiple Extraction Methods**: Cascading through different strategies if the primary one fails.

5. **Safe Fallbacks**: Always returns valid data structure even if extraction fails.

6. **LBB Online v2 Support**: Special handling for the 2025 redesign.

7. **Default Company Creation**: Creates a default company from client info if extraction fails.

8. **Aggressive Pattern Matching**: Uses regex to find role/person pairs in unstructured content.

## Example Usage with AI Enhancement

```python
from backend.scrapy.scraper.adaptive_extractor import scrape_project_adaptive

# Enable full adaptive extraction with AI enhancement
data = scrape_project_adaptive(
    url="https://lbbonline.com/work/132158",
    debug=True,
    ai_enabled=True,
    ai_model="gpt-4o-mini",
    normalize


## Example Usage with AI Enhancement (continued)

```python
from backend.scrapy.scraper.adaptive_extractor import scrape_project_adaptive

# Enable full adaptive extraction with AI enhancement
data = scrape_project_adaptive(
    url="https://lbbonline.com/work/132158",
    debug=True,
    ai_enabled=True,
    ai_model="gpt-4o-mini",
    normalize_roles=True
)

# Print extracted companies
for company in data.get("companies", []):
    print(f"Company: {company['name']} ({company['type']})")
    for credit in company.get("credits", []):
        print(f"  {credit['role']}: {credit['person']['name']}")
```

## Stand-alone Testing

You can also run the adaptive extractor directly from the command line for quick testing:

```bash
python -m backend.scrapy.scraper.adaptive_extractor https://lbbonline.com/work/132158 --debug --output test_output.json --ai
```

## Understanding Why the Original Code Failed Silently

The original code had several issues that contributed to silent failures:

1. **Unhandled Exceptions**: Many methods didn't catch exceptions, allowing them to propagate and crash the extraction process.

2. **Incomplete Structure Detection**: The code for detecting LBB Online's new design wasn't thorough enough.

3. **Bad Import Paths**: The module tried to import from specific paths that might not exist in your environment.

4. **Fragile Selectors**: The selectors for the v2 format of LBB Online weren't robust enough.

5. **Minimal Logging**: Without comprehensive logging, it was hard to see where failures occurred.

6. **No Fallback Mechanism**: The original code didn't gracefully handle missing data or extraction failures.

## Monitoring and Maintenance

1. **Log Analysis**: Regularly check `adaptive_extractor_debug.log` to identify patterns in extraction failures.

2. **Performance Metrics**: Track the success rate of extractions with different site types.

3. **Update Patterns**: When new site designs are encountered, add their patterns to the extractor.

4. **Periodic Testing**: Run tests against known difficult URLs to ensure extraction continues to work.

5. **AI Enhancement Monitoring**: Keep an eye on the AI suggestions and their success rate.

## Upgrading in the Future

As websites evolve, you may need to update the extractor:

1. **Add New Structure Types**: In the `_detect_structure` method, add detection for new site designs.

2. **Create New Extraction Methods**: Add methods like `_extract_credits_newsite`.

3. **Update Patterns**: Enhance the regex patterns in the `PATTERNS` dictionary.

4. **Improve Fallbacks**: Add more aggressive extraction techniques for difficult sites.

## Example Debug Output

When running with `--debug`, you should see detailed logs like:

```
2025-03-24 14:15:22 [INFO] Extracting data using structure type: lbbonline_v2
2025-03-24 14:15:22 [INFO] Using LBB Online v2 extractor
2025-03-24 14:15:22 [DEBUG] Found 4 credit blocks in LBB v2 format
2025-03-24 14:15:22 [DEBUG] LBB v2 extraction found 2 companies
2025-03-24 14:15:22 [DEBUG] Company 1: Agency Name (8 credits)
2025-03-24 14:15:22 [DEBUG] Company 2: Production Company (6 credits)
2025-03-24 14:15:23 [INFO] Completed adaptive extraction: found 2 companies
```

This level of detail helps identify exactly where any issues might occur.

## Additional Considerations

1. **Memory Usage**: The adaptive extractor might use more memory than the original due to multiple extraction attempts.

2. **Performance**: It may be slightly slower due to the additional extraction methods and validation.

3. **API Costs**: If using AI enhancement, be aware of API costs for Azure OpenAI calls.

4. **Data Quality**: The adaptive approach prioritizes getting some data over getting perfect data. You may want to add further validation if data quality is critical.

## Conclusion

By implementing the adaptive extractor, you'll be able to handle various website structures, including the challenging LBB Online 2025 design. The improved error handling and logging will make debugging easier, and the fallback mechanisms will ensure you get usable data even from difficult sites.

# Troubleshooting Guide for the Adaptive Extractor

This guide will help you diagnose and fix common issues with the adaptive extractor.

## Common Issues and Solutions

### 1. Empty Companies List

**Symptoms:** The extractor runs without errors but returns an empty companies list.

**Possible Causes and Solutions:**

- **Website Structure Changed:** The site may have implemented a new design.
  - Solution: Add debug logging and check the HTML structure.
  - Solution: Add a new extraction method for the new design.

- **Selectors Not Matching:** The selectors for the current site type aren't finding elements.
  - Solution: Update selectors in the appropriate extraction method.

- **JavaScript-Rendered Content:** The content might be rendered with JavaScript after the page loads.
  - Solution: Consider using a headless browser like Selenium or Playwright.

### 2. Import Errors

**Symptoms:** You get import errors when running the extractor.

**Possible Causes and Solutions:**

- **Incorrect Import Paths:** Your project structure might differ from the assumed structure.
  - Solution: Update the import paths in adaptive_extractor.py to match your project structure.

- **Missing Dependencies:** You might be missing required packages.
  - Solution: Install missing packages: `pip install beautifulsoup4 requests python-dotenv`.

### 3. Extraction Method Not Working

**Symptoms:** The extractor identifies the correct site type but fails to extract companies or credits.

**Possible Causes and Solutions:**

- **Misidentified Structure:** The site was incorrectly categorized.
  - Solution: Print the HTML and manually check the structure.
  - Solution: Update the `_detect_structure` method to be more accurate.

- **HTML Structure Changed:** The site's HTML structure might have changed.
  - Solution: Update the selectors for that site type.

### 4. Exception During Extraction

**Symptoms:** You see error logs from one of the extraction methods.

**Possible Causes and Solutions:**

- **Unexpected HTML Structure:** The HTML doesn't match the expected pattern.
  - Solution: Add more specific error handling in the problematic method.
  - Solution: Add a fallback extraction approach.

- **Network Errors:** Issues with fetching content.
  - Solution: Implement retries for network operations.
  - Solution: Add caching to reduce network dependencies.

### 5. AI Enhancement Fails

**Symptoms:** The AI enhancement step fails or doesn't improve extraction.

**Possible Causes and Solutions:**

- **Azure OpenAI API Issues:** Configuration or quota problems.
  - Solution: Check API key and endpoint.
  - Solution: Verify quota and limits.

- **AI Suggestions Not Helping:** The AI is suggesting ineffective selectors.
  - Solution: Improve the prompt in the AI enhancer.
  - Solution: Review and potentially manually override AI suggestions.

### 6. Debug Logging Not Showing

**Symptoms:** You enable debug but don't see detailed logs.

**Possible Causes and Solutions:**

- **Logger Configuration:** The logger might not be properly configured.
  - Solution: Add explicit logger configuration at the beginning of your script.
  ```python
  import logging
  logging.basicConfig(level=logging.DEBUG)
  logging.getLogger("adaptive_extractor").setLevel(logging.DEBUG)
  ```

- **Handler Issues:** Log handlers might not be processing debug messages.
  - Solution: Add a specific handler for debug messages.
  ```python
  handler = logging.StreamHandler()
  handler.setLevel(logging.DEBUG)
  logging.getLogger("adaptive_extractor").addHandler(handler)
  ```

## Diagnostic Steps

Follow these steps to diagnose issues with the adaptive extractor:

### 1. Enable Debug Mode

Always start with debug mode to get detailed logs:

```python
data = extract_project_adaptive(url, html, debug=True)
```

or with the command-line:

```bash
python -m backend.scrapy.scraper.adaptive_extractor URL --debug
```

### 2. Inspect the HTML

Save and inspect the HTML to understand the structure:

```python
with open("page.html", "w", encoding="utf-8") as f:
    f.write(html)
```

Then open in a browser and use the browser's developer tools to inspect elements.

### 3. Test Specific Extraction Methods

Test each extraction method individually to pinpoint issues:

```python
extractor = AdaptiveExtractor(html, url, debug=True)
extractor._extract_credits_lbbonline_v2()  # Test specific method
print(extractor.data["companies"])  # Check result
```

### 4. Check Structure Detection

Verify the structure detection is working correctly:

```python
extractor = AdaptiveExtractor(html, url, debug=True)
print(extractor.structure_type)  # Should match the expected site type
```

### 5. Try Alternative Extractions

Force the use of alternative extraction methods:

```python
extractor = AdaptiveExtractor(html, url, debug=True)
extractor._extract_credits_alternative()  # Try alternative methods
print(extractor.data["companies"])  # Check result
```

## Common Customizations

### Adding Support for a New Site Type

1. Add detection logic in `_detect_structure`:

```python
if "newsite.com" in self.domain or self.soup.select(".newsite-specific-class"):
    return "newsite_v1"
```

2. Add a new extraction method:

```python
def _extract_credits_newsite_v1(self):
    """Extract credits using NewSite v1 structure"""
    companies = []
    unknown_roles = []
    
    # Site-specific extraction logic
    # ...
    
    self.data["companies"] = companies
    self.data["meta"]["unknown_roles"] = unknown_roles
```

3. Add the method call in the `extract` method:

```python
if self.structure_type == "newsite_v1":
    logger.info("Using NewSite v1 extractor")
    self._extract_credits_newsite_v1()
```

### Customizing AI Enhancement

To modify how AI suggestions are used:

```python
# In scrape_project_adaptive function
if "companies" in missing_elements and suggestions.get("companies"):
    # Custom logic for applying AI suggestions
    soup = BeautifulSoup(html, "html.parser")
    selector = suggestions["companies"]
    
    # Custom extraction based on the selector
    # ...
```

### Adding New Fallback Methods

To add a new fallback extraction method:

1. Create a new method in the `AdaptiveExtractor` class:

```python
def _extract_credits_new_fallback(self):
    """New fallback method for credit extraction"""
    # Custom fallback logic
    # ...
```

2. Add it to the alternative extraction cascade:

```python
def _extract_credits_alternative(self):
    """Alternative extraction method when other methods fail"""
    try:
        # If the primary extraction methods failed, try to extract from tables
        if not self.data["companies"]:
            self._extract_credits_from_tables()
        
        # Add your new fallback here
        if not self.data["companies"]:
            self._extract_credits_new_fallback()
        
        # Continue with other fallbacks
        # ...
    except Exception as e:
        logger.error(f"❌ Error in alternative credit extraction: {str(e)}")
```

## Advanced Debugging Techniques

### Saving Extraction State

Add code to save the state at different points in the extraction process:

```python
def _extract_credits_lbbonline_v2(self):
    try:
        # Normal extraction code
        # ...
        
        # Save the state for debugging
        with open("extraction_state.json", "w", encoding="utf-8") as f:
            json.dump({
                "companies": companies,
                "unknown_roles": unknown_roles,
                "credit_blocks_count": len(credit_blocks),
                "role_elements_count": sum(len(block.select("div.team div")) for block in credit_blocks)
            }, f, indent=2)
        
        # Continue with the method
        # ...
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
```

### Detailed Element Inspection

Add code to inspect specific elements in detail:

```python
# In _extract_credits_lbbonline_v2
for i, block in enumerate(credit_blocks):
    if self.debug:
        logger.debug(f"Credit block {i+1} HTML: {block}")
        logger.debug(f"Company element: {block.select_one('span.font-barlow.font-bold.text-black')}")
    
    # Continue with normal extraction
    # ...
```

### Mock Testing

Create a test script that uses known HTML to test extraction:

```python
def test_extraction_with_mock():
    """Test extraction with mock HTML"""
    mock_html = """
    <div class="flex space-y-4">
        <span class="font-barlow font-bold text-black">Test Company</span>
        <div class="team">
            <div>Director: John Smith</div>
            <div>Producer: Jane Doe</div>
        </div>
    </div>
    """
    
    extractor = AdaptiveExtractor(mock_html, "https://lbbonline.com/test", debug=True)
    extractor._extract_credits_lbbonline_v2()
    print(json.dumps(extractor.data["companies"], indent=2))

# Run the test
test_extraction_with_mock()
```

## Performance Optimization

If the extractor becomes too slow, consider these optimizations:

1. **Avoid Multiple Parsing:** Parse the HTML once and reuse the soup object.

2. **Selective Extraction:** Only run extraction methods that are likely to work.

3. **Caching Results:** Cache extraction results for frequently accessed pages.

4. **Limit Fallback Cascades:** Prioritize fallbacks based on likelihood of success.

5. **Optimize Regexes:** Make regex patterns more specific to avoid expensive backtracking.