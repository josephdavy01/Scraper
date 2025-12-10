import json
import os
import random
import re
import logging
from pathlib import Path
import time
from urllib.parse import urlparse, parse_qs
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from tqdm import tqdm

COOKIES_FILE = "cookies.json"
MAIN_PAGE = "https://www.hoka.com/en/ae/"
PROXY_FILE = "proxy.txt"

# ─────────────────────────────────────────────
# Load cookies
def load_cookies():
    if not os.path.exists(COOKIES_FILE):
        print("cookies.json not found. Continuing without cookies.")
        return []

    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        normalized = []
        for cookie in cookies:
            c = cookie.copy()
            for key in ['hostOnly', 'session', 'storeId', 'id']:
                c.pop(key, None)
            ss = c.get("sameSite", "Lax")
            if isinstance(ss, str):
                ss_lower = ss.lower()
                if ss_lower == "strict":
                    c["sameSite"] = "Strict"
                elif ss_lower in ["lax", "unspecified"]:
                    c["sameSite"] = "Lax"
                elif ss_lower in ["none", "no_restriction"]:
                    c["sameSite"] = "None"
                else:
                    c["sameSite"] = "Lax"
            else:
                c["sameSite"] = "Lax"
            if c.get("domain", "").startswith("."):
                c["domain"] = c["domain"].lstrip(".")
            normalized.append(c)
        print(f"Loaded {len(normalized)} cookies from {COOKIES_FILE}")
        return normalized
    except Exception as e:
        print(f"Failed to load cookies: {e}")
        return []

def load_proxies():
    if not os.path.exists(PROXY_FILE):
        logging.warning(f"{PROXY_FILE} not found. Proxies disabled.")
        return []
    with open(PROXY_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    logging.info(f"Loaded {len(lines)} proxies")
    return lines

# ─────────────────────────────────────────────
# Browser setup with Chrome + stealth
def setup_context(pw, proxy_str=None):
    launch_args = {
        "headless": False,
        "args": ["--start-maximized", "--disable-blink-features=AutomationControlled"]
    }

    launch_options = launch_args.copy()
    if proxy_str:
        launch_options["proxy"] = {"server": proxy_str}

    browser = pw.chromium.launch(channel="chrome", **launch_options)
    context = browser.new_context()

    # Load cookies
    cookies = load_cookies()
    if cookies:
        try:
            context.add_cookies(cookies)
            logging.info("Cookies added to context.")
        except Exception as e:
            logging.warning(f"Failed to set cookies: {e}")

    page = context.new_page()
    # Apply stealth
    page.evaluate("""() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        window.navigator.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    }""")
    return context, browser, page

# ─────────────────────────────────────────────
# Save JSON
def save_json(main_category, sub_category, name, json_data, country, today_str):
    gender = main_category
    category = sub_category if sub_category else main_category
    base_path = Path(country) / "Data" / today_str / "Json_Data" / gender / category
    base_path.mkdir(parents=True, exist_ok=True)
    file_path = base_path / f'{name}.json'
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)

def json_exists(main_category, sub_category, name, country, today_str):
    gender = main_category
    category = sub_category if sub_category else main_category
    file_path = Path(country) / "Data" / today_str / "Json_Data" / gender / category / f'{name}.json'
    return file_path.exists()

def safe_visit(page, url, pw, proxies, max_attempts=2):
    try:
        page.goto(url, timeout=60000)
        simulate_user_behavior(page)
        return True
    except Exception as e:
        logging.warning(f"Normal visit failed for {url}: {e}")
        if not proxies:
            return False

        for attempt in range(max_attempts):
            proxy_str = random.choice(proxies)
            logging.info(f"Retrying with proxy ({attempt+1}/{max_attempts}): {proxy_str}")
            try:
                context, browser, page = setup_context(pw, proxy_str=proxy_str)
                page.goto(url, timeout=60000)
                simulate_user_behavior(page)
                return page, context, browser
            except Exception as e:
                logging.warning(f"Proxy attempt failed: {e}")
                continue
        return False

# ─────────────────────────────────────────────
# Load product URLs
def load_product_urls(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    product_urls = []

    def extract_urls(d, main_category=None, sub_category=None):
        if isinstance(d, dict):
            for k, v in d.items():
                if main_category is None:
                    extract_urls(v, k, None)
                else:
                    extract_urls(v, main_category, k)
        elif isinstance(d, list):
            for url in d:
                if isinstance(url, str):
                    product_urls.append((main_category, sub_category, url))
        elif isinstance(d, str):
            product_urls.append((main_category, sub_category, d))

    extract_urls(data)
    logging.info(f"Loaded {len(product_urls)} total product URLs")
    return product_urls

# ─────────────────────────────────────────────
# Simulate human-like scrolling
def simulate_user_behavior(page):
    for _ in range(random.randint(2, 4)):
        x = random.randint(0, 500)
        y = random.randint(0, 800)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.5, 1.5))
    page.evaluate("window.scrollBy(0, document.body.scrollHeight / 3)")
    time.sleep(random.uniform(2, 4))

# ─────────────────────────────────────────────
# Product Data Extraction
def get_product_data(page, url):
    path_name = url.split('?')[0].split('/')[-1].split('.')[0]
    query_params = parse_qs(urlparse(url).query)
    color = query_params.get(f'dwvar_{path_name}_color', ["default"])[0]
    name = f"{path_name}_{color}"
    json_data = {}

    page.goto(url, timeout=100000)
    time.sleep(10)

    soup = BeautifulSoup(page.content(), "html.parser")
    script_tag = soup.find('script', {'type': 'application/ld+json'})
    if not script_tag:
        raise Exception("Product JSON script not found")
    json_data['product'] = json.loads(script_tag.get_text())

    # Availability
    availability_dict = {}
    size_section = soup.find('div', class_='my-3 attribute-size')
    if size_section:
        for item in size_section.find_all('div', class_='item'):
            btn = item.find('button')
            if btn and (size := btn.get('data-attr-value')):
                availability = "Out of Stock"
                msg = item.find('div', class_='availability')
                if msg and msg.find('div', class_='message availability-type-instock'):
                    availability = "In Stock"
                elif msg and msg.find('div', class_='message availability-type-lowstock'):
                    availability = "Low Stock"
                availability_dict[size] = availability
    json_data['availibility'] = availability_dict

    # Color info
    color_id = None
    match = re.search(r'dwvar_[\w-]+_color=([A-Z0-9]+)', url)
    if match:
        color_id = match.group(1)
    if not color_id:
        color_container = soup.find('div', class_='attribute js-has-swatches attribute-type-color')
        if color_container:
            button = color_container.find('button', {'type': 'button'})
            if button:
                span = button.find('span', {'data-attr-value': True})
                if span:
                    color_id = span.get('data-attr-value')

    color_name_tag = soup.select_one("span.color-attr-value.swatch-group-label")
    json_data['color_id'] = color_id
    json_data['color_name'] = color_name_tag.text.strip() if color_name_tag else "Unknown"

    # Features
    features = []
    desc = soup.find("div", class_="description hide-on-zoom")
    if desc:
        for ul in desc.find_all("ul", class_=lambda c: c and "features-container" in c):
            features += [li.get_text(strip=True) for li in ul.find_all("li", class_="feature-item")]
    json_data['features'] = features

    # Composition
    comp = []
    material = soup.find("div", class_="description-techspecs description-techspecs--material card")
    if material:
        ul = material.find("div", class_="material-container").find("ul") if material.find("div", class_="material-container") else None
        if ul:
            for li in ul.find_all("li"):
                if li.find_previous_sibling("strong"):
                    break
                comp.append(li.get_text(strip=True))
    json_data['composition'] = comp if comp else None

    # Occasion
    occasion = None
    occ_container = soup.find("div", class_="description-techspecs__items collapsible-recommendations")
    if occ_container:
        items = occ_container.find_all("div", class_="description-techspecs__item")
        occasion = ", ".join(item.get_text(strip=True) for item in items)
    else:
        alt_ul = soup.find("ul", class_="description-techspecs__items designed-for-container")
        if alt_ul:
            items = alt_ul.find_all("li", class_="description-techspecs__item")
            occasion = ", ".join(item.get_text(strip=True) for item in items)
    json_data['occasion'] = occasion

    # Weight & Drop
    weight = drop = None
    for row in soup.find_all("div", class_="row pb-4 align-items-center"):
        label = row.find("div", class_="col-3 col-md-4")
        value = row.find("div", class_="col detail-col")
        if label:
            if "Weight" in label.get_text(strip=True):
                w = value.get_text(strip=True)
                weight = w if "g" in w else w + "g"
            if "Heel-To-Toe Drop" in label.get_text(strip=True):
                d = value.get_text(strip=True)
                drop = d if "mm" in d else d + "mm"
    json_data['weight'] = weight
    json_data['heel_to_toe_drop'] = drop

    # Gender
    gender_tag = soup.find("p", class_="product-prefix__item")
    json_data['gender'] = gender_tag.get_text(strip=True) if gender_tag else None

    # URL
    json_data['url'] = url

    # Images
    images = []
    img_container = soup.find("div", class_="deckers-swiper__grid-splash js-deckers-swiper__grid-splash")
    if img_container:
        for picture in img_container.find_all("picture"):
            img = picture.find("img")
            if img and img.get("src"):
                images.append(img["src"])
    json_data['images'] = images

    return name, json_data

# ─────────────────────────────────────────────
# Main Processing
def process_products(input_path, country, today_str):
    product_urls = load_product_urls(input_path)
    proxies = load_proxies()

    with sync_playwright() as pw:
        url_counter = 0
        context, browser, page = setup_context(pw)
        visit_result = safe_visit(page, MAIN_PAGE, pw, proxies)
        if visit_result is False:
            logging.error("Failed accessing main page even with proxies.")
        elif isinstance(visit_result, tuple):
            page, context, browser = visit_result

        for idx, (main_category, sub_category, url) in enumerate(tqdm(product_urls, desc="Scraping Products")):
            try:
                path_name = url.split('?')[0].split('/')[-1].split('.')[0]
                query_params = parse_qs(urlparse(url).query)
                color = query_params.get(f'dwvar_{path_name}_color', ["default"])[0]
                name = f"{path_name}_{color}"

                if json_exists(main_category, sub_category, name, country, today_str):
                    logging.info(f"Skipping {url} (already scraped)")
                    continue

                logging.info(f"[{idx + 1}] Processing ({sub_category}) - {url}")
                time.sleep(random.uniform(3, 6))

                try:
                    name, data = get_product_data(page, url)
                except Exception as e:
                    logging.warning(f"Normal access failed for {url}: {e}")
                    if proxies:
                        proxy_str = random.choice(proxies)
                        logging.info(f"Retrying with proxy: {proxy_str}")
                        context.close()
                        browser.close()
                        context, browser, page = setup_context(pw, proxy_str=proxy_str)
                        page, context, browser = safe_visit(page, url, pw, proxies)
                        name, data = get_product_data(page, url)
                    else:
                        raise e

                save_json(main_category, sub_category, name, data, country, today_str)

                url_counter += 1
                if url_counter % 3 == 0:
                    logging.info("Restarting browser to reduce detection...")
                    context.close()
                    browser.close()
                    context, browser, page = setup_context(pw)
                    visit_result = safe_visit(page, MAIN_PAGE, pw, proxies)
                    if isinstance(visit_result, tuple):
                        page, context, browser = visit_result

            except Exception as e:
                logging.error(f"Failed for {url}: {e}")

        context.close()
        browser.close()

def main(country, today_str):
    input_path = Path(country) / "Data" / today_str / "Item_urls" / f"{country}_variant_product_ids.json"
    process_products(input_path, country, today_str)

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    countries = ["UAE"]
    for country in countries:
        main(country, today_str)
