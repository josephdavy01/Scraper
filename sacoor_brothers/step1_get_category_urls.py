import os
import json
import logging
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.sync_api import sync_playwright

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

if day in ['Monday', 'Wednesday', 'Friday']:
    pop_keys = ['all-man', 'all-woman', 'kids','ties',"belts","perfumes",'wallet','handkerchief']

    countries = {
        'UAE': 'https://ae.sacoorbrothers.com/'
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for country, url in countries.items():
            temp_dict = {}

            try:
                page.goto(url, timeout=60000)
            except Exception as e:
                logging.info(f"Error loading {url}: {e}")
                continue

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(page.content(), 'html.parser')

            category_tags = soup.find_all('ul', {'class': 'navigation__tier-1'})
            if category_tags:
                main_category_tag = category_tags[-1]
                gender_tags = main_category_tag.find_all('li', {
                    'class': 'navigation__item navigation__item--with-children navigation__item--with-mega-menu'
                })

                for gender_tag in gender_tags:
                    gender_a = gender_tag.find('a')
                    if gender_a:
                        gender_name = gender_a.get_text(strip=True)
                        temp_dict[gender_name] = {}

                        a_tags = gender_tag.find_all('a', {'class': 'navigation__link'})
                        for a_tag in a_tags:
                            href = a_tag.get('href')
                            if href and '/collections/' in href:
                                link = 'https://ae.sacoorbrothers.com' + href
                                name = href.split('/')[-1]
                                if name not in pop_keys:
                                    temp_dict[gender_name][name] = link
            else:
                logging.info(f'Category tag not found on {url}.')
                continue

            output_path = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(output_path, exist_ok=True)
            output_file = f'{output_path}/{country}_category_urls.json'
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(temp_dict, f, ensure_ascii=False, indent=4)
            logging.info(f"Saved category URLs for {country} to {output_file}")

        browser.close()
else:
    logging.info("Today is not a scraping day.")