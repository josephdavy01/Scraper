import os
import json
import asyncio
import logging
import re
import time
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
today_str = date.today().strftime('%Y-%m-%d')

BASE = "https://paige.com"

def normalize_url(u: str) -> str:
    """Fix duplicated https and ensure correct formatting."""
    if not u:
        return None

    u = u.strip()

    # If already absolute, return as is
    if u.startswith("http://") or u.startswith("https://"):
        return u

    # Ensure no double slashes
    if u.startswith("/"):
        return BASE + u
    return BASE + "/" + u


def filter_category_urls(groups):
    temp = {}
    for gender_dict in groups:
        gender = gender_dict.get('title')
        if gender not in ['Women', 'Men']:
            continue

        temp[gender] = {}

        for main_category in gender_dict.get('sections', []):
            links = main_category.get('links', [])
            title = main_category.get('title')

            if not links or not title:
                continue

            for link in links:
                if link.get('text') == 'Shop All' or title == 'Shop All':
                    continue

                url = normalize_url(link.get('url'))
                if not url:
                    continue

                # Add country parameter
                if "?country=US" not in url:
                    url += "?country=US"

                name = url.split('/')[-1].split('?')[0]
                temp[gender][name] = url

    return temp


async def get_category_urls(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(url)
        time.sleep(7)

        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        script_tags = soup.find_all("script")

        for script_tag in script_tags:
            script_string = script_tag.string

            if not script_string:
                continue

            # Find the __next_f payload
            if 'self.__next_f.push' in script_string and '12:' in script_string:
                match = re.search(r'self\.__next_f\.push\(\[1,"12:(.+?)"\]\)', script_string, re.DOTALL)

                if not match:
                    continue

                try:
                    content = match.group(1).rstrip('"]').lstrip()
                    content = content.encode().decode("unicode_escape")
                    data = json.loads(content)

                    # Recursive search for navigation.groups
                    def find_navigation(obj):
                        if isinstance(obj, dict):
                            if 'navigation' in obj:
                                return obj['navigation'].get('groups')
                            for v in obj.values():
                                result = find_navigation(v)
                                if result:
                                    return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = find_navigation(item)
                                if result:
                                    return result
                        return None

                    product_groups = find_navigation(data)

                    if product_groups:
                        return filter_category_urls(product_groups)

                except Exception as e:
                    logging.error("Error parsing JSON: %s", e)

        return {}


async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = {
        'USA': 'https://paige.com/?country=US'
    }

    if day in ['Tuesday', 'Thursday', 'Saturday']:
        for country, url in countries.items():

            logging.info(f'Fetching {country} category URLs now')
            jsondata = await get_category_urls(url)

            output_path = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(output_path, exist_ok=True)
            output_file = f'{output_path}/{country}_category_urls.json'

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(jsondata, f, indent=4)

            logging.info(f'{country} category URLs saved to {output_file}')

    else:
        logging.info(f"Today is {day} — no need to run")


if __name__ == "__main__":
    asyncio.run(main())
