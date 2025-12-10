import os
import json
from datetime import datetime
from bs4 import BeautifulSoup
import asyncio
from playwright.async_api import async_playwright

async def scrape():
    countries = {
        'India': 'https://www.marksandspencer.in/',
        'UK': 'https://www.marksandspencer.com/',
        'USA': 'https://www.marksandspencer.com/us/'
    }
    today_time = datetime.now().strftime('%Y-%m-%d')
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()
        for country, url in countries.items():
            base_path = country
            new_path = f'{base_path}/Data/{today_time}/Item_urls'
            os.makedirs(new_path, exist_ok=True)
            output_file = f'{new_path}/{country}_category_urls.json'
            if os.path.exists(output_file):
                print(f"File already exists: {output_file}. Skipping scrape for {country}.")
                continue
            temp = {}
            print(f"Scraping {country} from {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            if country == "India":
                menu_items = soup.find('ul', {'class': 'nav'})
                if not menu_items:
                    print(f"No main categories found for {country}")
                    continue
                main_tags = menu_items.find_all('li', {'class': 'nav-item', 'role': 'menuitem'})
                for main_tag in main_tags:
                    main_category = main_tag.find('a').text.strip().lower()
                    if main_category in ['women', 'men']:
                        temp[main_category] = {}
                        li_tag = main_tag.find('li', {'class': 'dropdown-item'})
                        if li_tag:
                            a_tags = li_tag.find_all('a')
                            for a_tag in a_tags:
                                sub_category = a_tag.text.strip().lower()
                                sub_category_url = a_tag.get('href', '').strip()
                                if sub_category_url.startswith('https://'):
                                    temp[main_category][sub_category] = sub_category_url
            elif country == "UK":
                div = soup.find('div', class_='gnav_scrollableArea__bRX8I')
                if not div:
                    print(f"Could not find menu container for {country}")
                    continue
                p_to = div.find_all('div', {'class': 'gnav_tab__GM_Zu'})
                for p_tag in p_to:
                    main_category = p_tag.find('p').text.strip().lower()
                    if main_category in ['women', 'men']:
                        temp[main_category] = {}
                        div_tag = p_tag.find('div', {'class': 'gnav_section__A_vh7'})
                        if not div_tag:
                            continue
                        li_tag = div_tag.find_all('li')
                        for li in li_tag:
                            a_tag = li.find('a')
                            if not a_tag:
                                continue
                            subcategory_name = a_tag.text.strip().lower()
                            sub_url = a_tag.get('href')
                            if not sub_url:
                                continue
                            if "https://www.marksandspencer.com" not in sub_url:
                                sub_url = "https://www.marksandspencer.com" + sub_url
                            temp[main_category][subcategory_name] = sub_url
            elif country == "USA":
                menu_items = soup.find('ul', {'class': 'nav'})
                if not menu_items:
                    print(f"No main categories found for {country}")
                    continue
                main_tags = menu_items.find_all('li', {'class': 'nav-item', 'role': 'menuitem'})
                for main_tag in main_tags:
                    main_category = main_tag.find('a').text.strip().lower()
                    if main_category in ['women', 'men']:
                        temp[main_category] = {}
                        li_tag = main_tag.find('li', {'class': 'dropdown-item'})
                        if li_tag:
                            a_tags = li_tag.find_all('a')
                            for a_tag in a_tags:
                                sub_category = a_tag.text.strip().lower()
                                sub_category_url = a_tag.get('href', '').strip()
                                if sub_category_url.startswith('https://'):
                                    temp[main_category][sub_category] = sub_category_url
            with open(output_file, "w", encoding='utf-8') as outfile:
                json.dump(temp, outfile, ensure_ascii=False, indent=4)
            print(f"Saved category links to {output_file}")
        await browser.close()
if __name__ == "__main__":
    asyncio.run(scrape())
