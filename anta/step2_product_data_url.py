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
        "url": "https://anta.com",
        "cookies_file": "cookies_usa.json"
    },
    "UK": {
        "url": "https://uk.anta.com",
        "cookies_file": "cookies_uk.json"
    }
}

def load_category_urls(country):
    today_str = date.today().strftime("%Y-%m-%d")
    input_file = f"{country}/{today_str}/Category/{country}_category_urls.json"
    with open(input_file, 'r', encoding='utf-8') as f:
        return json.load(f)

async def scrape_product_data_uk(country, config):
    cookies_file = config.get('cookies_file')
    base_url = config.get('url')
    categories = load_category_urls(country)
    
    logging.info(f"Starting product URL scrape for {country}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        try:
            # Only load cookies for UK
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
            today_str = date.today().strftime("%Y-%m-%d")
            date_subfolder = os.path.join(country, today_str)
            
            total_products = 0
            for category_name, products in categories.items():
                logging.info(f"Processing category: {category_name} ({len(products)} products)")
                
                for product_name, product_url in products.items():
                    try:
                        # api call
                        product_handle = product_url.split("/")[-1].split("?")[0]
                        json_url = f"{base_url}/products/{product_handle}.js"
                        
                        # Fetch body_html from the .json endpoint
                        json_api_url = f"{base_url}/products/{product_handle}.json"
                        json_response = await page.goto(json_api_url, wait_until='domcontentloaded', timeout=30000)
                        
                        body_html = ""
                        if json_response.status == 200:
                            json_text = await page.content()
                            soup = BeautifulSoup(json_text, 'html.parser')
                            json_data_text = soup.get_text()
                            json_product_data = json.loads(json_data_text)
                            body_html = json_product_data.get("product", {}).get("body_html", "")
                        
                        # Now fetch the main product data from .js endpoint
                        response = await page.goto(json_url, wait_until='domcontentloaded', timeout=30000)                     
                        if response.status == 200:
                            json_text = await page.content()
                            soup = BeautifulSoup(json_text, 'html.parser')
                            json_data = soup.get_text()
                            product_data = json.loads(json_data)
                            
                            # Add body_html to product data
                            product_data['body_html'] = body_html
                            
                            json_path = os.path.join(date_subfolder, "Json_data", category_name)
                            os.makedirs(json_path, exist_ok=True)
                            json_file = os.path.join(json_path, f"{product_handle}.json")
                            with open(json_file, 'w', encoding='utf-8') as f:
                                json.dump(product_data, f, indent=2, ensure_ascii=False)
                            
                            total_products += 1
                            logging.info(f"  Saved: {product_name}")
                        else:
                            logging.warning(f"  Failed to fetch {product_name}: Status {response.status}")
                        
                        await asyncio.sleep(0.5)  
                        
                    except Exception as e:
                        logging.error(f"  Error processing {product_name}: {str(e)}")
                        continue
            
            logging.info(f"Total products saved: {total_products}")
            return total_products
            
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            raise
        finally:
            await context.close()
            await browser.close()



async def scrape_product_data_usa(country, config):
    base_url = config.get('url')
    categories = load_category_urls(country)
    
    logging.info(f"Starting product URL scrape for {country}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        try:
            page = await context.new_page()
            today_str = date.today().strftime("%Y-%m-%d")
            date_subfolder = os.path.join(country, today_str)
            
            total_products = 0
            all_urls_by_category = {}  
            
            for category_name, category_urls in categories.items():
                logging.info(f"Processing category: {category_name}")
                
                if category_name not in all_urls_by_category:
                    all_urls_by_category[category_name] = {}
                
                all_product_links = set()
                
                for item_name, item_url in category_urls.items():
                    if "/collections/" in item_url:
                        logging.info(f"  Scraping collection: {item_name}")
                        page_num = 1
                        prev_page_links = set()
                        
                        while True:
                            try:
                                paginated_url = f"{item_url}?page={page_num}"
                                await page.goto(paginated_url, wait_until='domcontentloaded', timeout=30000)
                                await asyncio.sleep(1)
                                
                                html_content = await page.content()
                                soup = BeautifulSoup(html_content, 'html.parser')
                                
                                product_containers = soup.find_all("div", class_="position-relative product-card-img-wrap")
                                if not product_containers:
                                    logging.info(f"    No products found on page {page_num}. Stopping pagination.")
                                    break
                                
                                current_links = set()
                                for container in product_containers:
                                    a_tag = container.find("a", attrs={"data-as-stretched-link": True})
                                    if a_tag:
                                        href = a_tag.get("href")
                                        if href and href.startswith("/products/"):
                                            full_url = urljoin(base_url, href)
                                            current_links.add(full_url)
                                
                                if current_links == prev_page_links or not current_links:
                                    break
                                
                                all_product_links.update(current_links)
                                prev_page_links = current_links
                                logging.info(f"Page {page_num}: Found {len(current_links)} products")
                                
                                all_urls_by_category[category_name][item_name] = list(all_product_links)
                                
                                item_urls_dir = os.path.join(date_subfolder, "Item_urls")
                                os.makedirs(item_urls_dir, exist_ok=True)
                                urls_file = os.path.join(item_urls_dir, f"{country}_product_urls.json")
                                with open(urls_file, 'w', encoding='utf-8') as f:
                                    json.dump(all_urls_by_category, f, indent=2, ensure_ascii=False)
                                
                                page_num += 1
                                
                            except Exception as e:
                                logging.error(f"    Error on page {page_num}: {e}")
                                break
                    
                    # If it's a direct product URL, add it
                    elif "/products/" in item_url:
                        all_product_links.add(item_url)
                        if item_name not in all_urls_by_category[category_name]:
                            all_urls_by_category[category_name][item_name] = []
                        all_urls_by_category[category_name][item_name].append(item_url)
                
                # Now fetch product data for all collected links
                logging.info(f"  Fetching data for {len(all_product_links)} products")
                for product_url in all_product_links:
                    try:

                        # Extract composition from product page
                        composition = ""
                        await page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
                        soup = BeautifulSoup(await page.content(), 'html.parser')
                        composition_divs = soup.find_all("div", class_="accordion-body px-0 pt-0 pb-0 pb-4 no-last-margin line-h-1-5")
                        if composition_divs:
                            composition_items = []
                            for div in composition_divs:
                                items = [li.get_text(strip=True) for li in div.find_all("li")]
                                composition_items.extend(items)
                            composition = ", ".join(composition_items) if composition_items else ""
                        
                        # Fetch whole product data from api call
                        product_handle = product_url.split("/")[-1].split("?")[0]
                        json_url = f"{base_url}/products/{product_handle}.js"
                        response = await page.goto(json_url, wait_until='domcontentloaded', timeout=30000)
                        
                        if response.status == 200:
                            json_text = await page.content()
                            soup = BeautifulSoup(json_text, 'html.parser')
                            json_data = soup.get_text()
                            product_data = json.loads(json_data)
                            
                            # Add composition to product data
                            product_data['composition'] = composition
                            
                            json_path = os.path.join(date_subfolder, "Json_data", category_name)
                            os.makedirs(json_path, exist_ok=True)
                            json_file = os.path.join(json_path, f"{product_handle}.json")
                            with open(json_file, 'w', encoding='utf-8') as f:
                                json.dump(product_data, f, indent=2, ensure_ascii=False)
                            
                            total_products += 1
                            logging.info(f"Saved: {product_handle}")
                        else:
                            logging.warning(f"Failed to fetch {product_handle}: Status {response.status}")
                        
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logging.error(f"    Error processing {product_url}: {str(e)}")
                        continue
            
            logging.info(f"Total products saved: {total_products}")
            return total_products
            
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            raise
        finally:
            await context.close()
            await browser.close()



async def main():
    for country, config in COUNTRIES.items():
        try:
            if country == "USA":
                await scrape_product_data_usa(country, config)
            if country == "UK":
                await scrape_product_data_uk(country, config)
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Failed {country}: {e}")

if __name__ == "__main__":
    asyncio.run(main())