import os
import json
import re
import csv
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed

def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*#%]', '_', name)

def save_json(base_dir, gender, category, filename, data):
    file_path = os.path.join(base_dir, gender, category)
    os.makedirs(file_path, exist_ok=True)
    with open(os.path.join(file_path, f"{filename}.json"), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_uk_variant_urls(page, base_url):
    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
    page.mouse.wheel(0, 1000)
    page.wait_for_timeout(1500)
    soup = BeautifulSoup(page.content(), "html.parser")
    variant_urls = []
    color_options = soup.select('div.selector-group-array_wrapper__yS98c li label')
    for label in color_options:
        aria_label = label.get("aria-label", "")
        if "colour option" in aria_label.lower() or "color option" in aria_label.lower():
            color_name = aria_label.replace("colour option", "").replace("color option", "").strip()
            color_param = color_name.replace(" ", "").upper()
            new_url = base_url.split("?")[0] + f"?color={color_param}"
            variant_urls.append((color_param, new_url))
    if not variant_urls:
        variant_urls.append(("DEFAULT", base_url))
    return variant_urls

def scrape_uk_product(page, url):
    BASE_URL = "https://assets.digitalcontent.marksandspencer.app/images/w_2560,q_auto,f_auto/"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.mouse.wheel(0, 1000)
    page.wait_for_timeout(2000)
    soup = BeautifulSoup(page.content(), 'html.parser')
    script_tag = soup.find('script', type='application/json')
    if not script_tag or not script_tag.string:
        raise ValueError(f"No <script type='application/json'> found for URL: {url}")
    temp = json.loads(script_tag.string)
    product_data = temp['props']['pageProps']['productDetails']
    images, seen_indices = [], set()
    def normalize_url(src: str) -> str:
        if not src:
            return None
        if "/SD_" in src:
            src = src.split("/SD_", 1)[-1]
            src = "SD_" + src
        return BASE_URL + src
    gallery_imgs = soup.select("ul.image-gallery_slides__N8x_w li img")
    for img in gallery_imgs:
        index = img.get("data-index")
        src = img.get("srcset", "").split(",")[-1].split()[0] if img.get("srcset") else img.get("src")
        if src and index not in seen_indices:
            seen_indices.add(index)
            final_url = normalize_url(src.strip())
            if final_url:
                images.append(final_url)
    template = soup.select_one("template.product-imagery-gallery_expandable__mpBuq")
    if template:
        template_soup = BeautifulSoup(template.decode_contents(), "html.parser")
        for img in template_soup.find_all("img"):
            index = img.get("data-index")
            src = img.get("srcset", "").split(",")[-1].split()[0] if img.get("srcset") else img.get("src")
            if src and index not in seen_indices:
                seen_indices.add(index)
                final_url = normalize_url(src.strip())
                if final_url:
                    images.append(final_url)
    if not images:
        try:
            raw_images = product_data['media']['images']
            for img in raw_images:
                if 'url' in img:
                    final_url = normalize_url(img['url'])
                    if final_url:
                        images.append(final_url)
        except KeyError:
            pass

    comp_block = soup.select_one("div.product-details_compositionContainer__xgv9c")
    upper_material, sole_material = None, None
    if comp_block:
        comp_text = comp_block.get_text(" ", strip=True)
        upper_match = re.search(r"Upper:\s*([^,]+)", comp_text, re.IGNORECASE)
        sole_match = re.search(r"Outsole:\s*([^,]+)", comp_text, re.IGNORECASE)
        if upper_match:
            upper_material = upper_match.group(1).strip()
        if sole_match:
            sole_material = sole_match.group(1).strip()

    product_data['upper_material'] = upper_material
    product_data['sole_material'] = sole_material
    product_data['images'] = images
    return product_data

def process_url(base_dir, gender, category, url, counts_dict):
    variants_saved = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            variant_urls = get_uk_variant_urls(page, url)
            for color_param, v_url in variant_urls:
                pid = v_url.split("/p/")[-1].split(".html")[0]
                filename = safe_filename(f"{pid}_{color_param}" if color_param else pid)
                file_path = os.path.join(base_dir, gender, category, f"{filename}.json")
                variants_saved += 1
                if os.path.exists(file_path):
                    print(f"Skipping UK: {filename}")
                    continue
                json_data = scrape_uk_product(page, v_url)
                save_json(base_dir, gender, category, filename, json_data)
                print(f"Saved UK: {filename}")
        except Exception as e:
            print(f"Error UK {url}: {e}")
        finally:
            browser.close()
    key = (gender, category)
    counts_dict[key] = counts_dict.get(key, 0) + variants_saved

def main():
    today_str = datetime.now().strftime('%Y-%m-%d')
    base_dir = f'UK/Data/{today_str}/Json_data'
    os.makedirs(base_dir, exist_ok=True)
    url_path = f'UK/Data/{today_str}/Item_urls/UK_unique_product_urls.json'
    if not os.path.exists(url_path):
        print("No UK URL file found.")
        return
    with open(url_path, 'r', encoding='utf-8') as file:
        all_data = json.load(file)
    from threading import Lock
    counts = {}
    lock = Lock()
    def safe_process_url(base_dir, gender, category, url):
        nonlocal counts, lock
        local_counts = {}
        process_url(base_dir, gender, category, url, local_counts)
        with lock:
            for key, val in local_counts.items():
                counts[key] = counts.get(key, 0) + val
    tasks = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        for gender, categories in all_data.items():
            for category, urls in categories.items():
                for url in urls:
                    tasks.append(executor.submit(process_url, base_dir, gender, category, url, counts))
        for future in as_completed(tasks):
            future.result()
    validation_path = os.path.join('UK', 'Data', today_str, 'Validation')
    os.makedirs(validation_path, exist_ok=True)
    csv_path = os.path.join(validation_path, 'unique_pid.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Gender', 'Category', 'Count'])
        for (gender, category), count in sorted(counts.items()):
            writer.writerow([gender, category, count])
    print(f"\nSaved UK variant counts to: {csv_path}")

if __name__ == "__main__":
    main()
