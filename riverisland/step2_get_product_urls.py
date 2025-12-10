import asyncio
import json
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
today_str = date.today().strftime('%Y-%m-%d')
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

async def get_product_urls(page, base_url, country_prefix=""):
    linklist = []
    page_num = 1
    while True:
        await page.set_viewport_size({"width": 1920, "height": 1080})
        url = f"{base_url}&pg={page_num}" if "?" in base_url else f"{base_url}?pg={page_num}"
        logging.info(f"Fetching products from: {url}")
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("a[data-qa='product-card']", timeout=20000)
        except PlaywrightTimeoutError:
            logging.warning(f"Timeout loading page: {url}")
            break
        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        product_list = soup.find("div", {"data-qa": "product-listing"})
        if not product_list:
            logging.info(f"No product list found, stopping pagination {url}.")
            # Debug: save HTML for inspection
            with open(f"debug_{country_prefix}_no_productlist_pg{page_num}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            break
        item_tags = product_list.find_all("a", {"data-qa": "product-card"})
        if not item_tags:
            logging.info(f"No product cards found, stopping pagination {url}.")
            # Debug: save HTML for inspection
            with open(f"debug_{country_prefix}_no_cards_pg{page_num}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            break
        for item in item_tags:
            href = item.get('href')
            if href:
                full_link = f'https://www.riverisland.com{country_prefix}{href}'
                if full_link not in linklist:
                    linklist.append(full_link)
        page_num += 1
    return linklist

async def scrape_country_data(page, country, prefix):
    today = date.today().strftime('%Y-%m-%d')
    json_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json')
    if not json_path.exists():
        logging.warning(f"Missing file: {json_path}")
        return
    with open(json_path) as f:
        url_dict = json.load(f)
    logging.info(f'Fetching {country.upper()} product URLs now')
    temp_urls = {}
    output_dir = Path(f'{country}/Data/{today}/Item_urls')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{country}_product_urls.json'
    for gender, categories in url_dict.items():
        logging.info(f'Fetching {country.upper()} {gender} product URLs now')
        temp_urls.setdefault(gender, {})
        for category, url in categories.items():
            logging.info(f"  Category: {category}")
            try:
                urls = await get_product_urls(page, url, prefix)
                if urls:
                    temp_urls[gender][category] = urls
                else:
                    logging.warning(f"No products found in category: {category}")
            except Exception as e:
                logging.error(f"Error fetching category {category}: {e}")
            with open(output_file, "w") as outfile:
                json.dump(temp_urls, outfile, ensure_ascii=False, indent=4)

        logging.info(f'{country.upper()} {gender} product URLs fetched.')

    logging.info(f'{country.upper()} product URLs saved to {output_file}.')


async def main():
    async with async_playwright() as p:
        browser_uk = await p.chromium.launch(headless=False)
        browser_us = await p.chromium.launch(headless=False)
        uk_page = await browser_uk.new_page()
        us_page = await browser_us.new_page()
        tasks = [
            scrape_country_data(uk_page, "UK", ""),   
            scrape_country_data(us_page, "USA", "")  
        ]

        await asyncio.gather(*tasks)
        await browser_uk.close()
        await browser_us.close()


if __name__ == "__main__":
    asyncio.run(main())
