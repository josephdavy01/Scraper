import json
import logging
import os
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ---------------- SETUP LOGGING ---------------- #
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------- IMAGE HELPERS ---------------- #
def ensure_https(url, base=None):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/") and base:
        return base.rstrip("/") + url
    return url

def force_width_1080(url):
    return url.replace("w=600", "w=1080").replace("w=480", "w=1080")

# ---------------- SAVE HANDLES ---------------- #
def save_handles(handles, handles_file_path):
    with open(handles_file_path, 'w', encoding="utf-8") as f:
        json.dump(sorted(set(handles)), f, indent=4, ensure_ascii=False)

# ---------------- IMAGE EXTRACTION ---------------- #
def extract_images_from_soup(soup, base):
    imgs = []

    slide_divs = soup.select("div.product-main-slide")
    for slide in slide_divs:
        img_tag = slide.find("img")
        if not img_tag:
            continue

        srcset = img_tag.get("srcset")
        if not srcset:
            continue

        for part in srcset.split(","):
            part = part.strip()
            if "1080w" in part:
                img_url = part.split()[0].strip()
                img_url = ensure_https(img_url, base)
                img_url = force_width_1080(img_url)

                if img_url not in imgs:
                    imgs.append(img_url)

    return imgs

# ---------------- DESCRIPTION ---------------- #
def description(soup):
    data = []

    containers = soup.find_all(
        'div',
        class_='product_template_features_loop_valuesboxs_new'
    )
    if not containers:
        return None

    container = containers[1] if len(containers) >= 2 else containers[0]

    li_tags = container.find_all('li')
    for li in li_tags:
        text = li.get_text(strip=True)
        if text:
            data.append(text)

    return data if data else None

def color(soup):
    """Extract color from span with id='js-product-color'"""
    color_span = soup.find_all('span', {'id': 'js-product-color', 'class': 'option-text'})
    for span in color_span:
        color_text = span.get_text(strip=True)
        if color_text:
            return color_text

    title_tag = (
        soup.find('h1', class_='product-single__title') or
        soup.find('h2', class_='product-single__title') or
        soup.find(class_='product-single__title')
    )
    
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        if ' - ' in title_text:
            color_name = title_text.split(' - ')[-1].strip()
            return color_name
        elif '-' in title_text:
            color_name = title_text.split('-')[-1].strip()
            return color_name
    
    return None

# ---------------- FETCH PRODUCT PAGE DATA ---------------- #
async def get_product_page_data(page, handle, max_retries=3):
    product_url = f"https://xyxxcrew.com/products/{handle}"
    logging.info(f"Fetching product page: {product_url}")

    # Retry logic for page load
    for attempt in range(max_retries):
        try:
            await page.goto(product_url, wait_until="domcontentloaded", timeout=120000) 
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"Retry {attempt + 1}/{max_retries - 1} for {product_url}")
            else:
                raise  # Re-raise on final attempt
    
    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")

    base = "https://xyxxcrew.com"

    images = extract_images_from_soup(soup, base)
    desc = description(soup)
    color_data = color(soup)

    return {
        'images': images,
        'description': desc,
        'color': color_data
    }

# ---------------- SAVE GROUP DATA ---------------- #
async def save_group_data(group_data, group_handles, category_folder_path, page):

    for pid, data in group_data.items():
        handle = data['handle']

        filename = f"{category_folder_path}/{handle}.json"

        #  SKIP IF FILE ALREADY EXISTS
        if os.path.exists(filename):
            logging.info(f"Already saved, skipping: {handle}")
            continue

        if 'data' not in data:
            logging.warning(f"No data found for handle: {handle}, skipping...")
            continue

        json_data = data['data']
        json_data['group_handles'] = group_handles

        json_data['product_url'] = f'https://xyxxcrew.com/products/{handle}'

        page_data = await get_product_page_data(page, handle)

        json_data['images'] = page_data['images']

        if page_data['description']:
            json_data['description'] = page_data['description']
        
        if page_data['color']:
            json_data['color'] = page_data['color']

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)

        logging.info(f"Saved data for handle: {handle}")

# ---------------- PROCESS CATEGORY ---------------- #
async def process_category(url_list, page, handles, handles_file_path, category_folder_path, successful_urls, failed_urls):

    for url in url_list:
        try:
            logging.info(f"Processing URL: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=120000)
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            different_group_tags = soup.find_all('div', {'class': 'hb_seconday-swatcher-list'})
            if not different_group_tags:
                continue

            for group_tag in different_group_tags:

                group_handles = []
                group_data = {}
                swiper_wrapper = group_tag.find('div', {'class': 'tab-panel-grid swiper-wrapper'})
                if not swiper_wrapper:
                    swipers_div = group_tag.find('div', {'class': 'swipers'})
                    if swipers_div:
                        swiper_wrapper = swipers_div.find('div', {'class': 'tab-panel-grid swiper-wrapper'})
                    
                    if not swiper_wrapper:
                        continue

                handle_divs = swiper_wrapper.find_all('div', {'data-product-handle': True})
                
                if not handle_divs:
                    continue

                for handle_div in handle_divs:
                    handle = handle_div.get('data-product-handle')
                    pid = handle_div.get('data-product-id')

                    if not handle or not pid:
                        continue

                    if handle in handles:
                        logging.info(f" Already scraped, skipping: {handle}")
                        continue

                    pid = str(pid)
                    group_handles.append(handle)
                    group_data[pid] = {"handle": handle}

                    handles.append(handle)
                    save_handles(handles, handles_file_path)
                    logging.info(f" Added: {handle}")

                data_tags = group_tag.find_all('script', {'type': 'text/json'})

                for data_tag in data_tags:
                    if not data_tag.string:
                        continue

                    data = json.loads(data_tag.string)
                    product_id = str(data.get('product_id'))

                    if product_id in group_data:
                        group_data[product_id]['data'] = data

                await save_group_data(
                    group_data,
                    group_handles,
                    category_folder_path,
                    page
                )

        except Exception as e:
            logging.error(f"Error processing URL {url}: {str(e)}")
            failed_urls.append({"url": url, "error": str(e)})
            continue
        
        # Mark URL as successfully processed
        successful_urls.append(url)


# ---------------- MASTER RUN FUNCTION ---------------- #
async def run_xyxxcrew_scraper(country="India", headless=False):

    today_str = date.today().strftime('%Y-%m-%d')

    input_folder_path = f'{country}/{today_str}/Items_urls'
    output_folder_path = f'{country}/{today_str}/Json_data'

    input_file_path = f'{input_folder_path}/{country}_unique_product_urls.json'
    handles_file_path = f'{input_folder_path}/{country}_handles.json'

    os.makedirs(input_folder_path, exist_ok=True)
    os.makedirs(output_folder_path, exist_ok=True)

    # -------- LOAD HANDLES -------- #
    if os.path.exists(handles_file_path):
        try:
            with open(handles_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    handles = json.loads(content)
                else:
                    handles = []
        except json.JSONDecodeError:
            logging.warning(f"Invalid JSON in handles file, starting with empty list")
            handles = []
    else:
        handles = []

    # -------- LOAD INPUT URLS -------- #
    if not os.path.exists(input_file_path):
        logging.error(f"Input file not found: {input_file_path}")
        return

    with open(input_file_path, 'r', encoding='utf-8') as f:
        url_json = json.load(f)
    
    # -------- TRACKING LISTS -------- #
    successful_urls = []
    failed_urls = []
    all_urls = []
    
    # Count total URLs
    for main_category, categories in url_json.items():
        for category, url_list in categories.items():
            all_urls.extend(url_list)

    # -------- PLAYWRIGHT SESSION -------- #
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless,channel="chrome")
        context = await browser.new_context()
        page = await context.new_page()

        for main_category, categories in url_json.items():
            for category, url_list in categories.items():

                category_folder_path = f'{output_folder_path}/{main_category}/{category}'
                os.makedirs(category_folder_path, exist_ok=True)

                logging.info(f"Processing category: {category}")

                await process_category(url_list, page, handles, handles_file_path, category_folder_path, successful_urls, failed_urls)

        await page.close()
        await context.close()
        await browser.close()

    # -------- SAVE DETAILED LOG -------- #
    log_dir = Path(f"{country}/{today_str}/Json_data/Logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    detailed_log_path = log_dir / f'{country}_scrape_log_detailed.json'
    detailed_log_data = {
        'scrape_date': today_str,
        'country': country,
        'total_urls_to_scrape': len(all_urls),
        'successful_scrapes': len(successful_urls),
        'failed_scrapes': len(failed_urls),
        'success_rate': f"{(len(successful_urls) / len(all_urls) * 100):.2f}%" if all_urls else "0%",
        'successful_urls': successful_urls,
        'failed_urls': failed_urls
    }
    
    with open(detailed_log_path, 'w', encoding='utf-8') as f:
        json.dump(detailed_log_data, f, indent=4, ensure_ascii=False)
    
    logging.info(f" SCRAPING COMPLETED SUCCESSFULLY")
    logging.info(f"Total URLs: {len(all_urls)}")
    logging.info(f"Successful: {len(successful_urls)}")
    logging.info(f"Failed: {len(failed_urls)}")
    logging.info(f"Detailed log saved to: {detailed_log_path}")

# ---------------- RUN SCRIPT ---------------- #
if __name__ == "__main__":
    import asyncio
    asyncio.run(run_xyxxcrew_scraper(country="India", headless=False))
