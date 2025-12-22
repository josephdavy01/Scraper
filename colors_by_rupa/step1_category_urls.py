import asyncio
import os
import json
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

countries = {"India":"https://livecolors.in/"}



async def category_urls():
    today_str = datetime.now().strftime("%Y-%m-%d")
    country = "India"
    base_dir = f"{country}/{today_str}/Category"
    os.makedirs(base_dir, exist_ok=True)

    logging.info(f"Starting scrape for {country}...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        logging.info(f"Loading {countries[country]}...")
        await page.goto(countries[country], wait_until="domcontentloaded")  
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        category_dict = {}
        pop_key = ["Accessories","Gift Set","Baby Essentials"]
        logging.info("Parsing categories...")
        main_categories = soup.find_all('li', class_='level0')
        for main_cat in main_categories:
            main_link = main_cat.find('a', class_='level-top')
            if not main_link:
                continue
            
            span = main_link.find('span')
            if not span:
                continue
                
            cat_name = span.get_text(strip=True).replace(" ","")
            if any(key in cat_name for key in pop_key):
                continue
            category_dict[cat_name] = {}
            
            sub_categories = main_cat.find_all('li', class_='level1')
            
            for sub_cat in sub_categories:
                sub_link = sub_cat.find('a')
                if not sub_link:
                    continue
                
                sub_name = sub_link.get_text(strip=True).replace(" ","")
                if any(key in sub_name for key in pop_key):
                    continue
                sub_url = sub_link.get('href')
                
                nested_items = sub_cat.find_all('li', class_='level2')
                
                if nested_items:
                    category_dict[cat_name][sub_name] = {}
                    
                    for nested in nested_items:
                        nested_link = nested.find('a')
                        if nested_link:
                            nested_name = nested_link.get_text(strip=True).replace(" ","")
                            if any(key in nested_name for key in pop_key):
                                continue
                            nested_url = nested_link.get('href')
                            category_dict[cat_name][sub_name][nested_name] = nested_url
                else:
                    category_dict[cat_name][sub_name] = sub_url
        
        await browser.close()
        logging.info(f"Found {len(category_dict)} main categories")

    save_path = os.path.join("India", today_str, "Category")
    os.makedirs(save_path, exist_ok=True)
    file_path = os.path.join(save_path,f"{country}_category_urls.json")
    with open(file_path, "w",encoding="utf-8") as f:
        json.dump(category_dict, f, ensure_ascii=False, indent=4)
    
    logger.info(f"Saved {country} category urls to {file_path}")
    logging.info(f"Saved to: {file_path}")
    logging.info(f"Categories found:")
    for cat_name, subcats in category_dict.items():
        logging.info(f"{cat_name}: {len(subcats)} subcategories")
        logging.info(f"Category '{cat_name}' has {len(subcats)} subcategories")


if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(category_urls())
