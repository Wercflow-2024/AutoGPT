🧠 Werc AI-Enhanced Web Scraper – README
Version: v1.4 – Last Updated: 2025-03-22
Scrapes creative-industry websites (e.g. LBBOnline, D&AD) using hybrid scraping + Azure OpenAI for selector suggestions, validation, and role enrichment.

📁 Directory Structure
bash
Copy
Edit
backend/scrapy/
├── mission_runner.py             # Main orchestrator
├── scraper/
│   ├── project_scraper.py        # Project data extractor
│   ├── ai_enhancer.py            # Azure OpenAI integration
│   ├── snapshot_analyzer.py      # Snapshot debugger
│   ├── site_analyzer.py          # Infers page structure
│   ├── domain_scanner.py         # Finds project links
│   ├── company_scraper.py        # Entity extraction
│   ├── validator.py              # Data completeness checks
│   └── fallback_mapping.json     # Maps role IDs to normalized roles
├── utils/
│   ├── config.py                 # .env + settings manager
│   └── testing.py                # AI test harness
├── blob/uploader.py             # Uploads media to Azure Blob
├── sql/db_writer.py             # Final DB writer
├── snapshots/                   # HTML snapshots for debugging
├── test_results/                # Output from test runs
⚙️ Setup Instructions
🔧 Install Dependencies
bash
Copy
Edit
pip install rich==13.7.0 python-slugify==8.0.4 tqdm==4.66.2 python-dotenv==1.0.1
📦 Initialize Directory
bash
Copy
Edit
mkdir -p backend/scrapy/snapshots backend/scrapy/test_results
cp .env.example .env  # Then add Azure OpenAI API keys
🔐 Required .env Keys
dotenv
Copy
Edit
AZURE_OPENAI_API_KEY1=your-key
AZURE_OPENAI_ENDPOINT=https://wercopenai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-08-01-preview
AZURE_OPENAI_4OM_ENDPOINT=https://wercopenai.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2025-01-01-preview
🚀 6-Step Project Scraper Process
python
Copy
Edit
1. html = fetch_html_and_snapshot(url)
2. strategy = select_strategy(html, url)
3. data = extract_project_data(html, strategy, url, fallback_mapping)
4. missing = validate_scraped_data(data)
5. if missing: suggest_fixes_via_openai(html, url, missing)
6. return data
💻 Example Usage
🔹 Basic Scrape
bash
Copy
Edit
python -m backend.scrapy.scraper.project_scraper https://lbbonline.com/work/132158 --output results.json
🔹 Scrape with AI Enhancer
bash
Copy
Edit
python -m backend.scrapy.scraper.project_scraper https://lbbonline.com/work/132158 --output results.json --ai-model gpt-4o-mini
🔹 Normalize Roles with Fallback
bash
Copy
Edit
python -m backend.scrapy.scraper.project_scraper https://lbbonline.com/work/132158 --normalize-roles
🧪 Snapshot Analyzer
🔍 Listing & Debugging
bash
Copy
Edit
python -m backend.scrapy.scraper.snapshot_analyzer list
python -m backend.scrapy.scraper.snapshot_analyzer analyze lbbonline_com__HASH.html
🔬 Selector Testing
bash
Copy
Edit
python -m backend.scrapy.scraper.snapshot_analyzer analyze lbbonline_com__HASH.html --selector ".credit-entry"
🧠 Generate Strategy
bash
Copy
Edit
python -m backend.scrapy.scraper.snapshot_analyzer strategy lbbonline_com__HASH.html --ai --output strategy.json
🧑‍🚀 Full Mission Execution
bash
Copy
Edit
python -m backend.scrapy.mission_runner "https://lbbonline.com/work?edition=international" --debug
Agents triggered based on site_analyzer output.

🤖 AI Features
1. Selector Suggestions
json
Copy
Edit
{
  "selectors": {
    "companies": ".credit-entry",
    "roles": ".role-name"
  },
  "explanations": {
    "companies": "Targets credit blocks",
    "roles": "Targets role titles"
  }
}
2. Role Normalization
json
Copy
Edit
{
  "12345": "Creative Director",
  "67890": "Director of Photography"
}
3. Full Strategy Generation
json
Copy
Edit
{
  "strategy": "lbbonline_v1",
  "selectors": {
    "title": "h1",
    "description": ".field--name-field-description",
    "credit_blocks": ".credit-entry",
    "company_name": ".company-name a"
  }
}
🧪 Testing
Snapshot Comparison
bash
Copy
Edit
python -m backend.scrapy.scraper.test_ai_enhanced --test-url https://lbbonline.com/work/132158
Generates logs and comparison between:

Default strategy
AI-enhanced recovery
✅ Output Format
json
Copy
Edit
{
  "title": "Project Title",
  "client": "Brand Name",
  "date": "2025",
  "companies": [
    {
      "name": "Company A",
      "type": "Production",
      "credits": [
        {
          "person": { "name": "Jane Doe" },
          "role": "Creative Director"
        }
      ]
    }
  ],
  "meta": {
    "strategy": "lbbonline_v1",
    "credits_enriched": true
  }
}
🧠 Future Roadmap
Agent reward system (scores per mission)
Interactive scraping strategy builder
Multi-agent replay debugging
Entity deduplication across domains
🛠️ Troubleshooting
Issue	Fix
ModuleNotFoundError	Ensure __init__.py files exist
ImportError	Run from root autogpt_platform/
Missing Roles	Use --normalize-roles or snapshot debugger
AI not responding	Check .env Azure key & endpoint
Invalid data	Use --debug to step through each phase
