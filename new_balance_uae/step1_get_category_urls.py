import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE_DIR = os.path.join("UAE", "Data", datetime.today().strftime("%Y-%m-%d"))

# Subfolder for item_urls
ITEM_URLS_DIR = os.path.join(BASE_DIR, "Item_urls")
os.makedirs(ITEM_URLS_DIR, exist_ok=True)

# Output JSON file path
output_path = os.path.join(ITEM_URLS_DIR, "UAE_category_urls.json")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.newbalance.co.ae/en/")
    page.wait_for_timeout(5000)

    soup = BeautifulSoup(page.content(), "html.parser")
    subcategories = {}

    # Find all level-2 category containers
    main_category_tags = soup.find_all('ul', {'class': 'submenu-ul submenu-ul-2'})
    for main_category in main_category_tags:
        # Get the main category name (level-2)
        main_header = main_category.find('li', {'class': 'submenu-header'})
        if not main_header:
            print("Warning: No submenu-header found in a level-2 category")
            continue
        main_name_tag = main_header.find('h5', {'class': 'menu-header-title'})
        if not main_name_tag:
            print("Warning: No menu-header-title found in submenu-header")
            continue
        main_name = main_name_tag.text.strip()
        subcategories[main_name] = {}

        # Find all level-3 categories within this level-2 category
        level3_categories = main_category.find_all('li', {'class': 'submenu-li level-3-li'})
        for level3_cat in level3_categories:
            level3_link = level3_cat.find('a', {'class': 'submenu-link'})
            if not level3_link:
                print(f"Warning: No submenu-link found in level-3 category under {main_name}")
                continue
            level3_name = level3_link.text.strip()
            level3_url = level3_link.get('href')
            if level3_url.startswith("/"):
                level3_url = "https://www.newbalance.co.ae" + level3_url

            if main_name == "New":
                # For "New" category, store level-3 URLs directly
                subcategories[main_name][level3_name] = level3_url
                print(f"{main_name} -> {level3_name}: {level3_url}")
            else:
                # For other categories, check for level-4 categories and "View All"
                level4_ul = level3_cat.find('ul', {'class': 'submenu-ul submenu-ul-3'})
                if level4_ul:
                    # Check for "View All" link with flexible class matching
                    view_all = level4_ul.find('li', {'class': 'submenu-li submenu-li-viewall'})
                    if view_all:
                        view_all_link = view_all.find('a')
                        if view_all_link and 'href' in view_all_link.attrs:
                            view_all_url = view_all_link.get('href')
                            if view_all_url.startswith("/"):
                                view_all_url = "https://www.newbalance.co.ae" + view_all_url
                            combined_key = f"{level3_name}-View All"
                            subcategories[main_name][combined_key] = view_all_url
                            print(f"{main_name} -> {combined_key}: {view_all_url}")
                        else:
                            print(f"Warning: No valid 'View All' link found under {main_name} -> {level3_name}")

                    # Process level-4 categories
                    level4_categories = level4_ul.find_all('li', {'class': 'submenu-li level-4-li'})
                    for level4_cat in level4_categories:
                        level4_link = level4_cat.find('a', {'class': 'submenu-link'})
                        if not level4_link:
                            print(f"Warning: No submenu-link found in level-4 category under {main_name} -> {level3_name}")
                            continue
                        level4_name = level4_link.text.strip()
                        level4_url = level4_link.get('href')
                        if level4_url.startswith("/"):
                            level4_url = "https://www.newbalance.co.ae" + level4_url
                        combined_key = f"{level3_name}-{level4_name}"
                        subcategories[main_name][combined_key] = level4_url
                        print(f"{main_name} -> {combined_key}: {level4_url}")
                else:
                    # If no level-4 categories or "View All", add level-3 as an empty dictionary
                    subcategories[main_name][level3_name] = {}
                    print(f"{main_name} -> {level3_name}: {{}}")

    browser.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(subcategories, f, indent=2, ensure_ascii=False)

    print(f"✅ Categories saved to {output_path}")