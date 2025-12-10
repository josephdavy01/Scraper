import os
import json
import asyncio
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

today = date.today().strftime("%Y-%m-%d")
# today = '2025-10-07'
BASE_DIR = os.path.join("India", "data", today, "Json_data")
os.makedirs(BASE_DIR, exist_ok=True)
INPUT_FILE = os.path.join("India", "data", today, "Item_urls", "unique_product_url.json")
VARIANT_FILE = os.path.join("India", "data", today, "Item_urls", "variant_urls.json")
CATEGORY_FILE = os.path.join("India", "data", today, "Item_urls", "category_id.json")

CATEGORY_API = (
    "https://www.uniqlo.com/in/api/commerce/v3/en/products"
    "?categoryId={cat_id}&groupBy=subCategoryId&limit=24&offset={offset}&imageRatio=3x4&isV2Review=true"
)

progress_lock = asyncio.Lock()

def parse_product_id(soup):
    p_tag = soup.find("p", string=lambda s: s and "Product ID:" in s)
    if p_tag:
        text = p_tag.get_text(strip=True)
        import re
        match = re.search(r"Product ID:\s*(\w+)", text)
        if match:
            return match.group(1).strip()
    return None


async def parse_price(soup):
    launch_price = None
    price = None
    price_spans = soup.select("span.fr-price-currency.ktVAZaqso8QtBL2hOQKK8")

    def extract_number(span):
        abbr = span.find("abbr")
        if abbr:
            number_span = abbr.find_next_sibling("span")
            if number_span:
                return number_span.get_text(strip=True).replace(",", "")
        inner_spans = span.find_all("span")
        if inner_spans:
            return inner_spans[-1].get_text(strip=True).replace(",", "")
        return None

    if len(price_spans) == 0:
        return {"launch_price": None, "price": None}
    elif len(price_spans) == 1:
        p = extract_number(price_spans[0])
        return {"launch_price": p, "price": p}
    else:
        launch_price = extract_number(price_spans[0])
        price = extract_number(price_spans[1])
        return {"launch_price": launch_price, "price": price}

def parse_colors(soup, product_url):
    colors = []
    chips = soup.select(".color-picker-wrapper input[name='product-color-picker']")
    for chip in chips:
        val = chip.get("value")
        span = chip.find_next("span", {"class": "fr-implicit"})
        color_name = span.get_text(strip=True) if span else val
        color_id = f"COL{val}"
        variant_url = f"{product_url.split('?')[0]}?colorCode={color_id}"
        colors.append({"color_id": color_id, "color_name": color_name, "url": variant_url})
    return colors

def parse_sizes(soup):
    sizes = []
    chips = soup.select(".size-picker-wrapper [class*='fr-chip-wrapper']")
    for chip in chips:
        size_span = chip.select_one(".fr-chip-text")
        if not size_span:
            continue
        size_name = size_span.get_text(strip=True)
        input_el = chip.select_one("input")
        size_id = input_el["value"] if input_el else None
        availability = "out_of_stock" if chip.select_one(".chip-strikethrough-icon") else "in_stock"
        sizes.append({"size_id": size_id, "size_name": size_name, "availability": availability})
    return sizes

def parse_origin(soup):
    dt_tag = soup.find("dt", string=lambda s: s and "Country of origin" in s)
    if dt_tag:
        dd_tag = dt_tag.find_next_sibling("dd")
        if dd_tag:
            return dd_tag.get_text(strip=True)
    return None

def parse_gender(soup):
    try:
        span = soup.select_one("span._1kLSda5-fn20Mr_BiNq8he span._3ZCRetYsLGqegtYYXaS6tt")
        if span:
            gender_text = span.get_text(strip=True).replace("\xa0", "").strip()
            return gender_text.lower()
    except Exception:
        pass
    return None


async def fetch_category_api(page, cat_id):
    offset = 0
    collected = []
    seen_ids = set()
    while True:
        url = CATEGORY_API.format(cat_id=cat_id, offset=offset)
        await page.goto(url)
        pre_text = await page.inner_text("pre")
        data = json.loads(pre_text)
        result = data.get("result", {})
        products = result.get("groupedItems", {})
        new_products = []
        for prod_list in products.values():
            for p in prod_list:
                pid = p.get("productId")
                if pid and pid not in seen_ids:
                    new_products.append(p)
                    seen_ids.add(pid)
        collected.extend(new_products)
        pagination = result.get("pagination", {})
        count = pagination.get("count", 0)
        total = pagination.get("total", len(collected))
        offset = pagination.get("offset", offset + count)
        if len(collected) >= total or count == 0:
            break
    return collected


async def scrape_variants(page, product_url, base_info, variant_urls_data, gender, subcat, total_progress, done_progress):
    await page.goto(product_url, timeout=60000)
    try:
        await page.wait_for_selector(".color-picker-wrapper", timeout=15000)
    except Exception:
        print(f"Warning: color picker not found for {product_url}")
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    actual_pid = parse_product_id(soup)
    if actual_pid:
        base_info["product_id"] = actual_pid
    colors = parse_colors(soup, product_url)
    variant_urls_data.setdefault(gender, {}).setdefault(subcat, []).extend([c["url"] for c in colors])

    for col in colors:
        cat_folder = f"{subcat.replace(' ', '_')}"
        save_dir = os.path.join(BASE_DIR, gender, cat_folder)
        os.makedirs(save_dir, exist_ok=True)
        pid = base_info['product_id']
        fname = f"{pid}_{col['color_id']}.json"
        fpath = os.path.join(save_dir, fname)
        if os.path.exists(fpath):
            print(f"Skipping {fname}, already exists")
            continue
        await page.goto(col["url"], timeout=60000)
        try:
            await page.wait_for_selector(".size-picker-wrapper", timeout=15000)
            await page.wait_for_selector("span[class*='fr-price']", timeout=15000)
        except Exception:
            print(f"Warning: sizes/prices not fully loaded for {col['url']}")
        vhtml = await page.content()
        vsoup = BeautifulSoup(vhtml, "html.parser")
        price_info = await parse_price(vsoup)
        if not price_info["price"]:
            price_info = {
                "launch_price": base_info.get("originalPrice"),
                "price": base_info.get("currentPrice"),
            }
        if not price_info["price"]:
            print(f"Skipping {pid} color {col['color_name']} - price is null")
            continue

        sizes = parse_sizes(vsoup)
        if not sizes and base_info.get("sizes"):
            sizes = [
                {"size_id": s.get("sizeCode"), "size_name": s.get("name"), "availability": "in_stock"}
                for s in base_info.get("sizes", [])
            ]
        origin = parse_origin(vsoup)
        gender_tag = parse_gender(vsoup)
        if gender_tag:
            gender = gender_tag  

        variant = {
            **base_info,
            "gender": gender,  
            "color_id": col["color_id"],
            "color_name": col["color_name"],
            "variant_url": col["url"],
            "sizes": sizes,
            "prices": price_info,
            "origin": origin,
        }

        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(variant, f, indent=2, ensure_ascii=False)
        print(f"Saved {fname}")

    async with progress_lock:
        done_progress[0] += 1
        percent = (done_progress[0] / total_progress) * 100
        print(f"Progress: {done_progress[0]} / {total_progress} ({percent:.1f}%)")


async def worker_slice(browser, task_slice, gender, subcat, category_ids, product_details, variant_urls_data, total_progress, done_progress):
    page = await browser.new_page()
    cat_id = category_ids.get(gender, {}).get(subcat)
    if not cat_id:
        print(f"Missing cat_id for {gender} → {subcat}, skipping")
        await page.close()
        return
    all_products = await fetch_category_api(page, cat_id)

    for product_url in task_slice:
        try:
            pid = product_url.split("/")[-1].split("?")[0]
            prod = next((p for p in all_products if p.get("productId") == pid), None)
            if not prod:
                print(f"No product found in category API for {pid}")
                async with progress_lock:
                    done_progress[0] += 1
                    percent = (done_progress[0] / total_progress) * 100
                    print(f"Progress: {done_progress[0]} / {total_progress} ({percent:.1f}%)")
                continue
            base_info = {
                "product_id": pid,
                "gender": gender,
                "subcategory": subcat,
                "title": prod.get("name"),
                "description": prod.get("longDescription"),
                "composition": prod.get("composition"),
                "images": prod.get("images", {}),
                "originalPrice": prod.get("originalPrice"),
                "currentPrice": prod.get("currentPrice"),
                "sizes": prod.get("sizes"),
            }
            await scrape_variants(page, product_url, base_info, variant_urls_data, gender, subcat, total_progress, done_progress)
        except Exception as e:
            print(f"Error with {product_url}: {e}")
            async with progress_lock:
                done_progress[0] += 1
                percent = (done_progress[0] / total_progress) * 100
                print(f"Progress: {done_progress[0]} / {total_progress} ({percent:.1f}%)") # type: ignore
    await page.close()

# ------------------ Main ------------------

async def main():
    day = datetime.today().strftime('%A')
    if day not in ["Monday", "Wednesday", "Friday"]:
        print(f"Today is {day}. Script runs only on Monday, Wednesday, and Friday. Exiting.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        product_urls = json.load(f)
    with open(CATEGORY_FILE, "r", encoding="utf-8") as f:
        category_ids = json.load(f)

    variant_urls_data = {}
    tasks = []

    for gender, cats in product_urls.items():
        for subcat, urls in cats.items():
            tasks.append((gender, subcat, urls))

    total_urls = sum(len(urls) for _, _, urls in tasks)
    done_progress = [0]

    async with async_playwright() as p:
        browsers = [await p.chromium.launch(headless=False) for _ in range(2)]  

        # Split tasks among the 2 browsers sequentially
        for i, (gender, subcat, urls) in enumerate(tasks):
            browser = browsers[i % 2]
            await worker_slice(browser, urls, gender, subcat, category_ids, product_urls, variant_urls_data, total_urls, done_progress)

        for b in browsers:
            await b.close()

    with open(VARIANT_FILE, "w", encoding="utf-8") as f:
        json.dump(variant_urls_data, f, indent=2, ensure_ascii=False)
    print(f"Done! Variant URLs saved to {VARIANT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
