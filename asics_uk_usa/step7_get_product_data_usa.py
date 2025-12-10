import os
import json
import re
import logging
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import random

# --- Log Configuration ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# File Handler
file_handler = logging.FileHandler('log.txt', mode='a', encoding='utf-8')
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

# --- Helper Functions ---

def sanitize_folder_name(folder_name):
    sanitized = re.sub(r'[<>:"/\\|?*&]', '_', folder_name)
    sanitized = sanitized.rstrip('. ')
    return sanitized

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
    safe_category = sanitize_folder_name(category)
    return os.path.exists(f'{date_subfolder}/Json_data/{gender}/{safe_category}/{name}.json')

def extract_html_data(soup, url):
    data = soup.select_one('main#maincontent.ov-x_hidden.d_contents')
    if data is None:
        logging.warning(f"No product main section found for {url}. Skipping.")
        return None

    title_elem = data.find('h1', class_='text--variant_heading4')
    product_title = title_elem.get_text(strip=True) if title_elem else ''

    images = set()
    image_tag = data.find('div', attrs={'data-test': 'pdp-image-gallery-grid'})
    if image_tag:
        image_tags = image_tag.find_all('img')
        image_urls = [img.get('src') for img in image_tags if img.get('src')]
        images.update(image_urls)

    breadcrumbs = [
        a.get_text(strip=True)
        for a in data.find_all('a', class_='breadcrumbs__link')
    ]
    breadcrumb_text = breadcrumbs[-1] if breadcrumbs else ''

    price, sale_price = '', ''
    price_elem = data.select_one('div[data-test="product-price"]')
    
    if price_elem:
        orig_elem = price_elem.select_one('span.product-list-price')
        sale_elem = price_elem.select_one('span.product-sale-price')
        
        if orig_elem and sale_elem:
            price = orig_elem.get_text(strip=True)
            sale_price = sale_elem.get_text(strip=True)
        else:
            price = price_elem.get_text(strip=True)
            sale_price = price

    color_elem = data.find('p', attrs={'data-test': 'pdp-selected-color'})
    color = color_elem.get_text(strip=True) if color_elem else ''

    sizes = []
    buttons = data.find_all('button', attrs={'data-test': 'size-button'})
    for btn in buttons:
        size_name = btn.get_text(strip=True)
        in_stock = btn.get('data-instock') == 'true'
        sizes.append({
            'size_name': size_name,
            'in_stock': in_stock
        })
    
    accordion_sections = {}
    accordion_root = data.find('div', class_='accordion__root')

    if accordion_root:
        accordion_items = accordion_root.find_all('div', class_='accordion__item')
        
        for item in accordion_items:
            header = item.find('button')
            title = ''
            if header:
                title_elem = header.find('h2', class_='text--variant_heading4')
                if title_elem:
                    title = title_elem.get_text(strip=True)
            if not title:
                h2_any = header.find('h2') if header else None
                if h2_any:
                    title = h2_any.get_text(strip=True)
            
            content = ''
            content_div = item.find('div', class_='accordion__content')
            if content_div:
                inner_content = []
                sub_items = content_div.find_all('div', class_='d_flex')
                if sub_items:
                    for sub in sub_items:
                        sub_title = sub.find('h2')
                        sub_text = sub.find('div')
                        if sub_title and sub_text:
                            inner_content.append(f"{sub_title.get_text(strip=True)}: {sub_text.get_text(strip=True)}")
                        elif sub_title:
                            inner_content.append(sub_title.get_text(strip=True))
                        elif sub_text:
                            inner_content.append(sub_text.get_text(strip=True))
                    content = "\n".join(inner_content)
                else:
                    content = content_div.get_text(separator="\n", strip=True)
            
            if title:
                accordion_sections[title] = content

    product_specs = {}
    specs_container = data.select_one('div[data-test="product-specs"]')
    if specs_container:
        spec_items = specs_container.select('div[data-test^="product-specs-item-"]')
        
        for item in spec_items:
            label_elem = item.find('p')
            value_elem = item.find('span')
            
            if label_elem and value_elem:
                product_specs[label_elem.get_text(strip=True)] = value_elem.get_text(strip=True)

    product_data = {
        'extraction_timestamp': datetime.now().isoformat(),
        'product_url': url,
        'title': product_title,
        'price': price,
        'discount_price': sale_price,
        'breadcrumb': breadcrumb_text,
        'color': color,
        'sizes': sizes,
        'images': list(images),
        'accordion_sections': accordion_sections,
        'product_specifications': product_specs
    }
    return product_data
     
# --- Main Scraper Function ---

def product_data_usa():
    # today_str = date.today().strftime('%Y-%m-%d')
    today_str = '2025-11-17'
    countries = ['USA'] 

    for country in countries:
        date_subfolder = f'{country}/Data/{today_str}'
        read_file_path = f'{date_subfolder}/Item_urls/{country}_unique_product_urls.json'

        if not os.path.exists(read_file_path):
            logging.warning(f"Missing: {read_file_path}. Skipping country {country}.")
            continue 

        with open(read_file_path, encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)

        for gender, categories in urls_dict.items():
            logging.info(f'Starting {country} {gender} section...')
            
            for category, urls in categories.items():
                if not urls:
                    logging.warning(f"No URLs found for {country} {gender} {category}. Skipping.")
                    continue
                
                logging.info(f'Starting {country} {gender} {category} section with {len(urls)} URLs...')

                # --- Loop through URLs ---
                for url in urls:
                    name = file_name(url)

                    # 1. Check if file exists BEFORE opening browser (Efficiency)
                    if check_file(gender, category, name, date_subfolder):
                        logging.info(f"skipping (already exists): {name}.json")
                        continue
                    
                    logging.info(f"Processing URL: {url}")

                    # 2. Open NEW Browser for THIS specific URL
                    try:
                        with sync_playwright() as p:
                            browser = p.firefox.launch(headless=False)
                            # Create a new context to ensure clean slate (cookies/storage) per URL if needed
                            context = browser.new_context()
                            page = context.new_page()
                            
                            try:
                                page.goto(url, wait_until='domcontentloaded', timeout=60000)

                                # --- Initial Cookie Handling (Aggressive) ---
                                try:
                                    cookie_btn = page.locator("#onetrust-accept-btn-handler")
                                    if cookie_btn.is_visible(timeout=5000):
                                        cookie_btn.click()
                                        # Wait for overlay to disappear
                                        page.wait_for_selector('.onetrust-pc-dark-filter', state='hidden', timeout=3000)
                                except Exception:
                                    pass

                                # --- RTM Close ---
                                try:
                                    rtm_close_selector = 'div[data-sc-action="close"]'
                                    if page.locator(rtm_close_selector).is_visible():
                                        page.locator(rtm_close_selector).click(timeout=5000)
                                        page.wait_for_timeout(500) 
                                except Exception:
                                    pass

                                # --- Accordion Handling (Robust with Retry) ---
                                button_selector = 'div[data-test="product-specs-tabs"] button.accordion__trigger'
                                try:
                                    # Wait slightly for dynamic load
                                    page.wait_for_timeout(2000) 
                                    
                                    if page.locator(button_selector).count() > 0:
                                        logging.info("Accordion found. Clicking all sections...")
                                        accordion_buttons = page.locator(button_selector).all()
                                        
                                        for button in accordion_buttons:
                                            if button.is_visible():
                                                try:
                                                    # Attempt Normal Click
                                                    button.click(timeout=2000)
                                                except Exception:
                                                    # Click Intercepted? Check for Cookie Banner again!
                                                    logging.info("Click intercepted. Checking for popup...")
                                                    try:
                                                        popup_btn = page.locator("#onetrust-accept-btn-handler")
                                                        if popup_btn.is_visible():
                                                            popup_btn.click()
                                                            page.wait_for_timeout(1000)
                                                        
                                                        # Retry click with FORCE
                                                        button.click(force=True, timeout=2000)
                                                    except Exception as retry_e:
                                                        logging.warning(f"Retry failed for accordion: {retry_e}")

                                                page.wait_for_timeout(300)
                                    
                                    # Verification (optional)
                                    try:
                                        page.wait_for_selector('div[data-state="open"]', timeout=3000)
                                    except:
                                        pass 

                                except Exception as e:
                                    logging.warning(f"Accordion issue for {url}: {e}")

                                # --- Popup Handling (InMoment) ---
                                inmoment_overlay_selector = 'section[id^="_im_iframe_overlay"]'
                                try:
                                    popup = page.query_selector(inmoment_overlay_selector) 
                                    if popup: 
                                        viewport = page.viewport_size or {'width': 1920, 'height': 1080}
                                        x = viewport['width'] - 10
                                        y = viewport['height'] - 10 
                                        page.mouse.click(x, y) 
                                        page.wait_for_timeout(1000)
                                except Exception:
                                    pass

                                # --- View More Images ---
                                try:
                                    view_more_sel = 'button[data-test="pdp-image-gallery-view-more"]'
                                    if page.locator(view_more_sel).is_visible():
                                        logging.info("View More button found. Clicking...")
                                        view_more_buttons = page.locator(view_more_sel).all()
                                        for button in view_more_buttons:
                                            if button.is_visible():
                                                button.click()
                                                page.wait_for_timeout(200)
                                except Exception:
                                    pass

                                # --- Extraction ---
                                page_html = page.content()
                                if not page_html:
                                    logging.warning(f"Skipping {url} due to fetch error.")
                                else:
                                    soup = BeautifulSoup(page_html, 'html.parser')
                                    result = extract_html_data(soup, url)

                                    if result is None:
                                        logging.info(f"Data extraction returned None for {url}")
                                    else:
                                        save_json(gender, category, name, result, date_subfolder)
                                        logging.info(f"Successfully processed: {name}.json")

                            except Exception as e:
                                logging.error(f"Error inside browser processing for {url}: {e}", exc_info=True)
                            
                            finally:
                                # 3. Close browser strictly after each URL
                                context.close()
                                browser.close()
                                logging.info(f"Browser closed for: {name}")

                    except Exception as e:
                        logging.error(f"Failed to launch Playwright for {url}: {e}")

                logging.info(f'{country} {gender} {category} section complete.')
        
        logging.info(f'{country} products completed.')

if __name__ == "__main__":
    product_data_usa()