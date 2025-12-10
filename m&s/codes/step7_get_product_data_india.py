import os
import json
import re
import csv
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

country = "India"

def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*#%]', '_', name)

def save_json(base_dir, gender, category, filename, data):
    file_path = os.path.join(base_dir, gender, category)
    os.makedirs(file_path, exist_ok=True)
    with open(os.path.join(file_path, f"{filename}.json"), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def parse_india_page(soup, pid, url):
    sizes_dict = {}
    menu_items = soup.find('div', {'class': 'size'})
    if menu_items:
        sizes = menu_items.find_all('option')
        for size in sizes:
            sizes_dict[size.text.strip()] = size.get('value', '')
    product_id, product_description = None, None
    value = soup.find('div', {'class': 'product-information'}) or soup.find('div', {'class': 'collapse show'})
    if value:
        pid_tag = value.find('span')
        if pid_tag:
            product_id = pid_tag.text.strip()
        notes_tag = value.find('div', {'class': 'editors-notes'})
        if notes_tag:
            product_description = notes_tag.text.strip()
    style, detail = [], []
    details = soup.find('div', {'id': 'collapseDetailsNCare'})
    if details:
        sections = details.find_all('div', {'class': 'content-wrapper'})
        if sections:
            det = sections[0].find('ul', {'class': 'content'})
            if det:
                style.extend([li.text.strip() for li in det.find_all('li')])
            if len(sections) > 2:
                more_details = sections[2].find('ul', {'class': 'content'})
                if more_details:
                    detail.extend([li.text.strip() for li in more_details.find_all('li')])
            elif len(sections) > 1:
                more_details = sections[1].find('ul', {'class': 'content'})
                if more_details:
                    detail.extend([li.text.strip() for li in more_details.find_all('li')])
    composition = None
    comp_tag = soup.find('div', {'class': 'compositionInformation'})
    if comp_tag:
        composition = comp_tag.text.strip()
    final_images = []
    seen_indices = set()
    for slide in soup.select("div.swiper-slide"):
        index = slide.get("data-swiper-slide-index")
        img = slide.find("img")
        if not img:
            continue
        src = img.get("data-hover-image-src") or img.get("src")
        if not src:
            continue
        if index and index not in seen_indices:
            final_images.append(src.strip())
            seen_indices.add(index)
    color_name = None
    color_id = None
    color_div = soup.find('div', class_=lambda x: x and 'colour-picker color-display swatch-color-P60709296' in x and 'qa-pdp-color-display' in x)
    if color_div and color_div.has_attr('data-color-id'):
        color_id = color_div['data-color-id'].strip()
    color_picker = soup.find('div', class_='colour-picker')
    if color_picker:
        b_tag = color_picker.find('b')
        if b_tag:
            color_name = b_tag.text.strip()
    if not color_id:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        for key in query_params:
            if key.startswith("dwvar_") and key.endswith("_color"):
                color_id = query_params[key][0]
                break
    new_price, old_price = None, None
    price_div = soup.find('div', {'class': 'price-display'})
    if price_div:
        price_spans = price_div.find_all('span', {'class': 'value'})
        try:
            if price_spans:
                new_price = float(price_spans[0].get('content', 0) or 0)
                old_price = float(price_spans[1].get('content', new_price)) if len(price_spans) > 1 else new_price
        except Exception:
            pass
    brand_name = None
    brand_div = soup.find('div', {'class': 'pdp-brand'})
    if brand_div:
        brand_name = brand_div.text.strip().lower()
    product_title = None
    title_tag = soup.find('h1', {'class': 'product-name'})
    if title_tag:
        product_title = title_tag.text.strip().lower()
    size_fit = []
    size_fit_section = soup.find('div', id='collapseSizeFit')
    if size_fit_section:
        lis = size_fit_section.find_all('li')
        for li in lis:
            text = li.get_text(strip=True)
            if text and "Unsure about size" not in text:
                size_fit.append(text)
    return {
        'pid': pid,
        'url': url,
        'Brand_name': brand_name,
        'Product_title': product_title,
        'product_size': sizes_dict,
        "product_color_id": {
            "color_name": color_name,
            "color_id": color_id
        },
        'product_description': {'product_id': product_id, 'product_description': product_description},
        'details_and_cares': {
            'style': style,
            'Composition': composition,
            'more_details': detail,
            'Size & Fit': size_fit,
            'image': final_images,
            'prize': {'current_prize': new_price, 'old_prize': old_price}
        }
    }

def scrape_india_product(page, url, base_dir, gender, category):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    soup = BeautifulSoup(page.content(), 'html.parser')
    pid = url.split('.html')[0].split('/')[-1]
    variant_urls = []
    swatcher_div = soup.find('div', class_='colour-swatcher')
    if swatcher_div:
        swatches = swatcher_div.find_all('a', class_='swatch-link')
        for sw in swatches:
            swatchid = sw.get('data-swatchid')
            if not swatchid:
                continue
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            query['dwvar_' + pid + '_color'] = [swatchid]
            query['pid'] = [pid]
            query['quantity'] = ['1']
            new_query = urlencode(query, doseq=True)
            new_url = urlunparse(parsed._replace(query=new_query))
            variant_urls.append((swatchid, new_url))
    if not variant_urls:
        variant_urls.append(("DEFAULT", url))
    count = 0
    for swatchid, v_url in variant_urls:
        page.goto(v_url, wait_until="domcontentloaded", timeout=60000)
        soup_var = BeautifulSoup(page.content(), 'html.parser')
        product_data = parse_india_page(soup_var, pid, v_url)
        filename = safe_filename(f"{pid}_{swatchid}")
        save_json(base_dir, gender, category, filename, {'product_details': product_data})
        print(f"Saved {country}: {filename}")
        count += 1
    return count

def process_india_url(base_dir, gender, category, url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            pid = url.split('.html')[0].split('/')[-1]
            filename = safe_filename(f'{pid}_{url.split("color=")[-1]}' if 'color=' in url else pid)
            file_path = os.path.join(base_dir, gender, category, f"{filename}.json")
            if os.path.exists(file_path):
                print(f"Skipping {country}: {filename}")
                return (gender, category, 0)
            count = scrape_india_product(page, url, base_dir, gender, category)
            return (gender, category, count)
        except Exception as e:
            print(f"Error {country} {url}: {e}")
            return (gender, category, 0)
        finally:
            browser.close()

def main():
    today_str = datetime.now().strftime('%Y-%m-%d')
    base_dir = f'{country}/Data/{today_str}/Json_data'
    os.makedirs(base_dir, exist_ok=True)
    url_path = f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json'
    if not os.path.exists(url_path):
        print(f"No {country} URL file found.")
        return
    with open(url_path, 'r', encoding='utf-8') as file:
        all_data = json.load(file)
    tasks = []
    result_counts = []
    with ThreadPoolExecutor(max_workers=7) as executor:
        future_to_url = {}
        for gender, categories in all_data.items():
            for category, urls in categories.items():
                for url in urls:
                    future = executor.submit(process_india_url, base_dir, gender, category, url)
                    future_to_url[future] = (gender, category)
        for future in as_completed(future_to_url):
            gender, category, count = future.result()
            if count > 0:
                result_counts.append((gender, category, count))
    count_dict = {}
    for gender, category, count in result_counts:
        key = (gender, category)
        count_dict[key] = count_dict.get(key, 0) + count
    validation_path = os.path.join(country, "Data", today_str, "Validation")
    os.makedirs(validation_path, exist_ok=True)
    output_csv_path = os.path.join(validation_path, "unique_pid.csv")
    with open(output_csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Gender", "Category", "Count"])
        for (gender, category), count in sorted(count_dict.items()):
            writer.writerow([gender, category, count])
    print(f"\nSaved unique product variant counts to: {output_csv_path}")

if __name__ == "__main__":
    main()
