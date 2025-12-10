import os
import json
import logging
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Setup logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),  # Save logs to a file
        logging.StreamHandler()  # Also print logs to console
    ]
)

# Today's date
today_str = datetime.now().strftime('%Y-%m-%d')

# Config
country = 'levis_India'
category_folder_path = os.path.join(country, 'data', today_str, 'item_urls')
product_file_path = os.path.join(category_folder_path, 'unique_product_url.json')
json_output_folder = os.path.join(country, 'data', today_str, 'Json_data')
os.makedirs(json_output_folder, exist_ok=True)

# Number of browser instances to use
NUM_BROWSERS = 4

# Core scraping function
def scrape_page_data(url, output_file_path, browser_id):
    """
    Scrape product data from a URL and save it to a JSON file.
    Skip if the output file already exists (handled before calling this function).
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless= True)  # Headless for efficiency
            context = browser.new_context()
            page = context.new_page()
            logging.info(f"[Browser {browser_id}] Scraping URL: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for variant div to ensure dynamic content loads
            try:
                page.wait_for_selector('div.tw-flex.tw-gap-4.tw-pb-2.tw-items-center.tw-flex-wrap', timeout=10000)
            except Exception as e:
                logging.warning(f"[Browser {browser_id}] Variant div not found: {e}")

            soup = BeautifulSoup(page.content(), 'html.parser')

            # Hulkapps JSON
            hulkapps_data = None
            for script in soup.find_all('script', type='text/javascript'):
                if script.string and 'window.hulkappsWishlist.productJSON' in script.string:
                    match = re.search(r'window\.hulkappsWishlist\.productJSON\s*=\s*(\{.*?\});', script.string, re.DOTALL)
                    if match:
                        try:
                            hulkapps_data = json.loads(match.group(1))
                        except json.JSONDecodeError as e:
                            logging.error(f"[Browser {browser_id}] JSON decode error: {e}")

            # Composition & Care
            composition_data = []
            for details in soup.find_all('details', class_='details__container'):
                summary = details.find('summary')
                if summary and 'Composition and Care' in summary.get_text():
                    metafield = details.find('div', class_='metafield-rich_text_field')
                    if metafield:
                        items = metafield.find_all('li')
                        composition_data = [item.get_text(strip=True) for item in items]

            # Variant IDs
            variant_ids = []
            variant_div = soup.find('div', class_='tw-flex tw-gap-4 tw-pb-2 tw-items-center tw-flex-wrap')
            if variant_div:
                logging.info(f"[Browser {browser_id}] Found variant div with {len(variant_div.find_all('a'))} links")
                for a_tag in variant_div.find_all('a', href=True):
                    href = a_tag['href']
                    variant_id = href.split('/')[-1]
                    if variant_id:
                        variant_ids.append(variant_id)
            else:
                logging.warning(f"[Browser {browser_id}] Variant div not found on {url}")

            page.close()
            browser.close()

            # Save data if any exists
            if hulkapps_data or composition_data or variant_ids:
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "hulkapps_product_json": hulkapps_data,
                        "composition_and_care": composition_data,
                        "variant_ids": variant_ids
                    }, f, ensure_ascii=False, indent=2)
                return f"[Browser {browser_id}] Saved: {url}"
            else:
                return f"[Browser {browser_id}] No data found: {url}"

    except Exception as e:
        logging.error(f"[Browser {browser_id}] Error scraping {url}: {e}")
        return f"[Browser {browser_id}] Error scraping {url}: {e}"

# Function to divide list into N chunks
def chunk_list(lst, n):
    """Divide a list into n chunks for parallel processing."""
    k, m = divmod(len(lst), n)
    return [lst[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n)]

# Check if output file exists for a URL
def check_existing_output(url, gender, category):
    """Check if the output JSON file for a URL already exists."""
    category_clean = category.replace(' & ', '_').replace(' ', '_')
    output_category_path = os.path.join(json_output_folder, gender, category_clean)
    handle = url.split('/')[-1]
    filename = f"{handle}.json"
    output_file_path = os.path.join(output_category_path, filename)
    return os.path.exists(output_file_path), output_file_path

# Scraping logic for a category
def process_category(gender, category, urls):
    """Process all URLs for a given gender and category."""
    category_clean = category.replace(' & ', '_').replace(' ', '_')
    output_category_path = os.path.join(json_output_folder, gender, category_clean)
    os.makedirs(output_category_path, exist_ok=True)

    # Pre-filter URLs to skip those with existing output files
    filtered_urls = []
    skipped_count = 0
    for url in urls:
        exists, output_file_path = check_existing_output(url, gender, category)
        if exists:
            logging.info(f"Skipped (already exists): {url}")
            skipped_count += 1
        else:
            filtered_urls.append((url, output_file_path))

    logging.info(f"Processing {gender} - {category} ({len(filtered_urls)} URLs to scrape, {skipped_count} skipped)")

    if not filtered_urls:
        logging.info(f"No URLs to scrape for {gender}/{category}")
        return

    # Split filtered URLs into NUM_BROWSERS chunks
    url_chunks = chunk_list(filtered_urls, NUM_BROWSERS)
    progress = tqdm(total=len(filtered_urls), desc=f"{gender}/{category}", unit="url")

    def worker(browser_id, url_list):
        """Worker function to process a chunk of URLs."""
        results = []
        for url, output_file_path in url_list:
            result = scrape_page_data(url, output_file_path, browser_id)
            results.append(result)
            progress.update(1)
        return results

    with ThreadPoolExecutor(max_workers=NUM_BROWSERS) as executor:
        futures = []
        for i in range(NUM_BROWSERS):
            futures.append(executor.submit(worker, i + 1, url_chunks[i]))

        for future in futures:
            for msg in future.result():
                logging.info(msg)

    progress.close()

# Main function
def main():
    """Main function to orchestrate the scraping process."""
    # Load product URLs
    try:
        with open(product_file_path, encoding="utf-8") as f:
            product_urls = json.load(f)
    except FileNotFoundError as e:
        logging.error(f"Product URLs file not found: {e}")
        exit(1)

    # Log total URLs
    total_urls = sum(len(urls) for categories in product_urls.values() for urls in categories.values())
    logging.info(f"Total URLs to process: {total_urls}")

    # Process each gender and category
    for gender, categories in product_urls.items():
        for category, urls in categories.items():
            process_category(gender, category, urls)

    logging.info("Scraping completed.")

if __name__ == "__main__":
    main()