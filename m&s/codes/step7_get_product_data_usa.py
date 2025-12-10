import os
import json
import re
import csv
import random
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*#%]', '_', name)

def save_json(base_dir, gender, category, filename, data):
    file_path = os.path.join(base_dir, gender, category)
    os.makedirs(file_path, exist_ok=True)
    with open(os.path.join(file_path, f"{filename}.json"), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_proxies(proxy_file="proxy_usa.txt"):
    proxies = []
    if os.path.exists(proxy_file):
        with open(proxy_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) == 4:
                    server, port, username, password = parts
                    proxies.append({
                        "server": f"{server}:{port}",
                        "username": username,
                        "password": password
                    })
    return proxies

def parse_usa_page(soup, pid, url):
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
    details_list, care_list = [], []
    details_block = soup.find('div', {'id': 'collapseDetailsNCare'})
    if details_block:
        wrappers = details_block.find_all('div', recursive=False)
        for wrapper in wrappers:
            heading = wrapper.find('div', class_='sub-heading')
            if not heading:
                continue
            heading_text = heading.get_text(strip=True).lower()
            ul = wrapper.find('ul') 
            if not ul:
                continue
            items = [li.get_text(strip=True) for li in ul.find_all('li')]
            if "detail" in heading_text:
                details_list.extend(items)
            elif "care" in heading_text:
                care_list.extend(items)
    size_and_fit_list = []
    size_fit_block = soup.find('div', class_='size-wrapper')
    if size_fit_block:
        all_uls = size_fit_block.find_all('ul')
        for ul in all_uls:
            items = [li.get_text(strip=True) for li in ul.find_all('li')]
            size_and_fit_list.extend(items)
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
    color_name, color_id = None, None
    color_div = soup.find('div', class_=lambda x: x and 'colour-picker' in x and 'qa-pdp-color-display' in x)
    if color_div:
        b_tag = color_div.find('b')
        if b_tag and b_tag.text.strip():
            color_name = b_tag.text.strip()
        elif color_div.has_attr('data-colorname'):
            color_name = color_div['data-colorname'].strip()
        if color_div.has_attr('data-color-id'):
            color_id = color_div['data-color-id'].strip()
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
        'product_description': {
            'product_id': product_id,
            'product_description': product_description
        },
        'details_and_cares': {
            'details': details_list,
            'care': care_list,
            'size_and_fit': size_and_fit_list,
            'Composition': composition,
            'image': final_images,
            'prize': {
                'current_prize': new_price,
                'old_prize': old_price
            }
        }
    }

def scrape_usa_product(url, base_dir, gender, category, proxies):
    proxy = random.choice(proxies) if proxies else None
    variant_count = 0  
    with sync_playwright() as p:
        browser = None
        try:
            if proxy:
                for scheme in ["http"]:
                    try:
                        browser = p.chromium.launch(
                            headless=True,
                            proxy={
                                "server": f"{scheme}://{proxy['server']}",
                                "username": proxy['username'],
                                "password": proxy['password']
                            }
                        )
                        print(f"Using proxy: {scheme}://{proxy['server']}")
                        break
                    except Exception as e:
                        print(f"Proxy failed ({scheme}://{proxy['server']}): {e}")
                        browser = None
            if not browser:
                print("No working proxy, running without proxy...")
                browser = p.chromium.launch(headless=True)
            page = browser.new_page()
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
            for swatchid, v_url in variant_urls:
                page.goto(v_url, wait_until="domcontentloaded", timeout=60000)
                soup_var = BeautifulSoup(page.content(), 'html.parser')
                product_data = parse_usa_page(soup_var, pid, v_url)
                filename = safe_filename(f"{pid}_{swatchid}")
                file_path = os.path.join(base_dir, gender, category, f"{filename}.json")
                if os.path.exists(file_path):
                    print(f"Skipping USA: {filename}")
                    continue
                save_json(base_dir, gender, category, filename, {'product_details': product_data})
                print(f"Saved USA: {filename}")
                variant_count += 1
        except Exception as e:
            print(f"Error scraping USA {url}: {e}")
        finally:
            if browser:
                browser.close()
        return (gender, category, variant_count)

def main():
    today_str = datetime.now().strftime('%Y-%m-%d')
    base_dir = f'USA/Data/{today_str}/Json_data'
    os.makedirs(base_dir, exist_ok=True)
    url_path = f'USA/Data/{today_str}/Item_urls/USA_unique_product_urls.json'
    if not os.path.exists(url_path):
        print("No USA URL file found.")
        return
    with open(url_path, 'r', encoding='utf-8') as file:
        all_data = json.load(file)
    proxies = load_proxies("proxy_usa.txt")
    tasks = []
    results = []
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = []
        for gender, categories in all_data.items():
            for category, urls in categories.items():
                for url in urls:
                    pid = url.split('.html')[0].split('/')[-1]
                    color_part = url.split("color=")[-1] if 'color=' in url else "DEFAULT"
                    filename = safe_filename(f'{pid}_{color_part}')
                    file_path = os.path.join(base_dir, gender, category, f"{filename}.json")
                    if os.path.exists(file_path):
                        print(f"Skipping USA: {filename}")
                        continue
                    futures.append(executor.submit(scrape_usa_product, url, base_dir, gender, category, proxies))
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    counts = {}
    for gender, category, count in results:
        key = (gender, category)
        counts[key] = counts.get(key, 0) + count
    validation_path = os.path.join('USA', 'Data', today_str, 'Validation')
    os.makedirs(validation_path, exist_ok=True)
    csv_path = os.path.join(validation_path, 'unique_pid.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Gender', 'Category', 'Count'])
        for (gender, category), count in sorted(counts.items()):
            writer.writerow([gender, category, count])
    print(f"\nSaved USA variant counts to: {csv_path}")

if __name__ == "__main__":
    main()
