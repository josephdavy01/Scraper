import re
import json
import time
import logging
from tqdm import tqdm
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from seleniumbase import Driver



# Save JSON (separate file for each product)
def save_json(main_category, sub_category, product_name, product_data, country, today_str):
    gender = main_category
    category = sub_category if sub_category else main_category
    safe_name = "".join(c for c in product_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    base_path = Path(country) / "Data" / today_str / "Json_Data" / gender / category
    base_path.mkdir(parents=True, exist_ok=True)
    file_path = base_path / f'{safe_name}.json'

    counter = 1
    while file_path.exists():
        file_path = base_path / f'{safe_name}_{counter}.json'
        counter += 1

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(product_data, f, indent=4, ensure_ascii=False)

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


# Get product data
def get_product_data(driver, url, today_str):
    product_json = {}
    
    # Open URL using UC mode with reconnect time to bypass detection
    driver.uc_open_with_reconnect(url, reconnect_time=4)
    
    # Remove common blocking elements
    blocking_selectors = [
        # Cookie banners
        '.cookie-banner', '.cookie-notice', '.cookie-consent', '#cookie-banner',
        '.gdpr-banner', '.privacy-notice', '.consent-banner',
        # Popups and modals
        '.popup', '.modal', '.overlay', '.lightbox', '.dialog',
        '.newsletter-popup', '.email-popup', '.subscription-popup',
        # Notifications
        '.notification', '.alert', '.toast', '.snackbar',
        # Age verification
        '.age-verification', '.age-gate', '.age-check',
        # Generic blocking elements
        '.blocking-overlay', '.site-overlay', '.page-overlay',
        '.interstitial', '.splash-screen'
    ]
    
    # Wait a moment for potential blocking elements to appear
    time.sleep(2)
    
    # Remove blocking elements using JavaScript
    for selector in blocking_selectors:
        try:
            driver.execute_script(f'''
                const elements = document.querySelectorAll("{selector}");
                elements.forEach(el => el.remove());
            ''')
        except:
            pass
    
    # Click any "Accept" or "Close" buttons for remaining popups
    close_button_selectors = [
        'button[class*="accept"]', 'button[class*="close"]', 'button[class*="dismiss"]',
        '.accept-btn', '.close-btn', '.dismiss-btn', '.continue-btn',
        '[aria-label*="close"]', '[aria-label*="dismiss"]', '[aria-label*="accept"]',
        '.cookie-accept', '.privacy-accept', '.consent-accept'
    ]
    
    for selector in close_button_selectors:
        try:
            if driver.is_element_present(selector):
                driver.click(selector)
                time.sleep(0.5)
        except:
            pass
    
    # Press ESC key to close any remaining modals
    try:
        driver.press_keys("body", "\ue00c")
        time.sleep(1)
    except:
        pass
    
    try:
        driver.wait_for_element("div.swatch-attribute.size .swatch-option.text", timeout=50)
    except Exception:
        logging.warning(f"No size selector found for {url}")
    
    time.sleep(2)

    # Get page content
    content = driver.get_page_source()
    soup = BeautifulSoup(content, "html.parser")

    # Product JSON
    script_tag = soup.find('script', {'type': 'application/ld+json'})
    if not script_tag:
        raise Exception("Product JSON script not found")
    product_json['product'] = json.loads(script_tag.get_text())

    # Extract product_id + color_id from URL
    match = re.search(r'([0-9a-zA-Z]+)-(\d+)\.html', url)
    if match:
        product_id = match.group(1)
        color_id = match.group(2)
        file_id = f"{product_id}_{color_id}"
    else:
        file_id = "unknown_id"

    # Sizes
    size_elements = soup.select("div.swatch-attribute.size .swatch-option.text")
    sizes = []
    for elem in size_elements:
        label = elem.get("data-option-label") or elem.get("aria-label") or elem.get_text(strip=True)
        if label and label not in sizes:
            sizes.append(label)
    product_json["available_sizes"] = sizes


    # Gender
    gender = soup.select("div.asc_gender_wrapper span")
    if gender:
        product_json["gender"] = gender[0].get_text(strip=True)

    # Images
    images = [img["src"] for img in soup.select(".revton-gallery__thumb__item img") if img.get("src")]
    product_json["images"] = images

    # Description
    for block in soup.select(".product-custom-attribute.asc_pronation"):
        title = block.select_one(".asc_pronation-title span")
        if title and "Description" in title.get_text(strip=True):
            content_div = block.select_one(".asc_pronation-content")
            if content_div:
                desc_lines = [
                    f.strip("• ").strip()
                    for f in content_div.get_text(separator="\n").split("\n")
                    if f.strip()
                ]
                product_json["desc"] = " ".join(desc_lines)

    # Color Name
    cname = soup.select_one("div.color-chooser span.current-color")
    if cname:
        product_json["cname"] = cname.get_text(strip=True)

    # Tech features
    for block in soup.select(".product-custom-attribute.asc_pronation"):
        title = block.select_one(".asc_pronation-title span")
        if title and "Tech & Features" in title.get_text(strip=True):
            content_div = block.select_one(".asc_pronation-content")
            if content_div:
                features = [
                    f.strip("• ").strip()
                    for f in content_div.get_text(separator="\n").split("\n")
                    if f.strip()
                ]
                product_json["tech_features"] = features

    product_json['url'] = url
    product_json['date'] = today_str

    return file_id, {"product": product_json}


# Worker for scraping
def scrape_product(driver, main_category, sub_category, url, country, today_str):
    try:
        name, data = get_product_data(driver, url, today_str)
        save_json(main_category, sub_category, name, data, country, today_str)
    except Exception as e:
        logging.error(f"Failed for {url}: {e}")


# Main processing function
def process_products(input_path, country, today_str):
    product_urls = load_product_urls(input_path)
    
    # Initialize SeleniumBase driver with UC mode
    driver = Driver(uc=True, headless=False)
    
    try:
        # Process each URL with progress bar
        for main_category, sub_category, url in tqdm(product_urls, desc="Scraping Products"):
            scrape_product(driver, main_category, sub_category, url, country, today_str)
    finally:
        driver.quit()

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-11-29'
    countries = ["UAE"]
    for country in countries:
        input_path = Path(country) / "Data" / today_str / "Item_urls" / f"{country}_unique_product_urls.json"
        process_products(input_path, country, today_str)
