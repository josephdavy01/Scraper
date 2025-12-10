from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from typing import Dict
import json, os, time

BASE_URL_dict = {
    "USA": "https://www.asics.com/us/en-us/",
    "UK": "https://www.asics.com/gb/en-gb/",
}

class CategoryScraper:
    def __init__(self, country: str = "USA") -> None:
        if country not in BASE_URL_dict:
            raise ValueError(f"Country {country} not supported. Available: {list(BASE_URL_dict.keys())}")
        
        self.country = country
        self.base_url = BASE_URL_dict[country]
        self.headers = {
            "User-Agent":
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/118.0.0.0 Safari/537.36")
        }
        print(f"Initialized scraper for {country}: {self.base_url}")
        
    def fetch_html(self) -> str:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False)
            try:
                page = browser.new_page()
                page.set_extra_http_headers(self.headers)
                page.goto(self.base_url, wait_until="domcontentloaded")

                #  cookie
                try:
                    page.locator("#onetrust-accept-btn-handler").click(timeout=3000)
                except Exception:
                    pass

                page.wait_for_timeout(2000)          
                return page.content()
            finally:
                browser.close()

    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def extract_category_links(self, soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
        result: Dict[str, Dict[str, str]] = {}

        # each top section: Men / Women / Kids / … (including Road Tested, Sale, etc)
        for top in soup.select('ul.menu-category > li[data-container-level="1"]'):
            section_tag = top.find('a', recursive=False)
            if not section_tag:
                continue
            section_name = section_tag.get_text(strip=True).lower()
            main_url=section_tag.get('href', '')
            if not section_name:
                continue
            result[section_name] = main_url

        print(f"Found {sum(len(v) for v in result.values())} total links for {self.country}")
        self._dump_json(result)
        return result

    def _dump_json(self, data: Dict[str, Dict[str, str]]) -> None:
        today = datetime.today().strftime("%Y-%m-%d")
        path = os.path.join(self.country, "Data", today, "Item_urls")
        os.makedirs(path, exist_ok=True)

        out_file = os.path.join(path, f"{self.country}_category_urls.json")
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4, ensure_ascii=False)

        print(f"Saved to {out_file}")

if __name__ == "__main__":
    countries_to_process = list(BASE_URL_dict.keys())
    
    for country in countries_to_process:
        print(f"\n{'='*50}")
        print(f"Processing {country}")
        print(f"{'='*50}")
        
        try:
            scraper = CategoryScraper(country)
            html = scraper.fetch_html()
            soup = scraper.parse_html(html)
            categories = scraper.extract_category_links(soup)
            print(f" {country} completed successfully!")
            
        except Exception as e:
            print(f" {country} failed: {e}")
            continue
    
    print(f"\n All selected countries processed!")