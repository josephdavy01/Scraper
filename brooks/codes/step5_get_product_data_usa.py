import os
import json
from datetime import date
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

today = date.today().strftime('%Y-%m-%d')
BASE_DIR = f"USA/data/{today}/Json_data"
URL_FILE = f"USA/data/{today}/Item_urls/unique_product_urls.json"
VARIANT_FILE = f"USA/data/{today}/Item_urls/variant_urls.json"
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(os.path.dirname(VARIANT_FILE), exist_ok=True)

def extract_price(soup):
    price_data = {"original_price": None, "sale_price": None}
    price_div = soup.find("div", class_="m-buy-box-header__price")
    if not price_div:
        return price_data
    sale_span = price_div.find("span", class_="pricing__sale")
    if sale_span:
        sale_price_text = sale_span.get_text(strip=True).replace("$", "").strip()
        if sale_price_text:
            try:
                price_data["sale_price"] = float(sale_price_text)
            except ValueError:
                pass
    original_span = price_div.find("span", class_="pricing__base")
    if original_span:
        orig_price_text = original_span.get_text(strip=True).replace("$", "").replace("Original price", "").strip()
        if orig_price_text:
            try:
                price_data["original_price"] = float(orig_price_text)
            except ValueError:
                pass
    if not price_data["sale_price"]:
        price_data["sale_price"] = price_data["original_price"]
    return price_data

def flatten_urls_with_categories(d):
    result = []
    if isinstance(d, dict):
        for main_cat, subcats in d.items():
            if isinstance(subcats, dict):
                for sub_cat, urls in subcats.items():
                    if isinstance(urls, list):
                        for url in urls:
                            result.append((url, main_cat, sub_cat))
                    else:
                        result.extend(flatten_urls_with_categories({main_cat: subcats}))
            else:
                result.extend(flatten_urls_with_categories(subcats))
    elif isinstance(d, list):
        for item in d:
            result.extend(flatten_urls_with_categories(item))
    elif isinstance(d, str) and d.startswith("http"):
        result.append((d, "unknown", "unknown"))
    return result

def extract_jsonld_data(soup):
    script_tag = soup.find("script", {"type": "application/ld+json", "id": "schemaData"})
    if script_tag:
        try:
            return json.loads(script_tag.string.strip())
        except json.JSONDecodeError:
            return None
    return None

def extract_sizes(soup):
    sizes = []
    size_types = ["size_Shoe", "size_Apparel", "size_Bra", "bandSize"]
    for size_type in size_types:
        size_div = soup.find("div", {"class": "js-generic-attributes", "data-attr": size_type})
        if not size_div:
            continue
        ul_tag = size_div.find("ul", class_=lambda x: x and f"m-buy-box-grid__{size_type}" in x)
        if not ul_tag:
            continue
        for li in ul_tag.find_all("li", class_="m-buy-box-grid__item js-product-change-item"):
            btn = li.find("button")
            if not btn:
                continue
            span = btn.find("span", class_="a-type-p--caption")
            if not span:
                continue
            size_name = span.get_text(strip=True)
            btn_classes = btn.get("class", [])
            in_stock = "m-buy-box-grid__btn--sold-out" not in btn_classes
            sizes.append({
                "size": size_name,
                "in_stock": in_stock,
                "size_type": size_type.replace("size_", "")
            })
    return sizes

def extract_color_info(soup, url):
    color_span = soup.find("span", class_="a-type-p--label m-buy-box__selected-name")
    if color_span:
        text = color_span.get_text(strip=True)
        if text and "-" in text:
            parts = text.split("-", 1)
            return {
                "color_id": parts[0].strip(),
                "color_name": parts[1].strip(),
                "is_sale": color_span.has_attr("data-is-sale")
            }
        elif text:
            return {"color_id": "default", "color_name": text.strip(), "is_sale": color_span.has_attr("data-is-sale")}
    color_div = soup.find("div", {"data-attr": "color"})
    if color_div:
        name_tag = color_div.find(["span", "p"], class_=lambda x: x and "selected-name" in x)
        if name_tag:
            text = name_tag.get_text(strip=True)
            if text and "-" in text:
                parts = text.split("-", 1)
                return {
                    "color_id": parts[0].strip(),
                    "color_name": parts[1].strip(),
                    "is_sale": name_tag.has_attr("data-is-sale")
                }
            elif text:
                return {"color_id": "default", "color_name": text.strip(), "is_sale": name_tag.has_attr("data-is-sale")}
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key, val in query.items():
        if key.lower().endswith("_color") and val:
            return {"color_id": val[0], "color_name": None, "is_sale": False}
    return {"color_id": "default", "color_name": None, "is_sale": False}

def extract_description_and_features(soup):
    data = {"full_description": None, "occasion": [], "features": [], "specs": {}}
    desc_section = soup.select_one("section.m-long-description")
    if desc_section:
        desc_p = desc_section.select_one("p.m-long-description-text")
        if desc_p:
            data["full_description"] = desc_p.get_text(strip=True)
        for li in desc_section.select("ul.m-long-description__best-for li.m-long-description__best-for-item div.m-long-description__best-for-text"):
            data["occasion"].append(li.get_text(strip=True))
        for li in desc_section.select("ul.m-long-description__features li.m-long-description__feature div.m-long-description__feature-text"):
            data["features"].append(li.get_text(strip=True))
    specs_section = soup.select_one("section#section-1")
    if specs_section:
        for tr in specs_section.select("table.m-definitions-table tr.m-definition-widget"):
            key_tag = tr.select_one("td.m-definition-widget__term div.m-info-label h3.m-info-label__headline")
            val_tag = tr.select_one("td.m-definition-widget__definition div.a-type-p--caption")
            if key_tag and val_tag:
                data["specs"][key_tag.get_text(strip=True)] = val_tag.get_text(strip=True)
    return data

def scrape_product(page, url):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        soup = BeautifulSoup(page.content(), "html.parser")
        result = {
            "url": url,
            "jsonld_data": extract_jsonld_data(soup),
            "color_info": extract_color_info(soup, url),
            "sizes": extract_sizes(soup),
            "price_info": extract_price(soup),
        }
        result.update(extract_description_and_features(soup))
        return result
    except PlaywrightTimeoutError:
        print(f"Timeout while loading: {url}")
        return None
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def save_product_data(data, main_cat, sub_cat, url):
    if not data:
        print(f"No data to save for {url}")
        return
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    color_id = "default"
    for k, v in query.items():
        if k.endswith("_color") and v:
            color_id = v[0]
            break
    product_id = url.split("/")[-1].split("?")[0].split(".")[0]  
    dir_path = os.path.join(BASE_DIR, main_cat, sub_cat)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{product_id}_{color_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {file_path}")

def extract_variant_params(soup):
    variants = []
    options_div = soup.find("div", class_="m-buy-box__options-container")
    if not options_div:
        return variants
    ul = options_div.find(
        "ul",
        class_="m-buy-box-grid m-buy-box-grid-variation-colors js-color-attributes"
    )
    if not ul:
        return variants
    for li in ul.find_all("li", class_="m-buy-box-grid__item js-product-change-item"):
        button = li.find("button")
        if not button or not button.has_attr("data-url"):
            continue
        data_url = button["data-url"]
        parsed = urlparse(data_url)
        q = parse_qs(parsed.query)
        pid = q.get("pid", [None])[0]
        if not pid:
            continue
        color_key = f"dwvar_{pid}_color"
        if color_key in q and not q[color_key][0]:
            color_val = button.get("data-attr-value")
            if color_val:
                q[color_key] = [color_val]
        if color_key in q:
            param_str = f"{color_key}={q[color_key][0]}"
            variants.append(param_str)
    return variants

def main():
    with open(URL_FILE, "r", encoding="utf-8") as f:
        nested_urls = json.load(f)
    product_entries = flatten_urls_with_categories(nested_urls)
    print(f"Found {len(product_entries)} product URLs to scrape.")
    variant_dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        for idx, (url, main_cat, sub_cat) in enumerate(product_entries, start=1):
            if not url.startswith("http"):
                print(f"Skipping invalid URL: {url}")
                continue
            print(f"[{idx}/{len(product_entries)}] Scraping base: {url}")
            base_data = scrape_product(page, url)
            if base_data:
                save_product_data(base_data, main_cat, sub_cat, url)
                print(f"Saved data for base URL: {url}")
            else:
                print(f"Failed to scrape base URL: {url}")
            parsed_base = urlparse(url)
            base_query = parse_qs(parsed_base.query)
            base_color = None
            for k, v in base_query.items():
                if k.endswith("_color") and v:
                    base_color = v[0]
                    break
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                soup = BeautifulSoup(page.content(), "html.parser")
            except Exception as e:
                print(f"Error loading page for variants {url}: {e}")
                soup = None
            variant_urls = [url] 
            if soup:
                variant_params = extract_variant_params(soup)
                print(f"Found {len(variant_params)} color variants for {url}")
                base_path = parsed_base.path
                base_url_no_query = f"{parsed_base.scheme}://{parsed_base.netloc}{base_path}"
                if not base_path.endswith(".html"):
                    base_url_no_query = url.split("?")[0]
                for param_str in variant_params:
                    param_color = None
                    if "_color=" in param_str:
                        param_color = param_str.split("=")[1]
                    if param_color == base_color:
                        continue
                    variant_url = f"{base_url_no_query}?{param_str}"
                    variant_urls.append(variant_url)
                    var_data = scrape_product(page, variant_url)
                    if var_data:
                        save_product_data(var_data, main_cat, sub_cat, variant_url)
                        print(f"Saved data for: {variant_url}")
                    else:
                        print(f"Failed to scrape: {variant_url}")
            if main_cat not in variant_dict:
                variant_dict[main_cat] = {}
            if sub_cat not in variant_dict[main_cat]:
                variant_dict[main_cat][sub_cat] = []
            seen = set()
            unique_urls = []
            for u in variant_urls:
                if u not in seen:
                    seen.add(u)
                    unique_urls.append(u)
            variant_dict[main_cat][sub_cat].extend(unique_urls)
        browser.close()
    with open(VARIANT_FILE, "w", encoding="utf-8") as f:
        json.dump(variant_dict, f, indent=2)
    print(f"Scraping completed! Variant URLs saved to: {VARIANT_FILE}")

if __name__ == "__main__":
    main()