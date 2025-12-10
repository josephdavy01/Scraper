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

def html_data(soup):
    data = soup.find('section', class_='_layout_1lzvc_59')
    sizes = []
    for btn in data.find_all('button', {'data-test-id': 'purchasePodSizeButton'}):
        size_value = btn.find('span', class_='_sizeValue_f7d4n_137')
        size_name = size_value.get_text(strip=True) if size_value else btn.get_text(strip=True)
        
        classes = btn.get('class', [])
        out_of_stock = any('OutOfStock' in c for c in classes)
        
        sr_only = btn.find('span', class_='srOnly')
        if sr_only and 'No items left in stock' in sr_only.get_text():
            out_of_stock = True
        
        stock_info = btn.find('span', class_='_stockInfo_f7d4n_148')
        stock_text = stock_info.get_text(strip=True) if stock_info else None
        
        sizes.append({
            'size_name': size_name, 
            'in_stock': not out_of_stock,
            'stock_info': stock_text
        })


    badge_elem = soup.find('p', {'data-wk-name': 'purchasePodProductBadge'})
    badge = badge_elem.get_text(strip=True) if badge_elem else None

    images = set()
    for slide in soup.find_all("div", class_="_slide_ak1fl_73"):
        for tag in slide.find_all(["img", "source"]):
            for attr in ("src", "srcset"):
                val = tag.get(attr)
                if not val:
                    continue 

                for i in val.split(','):
                    url = i.strip().split()[0]  
                    url = url.split('?')[0]    
                    if url:
                        images.add(url)

    mat_section = soup.find('section', id='materials-and-transparency')
    material_info = None
    if mat_section:
        material_data = {}
        materials_ul = mat_section.find('ul', class_='_sustainabilityClaims_15nou_157')
        if materials_ul:
            material_data['materials'] = [li.get_text(strip=True) for li in materials_ul.find_all('li') if li.get_text(strip=True)]
        else:
            mat_h3 = mat_section.find('h3', string=lambda x: x and 'material' in x.lower())
            if mat_h3:
                ul_tag = mat_h3.find_next_sibling('ul')
                if ul_tag:
                    material_data['materials'] = [li.get_text(strip=True) for li in ul_tag.find_all('li')]
                else:
                    p_tag = mat_h3.find_next_sibling('p')
                    if p_tag:
                        material_data['materials'] = [p_tag.get_text(strip=True)]

        supplier_h3 = mat_section.find('h3', string=lambda x: x and 'supplier transparency' in x.lower())
        if supplier_h3:
            supplier_p = supplier_h3.find_next_sibling('p')
            if supplier_p:
                material_data['supplier'] = supplier_p.get_text(strip=True)
        material_info = material_data if material_data else None

                        
    quick_facts = {}
    quick_facts_section = soup.find('section', id='quick-facts')
    if quick_facts_section:
        for article in quick_facts_section.find_all('article', class_='_quickFact_11exh_59'):
            title_elem = article.find('h2', class_='_title_11exh_122')
            value_elem = article.find('p', class_='_text_11exh_137')
                
            if title_elem and value_elem:
                title = title_elem.get_text(strip=True)
                value = value_elem.get_text(strip=True)
                if title:
                    quick_facts[title.lower().replace(' ', '_')] = value
                        
    product_highlights = []
    highlights_section = soup.find('section', id='highlights')
    if highlights_section:
        highlight_cards = highlights_section.find_all('div', attrs={'data-test-id': lambda x: x and x.startswith('productHighlightCard-')})
            
        for card in highlight_cards:
            title_elem = card.find('h2', class_='_imageTitle_x2jp6_90') 
            desc_elem = card.find('p', class_='_description_x2jp6_113')
                
            if title_elem and desc_elem:
                highlight = {
                    'title': title_elem.get_text(strip=True),
                    'description': desc_elem.get_text(strip=True)
                }
                product_highlights.append(highlight)
        
    key_features = []
    features_section = soup.find('section', id='product-features')
    if features_section:
        features_ul = features_section.find('ul', class_='_usps_8gsmh_77')
        if features_ul:
            for li in features_ul.find_all('li'):
                feature_p = li.find('p', class_='_usp_8gsmh_77')
                if feature_p:
                    feature_text = feature_p.get_text(strip=True)
                    if feature_text:
                        key_features.append(feature_text)
    
    image_urls = {}
    index = -1
    # image_tag = soup.find('div', class_='_wrapper_ak1fl_65')
    image_tag = soup.find('div', class_='_wrapper_57zia_65')
    if image_tag and hasattr(image_tag, 'find_all'):
        sub_image_tags = image_tag.find_all('div', class_='_slide_57zia_73')
        for sub_image_tag in sub_image_tags[:len(sub_image_tags)//2]:
            index += 1
            picture_tag = sub_image_tag.find('picture')
            if picture_tag:
                source_tag = picture_tag.find('source')
                if source_tag and source_tag.get('srcset'):
                    img_tag = source_tag.get('srcset').split('?')[0]
                    image_urls[index] = img_tag

    return {'sizes': sizes,'images': image_urls,'material': material_info,'badge': badge , 'key_features': key_features,'quick_facts': quick_facts,'product_highlights': product_highlights }
       
def script_data(script_json, sku):
    gender = 'unisex'
    for node in script_json.get('@graph', []):
        if node.get('@type') == 'BreadcrumbList':
            all_items = ' '.join(li.get('item', '') for li in node.get('itemListElement', [])).lower()
            
            if any(keyword in all_items for keyword in ['women', 'womens']):
                gender = 'female'
            elif any(keyword in all_items for keyword in ['men', 'mens']) and 'women' not in all_items:
                gender = 'male'
            elif 'kids' in all_items:
                gender = 'kids'
            break

    for node in script_json.get('@graph', []):
        if node.get('@type') == 'ProductGroup':
            out = {
                'product_name': node.get('name'),
                'description': node.get('description'),
                'product_group_id': node.get('productGroupID'),
                'category_url': node.get('url'),
            }
            for var in node.get('hasVariant', []):
                if var.get('sku') == sku:
                    out.update({
                        'sku': var.get('sku'),
                        'color_name': var.get('color'),
                        'variant_name': var.get('name'),
                        'images': var.get('image'),
                        'variant_url': var.get('offers', {}).get('url'),
                        'price': var.get('offers', {}).get('price'),
                        'currency': var.get('offers', {}).get('priceCurrency'),
                        'availability': (
                            var.get('offers', {}).get('availability', '').split('/')[-1].lower()
                            if var.get('offers', {}).get('availability') else None
                        ),
                        'gender': gender
                    })
                    return out
    return {}

def flatten(html_out, script_out):
    result = dict(script_out)
    result['sizes'] = html_out['sizes']
    result['all_images'] = html_out['images']
    result['badge'] = html_out['badge']
    result['material'] = html_out['material']
    result['key_features'] = html_out['key_features']
    result['quick_facts'] = html_out['quick_facts'] 
    result['product_highlights'] = html_out['product_highlights']
    result['date_of_scraping'] = date.today().isoformat()
    return result

async def scrape_url(url, gender, category, date_subfolder):
    name = url.split('?')[0].split('/')[-1]
    if check_file(gender, category, name, date_subfolder):
        return url

    async with semaphore:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False,
                args=["--disable-setuid-sandbox", "--disable-sandbox", "--window-position=-32000,0"])
                page = await browser.new_page()
                await page.goto(url)
                time.sleep(3)
                await page.wait_for_load_state('domcontentloaded')
                try:
                    await page.wait_for_selector('p[data-wk-name="purchasePodProductBadge"]', timeout=15000)
                except: pass
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')

                script_tag = soup.find('script', id='json-ld', type='application/ld+json')
                script_json = json.loads(script_tag.string) if script_tag and script_tag.string else {}

                sku = url.split('-')[-1]
                html_out = html_data(soup)
                script_out = script_data(script_json, sku)
                result = flatten(html_out, script_out)

                save_json(gender, category, name, result, date_subfolder)
                await browser.close()
                return url
        except Exception as e:
            logging.error(f"Error processing URL {url}: {e}")
            return None

async def process_urls(gender, category, urls, date_subfolder):
    tasks = [scrape_url(u, gender, category, date_subfolder) for u in urls]
    await asyncio.gather(*tasks)

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-03'
    
    countries = ['UK']

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