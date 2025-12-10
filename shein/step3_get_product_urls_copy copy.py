import asyncio
import json
import os
import re
import random
import logging
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

REQUEST_DELAY = 20
MAX_PROXY_ATTEMPTS = 5
MAX_TABS = 4
GOTO_TIMEOUT = 30000
PROXY_LIST_FILE = 'proxies.txt'
WEBSITE_NAME = "SHEININDIA"
time_stamp = datetime.now().strftime("%Y%m%d")

dead_proxies = set()
domain_blocked = {}
# Tracking consecutive access denied responses
access_denied_counter = 0

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

os.makedirs(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}", exist_ok=True)
os.makedirs(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}", exist_ok=True)

def load_proxies():
    proxies = []
    if os.path.exists(PROXY_LIST_FILE):
        with open(PROXY_LIST_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    proxies.append(line)
    return proxies

proxy_list = load_proxies()

def parse_proxy(proxy):
    pattern_auth = re.compile(r"^(?P<ip>[\d\.]+):(?P<port>\d+):(?P<user>[^:]+):(?P<pass>.+)$")
    pattern_noauth = re.compile(r"^(?P<ip>[\d\.]+):(?P<port>\d+)$")
    m_auth = pattern_auth.match(proxy)
    m_noauth = pattern_noauth.match(proxy)
    if m_auth:
        gd = m_auth.groupdict()
        return {
            "server": f"http://{gd['ip']}:{gd['port']}",
            "username": gd["user"],
            "password": gd["pass"],
        }
    elif m_noauth:
        gd = m_noauth.groupdict()
        return {"server": f"http://{gd['ip']}:{gd['port']}"}
    else:
        logging.warning(f"Skipping invalid proxy format: {proxy}")
        return None

def flatten_shein_data(data):
    flat_data = []
    for gender, categories in data.items():
        for category_name, category_info in categories.items():
            category_url = category_info.get("url")
            subcategories = category_info.get("subcategories", {})
            item = {
                "gender": gender,
                "category": category_name,
                "category_url": category_url,
                "subcategories": []
            }
            for sub_name, sub_url in subcategories.items():
                item["subcategories"].append({
                    "sub_cat_name": sub_name,
                    "sub_cat_url": sub_url
                })
            if not item["subcategories"]:
                item["subcategories"] = None
            flat_data.append(item)
    return flat_data

def append_to_json_file(filepath, new_data):
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4)
    with open(filepath, 'r+', encoding='utf-8') as f:
        try:
            existing_data = json.load(f)
        except Exception:
            existing_data = []
        if not isinstance(existing_data, list):
            existing_data = [existing_data]
        existing_data.append(new_data)
        f.seek(0)
        json.dump(existing_data, f, indent=4)
        f.truncate()

def extract_domain(url):
    return re.sub(r'^https?://', '', url).split('/')[0].replace('www.', '')

async def process_products(item):
    global access_denied_counter
    url = item.get('category_url') or (item['subcategories'][0]['sub_cat_url'] if item['subcategories'] else None)
    if not url:
        logging.info(f"No URL found for {item}")
        return

    domain = extract_domain(url)
    use_proxy = domain_blocked.get(domain, False)
    proxy_attempted = set()
    attempt_number = 0

    while True:
        proxy_config = None
        proxy_str = None
        if use_proxy:
            if len(proxy_attempted) >= MAX_PROXY_ATTEMPTS:
                logging.warning(f"Too many failed proxies for {url}, aborting.")
                return
            proxies_available = [p for p in proxy_list if p not in proxy_attempted and p not in dead_proxies]
            while proxies_available:
                candidate = random.choice(proxies_available)
                proxy_config = parse_proxy(candidate)
                if proxy_config:
                    proxy_str = candidate
                    break
                else:
                    proxy_attempted.add(candidate)
                    proxies_available.remove(candidate)
            if not proxy_config:
                logging.error(f"No valid proxies available for {url}")
                return

        logging.info(f"{item['category']} [{attempt_number+1}] {'with proxy' if use_proxy else 'direct'} {proxy_str or ''}")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False, proxy=proxy_config)
                context = await browser.new_context()
                page = await context.new_page()
                await asyncio.sleep(REQUEST_DELAY)
                await page.goto(url, timeout=GOTO_TIMEOUT)
                content = await page.content()

                # Check for access denied
                if "Access Denied" in content or "verify you are human" in content:
                    access_denied_counter += 1
                    logging.warning(f"Access denied: {url} [{proxy_str or 'direct'}] - count {access_denied_counter}")
                    await context.close()
                    await browser.close()

                    if access_denied_counter >= 3:
                        logging.info("Access denied encountered 3 times, sleeping for 30 minutes")
                        await asyncio.sleep(1800)  # 30 minutes
                        access_denied_counter = 0
                    # Set domain blocked and switch to proxy for subsequent attempts
                    if not use_proxy:
                        domain_blocked[domain] = True
                        use_proxy = True
                    attempt_number = 0
                    continue
                else:
                    # Reset counter on successful access
                    access_denied_counter = 0

                # --- your scraping logic below: adjust selectors as needed ---
                try:
                    total_products_text = await page.locator('.length strong').inner_text()
                    total_products = int(total_products_text.split()[0].replace(",", ""))
                    product_links = await page.locator(".item.rilrtl-products-list__item.item a").all()
                    urls = []
                    for locator in product_links:
                        link = await locator.get_attribute("href")
                        if link:
                            urls.append(link)
                    item_details = {
                        "gender": item["gender"],
                        "category": item["category"],
                        "sub_cat_name": (item['subcategories'][0]['sub_cat_name'] if item['subcategories'] else None),
                        "product_count_from_url": total_products,
                        "product_count_found": len(urls),
                        "url": urls
                    }
                    append_to_json_file(f"{WEBSITE_NAME}/PRODUCT/{time_stamp}/product_url.json", item_details)
                    await context.close()
                    await browser.close()
                    return
                except Exception as page_ex:
                    logging.warning(f"Parsing error {page_ex}")
                    await context.close()
                    await browser.close()
                    return

        except PlaywrightTimeoutError as t_ex:
            logging.warning(f"Timeout: {url} [{proxy_str or 'direct'}]: {t_ex}")
            if proxy_str:
                dead_proxies.add(proxy_str)
                proxy_attempted.add(proxy_str)
            attempt_number += 1
            continue

        except Exception as ex:
            logging.warning(f"Error: {url} [{proxy_str or 'direct'}]: {ex}")
            if proxy_str:
                dead_proxies.add(proxy_str)
                proxy_attempted.add(proxy_str)
            attempt_number += 1
            continue

async def run_all(flat_data):
    semaphore = asyncio.Semaphore(MAX_TABS)

    async def sem_task(item):
        async with semaphore:
            await process_products(item)

    tasks = [asyncio.create_task(sem_task(item)) for item in flat_data]
    await asyncio.gather(*tasks)

def main():
    file_path_category = f"{WEBSITE_NAME}/CATEGORY/{time_stamp}/sheinindia_category_urls.json"
    if os.path.exists(file_path_category):
        with open(file_path_category, "r", encoding="utf-8") as file:
            category_data = json.load(file)
        category_data.pop('status', None)
        category_data.pop('date', None)
    else:
        category_data = {}
    flat_data = flatten_shein_data(category_data)
    asyncio.run(run_all(flat_data))

if __name__ == "__main__":
    main()
