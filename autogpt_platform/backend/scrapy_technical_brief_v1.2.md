Werc AI Agent System – Technical Brief (v1.2)
🌟 Overview
The Werc Agent System is a multi-agent, AI-powered framework for autonomously scraping, validating, and structuring creative-industry data from websites (like LBBOnline, D&AD, Eyecandy) into an Azure SQL database — with assets uploaded to Azure Blob.

Unlike traditional crawlers, this system:

Writes and adapts its own scraping logic
Detects site structures dynamically (e.g., galleries vs directories)
Validates results before inserting
Stores media assets and links them in schema
Uses retry/debug loops on partial or failed scrapes
Routes scraping logic by agent strategy
🧑‍💻 Core Concept
Give it a mission like:

"Scrape all projects from lbbonline.com, validate and insert them."

It will:

Analyze the site or snapshot
Recommend a strategy + agent plan
Scan for project links
Scrape projects, companies, people
Upload media, validate structure
Insert data into your SQL DB
You control it with a single task dictionary.

🤖 Agent Roles
🔵 Agent A – Domain Scanner
Scans index/listing pages (e.g. /work)
Finds project URLs
Detects pagination & structure
Passes links to Agent B
🔶 Agent B – Project Scraper
Visits project pages
Extracts title, media, credits, companies
Triggers retry via Agent D if data is incomplete
🔷 Agent C – Entity Scraper
Scrapes companies/people from /company or /profile URLs
Extracts roles, logos, bios, websites
Uploads assets
🔸 Agent D – Validator / Debugger
Confirms:
Required fields are present
Roles link to people + companies
Asset URLs valid
Retries scraping if needed
🔹 Agent E – Memory / Tool Builder
Caches working scrapers
Suggests scraping patterns for similar sites
Will eventually support tool recommendations
🔎 Smart Site Analyzer
Located at: scraper/site_analyzer.py
Input: local HTML snapshot or live URL
Extracts:
Project, company, person link patterns
Role keywords (director, agency, etc.)
Pagination info and depth
Recommends:
Strategy (e.g. project_with_credits)
Agent routing plan (["domain_scanner", "project_scraper", "entity_scraper", ...])
🧠 Intelligence Highlights
Routing Logic: Analyzer determines which agents to activate
Retry Chain: Failed scrapes pass through validator and retry
Debug Mode: Interactive step-through per agent (pause + resume)
Logging + Time Tracking: Inline terminal logs show progress
Stub Fallbacks: Each scraper supports stub returns during testing
📄 Output Destinations
Type	Destination	Notes
Structured data	Azure SQL	Projects, companies, people, roles
Assets	Azure Blob Storage	Referenced by public URLs
Logs & Scripts	Git or Blob	Debugging + reuse
Screenshots	Optional local/Blob	For validation and audit
🛠 Key Modules
Path	Description
scrapy/mission_runner.py	Orchestrates full scraping mission
scrapy/scraper/site_analyzer.py	Detects strategy and agent plan
scrapy/scraper/domain_scanner.py	Collects target links
scrapy/scraper/project_scraper.py	Extracts main project data
scrapy/scraper/company_scraper.py	Scrapes company/person profiles
scrapy/scraper/validator.py	Validates result structure
scrapy/blob/uploader.py	Uploads media to Azure Blob
scrapy/sql/db_writer.py	Writes validated data into DB
docs/site_analyzer.md	Site analysis reference
fallback_mapping.json	Role normalization rules
🧪 Example Mission (Debug Mode)
bash
Copy
Edit
python -m backend.scrapy.mission_runner "https://lbbonline.com/work?edition=international" --debug
Agent A finds all /work/ links
Agent B scrapes projects
Agent C scrapes linked companies
Agent D validates each result
Assets are uploaded
Everything prints step-by-step
✅ Summary
This is a modular AI agent system that mirrors a real researcher:

Navigates inconsistent creative websites
Extracts structured data + media
Validates before storing
Improves its own scrapers over time
Every mission is traceable, correctable, and scalable. Now tested and pushed to Git ✅