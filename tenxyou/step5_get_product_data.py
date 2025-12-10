import os
import re
import json
import logging
import asyncio
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def save_json(gender, category, name, json_data, date_subfolder):
    """Save product JSON to file."""
    try:
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name)
        json_path = date_subfolder / 'Json_data' / gender / category
        json_path.mkdir(parents=True, exist_ok=True)
        with open(json_path / f'{safe_name}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved JSON for {name}")
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")


def check_file(gender, category, name, date_subfolder):
    """Check if JSON file already exists."""
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", name)
    return (date_subfolder / 'Json_data' / gender / category / f'{safe_name}.json').exists()


async def process_urls(page, gender, category, urls, date_subfolder):
    """Process each product URL (scrape + API)."""
    API_URL = "https://api.tenxyou.com/saleor/products-by-variant-ids"

    for url in urls:
        variant_id = url.split("/")[-1].strip()
        if not variant_id:
            logging.warning(f"Skipping invalid URL: {url}")
            continue

        if check_file(gender, category, variant_id, date_subfolder):
            continue

        product_data = {"url": url, "variant_id": variant_id}

        try:
            # -------------------------------
            # Step 1: Scrape product page
            # -------------------------------
            logging.info(f" Loading page: {url}")
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            })

            await page.goto(url, timeout=45000)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)

            # Extract HTML content
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Structured data JSON (if available)
            script_tag = soup.find("script", attrs={"type": "application/ld+json"})
            if script_tag and script_tag.string:
                try:
                    json_data = json.loads(script_tag.string)
                    if isinstance(json_data, dict):
                        product_data["structured_data"] = json_data
                    elif isinstance(json_data, list):
                        product_data["structured_data"] = [obj for obj in json_data if isinstance(obj, dict)]
                except json.JSONDecodeError:
                    logging.warning(f" Malformed JSON on page: {url}")

            # Extract sizes
            size_parent = soup.find("div", id="PDP-Size")
            if size_parent:
                size_buttons = size_parent.find_all("button")
                sizes = [btn.get_text(strip=True) for btn in size_buttons if btn.get_text(strip=True)]
                sizes = [s for s in sizes if not s.lower().startswith("size")]
                if sizes:
                    product_data["available_sizes"] = sizes

            # -------------------------------
            # Step 2: Fetch API Data
            # -------------------------------
            payload = {
                "first": 10,
                "variantIds": [variant_id],
                "channel": "txy"
            }

            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.tenxyou.com",
                "Referer": "https://www.tenxyou.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }

            logging.info(f" POST → {API_URL} | ID: {variant_id}")
            response = await page.request.post(
                API_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=30000
            )

            if response.ok:
                try:
                    api_json = await response.json()
                    product_data["api_data"] = api_json
                except Exception as parse_err:
                    text = await response.text()
                    logging.error(f" Failed to parse API JSON for {variant_id}: {parse_err}\n{text[:500]}")
            else:
                text = await response.text()
                logging.error(f" API returned {response.status} for {variant_id}: {text[:500]}")

            save_json(gender, category, variant_id, product_data, date_subfolder)

        except Exception as e:
            logging.error(f"Error processing {variant_id}: {e}")
            continue


async def process_gender_section(page, gender, categories, date_subfolder):
    logging.info(f"Starting India {gender} section with {len(categories)} categories...")
    for category, urls in categories.items():
        logging.info(f"  Processing category: {category} ({len(urls)} URLs)")
        await process_urls(page, gender, category, urls, date_subfolder)
    logging.info(f"India {gender} section complete.")


async def limited_process_gender_section(p, gender, categories, date_subfolder, semaphore):
    async with semaphore:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        page = await browser.new_page()
        try:
            await process_gender_section(page, gender, categories, date_subfolder)
        finally:
            await browser.close()


async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = "2025-11-26"
    country = 'India'
    logging.info(f'Now starting {country} products...')
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / 'Item_urls' / f'{country}_unique_product_urls.json'
    if not file_path.exists():
        logging.error(f"Product link JSON file not found at: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as json_file:
        urls_dict = json.load(json_file)

    semaphore = asyncio.Semaphore(1)

    async with async_playwright() as p:
        tasks = [
            limited_process_gender_section(p, gender, categories, date_subfolder, semaphore)
            for gender, categories in urls_dict.items()
        ]
        await asyncio.gather(*tasks)

    logging.info(f"{country} products completed.")


if __name__ == "__main__":
    asyncio.run(main())
