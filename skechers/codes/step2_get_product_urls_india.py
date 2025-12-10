import os
import json
import asyncio
import logging
import traceback
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(message)s')

today_str = date.today().strftime('%Y-%m-%d')
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

def matches_title_with_url_segment(href, title):
    if not href or not title:
        return False
    
    if not href.endswith('.html'):
        return False
    
    url_parts = href.split('/')
    segments = []
    for part in url_parts:
        if (part and 
            not part.startswith('http') and 
            part not in ['www.skechers.in', ''] and
            not part.endswith('.html')):
            segments.append(part)
    
    title_first = title[0].upper() if title else ''
    
    for segment in segments:
        if segment and segment[0].upper() == title_first:
            return True
    
    return False

async def find_urls(page, url, initial, country, gender, category):
    urls_set, page_num = set(), 0 
    previous_page_urls = set() 

    try:
        while True:
            page_url = f"{url}?start={page_num}"
            logging.info(f"Fetching: {page_url}")

            try:
                await page.goto(page_url, timeout=60000)
                await page.wait_for_selector("a[href$='.html'][title][tabindex]", timeout=10000)
                soup = BeautifulSoup(await page.content(), "html.parser")
                
                slick_track = soup.find('div', class_='slick-track')
                
                a_tags = soup.find_all('a', attrs={
                    'href': lambda href: href and href.endswith('.html'),
                    'title': True, 
                    'tabindex': True
                })
                
                logging.info(f"Found {len(a_tags)} anchors ending with .html on page {page_num}")

                if not a_tags:
                    if slick_track:
                        logging.info(f"No anchors but container present on page {page_num} - continuing")
                    else:
                        logging.info(f"pagination end {page_num} {page_url} - no anchors and no containers")
                        break
                elif not slick_track:
                    logging.info(f"pagination end {page_num} {page_url} - slick-track not found")
                    break

                page_urls_set = set() 
                for a in a_tags:
                    href = a.get('href')
                    title = a.get('title')
                    tabindex = a.get('tabindex')

                    if matches_title_with_url_segment(href, title):
                        if href.startswith('/'):
                            href = initial.rstrip('/') + href
                        elif not href.startswith('http'):
                            href = initial.rstrip('/') + '/' + href

                        page_urls_set.add(href)

                if page_num > 0 and page_urls_set == previous_page_urls:
                    logging.info(f"Same URLs found on page {page_num} as previous page - moving to next category")
                    break

                if page_num > 0 and page_urls_set.issubset(previous_page_urls):
                    logging.info(f"Current page URLs are subset of previous page - moving to next category")
                    break

                urls_set.update(page_urls_set)

                if page_urls_set:
                    try:
                        out_dir  = f'{country}/Data/{today_str}/Item_urls'
                        os.makedirs(out_dir, exist_ok=True)

                        # Convert set to sorted list for JSON
                        page_urls_list = sorted(list(page_urls_set))
                        logging.info(f"saved {len(page_urls_list)} unique URLs from page {page_num} for {gender} > {category}")
                    except Exception as e:
                        logging.error(f"Error saving page {page_num} data: {e}")

                previous_page_urls = page_urls_set.copy()

            except PlaywrightTimeout:
                logging.warning(f"Timeout / no anchors on page {page_num}. Stopping.")
                break

            page_num += 24

    except Exception:
        logging.error("Exception while scraping product URLs:")
        traceback.print_exc()

    return sorted(list(urls_set))

async def main():
    countries = {
        'India': 'https://www.skechers.in/'
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        for country, initial in countries.items():
            purls = {}
    
            try:
                cat_file = f'{country}/Data/{today_str}/Item_urls/category_urls.json'
                with open(cat_file, encoding='utf-8') as jf:
                    suburls = json.load(jf)
                logging.info(f"Loaded categories for {country}")
            except Exception as e:
                logging.error(f"Unable to read {cat_file}: {e}")
                continue

            for gender, categories in suburls.items():
                purls[gender] = {}
                for category, url in categories.items():
                    logging.info(f"Scraping  {gender}  >  {category}")
                    urls = await find_urls(page, url, initial, country, gender, category)
                    purls[gender][category] = urls

                    # Save after each category
                    try:
                        out_dir  = f'{country}/Data/{today_str}/Item_urls'
                        os.makedirs(out_dir, exist_ok=True)
                        out_file = f'{out_dir}/{country}_product_urls.json'

                        with open(out_file, 'w', encoding='utf-8') as f:
                            json.dump(purls, f, ensure_ascii=False, indent=4)
                        logging.info(f"Saved {len(urls)} unique URLs for {gender} > {category}")
                    except Exception as e:
                        logging.error(f"Error saving {gender} > {category}: {e}")
 
            if purls:
                try:
                    out_dir  = f'{country}/Data/{today_str}/Item_urls'
                    os.makedirs(out_dir, exist_ok=True)
                    out_file = f'{out_dir}/{country}_product_urls.json'

                    with open(out_file, 'w', encoding='utf-8') as f:
                        json.dump(purls, f, ensure_ascii=False, indent=4)
                    logging.info(f"{country} product URLs saved to {out_file}")
                except Exception as e:
                    logging.error(f"Final save error for {country}: {e}")
            else:
                logging.warning(f"No product URLs scraped for {country}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
