import os
import json
import asyncio
import logging
import traceback
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

today_str = date.today().strftime('%Y-%m-%d')
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

pop_key = ['countries.html', 'help-center.html', 'shoefinder.html', 'store-locator.html','WorkShoes_Certificates.html']

async def find_urls(page, url, initial, country, gender, category, out_dir):
    urls_set, page_num = set(), 0
    previous_page_urls = set()
    try:
        while True:
            separator = '&' if '?' in url else '?'
            page_url = f"{url}{separator}start={page_num}"

            logging.info(f"Fetching: {page_url}")
            try:
                await page.goto(page_url, wait_until='load',timeout=150000)
            except TimeoutError:
                print(f"Timeout loading: {page_url}")
                return[]
            soup = BeautifulSoup(await page.content(), "html.parser")
            a_tags = soup.find_all('a', attrs={'href': lambda href: href and href.endswith('.html')})
            if a_tags:
                for a in a_tags:
                    href = a.get('href', '')
                    if href.endswith(tuple(pop_key)):
                        continue
                    href_abs = urljoin(initial, href)
                    urls_set.add(href_abs)
                logging.info(f"Found {len(a_tags)} anchors ending with .html on page {page_num}")
                if urls_set == previous_page_urls:
                    logging.info("No new URLs found, ending pagination.")
                    break
                previous_page_urls = urls_set.copy()
                page_num += 12
            else:
                logging.info(f"No .html anchors found on page {page_num}. Breaking loop.")
                break
            logging.debug(str(a_tags))
    except Exception:
        logging.error("Exception while scraping product URLs:")
        traceback.print_exc()
    logging.info(f"Returning {len(urls_set)} URLs from find_urls")
    return sorted(list(urls_set))

async def scrape_country(p, country, initial):
    purls = {}
    browser = await p.chromium.launch(headless=False)
    page = await browser.new_page(viewport={"width": 1920, "height": 1080})

    try:
        cat_file = f'{country}/Data/{today_str}/Item_urls/category_urls.json'
        with open(cat_file, encoding='utf-8') as jf:
            suburls = json.load(jf)
        logging.info(f"Loaded categories for {country}")
    except Exception as e:
        logging.error(f"Unable to read {cat_file}: {e}")
        await browser.close()
        return

    for gender, categories in suburls.items():
        purls[gender] = {}
        for category, url in categories.items():
            logging.info(f"Scraping  {gender}  >  {category}")
            out_dir = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(out_dir, exist_ok=True)

            try:
                urls = await find_urls(page, url, initial, country, gender, category, out_dir)
                purls[gender][category] = urls

                # Save after each category
                out_file = f'{out_dir}/{country}_product_urls.json'
                with open(out_file, 'w', encoding='utf-8') as f:
                    json.dump(purls, f, ensure_ascii=False, indent=4)
                logging.info(f"Saved {len(urls)} unique URLs for {gender} > {category}")
            except Exception as e:
                logging.error(f"Error scraping or saving {gender} > {category}: {e}")
                traceback.print_exc()

    if purls:
        try:
            out_file = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(purls, f, ensure_ascii=False, indent=4)
            logging.info(f"{country} product URLs saved to {out_file}")
        except Exception as e:
            logging.error(f"Final save error for {country}: {e}")
    else:
        logging.warning(f"No product URLs scraped for {country}")

    await browser.close()

async def main():
    countries = {
        'UK': 'https://www.skechers.co.uk/',
        'USA': 'https://www.skechers.com/'
    }

    async with async_playwright() as p:
        tasks = [
            scrape_country(p, country, initial)
            for country, initial in countries.items()
        ]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
