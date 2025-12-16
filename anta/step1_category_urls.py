import logging
import os
import json
import re
import asyncio
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Country configurations
# cookie configuration for redirection
COUNTRIES = { 
    "USA": {
        "url": "https://anta.com/",
        "cookies_file": "cookies_usa.json"
    },
    "UK": {
        "url": "https://uk.anta.com/",
        "cookies_file": "cookies_uk.json"
    }
}

pop_key =["Accessories","Socks","Cap","Bag","Hat"]

def create_base_dir(country):
      today_str = date.today().strftime("%Y-%m-%d")
      base_dir = f"{country}/{today_str}/Category"
      os.makedirs(base_dir, exist_ok=True)
      return base_dir

async def scrape_category_urls(country, config):
    url = config['url']
    cookies_file = config.get('cookies_file')
    
    logging.info(f"Starting scrape for {country}: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        try:
            if cookies_file and os.path.exists(cookies_file):
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                playwright_cookies = []
                for cookie in cookies:
                    pc = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie['domain'],
                        'path': cookie['path'],
                    }
                    if 'expirationDate' in cookie:
                        pc['expires'] = cookie['expirationDate']
                    if 'httpOnly' in cookie:
                        pc['httpOnly'] = cookie['httpOnly']
                    if 'secure' in cookie:
                        pc['secure'] = cookie['secure']

                    if 'sameSite' in cookie:
                        same_site = cookie['sameSite'].lower()
                        if same_site == 'strict':
                            pc['sameSite'] = 'Strict'
                        elif same_site == 'lax':
                            pc['sameSite'] = 'Lax'
                        elif same_site in ['none', 'no_restriction']:
                            pc['sameSite'] = 'None'
                    playwright_cookies.append(pc)
                
                await context.add_cookies(playwright_cookies)
                logging.info(f"Loaded {len(playwright_cookies)} cookies from {cookies_file}")
            
            page = await context.new_page()
            
            logging.info(f"Navigating to {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            current_url = page.url
            logging.info(f"Current URL: {current_url}")
            await asyncio.sleep(2)
            
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            categories = {}
            # Country-specific scraping logic

            if country == "USA":
                
                main_ul = soup.find("ul", class_="nav-link-container")
                if main_ul:
                    # Find all level 1 menu items
                    top_menus = main_ul.find_all("a", attrs={"data-link_position": "level_1_menu"})
                    logging.info(f"Found {len(top_menus)} top-level menus")
                                
                    for top_a in top_menus:
                        top_category_name = top_a.get_text(strip=True).lower().replace("🔥", "").strip()
                        if any(key in top_category_name for key in pop_key):
                            continue
                        if not top_category_name:
                            continue
                            
                        # Initialize category
                        if top_category_name not in categories:
                            categories[top_category_name] = {}
                        
                        # Find the parent li to look for dropdown menu
                        parent_li = top_a.find_parent("li")
                        if parent_li:
                            dropdown_menu = parent_li.find("div", class_="dropdown-menu")
                            if dropdown_menu:
                                # Find all sub-items links in the dropdown
                                links = dropdown_menu.find_all("a", class_="sub-dropdown-item", href=True)
                                logging.info(f"Category '{top_category_name}': Found {len(links)} product links")
                                for link in links:
                                    href = link["href"]
                                    if not href: 
                                        continue
                                        
                                    product_name = link.get_text(strip=True).replace("\"", "").replace("à", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").strip()
                                    if any(key in product_name for key in pop_key):
                                        continue
                                    
                                    # Handle relative URLs
                                    full_url = url.rstrip("/") + href if href.startswith("/") else url + href
                                    categories[top_category_name][product_name] = full_url
                            else:
                                logging.warning(f"No dropdown menu found for category '{top_category_name}'")

                            
                        # If category is empty (no sub-items), use the top link itself
                        if not categories[top_category_name]:
                            href = top_a.get("href")
                            if href:
                                full_url = url.rstrip("/") + href if href.startswith("/") else url + href
                                categories[top_category_name][top_category_name] = full_url
                
                # Process sale category last so it appears at the end
                sale_tag = soup.find("a", class_="nav-link nav-link-outline d-flex align-items-center nav-fw container-topic-header-custom", href=True)
                if sale_tag:
                    category_name = sale_tag.get_text(strip=True).replace("🔥", "").lower()
                    sale_url = url + sale_tag["href"]
                    categories[category_name] = {}
                    categories[category_name][category_name] = sale_url
            
            # Additional UK logic if needed
            if country == "UK":
                main_ul = soup.find("ul", class_="nav-link-container")
                if main_ul:
                    top_menus = main_ul.find_all("li", class_="nav-item", recursive=False)
                    for li in top_menus:
                        top_a = li.find("a", href=True)
                        if not top_a or "/collections/" not in top_a["href"]:
                            continue
                        
                        category_name = top_a.get_text(strip=True).lower().replace(" ", "-").replace("🔥", "")
                        if any(key in category_name for key in pop_key):
                            continue
                        categories[category_name] = {}
                        
                        links = li.find_all("a", href=True)
                        
                        for a in links:
                            href = a["href"]
                            
                            if not href.startswith("/products/"):
                                continue
                            
                            product_name = a.get_text(strip=True).replace("\"", "").replace("à", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                            if not product_name:
                                continue
                            
                            product_url = url + href.split("?")[0]
                            categories[category_name][product_name] = product_url

            base_dir = create_base_dir(country)
            output_file = os.path.join(base_dir, f"{country}_category_urls.json")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(categories, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Saved to {output_file}")
            return categories
            
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            raise
        finally:
            await context.close()
            await browser.close()




async def main():
    for country, config in COUNTRIES.items():
        try:
            await scrape_category_urls(country, config)
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Failed {country}: {e}")

if __name__ == "__main__":
    asyncio.run(main())