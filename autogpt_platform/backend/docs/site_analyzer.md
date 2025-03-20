## 🧠 Site Snapshot Analyzer — Reference Guide

### 🔍 Purpose
This module analyzes static HTML pages from media/creative websites and returns structured metadata about the site’s layout, link patterns, and scraping strategy.

---

### ⚒ How It Works

#### 1. **Inputs**
- `html_path`: path to a saved HTML snapshot of a web page.

#### 2. **Outputs**
A dictionary with three key blocks:
- `meta`: Headline and source file info.
- `structure`: Detected features (pagination, roles, link types).
- `strategy`: Suggested scraping approach and confidence level.
- `samples`: A handful of detected links (for QA/debugging).

---

### 🔬 Detection Categories

| Feature              | How It’s Detected                                                 |
|----------------------|-------------------------------------------------------------------|
| `has_project_links`  | URLs that contain `/work/`, `/project`, `/case`, `/entry`        |
| `has_company_links`  | URLs with `/company`, `/studio`, `/vendor`                       |
| `has_person_links`   | `/profile` or links with `director`, `editor`, `dop`, etc.       |
| `has_pagination`     | Presence of `page=`, `.pagination`, or "next page" in text       |
| `max_page`           | Largest numeric value from `page=` query params in links         |
| `has_role_info`      | Text contains keywords like `director`, `client`, etc.           |
| `has_sections`       | Sections like `topics`, `collections`, or `awards` found         |

---

### 🧠 Strategy Logic

| Strategy              | Conditions                                                                 |
|-----------------------|---------------------------------------------------------------------------|
| `project_with_credits`| >10 project links + known role info                                       |
| `basic_gallery`       | >10 project links, but no role info                                       |
| `directory_style`     | Has company or person pages, but no gallery                               |
| `unknown`             | Fallback if none of the above detected                                    |

Each strategy returns a **confidence score** based on strength of matching signals.

---

### 💡 Use Case

This is especially useful when:
- You're evaluating **new websites** to scrape
- You're building an **automated agent** to adapt scraping plans
- You want to **compare multiple site types** at scale

---

### 📦 Folder Structure

Your snapshot HTML files should live here:

```bash
backend/scrapy/scraper/snapshots/
```

You can run the analyzer across them with:

```bash
python backend/scrapy/scraper/analyze_snapshots.py
```

> You’ll get structured console output or can modify to dump JSON/CSV.

---

### ✅ Next Steps

1. This doc lives at `backend/docs/site_analyzer.md`
2. The analyzer script is renamed `analyze_snapshots.py`
3. Use the results to fine-tune your site strategy logic

