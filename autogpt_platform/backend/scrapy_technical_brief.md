# Werc AI Agent System – Technical Brief (v1.1)

## 🌟 Overview
The Werc Agent System is a multi-agent, self-evolving AI-powered platform designed to autonomously scrape, validate, normalize, and insert structured data from creative-industry websites (e.g., LBBOnline, D&AD, Eyecandy) into a production-grade Azure SQL database.

Unlike traditional scrapers, this system is capable of:
- Writing and evolving scraping logic per website
- Validating extracted data with traceable evidence
- Learning from failures with retry and correction cycles
- Linking entities across domains (projects, companies, people)
- Uploading and referencing assets (images, videos) to Azure Blob
- Dynamically adjusting strategy based on site structure

This mimics a human researcher who ensures accuracy, schema compliance, and contextual integrity across all extracted data.

---

## 🧑‍💻 Core Concept
This is not just a scraper. It’s an autonomous data engineering framework.

You give it a **mission** like:
> "Scrape all projects from lbbonline.com, extract companies & people, validate everything, and insert into the Azure SQL database."

The system will:
1. Analyze the site snapshot or URL structure
2. Infer a strategy and write custom scraping logic
3. Run the scrapers with retry/refinement loops
4. Validate the results (DOM diffing, schema checks, screenshots)
5. Upload assets to Azure Blob
6. Insert fully validated data into SQL DB

---

## 🤖 Agent Roles

### 🔵 Agent A – Domain Scanner
- Analyzes the structure of a base URL
- Detects pagination, project links, and structure
- Outputs a scraping strategy and feed of target links

### 🔶 Agent B – Project Scraper
- Visits individual project pages
- Extracts:
  - Title, Description, Media, Credits
  - Related company/person links
- Triggers Agent D if any field fails validation

### 🔷 Agent C – Entity Scraper
- Visits company/person profile pages
- Extracts structured info:
  - Names, roles, websites, bios, images
- Uploads all relevant assets to Azure Blob

### 🔸 Agent D – Validator / Debugger
- Checks:
  - Schema compliance (project must have company/people)
  - Relationships and data completeness
  - Media uploads present
- Uses DOM diffing, screenshot comparison, and LLM reasoning
- If validation fails, rewrites scraping logic and reassigns task

### 🔹 Agent E (Optional) – Tool Builder / Memory
- Stores reusable scraping patterns and code
- Suggests known-good logic for similar sites
- Learns from previous missions

---

## 📋 Validation Rules

All data must:
- Match strict schema for Azure SQL
- Link people → roles → projects → companies
- Include asset uploads (images/videos) with public blob URLs
- Be backed by screenshots or HTML structure
- Use `fallback_mapping.json` to map vague roles into standard taxonomy

Nothing is inserted until it's 100% validated.

---

## 📄 Output Destinations

| Type              | Destination                | Purpose |
|-------------------|-----------------------------|---------|
| Structured data   | Azure SQL DB               | Projects, companies, people, roles |
| Media             | Azure Blob Storage         | Referenced by URL in DB |
| Scraper logs/code | Blob or Git repo           | Debugging, reuse |
| Screenshots       | Blob or local store         | For validation / audit trail |

---

## ⚖️ Strategy Detection

The system starts with **`site_analyzer.py`**, which:
- Loads HTML snapshots (or live URL fetch)
- Checks:
  - Link patterns (e.g., `/work/`, `/case`, `/entry`, `/project`)
  - Pagination presence
  - Role language ("director", "agency", etc.)
  - Company/person profiles (e.g., `/company`, `/profile`, etc.)
- Returns a strategy:
  - `project_with_credits`
  - `basic_gallery`
  - `directory_style`
  - `unknown`

---

## 🔧 Agent Intelligence

- **Dynamic Code Gen**: OpenAI writes and rewrites scraping logic
- **Retry System**: Failed missions are debugged and re-executed
- **Validation Loop**: Results must pass validation rules or retry
- **Adaptive Memory**: Stores working code for reuse
- **DOM Reasoning**: LLM can compare HTML structures for diffs

---

## 🚧 System Components (v1)

| Path                         | Description |
|------------------------------|-------------|
| `/frontend/app/scraper`      | Mission submission & UI results |
| `/backend/api/missions.py`   | Trigger endpoint |
| `/backend/scrapy/mission_runner.py` | Orchestrates scraping steps |
| `/backend/scrapy/scraper/`   | Core scraping agents |
| `/backend/scrapy/blob/`      | Asset upload logic |
| `/backend/scrapy/sql/`       | Data insert logic |
| `/backend/docs/site_analyzer.md` | Analyzer reference guide |
| `fallback_mapping.json`      | Role mapping dictionary |

---

## 🚀 Example Mission (E2E)

> Mission: Scrape all work pages from lbbonline.com with full credits and company info

1. **Agent A** scans `/work?edition=international`
2. Detects paginated `/work/xxxxx` links
3. **Agent B** visits each link and scrapes content
4. **Agent C** follows `/company/` or `/profile/` links
5. **Agent D** validates:
   - Project has video/image
   - All credits linked
   - Blob links are present
6. **Agent D** retries if anything is missing
7. Final insert into Azure SQL + asset links

---

## ✅ Summary
This system automates structured scraping of creative-industry data. With multiple AI agents, retry loops, validation checks, and blob/media uploads, it ensures robust and reusable data ingestion workflows. Every step mimics what a research analyst would do — but at scale and speed.