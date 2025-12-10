import os
import json
import asyncio
import logging
import traceback
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

today_str = date.today().strftime('%Y-%m-%d')
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

file_lock = asyncio.Lock()


# ---------------------------------------------------------
# POPUP HANDLER
# ---------------------------------------------------------
async def handle_popups(page):
    try:
        await page.evaluate("""
            const modal = document.querySelector('.js-close-modal');
            if (modal) modal.click();

            const popup = document.querySelector('.popup, .overlay, .newsletter-modal');
            if (popup) popup.style.display = 'none';
        """)
        logging.info("Handled popups.")
    except Exception as e:
        logging.warning(f"Popup handling error: {e}")


# ---------------------------------------------------------
# ONLY SCROLLING FUNCTION
# ---------------------------------------------------------
async def auto_scroll(page):
    logging.info("Starting slow scroll...")
    await page.evaluate("""
        async () => {
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            let lastHeight = document.body.scrollHeight;
            let noChangeCount = 0;
            const maxAttempts = 25;

            while (noChangeCount < maxAttempts) {
                window.scrollBy(0, 500);
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


# ---------------------------------------------------------
# PRODUCT SCRAPER
# ---------------------------------------------------------
async def find_urls(page, url, initial, visited_urls: set, browser_id: str):
    urls = []
    try:
        if url in visited_urls:
            logging.info(f"[{browser_id}] Already visited {url}, skipping...")
            return urls

        visited_urls.add(url)
        logging.info(f"[{browser_id}] Visiting: {url}")

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await handle_popups(page)
        except PlaywrightTimeout as e:
            logging.warning(f"[{browser_id}] Timeout on: {url} ({e})")
            return urls

        await auto_scroll(page)
        await handle_popups(page)

        await page.wait_for_timeout(1500)

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        products = (
            soup.find_all('product-block') or
            soup.find_all('div', class_='product-block')
        )

        logging.info(f"[{browser_id}] Found {len(products)} products on {url}")

        for product in products:
            product_link = product.find('a', class_='product-link')
            if product_link:
                href = product_link.get('href')
                if href:
                    urls.append(initial + href)

        logging.info(f"[{browser_id}] Collected {len(urls)} URLs from {url}")

    except Exception as e:
        logging.error(f"[{browser_id}] Error scraping {url}: {e}")
        traceback.print_exc()

    return urls


# ---------------------------------------------------------
# CATEGORY PROCESSOR
# ---------------------------------------------------------
async def process_categories(page, categories, initial, visited_urls, purls, gender, browser_id, output_file):
    for category, url in categories.items():
        logging.info(f"[{browser_id}] Scraping {gender} → {category}")

        urls = await find_urls(page, url, initial, visited_urls, browser_id)
        purls[gender][category] = urls

        async with file_lock:
            try:
                with open(output_file, "w", encoding='utf-8') as outfile:
                    json.dump(purls, outfile, ensure_ascii=False, indent=4)
                logging.info(f"[{browser_id}] Saved: {gender} > {category}")
            except Exception as e:
                logging.error(f"[{browser_id}] Error writing JSON: {e}")

    return purls


async def scrape_product_urls():

    countries = {
        'UAE': 'https://ae.sacoorbrothers.com'
    }

    async with async_playwright() as p:

        browser1 = await p.chromium.launch(headless=False)
        browser2 = await p.chromium.launch(headless=False)

        page1 = await browser1.new_page(viewport={"width": 1344, "height": 840})
        page2 = await browser2.new_page(viewport={"width": 1344, "height": 840})

        for country, initial in countries.items():

            try:
                category_file = f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json'
                with open(category_file, encoding='utf-8') as file:
                    suburls = json.load(file)
                logging.info(f"Loaded categories for {country}")
            except Exception as e:
                logging.error(f"Error loading category file: {e}")
                continue

            output_dir = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(output_dir, exist_ok=True)

            output_file = f"{output_dir}/{country}_product_urls.json"
            purls = {}
            visited_urls = set()

            for gender in suburls:
                purls.setdefault(gender, {})

                categories_list = list(suburls[gender].items())
                mid = len(categories_list) // 2

                categories1 = dict(categories_list[:mid])
                categories2 = dict(categories_list[mid:])

                logging.info(f"Browser1 → {len(categories1)} categories")
                logging.info(f"Browser2 → {len(categories2)} categories")

                task1 = asyncio.create_task(
                    process_categories(page1, categories1, initial, visited_urls, purls, gender, "Browser1", output_file)
                )

                task2 = asyncio.create_task(
                    process_categories(page2, categories2, initial, visited_urls, purls, gender, "Browser2", output_file)
                )

                await asyncio.gather(task1, task2)

        await browser1.close()
        await browser2.close()

    logging.info(" Scraping completed successfully!")


# ---------------------------------------------------------
# RUN FUNCTION
# ---------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(scrape_product_urls())
