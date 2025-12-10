import asyncio
import json
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def get_urls(page, url):
    urls = []
    try:
        await page.goto(url, wait_until="domcontentloaded");
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        grid = soup.find('div', {'class': 'products-list-productGrid MuiBox-root mui-0'})
        if grid:
            for a in grid.find_all('a'):
                href = a.get('href')
                if href:
                    urls.append('https://www.primark.com' + href)
        else:
            logging.warning(f"No grid found at {url}")
        return list(set(urls))
    except Exception as e:
        logging.error(f"Error fetching URLs from {url}: {e}")
        return []

async def process_categories(page, category, curl, gender, country, item_file, count_file):
    total = 0
    curls = []
    try:
        await page.goto(curl,wait_until="domcontentloaded" )
        await page.wait_for_timeout(6000)
        await page.set_viewport_size({'width': 1665 , 'height': 915})


        soup = BeautifulSoup(await page.content(), 'html.parser')
        count_tag = soup.find('p', {'class': 'MuiTypography-root MuiTypography-body2 title-caption mui-4k385d'})

        if not count_tag:
            logging.warning(f"No count tag for category {category}")
            return

        total = int(count_tag.text.strip().split(' ')[0])
        pages = (total + 23) // 24

        logging.info(f"Processing: {country} > {gender} > {category} ({total} products)")

        for i in range(2, pages + 1):
            url = f"{curl}?page={i}"
            urls = await get_urls(page, url)
            if not urls:
                logging.info(f"No products found on page {i} of {category}. Ending pagination.")
                break
            curls.extend(urls)

        # Load existing data
        if item_file.exists():
            with open(item_file, 'r', encoding='utf-8') as f:
                item_data = json.load(f)
        else:
            item_data = {}

        if count_file.exists():
            with open(count_file, 'r', encoding='utf-8') as f:
                count_data = json.load(f)
        else:
            count_data = {}

        # Ensure nested keys exist
        item_data.setdefault(gender, {})[category] = curls
        count_data.setdefault(gender, {})[category] = total

        # Save immediately
        with open(item_file, 'w', encoding='utf-8') as f:
            json.dump(item_data, f, ensure_ascii=False, indent=4)

        with open(count_file, 'w', encoding='utf-8') as f:
            json.dump(count_data, f, ensure_ascii=False, indent=4)

        logging.info(f"Saved {len(curls)} URLs for {category}")

    except Exception as e:
        logging.error(f"Failed processing {category}: {e}")

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.now().strftime('%A')

    countries = ['UK'] if day in ['Monday', 'Wednesday', 'Friday'] else ['USA'] if day in ['Tuesday', 'Thursday', 'Saturday'] else []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, 
            args=[ "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                ]
            )
        context = await browser.new_context()
        page = await context.new_page()

        for country in countries:
            try:
                base_dir = Path(country) / 'Data' / today_str
                item_file = base_dir / 'Item_urls' / f'{country}_product_urls.json'
                count_file = base_dir / 'Validation' / f'{country}_product_counts.json'
                item_file.parent.mkdir(parents=True, exist_ok=True)
                count_file.parent.mkdir(parents=True, exist_ok=True)

                category_json = Path(f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json')
                if not category_json.exists():
                    logging.error(f"Missing category file: {category_json}")
                    continue

                with category_json.open('r', encoding='utf-8') as f:
                    data = json.load(f)

                for gender, categories in data.items():
                    for category, curl in categories.items():
                        await process_categories(page, category, curl, gender, country, item_file, count_file)

            except Exception as e:
                logging.error(f"Failed processing {country}: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())