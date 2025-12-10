import os
import json
import re
import time
import asyncio
import logging
import random                            
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
semaphore = asyncio.Semaphore(8)

def sanitize_folder_name(folder_name):
    sanitized = re.sub(r'[<>:"/\\|?*&]', '_', folder_name)
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.rstrip('. ')
    return sanitized

def parse_price(price_str):
    try:
        cleaned = re.sub(r'[^\d.]', '', price_str)
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0
    
def save_json(gender, category, name, json_data, date_subfolder):
    try:
        safe_category = sanitize_folder_name(category)
        json_file_path = f'{date_subfolder}/Json_data/{gender}/{safe_category}'
        os.makedirs(json_file_path, exist_ok=True)
        with open(f'{json_file_path}/{name}.json', 'w', encoding='utf-8') as outfile:
            json.dump(json_data, outfile, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")

def file_name(url):
    last_part = url.split('/')[-1]
    sanitized = re.sub(r'[?=&]', '', last_part)
    return sanitized

def check_file(gender, category, name, date_subfolder):
    return os.path.exists(f'{date_subfolder}/Json_data/{gender}/{category}/{name}.json')

def extract_html_data(soup, url):
    title_elem = soup.find('h1', {'data-test-id': 'pdp-title'})
    title = title_elem.get_text(strip=True) if title_elem else ''
    subtitle_elem = soup.find('p', {'data-test-id': 'pdp-product-subheader'})
    subtitle = subtitle_elem.get_text(strip=True) if subtitle_elem else ''

    sale_price_elem = soup.find('span', {'data-test-id': 'item-sale-price-pdp'})
    original_price_elem = soup.find('span', {'data-test-id': 'item-price-pdp'})
    sale_price = sale_price_elem.get_text(strip=True) if sale_price_elem else ''
    original_price = original_price_elem.get_text(strip=True) if original_price_elem else ''
    
    colors = []
    color_section = soup.find('div', id='style-picker')
    if color_section:
        for color_elem in color_section.find_all('label', {'data-test-id': 'color'}):
            name_elem = color_elem.find('span', class_='sr-only')
            img_elem = color_elem.find('img')
            if name_elem:
                colors.append({
                    'name': name_elem.get_text(strip=True),
                    'image': img_elem.get('src') if img_elem else ''
                })
    
    sizes = []
    size_section = soup.find('div', {'data-test-id': 'size-picker'})
    if size_section:
        for size_elem in size_section.find_all('span', {'data-content': 'size-value'}):
            sizes.append(size_elem.get_text(strip=True))
    
    description = ''
    desc_section = soup.find('div', {'data-test-id': 'pdp-product-description'})
    if desc_section:
        text_div = desc_section.find('div', {'data-uds-child': 'text'})
        if text_div:
            description = text_div.get_text(strip=True)
    
    style_color = []
    desc_lists = soup.find_all('ul', {'data-uds-child': 'text'})
    for ul in desc_lists:
        for li in ul.find_all('li'):
            style_color.append(li.get_text(strip=True))
    
    images = set()
    gallery_section = soup.find('section', {'data-test-id': 'product-image-gallery-section'})
    if gallery_section:
        for img in gallery_section.find_all('img', src=True):
            images.add(img.get('src'))
    
    product_story = ""
    story_section = soup.find('section', id='product-story')
    if story_section:
        description_p = story_section.find('p')
        if description_p:
            product_story = description_p.get_text(strip=True)
    
    features_benefits = []
    if story_section:
        features_h2 = story_section.find('h2', string=lambda text: text and 'FEATURES' in text.upper())
        if features_h2:
            features_ul = features_h2.find_next('ul')
            if features_ul:
                features_benefits = [li.get_text(strip=True) for li in features_ul.find_all('li')]
    
    product_details = []
    if story_section:
        details_h2 = story_section.find('h2', string=lambda text: text and 'DETAILS' in text.upper())
        if details_h2:
            details_ul = details_h2.find_next('ul')
            if details_ul:
                product_details = [li.get_text(strip=True) for li in details_ul.find_all('li')]
                
    material_info = {}
    if story_section:
        material_h2 = story_section.find('h2', string=lambda text: text and 'MATERIAL' in text.upper())
        if material_h2:
            material_ul = material_h2.find_next('ul')
            if material_ul:
                for li in material_ul.find_all('li'):
                    material_text = li.get_text(strip=True)
                    if ':' in material_text:
                        key, value = material_text.split(':', 1)
                        material_info[key.strip()] = value.strip()
    
    country_of_origin = ""
    if story_section:
        origin_div = story_section.find('div', {'data-test-id': 'country-of-origin-container'})
        if origin_div:
            origin_details = origin_div.find('div', {'data-test-id': 'country-of-origin-details'})
            if origin_details:
                country_of_origin = origin_details.get_text(strip=True)
    
    breadcrumbs = []
    breadcrumb_nav = soup.find('nav', {'data-test-id': 'breadcrumb-nav'})
    if breadcrumb_nav:
        for link in breadcrumb_nav.find_all('a'):
            breadcrumbs.append(link.get_text(strip=True))
    
    return {
        'product_url': url,'title': title,'subtitle': subtitle,'sale_price': sale_price,'original_price': original_price, 'breadcrumbs': breadcrumbs,
        'colors': colors,'sizes': sizes,'images': list(images),'description': description,'style_color': style_color,'product_story': product_story,
        'features_benefits': features_benefits,'product_details': product_details, 'material_info': material_info,'country_of_origin': country_of_origin,
        'extraction_date': date.today().isoformat()
    }

class ProductWorker:
    def __init__(self, playwright):
        self.playwright = playwright
        self.browser = None
        self.context = None

    async def ensure_browser(self):
        if not self.browser:
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                # channel='chrome',
                args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                # '--window-position=-32000,0'
                ]

            )
            
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
            
            self.context = await self.browser.new_context(
                user_agent=random.choice(user_agents),
                locale='en-GB',
                timezone_id='Europe/London',
                viewport={'width': 1280, 'height': 800},
                extra_http_headers={
                    "accept-language": "en-GB,en;q=0.9",
                    "referer": "https://www.google.com"
                }
            )
            
            stealth_js = """
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en'] });
            window.chrome = window.chrome || { runtime: {} };
            """
            await self.context.add_init_script(stealth_js)

    async def process_url(self, url, gender, category, date_subfolder):
        name = file_name(url)
        if check_file(gender, category, name, date_subfolder):
            logging.info(f"skipping: {name}.json")
            return url

        try:
            await self.ensure_browser()
            page = await self.context.new_page()
            await page.goto(url)
            await asyncio.sleep(15)

            try:
                await page.wait_for_selector('h1[data-test-id="pdp-title"]', timeout=150000)
                await page.wait_for_selector('span[data-test-id="item-price-pdp"]', timeout=150000)
                await page.wait_for_selector('div[id="style-picker"]', timeout=150000)
            except:
                pass

            await page.wait_for_load_state('domcontentloaded', timeout=150000)
            content = await page.content()

            soup = BeautifulSoup(content, 'html.parser')
            result = extract_html_data(soup, url)

            sale_price = parse_price(result.get('sale_price', ''))
            original_price = parse_price(result.get('original_price', ''))
            title = result.get('title', '').strip()

            if (sale_price == 0.0 and original_price == 0.0) or not title:
                logging.warning(f"Skipping saving JSON for {name} due to zero price or missing title.")
                await page.close()
                return url

            save_json(gender, category, name, result, date_subfolder)

            await page.close()
            return url

        except Exception as e:
            logging.error(f"Error processing URL {url}: {e}")
            return None

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

async def worker(worker_id, task_queue, date_subfolder):
    async with async_playwright() as playwright:
        worker_scraper = ProductWorker(playwright)
        
        while not task_queue.empty():
            try:
                async with semaphore:
                    gender, category, url = await task_queue.get()
                    await worker_scraper.process_url(url, gender, category, date_subfolder)
                    task_queue.task_done()
            except Exception as e:
                logging.error(f"Worker {worker_id} error: {e}")
        
        await worker_scraper.close()

async def process_urls(gender, category, urls, date_subfolder):
    task_queue = asyncio.Queue()
    
    for url in urls:
        task_queue.put_nowait((gender, category, url))
    
    workers = [asyncio.create_task(worker(i, task_queue, date_subfolder)) for i in range(8)]
    await asyncio.gather(*workers)

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str= '2025-12-08'

    countries = ['INDIA']

    for country in countries:
        date_subfolder = f'{country}/Data/{today_str}'
        read_file_path = f'{date_subfolder}/Item_urls/{country}_unique_product_urls.json'

        if not os.path.exists(read_file_path):
            logging.warning(f"Missing: {read_file_path}")
            continue

        with open(read_file_path, encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)

        for gender, categories in urls_dict.items():
            logging.info(f'Starting {country} {gender} section...')
            for category, urls in categories.items():
                logging.info(f'Starting {country} {gender} {category} section...')
                await process_urls(gender, category, urls, date_subfolder)
                logging.info(f'{country} {gender} {category} section complete.')
            logging.info(f'{country} {gender} section complete.')

        logging.info(f'{country} products completed.')

if __name__ == "__main__":
    asyncio.run(main())