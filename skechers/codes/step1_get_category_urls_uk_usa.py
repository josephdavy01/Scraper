import datetime
import logging
import os
import json
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

countries = {
    'UK': 'https://www.skechers.co.uk/',
    'USA':'https://www.skechers.com/'
}

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_links_by_gender(soup, base_url):
    a_tags = soup.find_all("a", href=True, id=True, role=True, tabindex=True, class_=True)

    all_links = {a['id']: a['href'] for a in a_tags}

    women_links = {}
    men_links = {}
    kids_links = {}

    for category, href in all_links.items() :
        category_lower = category.lower()
        full_url = urljoin(base_url, href)
        if 'women' in category_lower or 'womens' in category_lower:
            women_links[category] = full_url
        elif 'men' in category_lower or 'mens' in category_lower:
            men_links[category] = full_url
        elif 'kids' in category_lower:
            kids_links[category] = full_url

    categorized_links = {}
    if women_links: categorized_links['Women'] = women_links
    if men_links: categorized_links['Men'] = men_links
    if kids_links: categorized_links['Kids'] = kids_links
    return categorized_links

if __name__ == "__main__":
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page() 


        for country, url in countries.items():
            logging.info(f'Processing {country} now...')
            
            # Navigate to the URL
            page.goto(url)
            time.sleep(3)  
            
            # Get the HTML content
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get category data using the function
            category_links = get_links_by_gender(soup, url)

            if not category_links:
                logging.warning(f"No category links found for {country}")
            else:
                logging.info(f"Found categories: {list(category_links.keys())}")

            out_dir = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(out_dir, exist_ok=True)
            json_file_path = os.path.join(out_dir, 'category_urls.json')

            if category_links:
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(category_links, f, ensure_ascii=False, indent=4)


                logging.info(f'{country} category URLs saved to {json_file_path}')
            else:
                logging.warning(f'{country} category file not saved — no data.')

        browser.close()
