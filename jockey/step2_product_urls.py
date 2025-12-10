import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright


today = datetime.today().strftime("%Y-%m-%d")
country = "India"
BASE_DIR = os.path.join("India",  today, "Category")
CATEGORY_FILE = os.path.join(BASE_DIR, f"{country}_category_urls.json")

async def scrape_product_urls(page, url):
    await page.goto(url, timeout=0)
    await page.wait_for_load_state("domcontentloaded")
    max_scrolls = 200      
    scroll_pause = 2000      
    unchanged_scrolls = 0
    previous_height = 0

    for _ in range(max_scrolls):
        await page.mouse.wheel(0, 800)
        await page.wait_for_timeout(scroll_pause)
        current_height = await page.evaluate("document.body.scrollHeight")
        if current_height == previous_height:
            unchanged_scrolls += 1
        else:
            unchanged_scrolls = 0
        previous_height = current_height
        if unchanged_scrolls >= 10:
            break

    product_links = set()
    for a in await page.query_selector_all("a"):
        href = await a.get_attribute("href")
        if not href:
            continue
        if "product" in href:
            if href.startswith("/"):
                href = "https://www.jockey.in" + href
            product_links.add(href)

    return list(product_links)


async def build_product_tree(obj, page, output_file=None, root_tree=None, current_path=None, progress_file=None):
    if root_tree is None:
        root_tree = {}
    if current_path is None:
        current_path = []

    if isinstance(obj, str) and obj.startswith("http"):
        # Check if this URL was already scraped (for resume capability)
        target = root_tree
        for key in current_path[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Skip if already scraped
        if current_path and current_path[-1] in target and target[current_path[-1]]:
            logging.info(f"Skipping (already scraped): {obj}")
            return target[current_path[-1]]
        
        logging.info(f"Scraping: {obj}")
        start_time = datetime.now()
        data = await scrape_product_urls(page, obj)
        end_time = datetime.now()
        
        # Update root_tree at current_path
        target[current_path[-1]] = data
        
        # Granular save
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(root_tree, f, indent=4, ensure_ascii=False)
            logging.info(f"Saved {len(data)} items for '{current_path[-1]}' to {output_file}")
        
        # Log progress
        if progress_file:
            # Create simple pipe-separated path format
            category_path = "|".join(current_path).lower().replace(" ", "_")
            with open(progress_file, "a", encoding="utf-8") as pf:
                pf.write(f"{category_path}\n")
            
        return data

    elif isinstance(obj, dict):
        result = {}
        # Ensure dict exists in root_tree structure
        target = root_tree
        for key in current_path:
            if key not in target:
                target[key] = {}
            target = target[key]

        for k, v in obj.items():
            print(f"Processing category: {k}")
            result[k] = await build_product_tree(v, page, output_file, root_tree, current_path + [k], progress_file)
        return result

    elif isinstance(obj, list):
        result = []
        for i, v in enumerate(obj):
            result.append(await build_product_tree(v, page, output_file, root_tree, current_path, progress_file))
        return result
    else:
        return obj

def count_product_urls(d):
    if isinstance(d, list):
        return len(d)
    elif isinstance(d, dict):
        return sum(count_product_urls(v) for v in d.values())
    else:
        return 0


def print_product_counts(d, prefix=""):
    if isinstance(d, list):
        logging.info(f"{prefix}: {len(d)} product URLs")
    elif isinstance(d, dict):
        for k, v in d.items():
            new_prefix = f"{prefix}/{k}" if prefix else k
            print_product_counts(v, new_prefix)


async def product_urls():
    # Load category file when function is called, not at import time
    COUNTRY = "India"
    category_file = Path(CATEGORY_FILE)
    
    if not category_file.exists():
        raise FileNotFoundError(f"Category file not found at: {CATEGORY_FILE}")
    
    # Load category data
    try:
        with open(category_file, "r", encoding="utf-8") as f:
            category_tree = json.load(f)
            logging.info(f"Loaded categories from {category_file}")
    except Exception as e:
        logging.error(f"Category file error: {e}")
        return
    
    output_dir = Path("India") / today / "Item_urls"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    country = "india"
    output_file = output_dir / f"{country}_product_urls.json"
    progress_file = output_dir / f"{country}_progress.log"
    
    # Initialize progress file
    with open(progress_file, "w", encoding="utf-8") as pf:
        pf.write("")  # Start with empty file
    
    # Load existing output if resuming
    if output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as ef:
                output = json.load(ef)
                logging.info(f"Resuming from existing progress file: {output_file}")
        except Exception as e:
            logging.warning(f"Could not load existing output file: {e}")
            output = {}
    else:
        output = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        new_tree = await build_product_tree(category_tree, page, str(output_file), output, None, str(progress_file))
        await browser.close()
        
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(new_tree, f, indent=4, ensure_ascii=False)
    logging.info(f"Saved: {output_file}")

    total_products = count_product_urls(new_tree)
    logging.info(f"Total product URLs saved: {total_products}")

    logging.info("--- Product counts by category ---")
    print_product_counts(new_tree)
    
    logging.info(f"Progress log saved to: {progress_file}")

if __name__ == "__main__":
    asyncio.run(product_urls())
