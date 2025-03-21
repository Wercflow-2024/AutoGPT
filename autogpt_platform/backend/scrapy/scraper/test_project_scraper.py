#!/usr/bin/env python3
"""
Test script for the enhanced project scraper architecture.
This script runs the scraper against sample URLs and analyzes the results.
"""

import os
import json
import argparse
import hashlib
from urllib.parse import urlparse
from datetime import datetime
from rich.console import Console
from rich.table import Table
from pprint import pprint

from project_scraper import scrape_project, fetch_html_and_snapshot

console = Console()

TEST_URLS = [
    "https://lbbonline.com/work/132158",  # LBB project
    "https://www.dandad.org/awards/professional/2024/238864/up-in-smoke/",  # D&AD project
]

def test_scraper(urls=None, output_dir="test_results", force_refresh=False, debug=False):
    """
    Test the scraper with multiple URLs and analyze results
    """
    if urls is None:
        urls = TEST_URLS
    
    os.makedirs(output_dir, exist_ok=True)
    
    results = []
    
    # Create a summary table
    table = Table(title="Project Scraper Test Results")
    table.add_column("URL", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Companies", style="magenta")
    table.add_column("People", style="blue")
    table.add_column("Media", style="yellow")
    table.add_column("Status", style="red")
    
    for url in urls:
        console.print(f"\n[bold cyan]Testing scraper on:[/] {url}")
        
        try:
            # Run scraper
            start_time = datetime.now()
            scraped_data = scrape_project(url, debug=debug, force_refresh=force_refresh)
            duration = (datetime.now() - start_time).total_seconds()
            
            # Save results
            domain = urlparse(url).netloc.replace("www.", "")
            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            filename = f"{domain}_{url_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_path = os.path.join(output_dir, filename)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(scraped_data, f, indent=2)
            
            # Add to results
            missing = scraped_data.get("meta", {}).get("missing_elements", [])
            company_count = len(scraped_data.get("companies", []))
            
            # Count people across all companies
            people_count = 0
            for company in scraped_data.get("companies", []):
                people_count += len(company.get("credits", []))
            
            has_media = bool(scraped_data.get("video_links") or scraped_data.get("poster_image"))
            
            status = "✅ Success" if not missing else f"⚠️ Missing: {', '.join(missing)}"
            
            # Add row to table
            table.add_row(
                domain,
                scraped_data.get("title", "Missing"),
                str(company_count),
                str(people_count),
                "✓" if has_media else "✗",
                status
            )
            
            results.append({
                "url": url,
                "title": scraped_data.get("title"),
                "company_count": company_count,
                "people_count": people_count,
                "has_media": has_media,
                "missing": missing,
                "duration": duration,
                "output_file": output_path
            })
            
        except Exception as e:
            console.print(f"[bold red]Error processing {url}:[/] {str(e)}")
            table.add_row(
                urlparse(url).netloc,
                "ERROR",
                "-",
                "-",
                "-",
                f"❌ {str(e)}"
            )
    
    # Display summary table
    console.print("\n")
    console.print(table)
    
    # Summary statistics
    success_count = sum(1 for r in results if not r["missing"])
    console.print(f"\n[bold green]Success rate:[/] {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    avg_duration = sum(r["duration"] for r in results) / len(results) if results else 0
    console.print(f"[bold yellow]Average scraping time:[/] {avg_duration:.2f} seconds")
    
    # Output locations
    console.print(f"\n[bold cyan]Results saved to:[/] {output_dir}")
    for r in results:
        console.print(f"  - {os.path.basename(r['output_file'])}")

def test_html_snapshot(url, output_dir="snapshots"):
    """
    Test just the HTML snapshot functionality
    """
    console.print(f"[bold cyan]Testing HTML snapshot for:[/] {url}")
    
    try:
        html, is_cached = fetch_html_and_snapshot(url, force_refresh=True)
        
        domain = urlparse(url).netloc.replace("www.", "")
        url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
        filename = f"{domain}_{url_hash}.html"
        path = os.path.join(output_dir, filename)
        
        filesize = os.path.getsize(path)
        console.print(f"[green]✓ Snapshot saved:[/] {filename} ({filesize/1024:.1f} KB)")
        
    except Exception as e:
        console.print(f"[bold red]Error creating snapshot:[/] {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the enhanced project scraper")
    parser.add_argument("--urls", nargs="+", help="URLs to test (space-separated)")
    parser.add_argument("--output", default="test_results", help="Output directory for results")
    parser.add_argument("--snapshot-only", action="store_true", help="Test only the HTML snapshot functionality")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh HTML snapshots")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    args = parser.parse_args()
    
    if args.snapshot_only:
        test_urls = args.urls if args.urls else TEST_URLS
        for url in test_urls:
            test_html_snapshot(url)
    else:
        test_scraper(args.urls, args.output, args.force_refresh, args.debug)