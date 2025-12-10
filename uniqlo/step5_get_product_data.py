import os
import json
import re
import sys
from datetime import date, datetime
from functools import partial
from multiprocessing import Pool, cpu_count, set_start_method
from multiprocessing.pool import ThreadPool
from tqdm import tqdm
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

today = date.today().strftime("%Y-%m-%d")
day = datetime.today().strftime('%A')
if day in ["Monday", "Wednesday", "Friday"]:
    countries = ["UK", "USA", "India"]    
elif day in ["Tuesday", "Thursday", "Saturday"]:
    countries = ["Canada", "Spain", "Australia"]
else:
    print(f"Today is {day}. No scraping scheduled.")
    sys.exit(0)
HEADLESS = False

def safe_makedirs(path):
    os.makedirs(path, exist_ok=True)

def write_json_atomic(path, data):
    safe_makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_variant_urls_from_page(soup, base_url):
    variant_urls = []
    base_no_params = base_url.split("?")[0]
    for btn in soup.find_all("button", {"data-testid": "ITOChip"}):
        if btn.has_attr("value"):
            color_code = btn["value"].strip()
            variant_urls.append(f"{base_no_params}?colorDisplayCode={color_code}")
    if not variant_urls:
        for ul in soup.find_all("ul", class_=re.compile("collection-list-horizontal")):
            for btn in ul.find_all("button", {"data-testid": "ITOChip"}):
                if btn.has_attr("value"):
                    color_code = btn["value"].strip()
                    variant_urls.append(f"{base_no_params}?colorDisplayCode={color_code}")
    if not variant_urls:
        variant_urls = [base_no_params]
    return list(dict.fromkeys(variant_urls))

def parse_variant_page_generic(soup, url, country, gender_hint=None):
    product_id = None
    m = re.search(r"/products/([^/]+)/", url)
    if m:
        product_id = m.group(1)
    name_tag = soup.find("h1", class_=re.compile("fr-ec-display")) or soup.find("h1")
    product_name = name_tag.get_text(strip=True) if name_tag else None
    color_name = None
    color_id = "NA"
    if country.lower() == "usa":
        name_div = soup.select_one("div.gutter-container div[data-testid='ITOTypography']")
        if name_div:
            text = name_div.get_text(strip=True)
            if "Color:" in text:
                color_name = text.replace("Color:", "").strip()
                color_id = color_name.split()[0] if color_name else "NA"
    if not color_name:
        # generic
        ctag = soup.find(string=re.compile(r"(Colour:|Color:)"))
        if ctag:
            color_name = ctag.strip().split(":", 1)[-1].strip()
            color_id = color_name.split()[0] if color_name else "NA"

    # sizes
    sizes = []
    for btn in soup.find_all("button", {"data-testid": "ITOChip"}):
        size_text = btn.get_text(strip=True)
        if not size_text or size_text.lower().startswith("helpful"):
            continue
        wrapper = btn.find_parent("div", class_=re.compile("size-chip-wrapper")) or btn.parent
        available = "out_of_stock" if wrapper and wrapper.find(class_=re.compile("strike|strike-through|strike-through")) else "in_stock"
        sizes.append({
            "size_id": str(len(sizes) + 1).zfill(3),
            "size_name": size_text,
            "availability": available
        })

    # price
    price_block = soup.find("div", class_=re.compile("fr-ec-price"))
    launch_price = None
    offer_price = None
    if price_block:
        orig = price_block.find(class_=re.compile("strike"))
        offer = price_block.find(class_=re.compile("fr-ec-price-text--large|fr-ec-price-text"))
        if orig:
            launch_price = orig.get_text(strip=True)
        if offer:
            offer_price = offer.get_text(strip=True)
        if not (launch_price or offer_price):
            txt = price_block.get_text(strip=True)
            offer_price = txt
            launch_price = txt

    # description
    description = None
    desc_div = soup.find(id="productLongDescription-content") or soup.find("div", id=re.compile("product.*Description", re.I))
    if desc_div:
        description = desc_div.get_text(" ", strip=True)

    # composition / origin
    composition = None
    origin = None
    comp_div = soup.find(id="productMaterialDescription-content") or soup.find("div", id=re.compile("productMaterialDescription", re.I))
    if comp_div:
        dd = comp_div.find("dd") or comp_div.find(class_=re.compile("fr-ec-description-list-item-dd"))
        if dd:
            composition = dd.get_text(strip=True)

    # images
    images = []
    for img in soup.select("div.media-gallery--grid img, div.media-gallery img, img"):
        src = img.get("src") or img.get("data-src")
        if src:
            images.append(src.split("?")[0])

    return {
        "product_id": product_id,
        "color_id": color_id,
        "color_name": color_name,
        "gender": gender_hint,
        "title": product_name,
        "variant_url": url,
        "sizes": sizes,
        "prices": {"launch_price": launch_price, "price": offer_price},
        "description": description,
        "composition": composition,
        "origin": origin,
        "images": images,
    }

# --------- Worker for a generic (non-India) country ----------
def scrape_worker(country, gender, category, urls_chunk):
    processed_variants = 0
    variant_url_map = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        with tqdm(total=len(urls_chunk), desc=f"[{country}-{gender}-{category}]", unit="page") as pbar:
            for url in urls_chunk:
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(3500)
                    soup = BeautifulSoup(page.content(), "html.parser")
                    variants = extract_variant_urls_from_page(soup, url)
                    if not variants:
                        pbar.update(1)
                        continue
                    variant_url_map[url] = variants
                    for v_url in variants:
                        try:
                            page.goto(v_url, wait_until="domcontentloaded")
                            page.wait_for_timeout(3000)
                            vsoup = BeautifulSoup(page.content(), "html.parser")
                            data = parse_variant_page_generic(vsoup, v_url, country, gender)
                            out_dir = os.path.join(country, "data", today, "Json_data", gender, category)
                            safe_makedirs(out_dir)
                            filename = f"{data.get('product_id') or 'unknown'}_{data.get('color_id')}.json"
                            out_file = os.path.join(out_dir, filename)
                            if not os.path.exists(out_file):
                                with open(out_file, "w", encoding="utf-8") as jf:
                                    json.dump(data, jf, indent=2, ensure_ascii=False)
                                processed_variants += 1
                        except Exception as e:
                            tqdm.write(f"[{country}] Error parsing {v_url}: {e}")
                    pbar.update(1)
                except Exception as e:
                    tqdm.write(f"[{country}] Error processing {url}: {e}")
        browser.close()
    # write/merge variant urls
    variant_out_dir = os.path.join(country, "data", today, "Item_urls")
    safe_makedirs(variant_out_dir)
    variant_file = os.path.join(variant_out_dir, "variant_urls.json")
    if os.path.exists(variant_file):
        with open(variant_file, "r", encoding="utf-8") as vf:
            variant_data = json.load(vf)
    else:
        variant_data = {}
    variant_data.setdefault(gender, {})[category] = variant_url_map
    write_json_atomic(variant_file, variant_data)
    tqdm.write(f"[{country}] Completed {gender}/{category}: {processed_variants} variants saved and variant URLs logged.")

def scrape_country_products(country):
    product_file = os.path.join(country, "data", today, "Item_urls", "unique_product_url.json")
    if not os.path.exists(product_file):
        print(f"[{country}] No product_urls.json found → {product_file}")
        return
    with open(product_file, "r", encoding="utf-8") as f:
        product_urls = json.load(f)

    for gender, categories in product_urls.items():
        for category, urls in categories.items():
            if not urls:
                continue
            print(f"\n[{country}] Starting {gender}/{category} → {len(urls)} products")
            # split to 3 threads per category (like your previous code)
            url_chunks = [urls[i::3] for i in range(3)]
            worker = partial(scrape_worker, country, gender, category)
            with ThreadPool(processes=3) as pool:
                list(tqdm(pool.imap(worker, url_chunks), total=len(url_chunks), desc=f"[{country}] Threads", unit="chunk"))
    print(f"\n[{country}] All categories completed.")

# --------- India-specific scraper (uses Uniqlo India API flow) ----------
def fetch_category_api_sync(page, cat_id):
    """Synchronous equivalent of your async CATEGORY_API fetch using Playwright page.goto + pre text."""
    CATEGORY_API = (
        "https://www.uniqlo.com/in/api/commerce/v3/en/products"
        "?categoryId={cat_id}&groupBy=subCategoryId&limit=24&offset={offset}&imageRatio=3x4&isV2Review=true"
    )
    offset = 0
    collected = []
    seen_ids = set()
    while True:
        url = CATEGORY_API.format(cat_id=cat_id, offset=offset)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(300)
        try:
            pre_text = page.inner_text("pre")
            data = json.loads(pre_text)
        except Exception:
            # try page.content fallback
            try:
                txt = page.content()
                # extract JSON between <pre> tags if present
                m = re.search(r"<pre[^>]*>(.*?)</pre>", txt, re.S)
                if m:
                    data = json.loads(m.group(1))
                else:
                    data = {}
            except Exception:
                data = {}
        result = data.get("result", {})
        products = result.get("groupedItems", {})
        for prod_list in products.values():
            for p in prod_list:
                pid = p.get("productId")
                if pid and pid not in seen_ids:
                    collected.append(p)
                    seen_ids.add(pid)
        pagination = result.get("pagination", {})
        count = pagination.get("count", 0)
        total = pagination.get("total", len(collected))
        offset = pagination.get("offset", offset + count)
        if len(collected) >= total or count == 0:
            break
    return collected

def extract_colors_from_soup(soup, product_url):
    """Return a list of color dicts like {'color_id','color_name','url'} using similar selectors to your async code."""
    colors = []
    # color inputs wrapper used in your India parser
    chips = soup.select(".color-picker-wrapper input[name='product-color-picker']")
    for chip in chips:
        val = chip.get("value")
        span = chip.find_next("span", {"class": "fr-implicit"})
        color_name = span.get_text(strip=True) if span else (val or "")
        color_id = f"COL{val}" if val else "NA"
        variant_url = f"{product_url.split('?')[0]}?colorCode={color_id}"
        colors.append({"color_id": color_id, "color_name": color_name, "url": variant_url})
    # fallback: look for buttons with value attributes
    if not colors:
        for btn in soup.find_all("button", {"data-testid": "ITOChip"}):
            if btn.has_attr("value"):
                val = btn["value"].strip()
                variant_url = f"{product_url.split('?')[0]}?colorDisplayCode={val}"
                colors.append({"color_id": f"COL{val}", "color_name": val, "url": variant_url})
    if not colors:
        colors = [{"color_id": "NA", "color_name": "default", "url": product_url.split("?")[0]}]
    return colors

def parse_price_from_soup(soup):
    # replicate async parse_price behavior: look for price spans and extract numbers
    spans = soup.select("span.fr-price-currency")
    def extract_number(span):
        abbr = span.find("abbr")
        if abbr:
            nxt = abbr.find_next_sibling("span")
            if nxt:
                return nxt.get_text(strip=True).replace(",", "")
        inner_spans = span.find_all("span")
        if inner_spans:
            return inner_spans[-1].get_text(strip=True).replace(",", "")
        return None
    if not spans:
        return {"launch_price": None, "price": None}
    if len(spans) == 1:
        p = extract_number(spans[0])
        return {"launch_price": p, "price": p}
    launch = extract_number(spans[0])
    price = extract_number(spans[1])
    return {"launch_price": launch, "price": price}

def parse_sizes_from_soup(soup):
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

def scrape_india_products(country="India"):
    # load product list and category ids
    product_file = os.path.join("India", "data", today, "Item_urls", "unique_product_url.json")
    category_file = os.path.join("India", "data", today, "Item_urls", "category_id.json")
    if not os.path.exists(product_file) or not os.path.exists(category_file):
        print("[India] missing input files (unique_product_url.json or category_id.json). Skipping India.")
        return
    with open(product_file, "r", encoding="utf-8") as f:
        product_urls = json.load(f)
    with open(category_file, "r", encoding="utf-8") as f:
        category_ids = json.load(f)

    variant_url_map_total = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        # iterate over genders & subcategories from product_urls
        for gender, cats in product_urls.items():
            for subcat, urls in cats.items():
                if not urls:
                    continue
                print(f"\n[India] Starting {gender}/{subcat} → {len(urls)} products")
                # get cat_id for this gender/subcat
                cat_id = category_ids.get(gender, {}).get(subcat)
                # pre-fetch category API items (meta) if cat_id present
                all_products_meta = []
                if cat_id:
                    try:
                        all_products_meta = fetch_category_api_sync(page, cat_id)
                    except Exception as e:
                        print(f"[India] Error fetching category API for {subcat}: {e}")
                # process sequentially (you can parallelize later)
                variant_map_for_cat = {}
                for product_url in tqdm(urls, desc=f"[India] {gender}/{subcat}", unit="product"):
                    try:
                        # try to match product meta by productId from url
                        pid = product_url.split("/")[-1].split("?")[0]
                        matched_meta = None
                        for pm in all_products_meta:
                            if str(pm.get("productId")) == str(pid):
                                matched_meta = pm
                                break
                        base_info = {
                            "product_id": pid,
                            "gender": gender,
                            "subcategory": subcat,
                            "title": matched_meta.get("name") if matched_meta else None,
                            "description": matched_meta.get("longDescription") if matched_meta else None,
                            "composition": matched_meta.get("composition") if matched_meta else None,
                            "images": matched_meta.get("images", {}) if matched_meta else None,
                            "originalPrice": matched_meta.get("originalPrice") if matched_meta else None,
                            "currentPrice": matched_meta.get("currentPrice") if matched_meta else None,
                            "sizes": matched_meta.get("sizes") if matched_meta else None,
                        }
                        # open product page and extract colors
                        page.goto(product_url, wait_until="domcontentloaded")
                        page.wait_for_timeout(2000)
                        soup = BeautifulSoup(page.content(), "html.parser")
                        colors = extract_colors_from_soup(soup, product_url)
                        variant_map_for_cat[product_url] = [c["url"] for c in colors]
                        # write each variant
                        for col in colors:
                            pid_for_file = base_info.get("product_id") or pid
                            cat_folder = subcat.replace(" ", "_")
                            out_dir = os.path.join("India", "data", today, "Json_data", gender, cat_folder)
                            safe_makedirs(out_dir)
                            fname = f"{pid_for_file}_{col['color_id']}.json"
                            fpath = os.path.join(out_dir, fname)
                            if os.path.exists(fpath):
                                # skip existing
                                continue
                            # go to color variant page
                            page.goto(col["url"], wait_until="domcontentloaded")
                            page.wait_for_timeout(2000)
                            vsoup = BeautifulSoup(page.content(), "html.parser")
                            price_info = parse_price_from_soup(vsoup)
                            if not price_info["price"]:
                                price_info = {
                                    "launch_price": base_info.get("originalPrice"),
                                    "price": base_info.get("currentPrice"),
                                }
                            if not price_info["price"]:
                                # skip if no price found
                                continue
                            sizes = parse_sizes_from_soup(vsoup)
                            if not sizes and base_info.get("sizes"):
                                sizes = [
                                    {"size_id": s.get("sizeCode"), "size_name": s.get("name"), "availability": "in_stock"}
                                    for s in base_info.get("sizes", [])
                                ]
                            origin = None
                            # try origin
                            dt = vsoup.find("dt", string=re.compile("Country of origin", re.I))
                            if dt:
                                dd = dt.find_next_sibling("dd")
                                if dd:
                                    origin = dd.get_text(strip=True)
                            # gender tag
                            gender_tag = None
                            gspan = vsoup.select_one("span._1kLSda5-fn20Mr_BiNq8he span._3ZCRetYsLGqegtYYXaS6tt")
                            if gspan:
                                gender_tag = gspan.get_text(strip=True).lower()
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
                            with open(fpath, "w", encoding="utf-8") as jf:
                                json.dump(variant, jf, indent=2, ensure_ascii=False)
                    except Exception as e:
                        tqdm.write(f"[India] Error processing {product_url}: {e}")
                # save variant urls for category
                variant_url_dir = os.path.join("India", "data", today, "Item_urls")
                safe_makedirs(variant_url_dir)
                variant_file = os.path.join(variant_url_dir, "variant_urls.json")
                if os.path.exists(variant_file):
                    with open(variant_file, "r", encoding="utf-8") as vf:
                        existing = json.load(vf)
                else:
                    existing = {}
                existing.setdefault(gender, {})[subcat] = variant_map_for_cat
                write_json_atomic(variant_file, existing)

        page.close()
        browser.close()
    print("[India] Completed all categories.")

# --------- MAIN (multiprocessing across countries) ----------
def dispatch(country):
    if country.lower() == "india":
        scrape_india_products()
    else:
        scrape_country_products(country)


def main():
    try:
        set_start_method("spawn")
    except Exception:
        pass

    max_processes = min(cpu_count(), len(countries))

    with Pool(processes=max_processes) as pool:
        list(
            tqdm(
                pool.imap(dispatch, countries),
                total=len(countries),
                desc="Overall Progress",
                unit="country"
            )
        )


if __name__ == "__main__":
    main()
