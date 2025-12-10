import os
import json
import asyncio
import logging
from datetime import date
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm_asyncio
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def get_product_urls(page, url):
    purls = []
    page_num = 1

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    while True:
        paged_url = f"{url}?page={page_num}"
        logging.info(f"Fetching: {paged_url}")
        time.sleep(2)
        await page.goto(paged_url)
        time.sleep(3)
        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        items = soup.select("li.grid__item")

        if not items:
            break  

        for item in items:
            variant_container = item.select_one(".variant-carousel-product-card")
            if variant_container:
                variant_links = item.select('div[data-product-handle-switch] a[href]')
                for a in variant_links:
                    href = a.get("href")
                    if href:
                        full_url = urljoin(base_url, href)
                        if full_url not in purls:
                            purls.append(full_url)
            else:
                a = item.select_one(".product-card-img-link, .descripton-link-product-card")
                if a and a.get("href"):
                    full_url = urljoin(base_url, a["href"])
                    if full_url not in purls:
                        purls.append(full_url)

        page_num += 1

    return purls

async def fetch_product_urls(playwright, semaphore, gender, category, url, country):
    async with semaphore:
        logging.info(f'[{gender} - {category}] Launching browser instance...')

        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security'
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            result = await get_product_urls(page, url)
        except Exception as e:
            logging.error(f'Error fetching {gender} - {category}: {e}')
            result = []
        finally:
            await page.close()
            await context.close()
            await browser.close()
            logging.info(f'[{gender} - {category}] Browser closed.')

        return gender, category, result

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    
    country = 'UAE'

    read_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json'
    if not os.path.exists(read_file_path):
        logging.error(f"Category URL file not found: {read_file_path}")
        return

    with open(read_file_path, encoding='utf-8') as json_file:
        url_dict = json.load(json_file)

    output_dir = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(output_dir, exist_ok=True)
    file_path = f'{output_dir}/{country}_product_urls.json'

    purl_list = {}
    semaphore = asyncio.Semaphore(3)

    async with async_playwright() as p:
        all_tasks = []
        for gender, categories in url_dict.items():
            for category, url in categories.items():
                all_tasks.append(fetch_product_urls(p, semaphore, gender, category, url, country))

        results = await tqdm_asyncio.gather(*all_tasks, desc="Fetching product URLs", total=len(all_tasks))

        for gender, category, links in results:
            if gender not in purl_list:
                purl_list[gender] = {}
            purl_list[gender][category] = links

    with open(file_path, "w", encoding='utf-8') as outfile:
        json.dump(purl_list, outfile, ensure_ascii=False, indent=4)

    print(f'{country} product URLs fetched and saved to {file_path}')

if __name__ == "__main__":
    asyncio.run(main())
