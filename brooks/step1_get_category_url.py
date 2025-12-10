# step1_brooks_playwright.py
import json
import os
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

GEOGRAPHIES = {
    "UK": "https://www.brooksrunning.com/en_gb",
    "USA": "https://www.brooksrunning.com/en_us"
}
IGNORE_CATEGORIES = ["Accessories", "Shop All", "Shoe Finder", "Bra Finder", "Socks", "Size Guide", "_Shop all"]
BASE_FOLDER = "{geo}/data/{today}/Item_urls"
FILENAME = "category_urls.json"

def scrape_html(html):
    data = {}
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.find("nav", class_="m-main-nav__nav")
    if not nav:
        print("Navigation not found in returned HTML.")
        return data
    ul = nav.find("ul", class_="m-main-nav__items")
    if not ul:
        print("Main menu items not found.")
        return data
    # reuse parsing logic from Option A (omitted here for brevity)...
    for li in ul.find_all("li", class_="m-main-nav__item"):
        a_tag = li.find("a", class_="m-main-nav__item-link")
        if not a_tag:
            button = li.find("button", attrs={"data-category-title": True})
            if button:
                main_category = button.get("data-category-title", "").strip()
            else:
                continue
        else:
            main_category = a_tag.get("data-category-title", "") or a_tag.get_text(strip=True)
        if not main_category or main_category.lower() not in ["men","women"]:
            continue
        data.setdefault(main_category.lower(), {})
        submenu = li.find("div", class_="m-main-nav__submenu")
        if not submenu:
            continue
        subsubmenu = submenu.find("div", class_="m-main-nav-table")
        if not subsubmenu:
            continue
        columns = subsubmenu.find_all("div", class_="m-main-nav-table__column")
        for column in columns:
            h6_tag = column.find("h6", class_="m-main-nav-table__column-title")
            second_level_name = None
            if h6_tag:
                link = h6_tag.find("a", class_="m-main-nav-table__column-link")
                second_level_name = (link.get_text(strip=True) if link else h6_tag.get_text(strip=True))
            if not second_level_name or second_level_name in IGNORE_CATEGORIES:
                continue
            ul_rows = column.find("ul", class_="m-main-nav-table__rows")
            if not ul_rows:
                continue
            for li_row in ul_rows.find_all("li", class_="m-main-nav-table__row"):
                a_row = li_row.find("a")
                if not a_row:
                    continue
                third_level_name = a_row.get_text(strip=True)
                if third_level_name in IGNORE_CATEGORIES:
                    continue
                url = a_row.get("href")
                key = f"{second_level_name}_{third_level_name}"
                data[main_category.lower()][key] = url
    return data

def scrape_categories_with_playwright(url):
    data = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # try headless=True later
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116 Safari/537.36",
            java_script_enabled=True,
        )
        page = context.new_page()
        # globally increase timeouts
        page.set_default_navigation_timeout(60_000)  # 60s navigation timeout
        page.set_default_timeout(20_000)  # 20s for waits

        # abort images/fonts to speed up and reduce networkidle waits
        def handle_route(route, request):
            if request.resource_type in ("image", "font", "stylesheet"):
                return route.abort()
            return route.continue_()

        page.route("**/*", handle_route)

        # Use domcontentloaded or load instead of networkidle
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        # wait explicitly for nav element
        try:
            page.wait_for_selector("nav.m-main-nav__nav", timeout=10_000)
        except Exception as e:
            print("nav selector not found after wait:", e)
            html = page.content()
            data = scrape_html(html)
            context.close()
            browser.close()
            return data

        html = page.content()
        context.close()
        browser.close()

        data = scrape_html(html)
    return data

def main():
    today = date.today().strftime("%Y-%m-%d")
    # today = '2025-12-01'
    final_data = {}
    for geo, url in GEOGRAPHIES.items():
        print(f"Scraping {geo} ...")
        geo_data = scrape_categories_with_playwright(url)
        final_data[geo] = geo_data
        folder_path = BASE_FOLDER.format(geo=geo, today=today)
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, FILENAME)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(geo_data, f, indent=4)
        print(f"{geo} saved to {file_path}")

if __name__ == "__main__":
    main()
