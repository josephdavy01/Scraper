import os
import json
import asyncio
import logging
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def fetch_categories():
    """Fetch category URLs for each gender and save to JSON.
    The output is saved as <country>/<today>/Category/<country>_category_urls.json
    """
    country = "UAE"
    today_str = date.today().strftime('%Y-%m-%d')
    output_dir = os.path.join(country, today_str, "Category")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{country}_category_urls.json")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto('https://gant.ae')
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            temp = {}
            # Find the mega menu container
            menu_list = soup.find('ul', {
                'class': 'x-mega-menu list-menu list-menu--inline',
                'role': 'list'
            })
            if not menu_list:
                logging.error("Menu list not found.")
                await browser.close()
                return

            gender_main_tags = soup.find_all('header-menu')
            for gender_main_tag in gender_main_tags:
                span = gender_main_tag.find('span')
                if not span:
                    continue
                gender = span.get_text(strip=True)
                if gender not in ['Men', 'Women', 'Kids']:
                    continue
                temp[gender] = {}
                a_tags = gender_main_tag.find_all('a')
                for a_tag in a_tags:
                    href = a_tag.get('href')
                    if not href:
                        continue
                    # Skip currency switching / irrelevant links
                    if "aed" in href.lower():
                        continue
                    name = href.strip('/').split('/')[-1]
                    full_url = href if href.startswith('http') else f'https://gant.ae{href}'
                    temp[gender][name] = full_url

            # Write JSON file
            with open(output_file, "w", encoding="utf-8") as outfile:
                json.dump(temp, outfile, ensure_ascii=False, indent=4)
            logging.info(f"Category fetched and saved successfully to {output_file}.")

            await context.close()
            await browser.close()
    except Exception as e:
        logging.error(f"Error fetching categories: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_categories())
