import json
import logging
import asyncio
import time
from pathlib import Path
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_json(gender, category, name, json_data, date_subfolder):
    try:
        json_path = date_subfolder / 'Json_data' / gender / category
        json_path.mkdir(parents=True, exist_ok=True)
        with open(json_path / f'{name}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")
    
# Function to check if a file already exists
def check_file(gender, category, name, date_subfolder):
    return (date_subfolder / 'Json_data' / gender / category / f'{name}.json').exists()

async def process_urls(page, gender, category, urls, date_subfolder):
    max_retries = 3
    crawler_delay_ms = 0

    for url in urls:
        name = url.split("/")[-1].split("#")[0]
        if check_file(gender, category, name, date_subfolder):
            continue

        success = False
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"Fetching URL (attempt {attempt}/{max_retries}): {url}")
                await page.goto(url, timeout=100000)

                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                data_tag = soup.find("script", {"id": "__NEXT_DATA__"})

                if data_tag and data_tag.string:
                    product_data = json.loads(data_tag.string)
                    save_json(gender, category, name, product_data, date_subfolder)
                    success = True
                    break

                logging.warning(f"No product data found on attempt {attempt} for {url}")

            except Exception as e:
                logging.warning(f"Attempt {attempt} failed for {url}: {e}")
                await page.wait_for_timeout(2000)

        if not success:
            logging.error(f"Failed to fetch data after {max_retries} attempts: {url}")

        await page.wait_for_timeout(crawler_delay_ms)

# Function to process gender sections
async def process_gender_section(playwright, gender, categories, date_subfolder):
    browser = await playwright.chromium.launch(headless=False) 
    page = await browser.new_page()

    logging.info(f"Starting UK {gender} section with {len(categories)} categories...")
    for category, urls in categories.items():
        logging.info(f"  Processing category: {category} ({len(urls)} URLs)")
        await process_urls(page, gender, category, urls, date_subfolder)
    logging.info(f"UK {gender} section complete.")

    await browser.close()

# Main function to run the script
async def get_product_data_main():
    start_time = time.time()
    logging.info(f"Script started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    today_str = date.today().strftime('%Y-%m-%d')
    country = 'UK'
    logging.info(f'Now starting {country} products...')
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / 'Item_urls' / f'{country}_unique_product_urls.json'
    if not file_path.exists():
        logging.error(f"Product link JSON file not found at: {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)
    except Exception as e:
        logging.error(f"Failed to load JSON file: {e}")
        return

    async with async_playwright() as p:
        tasks = []

        for gender in ['men', 'women']:
            if gender in urls_dict:
                tasks.append(process_gender_section(p, gender, urls_dict[gender], date_subfolder))

        await asyncio.gather(*tasks)

    end_time = time.time()
    total_time = end_time - start_time
    logging.info(f"{country} products completed.")

    minutes, seconds = divmod(total_time, 60)
    logging.info(f"Script completed in {int(minutes)} minutes {int(seconds)} seconds.")

if __name__ == "__main__":
    # Run the script                
    asyncio.run(get_product_data_main())
                
