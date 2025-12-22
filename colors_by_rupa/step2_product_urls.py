import asyncio
import os
import json
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import logging

# Configure logging to show messages in the console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

async def auto_scroll(page):
    """
    Scrolls down the page slowly to ensure all lazy-loaded content is visible.
    """
    logging.info("Starting slow scroll...")
    await page.evaluate("""
        async () => {
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            let lastHeight = document.body.scrollHeight;
            let noChangeCount = 0;
            const maxAttempts = 15;

            while (noChangeCount < maxAttempts) {
                window.scrollBy(0, 200);
                await delay(500);
                let newHeight = document.body.scrollHeight;
                if (newHeight === lastHeight) {
                    noChangeCount++;
                } else {
                    noChangeCount = 0;
                    lastHeight = newHeight;
                }
            }
        }
    """)
    logging.info("Finished scrolling.")

async def scrape_product_urls(category_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        try:
            logging.info(f"Navigating to {category_url}")
            await page.goto(category_url, timeout=60000)
            
            # Scroll to load all products
            await auto_scroll(page)
            
            # Parse the page content
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find product items
            li_tags = soup.find_all("li", class_="item product product-item")
            product_urls = []
            
            for li in li_tags:
                a_tag = li.find("a")
                if a_tag:
                    href = a_tag.get("href")
                    if href:
                        product_urls.append(href)
                        
            logging.info(f"Found {len(product_urls)} products for {category_url}")
            return product_urls
            
        except Exception as e:
            logging.error(f"Error scraping {category_url}: {str(e)}")
            return []
        finally:
            await browser.close()
async def process_categories(categories, root_data, save_path, processed_categories, log_progress_func, current_path=[]):
    for name, value in categories.items():
        if isinstance(value, dict):
            await process_categories(value, root_data, save_path, processed_categories, log_progress_func, current_path + [name])
            
        elif isinstance(value, str):
            current_level = root_data
            for key in current_path:
                if key not in current_level:
                    current_level[key] = {}
                current_level = current_level[key]
            
            # Create a unique key for this category
            main_slug = "|".join(current_path) if current_path else "root"
            category_key = f"{main_slug}|{name}"
            
            # Check if already processed
            if category_key in processed_categories:
                logging.info(f"Skipping '{name}' (found in progress log)")
                continue
            
            # Also check if data already exists in output
            if name in current_level and isinstance(current_level[name], list) and len(current_level[name]) > 0:
                logging.info(f"Skipping '{name}' (already has data)")
                log_progress_func(main_slug, name)  # Log it for future runs
                continue
                
            logging.info(f"Processing category: {name}")
            urls = await scrape_product_urls(value)
            
            current_level[name] = urls
            
            # Save progress to output file
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(root_data, f, indent=4, ensure_ascii=False)
            logging.info(f"Saved progress to {save_path}")
            
            # Log this category as processed
            log_progress_func(main_slug, name)

async def product_urls():
    today_str = datetime.now().strftime("%Y-%m-%d")
    country = "India"
    
    # Setup paths
    input_base_dir = f"{country}/{today_str}/Category"
    category_file = os.path.join(input_base_dir, f"{country}_category_urls.json")
    
    output_dir = f"{country}/{today_str}/Item_urls"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{country}_product_urls.json")
    progress_file = os.path.join(output_dir, f"{country}_progress.log")
    
    # Check if category file exists
    if not os.path.exists(category_file):
        logging.error(f"Category file not found: {category_file}")
        return

    # Load category data
    try:
        with open(category_file, "r", encoding="utf-8") as f:
            category_data = json.load(f)
            logging.info(f"Loaded categories from {category_file}")
    except Exception as e:
        logging.error(f"Category file error: {e}")
        return

    # Load existing output if resuming
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as ef:
                output = json.load(ef)
                logging.info(f"Resuming from existing progress file: {output_file}")
        except Exception as e:
            logging.warning(f"Could not load existing output file: {e}")
            output = {}
    else:
        output = {}

    # Load progress log to skip already processed categories
    processed_categories = set()
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        processed_categories.add(line)
            logging.info(f"Found {len(processed_categories)} already-processed categories in progress log")
        except Exception as e:
            logging.warning(f"Could not read progress log: {e}")

    def log_progress(main_slug: str, subkey: str):
        """Write main_slug|subkey to progress log file"""
        key = f"{main_slug}|{subkey}"
        try:
            with open(progress_file, "a", encoding="utf-8") as f:
                f.write(f"{key}\n")
        except Exception as e:
            logging.warning(f"Could not write to progress log: {e}")

    logging.info("Starting product scraping...")
    await process_categories(category_data, output, output_file, processed_categories, log_progress)
    logging.info(f"Completed! Final data saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(product_urls())