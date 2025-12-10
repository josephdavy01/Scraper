import os
import json
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://lewkin.com/en-kr"
SAVE_DIR = os.path.join("South_korea", "Data", datetime.today().strftime("%Y-%m-%d"), "Item_urls")
os.makedirs(SAVE_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(SAVE_DIR, "categories_urls.json")
URL='https://lewkin.com/'

def make_absolute(url: str) -> str:
    """Ensure URL starts with https://lewkin.com/"""
    if not url:
        return None
    if url.startswith("http"):
        return url
    return URL.rstrip("/") + "/" + url.lstrip("/")


def scrape_categories():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=60000)
        soup = BeautifulSoup(page.content(), "html.parser")

        categories = {}

        # Top-level menu items
        for li in soup.select("li.sub"):
            a_tag = li.find("a", recursive=False)
            if not a_tag:
                continue

            main_name = a_tag.get_text(strip=True)
            if not main_name or main_name.lower() in ["sign in", "login"]:
                continue  # Skip unwanted menu items
            main_url = make_absolute(a_tag.get("href", ""))
            if not main_name:
                continue

            # Each top category is a dict
            if main_name not in categories:
                categories[main_name] = {}
            categories[main_name][main_name] = main_url

            # Process children
            sub_ul = li.find("ul")
            if sub_ul:
                for sub_li in sub_ul.find_all("li", recursive=False):
                    parse_subcategory(sub_li, categories[main_name], main_name)

        browser.close()
        return categories


def parse_subcategory(li_tag, container_dict, parent_name):
    """Recursive parser for submenus"""
    a_tag = li_tag.find("a", recursive=False)
    if not a_tag:
        return

    name = a_tag.get_text(strip=True)
    url = make_absolute(a_tag.get("href", ""))
    if not name:
        return

    key = f"{parent_name}- {name}"
    container_dict[key] = url

    sub_ul = li_tag.find("ul")
    if sub_ul:
        for sub_li in sub_ul.find_all("li", recursive=False):
            parse_subcategory(sub_li, container_dict, key)


if __name__ == "__main__":
    categories = scrape_categories()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=4, ensure_ascii=False)

    print(f"✅ Categories saved to {OUTPUT_FILE}")