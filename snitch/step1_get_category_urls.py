import os
import json
import logging
import re
import time
import multiprocessing
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.sync_api import sync_playwright
from alert import raise_ticket

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- UTILITY: Save JSON ---
def save_json(country, today_date, data, suffix="_category_urls"):
    base_path = f'{country}/{today_date}/Category'
    os.makedirs(base_path, exist_ok=True)
    out_file = f'{base_path}/{country}{suffix}.json'

    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logging.info(f"[{country}] Data saved to {out_file}")

def worker_playwright_india(country, config, today_date):
    url = config['base_url']
    
    logging.info(f"[{country}] Starting Playwright extraction on {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ]
        )
        # Use standard context (similar to Code 2)
        context = browser.new_context()
        page = context.new_page()

        logging.info(f"Loading page: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        try:
            # --- CODE 2 LOGIC: Wait for "TOP CATEGORIES" ---
            logging.info("Waiting for 'TOP CATEGORIES' section...")
            page.wait_for_selector("text=TOP CATEGORIES", timeout=20000)
        except Exception:
            logging.warning("Could not find 'TOP CATEGORIES' text via wait. Proceeding anyway...")

        page_source = page.content()
        context.close()
        browser.close()

        soup = BeautifulSoup(page_source, 'html.parser')
        result = {}

        # --- CODE 2 LOGIC START: Extracting exactly like Code 2 ---
        
        # Find TOP CATEGORIES section dynamically
        top_cat_header = soup.find("h2", string=lambda x: x and "TOP CATEGORIES" in x)
        
        if top_cat_header:
            # Parent (div) whose next sibling contains the grid
            container = top_cat_header.find_parent("div")
            
            if container:
                # category grid div
                grid = container.find("div", class_="grid")
                
                if grid:
                    logging.info("Found Category Grid. Extracting links...")
                    # Extract all <a> tags
                    for a in grid.find_all("a", href=True):
                        name = a.get_text(strip=True)
                        href = a["href"]

                        # Standardize names (Exact map from Code 2)
                        replacements = {
                            "T-shirts": "T-Shirts",
                            "Sweatshirts & Hoodies": "Sweatshirts",
                            "Joggers": "Joggers & Trackpants"
                        }
                        name = replacements.get(name, name)

                        full_url = "https://www.snitch.com" + href
                        
                        # Add to result
                        result[name] = full_url
                        logging.info(f"Found: {name}")
                else:
                    logging.warning("Category grid div not found inside container.")
            else:
                logging.warning("Container for TOP CATEGORIES header not found.")
        else:
            logging.warning("Header 'TOP CATEGORIES' not found in soup.")
            
        # --- CODE 2 LOGIC END ---

        # Wrap result in gender 'men' (Code 1 requirement)
        final_result = {"men": result}
        
        save_json(country, today_date, final_result)
        return final_result

def get_category_urls(config_dict, today_date, re_run):
    processes = []
    
    for country, settings in config_dict.items():
        base_path = f'{country}/{today_date}/Category'
        out_file = f'{base_path}/{country}_category_urls.json'
        
        if os.path.exists(out_file) and not re_run:
            logging.info(f"[{country}] Data already exists. Skipping... (Set re_run=True to force)")
            continue

        target_func = None
        if country == "India":
            target_func = worker_playwright_india
        else:
            logging.warning(f"No scraper defined for {country}")
        
        if target_func:
            p = multiprocessing.Process(target=target_func, args=(country, settings, today_date))
            processes.append(p)
            p.start()
        else:
            logging.error(f"No worker defined for country: {country}")
        
    for p in processes:
        p.join()

    logging.info("All Category URL extraction tasks finished.")