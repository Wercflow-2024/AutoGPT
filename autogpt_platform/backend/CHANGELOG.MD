# Changelog

## [v1.2] - 2025-03-20
### Added
- Modular mission runner with agent routing
- Smart site analyzer with structure inference
- Debug mode with pause checkpoints per agent
- Stub fallbacks for scraper functions
- Time logging + inline terminal printouts

### Changed
- Strategy detection now informs active agents
- Analyzer returns routing plan + confidence level

# Changelog

## [v1.3] - 2025-03-21
### Added
- First working project_scraper.py CLI script with --debug flag
- HTML snapshot support for testing real scraped content
- Self-correcting scaffold (fallback-aware structure, unknown roles logging)
- fallback_mapping.json support (foundation laid)
- Output file: output_project.json for parsed results

### Changed
- Mission runner now modularized into agent steps with pause support
- Analyzer now suggests agent strategy per mission
- LBB project structure reviewed and decoding strategy documented

## [v1.4] - 2025-03-22
### Added
- Azure OpenAI integration for AI-enhanced scraping
- Snapshot analyzer tool for debugging extractions
- Role normalization with AI suggestions
- Multi-strategy support for different websites
- Comprehensive testing suite with performance metrics 
- Configuration utilities for environment management
- HTML structure analysis with AI-generated strategies
- Organized strategy directory structure by domain/version
- Results saved with clean filenames and sequential IDs

### Changed
- Project scraper upgraded to 6-step process with AI assistance
- Enhanced error handling and recovery for failed extractions
- Snapshot directory with version tracking for scraped content
- Fallback system redesigned with AI-powered suggestions
- Missing element detection with intelligent selector recommendations
- Modularized agent routing for complex scraping missions
- Enhanced strategy selector to support both --strategy and --strategy-name
- Auto-creation of strategy/results folders via `config.py`
- Snapshot analyzer saves clean JSON selectors for AI usage

### Directory Structure
```
backend/scrapy/
├── strategies/
│   ├── lbbonline/
│   │   ├── v001_basic.json
│   │   ├── v002_enhanced.json
│   └── dandad/
│       ├── v001_basic.json
├── results/
│   ├── lbbonline/
│   │   ├── 001_project_title.json
│   │   ├── 002_another_project.json
├── scraper/
│   ├── project_scraper.py
│   ├── ai_enhancer.py
│   ├── snapshot_analyzer.py
│   ├── site_analyzer.py
├── utils/
│   ├── config.py
│   └── testing.py
```

### How to Use
1. Generate a strategy:
```bash
python -m backend.scrapy.scraper.snapshot_analyzer strategy lbbonline.com__HASH.html --ai
```
2. Run scraper using strategy version:
```bash
python -m backend.scrapy.scraper.project_scraper https://lbbonline.com/work/132158 --strategy-name lbbonline/v001
```
3. View results saved under:
```
backend/scrapy/results/lbbonline/
```

### Benefits
- Version control of strategies per domain
- Reusable, editable JSON strategy logic
- AI-assisted fallback, enrichment, and recovery
- Clean results naming with project titles
- Modular setup ready for team use or pipeline integration

