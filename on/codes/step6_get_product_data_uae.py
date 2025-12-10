import os
import json
import time
import asyncio
import logging
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
semaphore = asyncio.Semaphore(4)

def save_json(gender, category, name, json_data, date_subfolder):
    try:
        json_file_path = f'{date_subfolder}/Json_data/{gender}/{category}'
        os.makedirs(json_file_path, exist_ok=True)
        with open(f'{json_file_path}/{name}.json', 'w', encoding='utf-8') as outfile:
            json.dump(json_data, outfile, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")

def check_file(gender, category, name, date_subfolder):
    return os.path.exists(f'{date_subfolder}/Json_data/{gender}/{category}/{name}.json')

def extract_html_data(soup, url):
    # Extract current variant FIRST
    current_variant = None
    script_elem = soup.find('script', {'data-selected-variant': True})
    if script_elem and script_elem.string:
        try:
            current_variant = json.loads(script_elem.string)
        except json.JSONDecodeError:
            pass
    
    product_info = soup.find('div', class_='product-info-heading')
    title_elem = product_info.find('h1') if product_info else None
    title = title_elem.get_text(strip=True) if title_elem else None
  
    badge = None
    badge_elem = soup.find('div', class_='var-label')
    if badge_elem:
        badge_span = badge_elem.find('span', class_=lambda x: x and 'product-card-badge' in x)
        if badge_span:
            badge_text = badge_span.get_text(strip=True)
            if badge_text:
                badge = badge_text
   
    regular_price_elem = soup.find('span', class_='price-item--regular')
    regular_price = regular_price_elem.get_text(strip=True) if regular_price_elem else None

    sale_price_elem = soup.find('span', class_='price-item--sale')
    sale_price = sale_price_elem.get_text(strip=True) if sale_price_elem else None
    
    description_elem = soup.find('div', class_='product__description')
    description = description_elem.get_text(strip=True) if description_elem else None

    # Breadcrumbs
    breadcrumbs = []
    breadcrumb_elements = soup.find_all('li', class_='breadcrumb')
    for bc in breadcrumb_elements:
        link = bc.find('a')
        if link:
            breadcrumbs.append({
                'text': link.get_text(strip=True),
                'url': link.get('href')
            })

    # Gender selection 
    gender_selected = None
    if current_variant and current_variant.get('option1'):
        gender_selected = current_variant['option1'].lower()
    # Fallback: check for checked gender inputs (less reliable)
    if not gender_selected:
        gender_inputs = soup.find_all('input', {'name': lambda x: x and 'Gender' in x})
        for inp in gender_inputs:
            if inp.get('checked'):
                gender_selected = inp.get('value')
                break

    # Color options
    colors = []
    color_inputs = soup.find_all('input', {'name': lambda x: x and 'Color' in x})
    for inp in color_inputs:
        is_disabled = 'disabled' in inp.get('class', [])
        is_checked = inp.get('checked') is not None
        
        # Get color image
        label = soup.find('label', {'for': inp.get('id')})
        img_elem = label.find('img') if label else None
        img_url = img_elem.get('src') if img_elem else None
        
        colors.append({
            'color': inp.get('value'),
            'available': not is_disabled,
            'selected': is_checked,
            'image': img_url
        })

    # Size options
    sizes = []
    size_inputs = soup.find_all('input', {'name': lambda x: x and 'Size' in x})
    for inp in size_inputs:
        is_disabled = 'disabled' in inp.get('class', [])
        is_checked = inp.get('checked') is not None
        label = soup.find('label', {'for': inp.get('id')})
        has_notify = label and label.find('span', class_='notify-txt') is not None
        
        sizes.append({
            'size': inp.get('value'),
            'available': not is_disabled and not has_notify,
            'selected': is_checked,
            'notify_available': has_notify
        })

    image_urls = {}
    image_tag = soup.find('div', class_='swiper-wrapper main-swiper')
    if image_tag and hasattr(image_tag, 'find_all'):
        sub_image_tags = image_tag.find_all('div', class_='swiper-slide')
        for sub_image_tag in sub_image_tags:
            index = sub_image_tag.get('data-swiper-slide-index')
            picture_tag = sub_image_tag.find('picture')
            if picture_tag:
                source_tag = picture_tag.find('source')
                if source_tag and source_tag.get('srcset'):
                    img_tag = source_tag.get('srcset').split('?')[0]
                    image_urls[index] = img_tag

    # Materials info
    materials_info = {}
    materials_section = soup.find("h2", string=lambda t: t and "Materials" in t)
    if materials_section:
        container = materials_section.find_parent("accordion-element")
        if container:
            mat_tag = container.find("h3", string=lambda t: t and "Materials" in t)
            if mat_tag and mat_tag.find_next("p"):
                materials_info["materials"] = mat_tag.find_next("p").get_text(strip=True)
            
            sup_tag = container.find("h3", string=lambda t: t and "Supplier Transparency" in t)
            if sup_tag and sup_tag.find_next("p"):
                materials_info["supplier_transparency"] = sup_tag.find_next("p").get_text(strip=True)

    # Key features
    key_features = []
    features_section = soup.find('h2', string=lambda t: t and 'Key Features' in t)
    if features_section:
        ul_elem = features_section.find_next('ul')
        if ul_elem:
            key_features = [li.get_text(strip=True) for li in ul_elem.find_all('li')]
            
    quick_facts = []
    facts_div = soup.find('div', class_='quick-facts')
    if facts_div:
        for article in facts_div.find_all('article', class_='quick-fact'):
            title_tag = article.select_one('h2.quick-fact-title')
            value_tag = article.select_one('p.quick-fact-text')
            title = title_tag.get_text(strip=True) if title_tag else None
            value = value_tag.get_text(strip=True) if value_tag else None
            if title and value:
                quick_facts.append({
                    'title': title,
                    'value': value
                })
       
    # Simplified return statement
    return {
        'product_url': url, 
        'basic_info': {'title': title, 'badge': badge, 'description': description, 'current_variant': current_variant}, 
        'pricing': {'regular_price': regular_price, 'sale_price': sale_price}, 
        'navigation': {'breadcrumbs': breadcrumbs}, 
        'product_options': {'gender_selected': gender_selected, 'colors': colors, 'sizes': sizes}, 
        'images': image_urls,
        'additional_info': {'materials': materials_info, 'key_features': key_features,'quick_facts':quick_facts}, 
        'extraction_date': date.today().isoformat()
    }

async def scrape_url(url, gender, category, date_subfolder):
    name = url.split('variant=')[1].split('&')[0]
    if check_file(gender, category, name, date_subfolder):
        return url

    async with semaphore:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False,
                args=["--disable-setuid-sandbox", "--disable-sandbox", "--window-position=-32000,0"])
                page = await browser.new_page()
                time.sleep(3)
                await page.goto(url)
                time.sleep(3)
                await page.wait_for_load_state('domcontentloaded')
                try:
                    await page.wait_for_selector('.product-info-heading h1', timeout=15000)
                except: pass

                content = await page.content()
                await browser.close()
                
                soup = BeautifulSoup(content, 'html.parser')
                result = extract_html_data(soup, url)  # Pass url parameter
                save_json(gender, category, name, result, date_subfolder)
                return url
        except Exception as e:
            logging.error(f"Error processing URL {url}: {e}")
            return None

async def process_urls(gender, category, urls, date_subfolder):
    tasks = [scrape_url(u, gender, category, date_subfolder) for u in urls]
    await asyncio.gather(*tasks)

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    
    countries = ['UAE']

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