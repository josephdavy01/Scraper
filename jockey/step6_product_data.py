import os
import json
import re
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import time
import random
import asyncio
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

today = datetime.today().strftime("%Y-%m-%d")
country = "India"
BASE_DIR = os.path.join(country, today)
PRODUCTS_JSON = os.path.join(country, today, "Item_urls", f"{country.lower()}_unique_product_urls.json")


async def process_node(node, path_parts, results=None):
    if results is None:
        results = []
    
    if isinstance(node, dict):
        for key, value in node.items():
            clean_key = key.strip()
            await process_node(value, path_parts + [clean_key], results)

    elif isinstance(node, list):
        for item in node:
            await process_node(item, path_parts, results)

    elif isinstance(node, str) and node.startswith("http"):
        result = await save_product_json(node, path_parts, today)
        if result:
            results.append(result)
    
    return results


async def save_product_json(product_url, path_parts, today):
    # Save all product data into Json_data folder
    folder_path = os.path.join(BASE_DIR, "Json_data")
    os.makedirs(folder_path, exist_ok=True)

    filename = product_url.rstrip("/").split("/")[-1] + ".json"
    file_path = os.path.join(folder_path, filename)

    # Skip if file already exists
    if os.path.exists(file_path):
        print(f"Skipped (already exists)  {file_path}")
        return (True, product_url)  # Count as success

    # Retry logic for failures
    max_retries = 5

    for attempt in range(max_retries):
        try:
            await asyncio.sleep(random.uniform(2, 5))
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )
                page = await context.new_page()
                
                # Navigate to the page
                response = await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
                
                if response.status == 403:
                    await browser.close()
                    wait_time = (attempt + 1) * 10
                    print(f"403 Forbidden. Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                
                if response.status == 429:
                    await browser.close()
                    wait_time = (attempt + 1) * 10
                    print(f"429 Too Many Requests. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                if not response.ok:
                    await browser.close()
                    raise Exception(f"HTTP {response.status}")
                
                # Get the page content
                html = await page.content()
                await browser.close()
                
            break  # Success, exit retry loop
            
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed: {product_url} → {e}")
                return (False, product_url)  # Return failure
            print(f"Request failed ({e}). Retrying...")
            await asyncio.sleep(5)
            
    else:  # Loop finished without break
        print(f"Failed after {max_retries} retries: {product_url}")
        return (False, product_url)  # Return failure

    soup = BeautifulSoup(html, "html.parser")

    product_json = None

    for script in soup.find_all("script"):
        if script.string and "product_json" in script.string:
            match = re.search(
                r"(let|var)\s+product_json\s*=\s*(\{.*?\});",
                script.string,
                re.S
            )
            if match:
                product_json = json.loads(match.group(2))
                break

    variant_cards = soup.find_all("div", class_="variantCard")
    if variant_cards:
        for variant_card in variant_cards:
            temp_json = json.loads(variant_card.get('data-gtm-product-info'))
            if temp_json['name'].strip() == product_json['title'].strip():
                product_json['color_details'] = temp_json
                continue
    
    if not product_json:
        print(f"product_json not found → {product_url}")
        return (False, product_url)  # Return failure

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(product_json, f, indent=4, ensure_ascii=False)

    print(f"Saved  {file_path}")
    return (True, product_url)  # Return success


async def main():
    with open(PRODUCTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Collect all results
    results = await process_node(data, [])
    
    # Separate successful and failed URLs
    successful_urls = [url for success, url in results if success]
    failed_urls = [url for success, url in results if not success]
    all_urls = [url for _, url in results]
    
    # -------- SAVE DETAILED LOG -------- #
    log_dir = Path(f"{country}/{today}/Json_data/Logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    detailed_log_path = log_dir / f'{country.lower()}_scrape_log_detailed.json'
    detailed_log_data = {
        'scrape_date': today,
        'country': country,
        'total_urls_to_scrape': len(all_urls),
        'successful_scrapes': len(successful_urls),
        'failed_scrapes': len(failed_urls),
        'success_rate': f"{(len(successful_urls) / len(all_urls) * 100):.2f}%" if all_urls else "0%",
        'successful_urls': successful_urls,
        'failed_urls': failed_urls
    }
    
    with open(detailed_log_path, 'w', encoding='utf-8') as f:
        json.dump(detailed_log_data, f, indent=4, ensure_ascii=False)
    
    logging.info(f" SCRAPING COMPLETED SUCCESSFULLY")
    logging.info(f"Total URLs: {len(all_urls)}")
    logging.info(f"Successful: {len(successful_urls)}")
    logging.info(f"Failed: {len(failed_urls)}")
    logging.info(f"Detailed log saved to: {detailed_log_path}")


if __name__ == "__main__":
    asyncio.run(main())
