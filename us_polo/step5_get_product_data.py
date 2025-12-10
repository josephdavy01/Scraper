import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def save_json(gender, category, name, json_data, date_subfolder):
    try:
        json_file_path = date_subfolder / 'Json_data' / gender / category
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{name}.json', 'w', encoding='utf-8') as outfile:
            json.dump(json_data, outfile, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")

def check_file(gender, category, name, date_subfolder):
    file_path = date_subfolder / 'Json_data' / gender / category / f'{name}.json'
    return file_path.exists()

async def process_url_in_own_browser(playwright, gender, category, url, date_subfolder):
    name = url.strip('/').split('/')[-1]
    if check_file(gender, category, name, date_subfolder):
        logging.info(f"Skipping existing file: {name}")
        return
    
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()

    try:
        await page.goto(url, timeout=20000)
        await page.wait_for_timeout(2000)
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        json_data = {}
        product_tag = soup.find("script", {"id": "glood-loader"})
        if product_tag:
            try:
                product_string = str(product_tag).split("product:")[1].split("collection:")[0].strip()[:-1]
                product = json.loads(product_string)
                json_data["product"] = product
            except Exception as e:
                logging.warning(f"Product parse failed for {name}: {e}")

        swatch_tag = soup.find("ul", {"class": "swatch-product-container"})
        if swatch_tag:
            variants = [li.get("data-product-url") for li in swatch_tag.find_all("li") if li.get("data-product-url")]
            json_data["variants"] = variants

        descriptions = {}
        wrapper_tag = soup.find("div", {"class": "pdp-clps-wrapper"})
        if wrapper_tag:
            try:
                desc_items = wrapper_tag.find_all("div", {"class": "pdp-clps-item"})
                for item in desc_items:
                    header = item.find("div", {"class": "pdp-clps-header"})
                    if header and "Description" in header.get_text():
                        content = item.find("div", {"class": "pdp-clps-content"})
                        if content:
                            desc_tags = content.find_all("span", {"class": "metafield-multi_line_text_field"})
                            descriptions["description"] = desc_tags[-1].get_text(strip=True) if desc_tags else None
                        break
            except:
                descriptions["description"] = None

            try:
                comp_items = wrapper_tag.find_all("div", {"class": "pdp-clps-item"})
                for item in comp_items:
                    header = item.find("div", {"class": "pdp-clps-header"})
                    if header and "Composition" in header.get_text():
                        content = item.find("div", {"class": "pdp-clps-content"})
                        if content:
                            comp_tag = content.find("span", {"class": "metafield-multi_line_text_field"})
                            if comp_tag:
                                parts = [part.strip() for part in comp_tag.get_text().split('|') if part.strip()]
                                composition = ' | '.join(parts)
                            else:
                                composition = None
                        descriptions["composition"] = composition
                        break
            except:
                descriptions["composition"] = None


            try:
                terms_items = wrapper_tag.find_all("div", {"class": "pdp-clps-item"})
                for item in terms_items:
                    header = item.find("div", {"class": "pdp-clps-header"})
                    if header and "Terms" in header.get_text():
                        content = item.find("div", {"class": "pdp-clps-content"})
                        if content:
                            content_text = content.get_text()
                            if "Country of Origin:" in content_text:
                                origin = content_text.split("Country of Origin:")[-1].strip().lower()
                                origin = origin.split('\n')[0].strip().lower()
                                descriptions["origin"] = origin
                            else:
                                descriptions["origin"] = None
                        break
            except:
                descriptions["origin"] = None

        json_data["descriptions"] = descriptions
        save_json(gender, category, name, json_data, date_subfolder)
        logging.info(f"Saved: {gender} / {category} / {name}")

    except Exception as e:
        logging.error(f" Error processing URL {url}: {e}")
    finally:
        await page.close()
        await context.close()
        await browser.close()

async def main():
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    # today_str='2025-12-02'
    country = 'India'
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / f'Item_urls/{country}_product_urls.json'
    if not file_path.exists():
        logging.error(f"Missing file: {file_path}")
        return

    with open(file_path) as json_file:
        urls_dict = json.load(json_file)

    tasks = []
    for gender, categories in urls_dict.items():
        for category, urls in categories.items():
            for url in urls:
                tasks.append((gender, category, url))

    sem = asyncio.Semaphore(6)

    async with async_playwright() as playwright:
        async def sem_worker(gender, category, url):
            async with sem:
                await process_url_in_own_browser(playwright, gender, category, url, date_subfolder)

        await asyncio.gather(*(sem_worker(g, c, u) for g, c, u in tasks))

    logging.info("All scraping tasks completed.")

if __name__ == "__main__":
    asyncio.run(main())
