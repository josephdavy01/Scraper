import os
import json
import asyncio
import logging
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.async_api import async_playwright

async def run_product_urls_scraper():

    # Configure logging 
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Auto-scroll function
    async def auto_scroll(page, scroll_pause_time=1.5, max_scroll_attempts=3):
        scroll_attempts = 0
        last_height = await page.evaluate("() => document.body.scrollHeight")

        while scroll_attempts < max_scroll_attempts:
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(scroll_pause_time * 1000)

            new_height = await page.evaluate("() => document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            last_height = new_height

    # Function to get product urls from Gymshark
    async def get_product_urls(base_url, headless=False):
        product_urls = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )
            page = await browser.new_page(viewport=None)
            page_num = 0

            while True:
                url = f"{base_url}?page={page_num}"
                logging.info(f"Scraping: {url}")

                await page.set_viewport_size({"width": 1920, "height": 1080})
                await page.goto(url, timeout=10000)
                await page.wait_for_load_state("domcontentloaded")
                await auto_scroll(page)

                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                product_grid = soup.find("div", {"data-product-grid": "true"})
                if not product_grid:
                    logging.warning(f"No product grid found on page {page_num}. Ending pagination.")
                    break

                product_anchors = product_grid.find_all("a", href=True)
                valid_urls = 0

                for a_tag in product_anchors:
                    href = a_tag['href']
                    if "/products/" in href:
                        full_url = f"https://uk.gymshark.com{href}" if href.startswith("/") else href
                        if full_url not in product_urls:
                            product_urls.add(full_url)
                            valid_urls += 1

                if valid_urls == 0:
                    logging.info(f"No new product urls found on page {page_num}. Ending pagination.")
                    break

                logging.info(f"Page {page_num}: Found {valid_urls} new product urls.")
                page_num += 1

            await browser.close()
            return list(product_urls)

    # Main function to fetch product URLs
    async def main():
        with open(input_file, "r", encoding="utf-8") as f:
            url_dict = json.load(f)

        logging.info(f"Fetching {country} product URLs...")

        temp_urls = {}
        output_dir = f'{country}/Data/{today_str}/Item_urls'
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/{country}_product_urls.json"

        for gender, categories in url_dict.items():
            temp_urls.setdefault(gender, {})
            logging.info(f"Gender: {gender}")
            for category, url in categories.items():
                logging.info(f"Category: {category}")
                urls = []

                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        urls = await get_product_urls(url)
                        if urls:
                            break
                        else:
                            logging.warning(f"Attempt {attempt}: No urls found for {category}.")
                    except Exception as e:
                        logging.error(f"Attempt {attempt} failed for {category}: {e}")
                    if attempt == max_retries:
                        logging.error(f"All {max_retries} attempts failed for {category}. Proceeding with empty link list.")
                    
                unique_urls = list(set(urls))
                temp_urls[gender][category] = unique_urls

                logging.info(f"Fetched {len(unique_urls)} unique urls for {category}.")

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(temp_urls, f, indent=2)

        logging.info(f"All done! {country} product URLs saved to {output_path}")

    # === EXECUTION STARTS HERE === #

    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        global country, input_file
        country = 'UK'
        input_file = f'{country}/Data/{today_str}/Item_urls/{country}_category_links.json'

        # ALWAYS await main()
        await main()

    else:
        logging.info("Today is not a valid day for processing. Exiting script.")
