import os
import json
from datetime import date,datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

GEOGRAPHIES = {
    "UK": "https://www.uniqlo.com/uk/en/",
    "USA": "https://www.uniqlo.com/us/en/",
    "Canada": "https://www.uniqlo.com/ca/en/",
    "Spain": "https://www.uniqlo.com/es/en/",
    "Australia": "https://www.uniqlo.com/au/en/"
}
today = date.today().strftime("%Y-%m-%d")
day = datetime.strptime(today, '%Y-%m-%d').strftime('%A')
def accept_cookies(page):
    try:
        print("Waiting for cookies popup...")
        page.wait_for_selector("button#onetrust-accept-btn-handler", timeout=15000)
        page.click("button#onetrust-accept-btn-handler")
        print("Cookies accepted")
    except PlaywrightTimeoutError:
        print("No cookies popup found")

def detect_gender(url: str) -> str:
    url = url.lower()
    if "/women/" in url:
        return "women"
    elif "/men/" in url:
        return "men"
    elif "/kids/" in url:
        return "kids"
    elif "/baby/" in url:
        return "baby"
    return None

def clean_key(key: str, gender: str) -> str:
    if "_All" in key:
        key = key.split("_All")[0]
    if any(x in key.lower() for x in ["accessories", "socks", "slippers", "lifewear collection"]):
        return None
    first_level = key.split("_")[0].lower()
    if first_level == gender.lower():
        return None
    return key

def normalize_url(url: str, page_url: str) -> str:
    if not url.startswith("http"):
        url = f"{page_url.rstrip('/')}/{url.lstrip('/')}"
    parts = url.split("/")
    cleaned_parts = []
    seen_country_en = set()
    for part in parts:
        if part in ["uk", "us", "ca", "es", "au", "en"]:
            if part in seen_country_en:
                continue
            seen_country_en.add(part)
        cleaned_parts.append(part)
    return "/".join(cleaned_parts)

def scrape(page):
    results = {"women": {}, "men": {}, "kids": {}, "baby": {}}
    wrappers = page.locator("div.fr-ec-class-list__category-list-wrapper.fr-ec-hide")
    wrapper_count = wrappers.count()
    print(f"Found {wrapper_count} category wrappers")
    for i in range(wrapper_count):
        wrapper = wrappers.nth(i)
        child_containers = wrapper.locator("div.fr-ec-hide div.fr-ec-category-list__children")
        for k in range(child_containers.count()):
            child_container = child_containers.nth(k)
            links = child_container.locator("a.fr-ec-link.fr-ec-link--default.fr-ec-cursor-pointer")
            for j in range(links.count()):
                link = links.nth(j)
                url = link.get_attribute("href")
                if not url:
                    continue
                full_url = normalize_url(url, page.url)
                gender = detect_gender(full_url)
                if not gender:
                    continue
                parts = full_url.strip("/").split("/")
                if len(parts) < 2:
                    continue
                first_level = parts[-2].replace("-", " ").title()
                second_level = parts[-1].replace("-", " ").title()
                key = f"{first_level}_{second_level}"
                key = clean_key(key, gender)
                if not key:
                    continue
                results[gender][key] = full_url
    return results

def main():
    day_name = datetime.today().strftime('%A')  

    # if day_name in ["Monday", "Wednesday", "Friday"]:
    #     geos_to_scrape = {k: v for k, v in GEOGRAPHIES.items() if k in ["USA", "UK"]}
    # elif day_name in ["Tuesday", "Thursday", "Saturday"]:
    #     geos_to_scrape = {k: v for k, v in GEOGRAPHIES.items() if k  in ["Spain", "Australia", "Canada"]}
    # else:
    #     # Skip scraping on Sunday
    #     return
    geos_to_scrape = {k: v for k, v in GEOGRAPHIES.items() if k  in ["Spain", "Australia", "Canada", "USA", "UK"]}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        for geo, url in geos_to_scrape.items():
            print(f"\nScraping {geo} site: {url}")
            page = browser.new_page()
            page.goto(url)
            accept_cookies(page)
            page.wait_for_timeout(3000)
            results = scrape(page)
            base_dir = os.path.join(geo, "data", today, "Item_urls")
            os.makedirs(base_dir, exist_ok=True)
            output_file = os.path.join(base_dir, "category_url.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Saved subcategories for {geo} to {output_file}")
            page.close()
        browser.close()



if __name__ == "__main__":
    main()
