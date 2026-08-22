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
        json_path = date_subfolder / 'Json_data' / gender / category
        json_path.mkdir(parents=True, exist_ok=True)
        with open(json_path / f'{name}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")


def check_file(gender, category, name, date_subfolder):
    """Check if JSON file already exists."""
    return (date_subfolder / 'Json_data' / gender / category / f'{name}.json').exists()


async def process_urls(page, gender, category, urls, date_subfolder):
    """Process each product URL."""
    for url in urls:
        name = url.split("/")[-1]
        if check_file(gender, category, name, date_subfolder):
            continue

        try:
            await page.goto(url, timeout=30000)
            await asyncio.sleep(2)
            product_data = {"url": url}

            # --- Extract script[12] using XPath ---
            script_element = await page.query_selector('//html/body/script[12]')
            if script_element:
                script_text = await script_element.text_content()
                if script_text:
                    try:
                        match = re.search(r"const\s+pro\s*=\s*(\{.*?\});", script_text, re.DOTALL)
                        if match:
                            js_object = match.group(1)

                            cleaned = js_object.strip().rstrip(";")
                            try:
                                json_from_script = json.loads(cleaned)
                            except json.JSONDecodeError:
                                cleaned = re.sub(r"(\w+):", r'"\1":', cleaned)
                                cleaned = cleaned.replace("'", '"')
                                json_from_script = json.loads(cleaned)

                            if isinstance(json_from_script, dict):
                                product_data.update(json_from_script)
                            elif isinstance(json_from_script, list):
                                for obj in json_from_script:
                                    if isinstance(obj, dict):
                                        product_data.update(obj)
                        else:
                            logging.warning(f"No 'const pro' object found in script[12] for {url}")
                    except Exception as e:
                        logging.warning(f"Error parsing script[12] for {url}: {e}")
                else:
                    logging.warning(f"script[12] found but empty for {url}")
            else:
                logging.warning(f"No script[12] found for {url}")

            # --- Parse full HTML for JSON-LD and size availability ---
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            # --- Extract JSON-LD (if available) ---
            data_tag = soup.find("script", attrs={"type": "application/ld+json"})
            if data_tag and data_tag.string:
                try:
                    json_data = json.loads(data_tag.string)
                    if isinstance(json_data, dict):
                        product_data.update(json_data)
                    elif isinstance(json_data, list):
                        for obj in json_data:
                            if isinstance(obj, dict):
                                product_data.update(obj)
                except json.JSONDecodeError:
                    pass  
            save_json(gender, category, name, product_data, date_subfolder)

        except Exception as e:
            logging.error(f"Error processing URL {url}: {e}")
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

    semaphore = asyncio.Semaphore(4)

    async with async_playwright() as p:
        tasks = [
            limited_process_gender_section(p, gender, categories, date_subfolder, semaphore)
            for gender, categories in urls_dict.items()
        ]
        await asyncio.gather(*tasks)

    logging.info(f"{country} products completed.")


if __name__ == "__main__":
    asyncio.run(main())
