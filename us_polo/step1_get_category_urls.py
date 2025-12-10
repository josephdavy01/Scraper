import datetime
import logging
import os
from datetime import date
import re
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

countries = {
    'India': 'https://uspoloassn.in/'
}

pop_keys = ['all', 'best', 'sawai-padmanabh-singh-collection', "handbags", "kids-caps", "socks"]

def get_category_urls(page, url):
    temp = {}
    page.goto(url, wait_until='domcontentloaded')
    html_content = page.content()
    soup = BeautifulSoup(html_content, "html.parser")

    menu_tag = soup.find("ul", {"role": "menubar"})
    if menu_tag:
        gender_tags = menu_tag.find_all("li", {
            "class": "navigation__menuitem testt navigation__menuitem--dropdown js-aria-expand js-doubletap-to-go"
        })
        for gender_tag in gender_tags:
            gender_name_tag = gender_tag.find('a', {
                'class': 'navigation__menulink moengage-link js-menu-link js-open-dropdown-on-key is_upcase-true'
            })
            if not gender_name_tag:
                continue

            gender = gender_name_tag.get_text().strip()
            if gender in ['MEN', 'WOMEN', 'KIDS', 'FOOTWEAR', "INNERWEAR"]:
                temp[gender] = {}
                gender_category_tag = gender_tag.find('ul', {'class': 'menu ai-s mp-0'})
                if not gender_category_tag:
                    continue

                category_tags = gender_category_tag.find_all('a')
                for category_tag in category_tags:
                    category = category_tag.get_text().strip().lower()
                    if category:
                        category = category.replace('sale:', 'sale').replace(' ', '-')
                    if not any(keyword in category for keyword in pop_keys):
                        link = category_tag.get('href')
                        if link:
                            if 'https' not in link:
                                link = 'https://uspoloassn.in' + link
                            if '#' not in link:
                                link = link.split('?')[0]
                                if gender == 'KIDS':
                                    if category not in ['boys', 'girls']:
                                        name = link.split('/')[-1]
                                        temp[gender][name] = link
                                else:
                                    temp[gender][category] = link
    return temp


# Main script execution
if __name__ == "__main__":
    today = datetime.datetime.today().strftime('%A')
    today_str = date.today().strftime('%Y-%m-%d')
    if today not in ['Tuesday', 'Thursday', 'Saturday']:
        logging.info(f"Today is {today} — script runs only on Tuesday, Thursday, or Saturday.")
        exit()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for country, url in countries.items():
            logging.info(f'Fetching {country} category URLs now')
            jsondata = get_category_urls(page, url)

            # Create correct directory structure
            base_dir = os.path.join(country, "Data", today_str, "Item_urls")
            os.makedirs(base_dir, exist_ok=True)

            #  Save JSON in that directory
            file_path = os.path.join(base_dir, f"{country}_category_links.json")

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(jsondata, f, indent=4, ensure_ascii=False)

            logging.info(f'{country} category URLs fetched and saved to {file_path}')

        browser.close()
