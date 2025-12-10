import os
import json
import re
import time  # <-- ADDED: Needed for simple test
import logging
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright  # <-- CHANGED: Use sync_api

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# --- REMOVED: No semaphore needed for a single-threaded synchronous script ---

def sanitize_folder_name(folder_name):
    """Sanitizes a string to be used as a valid folder name."""
    sanitized = re.sub(r'[<>:"/\\|?*&]', '_', folder_name)
    sanitized = sanitized.rstrip('. ')
    return sanitized

def save_json(gender, category, name, json_data, date_subfolder):
    """Saves the extracted data to a JSON file."""
    try:
        safe_category = sanitize_folder_name(category)
        json_file_path = f'{date_subfolder}/Json_data/{gender}/{safe_category}'
        os.makedirs(json_file_path, exist_ok=True)
        with open(f'{json_file_path}/{name}.json', 'w', encoding='utf-8') as outfile:
            json.dump(json_data, outfile, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")

def file_name(url):
    """Creates a sanitized file name from a URL."""
    last_part = url.split('/')[-1]
    sanitized = re.sub(r'[?=&]', '', last_part)
    return sanitized

def check_file(gender, category, name, date_subfolder):
    """Checks if a JSON file already exists for a product."""
    safe_category = sanitize_folder_name(category)
    return os.path.exists(f'{date_subfolder}/Json_data/{gender}/{safe_category}/{name}.json')

def extract_html_data(soup, url, country):
    """Extracts product data from a BeautifulSoup object."""
    images = set()
    # Select all main image spans within the slider track
    image_spans = soup.select('.slick-track span.main-image')
    for span in image_spans:
        # Extract the standard image URL from the img tag
        img_tag = span.find('img')
        if img_tag:
            image_url = img_tag.get('data-src') or img_tag.get('src')
            # Add the URL if it's not a placeholder image
            if image_url and not image_url.startswith('data:image'):
                images.add(image_url)
        
        # Extract the high-resolution zoom image URL
        zoom_image_url = span.get('data-zoom-image')
        if zoom_image_url:
            images.add(zoom_image_url)

    color_variants = []
    color_items = soup.select('.variants__item--color')
    for item in color_items:
        variant_data = {}
        color_link = item.select_one('.variants__link')
        if color_link:
            variant_data['color_url'] = color_link.get('href', '')
            variant_data['color_params'] = color_link.get('data-params', '')
            variant_data['variation_group'] = color_link.get('data-variation-group-swatch', '')
            variant_data['aria_label'] = color_link.get('aria-label', '')
            swatch_data = color_link.get('data-swatchtype', '')
            if swatch_data:
                variant_data['swatch_data'] = swatch_data
        color_img = item.select_one('.variants__img')
        if color_img:
            variant_data['color_image'] = color_img.get('src', '')
            variant_data['color_alt'] = color_img.get('alt', '')
        for attr in item.attrs:
            if attr.startswith('data-'):
                variant_data[attr] = item.get(attr)
        if variant_data:
            color_variants.append(variant_data)

    sizes = []
    size_items = soup.select('.variants__item--size')
    for item in size_items:
        size_data = {}
        for attr in item.attrs:
            size_data[attr] = item.get(attr)
        size_link = item.select_one('.variants__link')
        if size_link:
            size_data['size_url'] = size_link.get('href', '')
            size_data['size_params'] = size_link.get('data-params', '')
            size_data['aria_label'] = size_link.get('aria-label', '')
            # Only add data-* attributes from size_link
            size_data.update({f'link_{attr}': size_link.get(attr) for attr in size_link.attrs if attr.startswith('data-')})
        size_text = item.get_text(strip=True)
        if size_text:
            size_data['size_text'] = size_text
        sizes.append(size_data)

    sections = {}
    accordion_divs = soup.select('.accordion[data-section]')
    for accordion in accordion_divs:
        section_name = accordion.get('data-section', 'unknown')
        section_data = {
            'title': '',
            'content': '', 
            'structured_data': {}
        }
        title_elem = accordion.select_one('.accordion__title')
        if title_elem:
            section_data['title'] = title_elem.get_text(strip=True)
        content_elem = accordion.select_one('.accordion__content')
        if content_elem:
            section_data['content'] = content_elem.get_text(separator=' ', strip=True)

            if section_name.lower() == 'specs':
                specs = {}
                spec_items = content_elem.select('.product-specs__attribute')
                for spec in spec_items:
                    key_elem = spec.select_one('.product-specs__key')
                    value_elem = spec.select_one('.product-specs__value')
                    if key_elem and value_elem:
                        key = key_elem.get_text(strip=True)
                        value = value_elem.get_text(strip=True)
                        specs[key] = value
                section_data['structured_data'] = specs
            elif section_name.lower() == 'pronation':
                pronation_data = {}
                pronation_types = content_elem.select('.pronation-types')
                for ptype in pronation_types:
                    pronation_data[ptype.get_text(strip=True)] = True
                pronation_details = content_elem.select('.pdp-pronation__flexParent__child-details-list')
                for detail in pronation_details:
                    header = detail.select_one('.pdp-pronation__flexParent__child-details-header')
                    inner = detail.select_one('.pdp-pronation__flexParent__child-details-inner')
                    if header and inner:
                        pronation_data[header.get_text(strip=True)] = inner.get_text(strip=True)
                section_data['structured_data'] = pronation_data
        sections[section_name] = section_data

    breadcrumbs = []
    breadcrumb_items = soup.select('.breadcrumb a, .breadcrumbs a, [aria-label="Breadcrumb"] a')
    for item in breadcrumb_items:
        text = item.get_text(strip=True)
        if text:
            breadcrumbs.append(text)

    meta_data = {}
    meta_tags = soup.select('meta[itemprop], meta[property], meta[name]')
    for meta in meta_tags:
        itemprop = meta.get('itemprop')
        property_attr = meta.get('property')
        name_attr = meta.get('name')
        content = meta.get('content', '')
        if itemprop:
            meta_data[f'itemprop_{itemprop}'] = content
        if property_attr:
            meta_data[f'property_{property_attr}'] = content
        if name_attr:
            meta_data[f'name_{name_attr}'] = content

    json_ld_data = []
    scripts = soup.select('script[type="application/ld+json"]')
    for script in scripts:
        try:
            data = json.loads(script.string)
            json_ld_data.append(data)
        except Exception:
            pass

    data_attrs = {}
    main_containers = soup.select('[data-attributes], .variants, .product-tile, .pdp-top')
    for container in main_containers:
        for attr in container.attrs:
            if attr.startswith('data-'):
                data_attrs[attr] = container.get(attr)

    title = ''
    title_elem = soup.select_one('h1.pdp-top__product-name__not-ot, h1[itemprop="name"], .product-name h1')
    if title_elem:
        title = title_elem.get_text(strip=True)

    price_info = {}
    price_elem = soup.select_one('meta[itemprop="price"]')
    if price_elem:
        price_info['meta_price'] = price_elem.get('content', '')
    original_price_elem = soup.select_one('.price-standard, .price-list')
    if original_price_elem:
        price_info['original_price'] = original_price_elem.get_text(strip=True)
    sale_price_elem = soup.select_one('.price-sales')
    if sale_price_elem:
        price_info['current_price'] = sale_price_elem.get_text(strip=True)
    discount_elem = soup.select_one('.price-sales-discount')
    if discount_elem and discount_elem.get_text(strip=True):
        price_info['discounted_price'] = discount_elem.get_text(strip=True)
    price_container = soup.select_one('.product-price-default[aria-label*="Price"]')
    if price_container:
        aria_label = price_container.get('aria-label', '')
        price_info['aria_label_price_info'] = aria_label
        if 'reduced from' in aria_label.lower():
            original_match = re.search(r'reduced from USD (\d+\.?\d*)', aria_label)
            sale_match = re.search(r'Sale price USD (\d+\.?\d*)', aria_label)
            if original_match:
                price_info['aria_original_price'] = f"${original_match.group(1)}"
            if sale_match:
                price_info['aria_sale_price'] = f"${sale_match.group(1)}"
    price_info['is_discounted'] = bool(original_price_elem and (discount_elem or 'reduced' in price_info.get('aria_label_price_info', '')))

    availability_info = {}
    out_of_stock_indicators = soup.select('.out-of-stock, .unavailable, [data-instock="false"]')
    in_stock_indicators = soup.select('.in-stock, .available, [data-instock="true"]')
    availability_info['out_of_stock_elements'] = len(out_of_stock_indicators)
    availability_info['in_stock_elements'] = len(in_stock_indicators)
    size_stock = {}
    size_items = soup.select('.variants__item--size')
    for size_item in size_items:
        size_value = size_item.get('data-sizevalue', '')
        is_in_stock = size_item.get('data-instock', 'false')
        if size_value:
            size_stock[size_value] = is_in_stock == 'true'
    availability_info['size_stock'] = size_stock

    product_data = {
        'extraction_timestamp': datetime.now().isoformat(),
        'source_url': url,
        'source_country': country,
        'title': title,
        'price_info': price_info,
        'availability_info': availability_info,
        'images': list(images),
        'color_variants': color_variants,
        'sizes': sizes,
        'accordion_sections': sections,
        'breadcrumbs': breadcrumbs,
        'meta_data': meta_data,
        'json_ld': json_ld_data,
        'data_attributes': data_attrs,
        'raw_content': {
            'full_text': soup.get_text(separator=' ', strip=True)[:5000],
            'product_description': '',
            'key_features': []
        }
    }
    desc_elem = soup.select_one('meta[itemprop="description"], .product-description, .pdp-description')
    if desc_elem:
        if desc_elem.name == 'meta':
            product_data['raw_content']['product_description'] = desc_elem.get('content', '')
        else:
            product_data['raw_content']['product_description'] = desc_elem.get_text(strip=True)
    feature_elems = soup.select('.product-features li, .key-features li, .features li')
    for feature in feature_elems:
        text = feature.get_text(strip=True)
        if text:
            product_data['raw_content']['key_features'].append(text)
    return product_data


# <-- CHANGED: Removed 'async'
def run_simple_test(url):
    """Runs a simple, non-scraping test to see if Playwright can connect."""
    logging.info("--- Starting Simple Firefox Test ---")
    try:
        with sync_playwright() as p:  # <-- CHANGED: sync_playwright
            logging.info("Launching Firefox...")
            browser = p.firefox.launch(headless=False)  # <-- CHANGED: No 'await'
            
            page = browser.new_page()  # <-- CHANGED: No 'await'
            
            logging.info(f"Attempting to load URL: {url}")
            
            # Go to the URL
            page.goto(url, wait_until='domcontentloaded', timeout=60000)  # <-- CHANGED: No 'await'
            
            logging.info("--- !!! SUCCESS !!! ---")
            logging.info("Page loaded. If you see this, the connection worked.")
            logging.info("The browser will close in 15 seconds.")
            
            time.sleep(15)      # <-- CHANGED: time.sleep
            browser.close()     # <-- CHANGED: No 'await'
            
    except Exception as e:
        logging.error("--- !!! TEST FAILED !!! ---")
        logging.error(f"An error occurred: {e}")

# --- REMOVED: process_url and process_urls functions are no longer needed.
# The logic is now inside main().

# <-- CHANGED: Removed 'async'
def main():
    """Main function to read URLs and start the scraping process."""
    today_str = date.today().strftime('%Y-%m-%d')
    countries = ['UK']

    for country in countries:
        date_subfolder = f'{country}/Data/{today_str}'
        read_file_path = f'{date_subfolder}/Item_urls/{country}_unique_product_urls.json'

        if not os.path.exists(read_file_path):
            logging.warning(f"Missing: {read_file_path}")
            continue  # Skip to the next country

        with open(read_file_path, encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)

        for gender, categories in urls_dict.items():
            logging.info(f'Starting {country} {gender} section...')
            for category, urls in categories.items():
                logging.info(f'Starting {country} {gender} {category} section...')
                
                # --- ADDED: Synchronous Playwright and browser logic ---
                # Launch one browser for the entire category
                with sync_playwright() as p:
                    browser = p.firefox.launch(headless=False)
                    
                    # Process URLs one by one
                    for url in urls:
                        name = file_name(url)
                        if check_file(gender, category, name, date_subfolder):
                            logging.info(f"Skipping (already exists): {url}")
                            continue

                        page = None
                        try:
                            logging.info(f"Processing: {url}")
                            page = browser.new_page()
                            page.goto(url, wait_until='domcontentloaded', timeout=60000)
                            content = page.content()
                            time.sleep(10)  # Allow time for dynamic content to load
                            
                            soup = BeautifulSoup(content, 'html.parser')
                            product_data = extract_html_data(soup, url, country)
                            
                            save_json(gender, category, name, product_data, date_subfolder)
                            logging.info(f"Successfully saved: {name}.json")

                        except Exception as e:
                            logging.error(f"Failed to process {url}: {e}")
                        finally:
                            if page:
                                page.close() # Close the page after use
                    
                    browser.close() # Close the browser after finishing the category
                # --- End of added logic ---
                
                logging.info(f'{country} {gender} {category} section complete.')
            logging.info(f'{country} {gender} section complete.')
    logging.info('All products completed.')

if __name__ == "__main__":
    # Example of how to run the simple test (optional)
    # test_url = "https://www.google.com"
    # run_simple_test(test_url)

    # <-- CHANGED: Call main() directly
    main()