import os
import json
import asyncio
import logging
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.async_api import async_playwright

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

pop_key = ['all', 'best', '$']

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

def build_full_url(base_url, href):
    if href.startswith("/us/") or href.startswith("/uk/"):
        return f"https://www.riverisland.com{href}"
    return base_url + href

async def get_category_urls(playwright, country, curl):
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    temp = {}

    try:
        await page.goto(curl)
        await page.wait_for_timeout(8000)  

        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        main_tag = soup.find("ul", {"data-menu-type": "desktop"})
        if not main_tag:
            logging.warning(f'{country}: Main <ul> tag not found')
            return country, None

        li_tags = main_tag.find_all('li', {'class': 'mega-menu__item mega-menu'})
        
        for li_tag in li_tags:
            main_link = li_tag.find('a', {'class': 'main-navigation__item'})
            if not main_link:
                continue
                
            gender = main_link.find('span', {'class': 'main-navigation__title'})
            if not gender:
                continue
                
            gender_name = gender.text.strip().title()
            
            if gender_name in ['Women', 'Men']:
                temp[gender_name] = {}
                
                # Find the sub-menu content
                sub_menu = li_tag.find('div', {'class': 'mega-menu__content mega-menu__content-multi-layer'})
                if not sub_menu:
                    continue
                
                clothing_sections = sub_menu.find_all('li', {'class': 'mega-menu__column'})
                
                for section in clothing_sections:
                    clothing_header = section.find('p', {'class': 'mega-menu__heading mega-menu__heading-multi-layer'})
                    if clothing_header and 'Clothing' in clothing_header.text:
                        
                        category_links = section.find_all('a')
                        
                        for link in category_links:
                            name = link.text.strip()
                            if name and name != 'All Womenswear' and name != 'All Menswear':
                                clean_name = name.lower().replace(' & ', '-').replace(' ', '-')
                                if not any(keyword in clean_name for keyword in pop_key):
                                    href = link.get('href')
                                    if href:
                                        url = build_full_url(curl, href)
                                        temp[gender_name][clean_name] = url

            elif gender_name == 'Kids':
                temp[gender_name] = {}
                
                sub_menu = li_tag.find('div', {'class': 'mega-menu__content mega-menu__content-multi-layer'})
                if not sub_menu:
                    continue
                
                for sub_gender in ['Girls', 'Boys']:
                    gender_sections = sub_menu.find_all('li', {'class': 'mega-menu__column'})
                    
                    for section in gender_sections:
                        gender_header = section.find('p', {'class': 'mega-menu__heading mega-menu__heading-multi-layer'})
                        if gender_header and sub_gender in gender_header.text:
                            category_links = section.find_all('a')
                            
                            for link in category_links:
                                name = link.text.strip()
                                if name and f'All {sub_gender}wear' not in name:
                                    clean_name = f"{sub_gender.lower()}_{name.lower().replace(' & ', '-').replace(' ', '-')}"
                                    if not any(keyword in clean_name for keyword in pop_key):
                                        href = link.get('href')
                                        if href:
                                            url = build_full_url(curl, href)
                                            temp[gender_name][clean_name] = url

        return country, temp
        
    except Exception as e:
        logging.error(f"Error processing {country}: {str(e)}")
        return country, None
        
    finally:
        await browser.close()


async def main():
    # Define available countries
    countries = {
        "UK": 'https://www.riverisland.com',
        "USA": 'https://www.riverisland.com/us'
    }

    # Determine which country to run based on the day of the week
    if day in ['Tuesday', 'Thursday', 'Saturday']:
      countries_to_run = {
           "UK": countries["UK"],
           "USA": countries["USA"]
       }
    else:
       logging.warning(f"No countries scheduled to run today: {day}")
       countries_to_run = {}
    countries_to_run={
        "UK":countries["UK"],
        "USA":countries["USA"]
    }
    if not countries_to_run:
        logging.info("No countries to run.")
        return

    async with async_playwright() as playwright:
        tasks = [
            get_category_urls(playwright, country, url)
            for country, url in countries_to_run.items()
        ]
        results = await asyncio.gather(*tasks)

        for country, jsondata in results:
            if not jsondata:
                logging.warning(f"{country}: No data fetched.")
                continue

            output_path = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(output_path, exist_ok=True)
            output_file = f'{output_path}/{country}_category_urls.json'
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(jsondata, f, ensure_ascii=False, indent=4)
            logging.info(f"Saved category URLs for {country} to {output_file}")

if __name__ == '__main__':
    asyncio.run(main())