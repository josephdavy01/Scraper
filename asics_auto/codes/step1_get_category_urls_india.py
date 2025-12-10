import json, os, time
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from typing import Dict, Any, List
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.asics.co.in"

class ProductScraper:
    def __init__(self):
        self.base_url = BASE_URL
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/58.0.3029.110 Safari/537.3'
            )
        }

    def fetch_html(self) -> str:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False)
            page = browser.new_page()
            page.set_extra_http_headers(self.headers)
            page.goto(self.base_url, wait_until='domcontentloaded')
            time.sleep(3)
            html = page.content()
            browser.close()
            return html

    def parse_html(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, 'html.parser')

    def extract_product_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        menu_container = soup.find('div', class_='text-root-iY-')
        main_menu = menu_container.find('ul', class_='mainMenu')

        categories: List[Dict[str, Any]] = []

        for li in main_menu.find_all('li', class_='isSubmenu', recursive=False):
            a_main   = li.find('a', href=True)
            name      = a_main.get_text(strip=True)
            url       = urljoin(self.base_url, a_main['href'])
            category  = {
                "category":      name,
                "url":           url,
                "subcategories": [],
                "_li":           li  # store original <li> for sale special case
            }

            # --- your existing drilling into subMenu ---
            sub_menu = li.find('ul', class_='subMenu')
            if sub_menu:
                # find the wrapper <li> (twoColumn, oneColumn, wideItems, or twoThird)
                wrapper = (
                    sub_menu.find('li', class_='twoColumn')
                    or sub_menu.find('li', class_='oneColumn')
                    or sub_menu.find('li', class_='wideItems')
                    or sub_menu.find('li', class_='twoThird')
                )
                if wrapper:
                    # find whichever inner UL (fourCol, threeCol, oneCol)
                    col_ul = None
                    for cls in ('fourCol','threeCol','oneCol'):
                        c = wrapper.find('ul', class_=cls)
                        if c:
                            col_ul = c
                            break

                    if col_ul:
                        # drill one level deep: h4 headings become subcategories
                        for col_li in col_ul.find_all('li', recursive=False):
                            inner_ul = col_li.find('ul')
                            if not inner_ul:
                                continue
                            current_sub = None
                            for item in inner_ul.find_all('li', recursive=False):
                                h4 = item.find('h4')
                                if h4:
                                    link = h4.find('a', href=True)
                                    if link:
                                        current_sub = {
                                            "name": link.get_text(strip=True),
                                            "url":  urljoin(self.base_url, link["href"]),
                                            "items": []
                                        }
                                        category["subcategories"].append(current_sub)
                                else:
                                    link = item.find('a', href=True)
                                    if link and current_sub:
                                        current_sub["items"].append({
                                            "name": link.get_text(strip=True),
                                            "url":  urljoin(self.base_url, link["href"])
                                        })

            categories.append(category)
        return categories

    def flatten_and_save(self, categories: List[Dict[str, Any]]) -> Dict[str, Dict[str,str]]:
        flattened: Dict[str, Dict[str,str]] = {}

        for cat in categories:
            name    = cat["category"]
            mapping: Dict[str,str] = {}

            if name.upper() == "SALE":
                # SPECIAL: only mens-footwear links under this <li>
                li = cat["_li"]
                for a in li.find_all('a', href=True):
                    href = urljoin(self.base_url, a['href'])
                    txt  = a.get_text(strip=True)
                    # if "/sale/mens-footwear/" in href:
                    mapping[txt] = href
            else:
                # normal: pull every sub-sub item
                for sub in cat["subcategories"]:
                    for itm in sub.get("items", []):
                        mapping[itm["url"].split('/')[-1].split('.')[0]] = itm["url"]

            flattened[name] = mapping

        # save
        country = 'India'
        today_str = datetime.today().strftime("%Y-%m-%d")
        base_path = f'{country}/Data/{today_str}/Item_urls'
        os.makedirs(base_path, exist_ok=True)
        out_file = f'{base_path}/{country}_category_urls.json'

        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(flattened, f, indent=4, ensure_ascii=False)

        print(f" Saved to {out_file}")
        return flattened

if __name__ == "__main__":
    scraper    = ProductScraper()
    html       = scraper.fetch_html()
    soup       = scraper.parse_html(html)
    categories = scraper.extract_product_links(soup)
    result     = scraper.flatten_and_save(categories)
