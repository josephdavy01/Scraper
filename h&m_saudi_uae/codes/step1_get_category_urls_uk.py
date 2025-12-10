import os
import json
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

countries = {
    'UK': 'https://www2.hm.com/en_gb/index.html'
}

def get_category_urls(page, url):
    page.goto(url, wait_until='domcontentloaded')
    page.wait_for_timeout(5000)

    # Parse the page source
    page_source = page.content()
    soup = BeautifulSoup(page_source, 'html.parser')

    json_tag = soup.find('script', {'id': '__NEXT_DATA__'})
    json_content = json_tag.get_text(strip=True)
    json_data = json.loads(json_content)
    return json_data['props']['pageProps']['headerData']['menuItems']

# Wrap the main logic in Playwright context
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    for country, url in countries.items():
        json_data = get_category_urls(page, url)

        temp = {}

        for gender_dict in json_data:
            gender = gender_dict['nodeId']
            if gender in ['ladies' ,'women', 'men']:
                if gender == 'ladies':
                    gender = 'women' 
                temp[gender] = {}
                for main_category in gender_dict['children']:
                    main_category_name = main_category['nodeName'].lower().replace(' ', '-').strip()
                    if main_category_name in ['clothing', 'sport', 'accessories', 'shoes']:
                        for category in main_category['children']:
                            category_name = category['nodeName'].lower().replace(' ', '-').strip()
                            if '-all' not in category_name:
                                url = 'https://www2.hm.com' + category['href']
                                temp[gender][category_name] = url

            elif gender in ['kids']:
                print(gender)
                temp[gender] = {}
                for sub_gender in gender_dict['children']:
                    sub_gender_name = sub_gender['nodeName'].lower().replace(' ', '-').strip()
                    if sub_gender_name in ['newborn', 'baby', 'kids-2-8-years', 'kids-9-14-years']:
                        for main_category in sub_gender['children']:
                            main_category_name = main_category['nodeName'].lower().replace(' ', '-').strip()
                            if 'children' in main_category:
                                for category in main_category['children']:
                                    category_name = category['nodeName'].lower().replace(' ', '-').strip()
                                    if 'children' in category:
                                        for sub_category in category['children']:
                                            sub_category_name = sub_category['nodeName'].lower().replace(' ', '-').strip()
                                            url = 'https://www2.hm.com' + sub_category['href']
                                            fname = f'{sub_gender_name}_{main_category_name}_{category_name}_{sub_category_name}'
                                            if  '-all' not in fname and '_all' not in fname and 'toys' not in fname:
                                                temp[gender][fname] = url
                                    else:
                                        fname = f'{sub_gender_name}_{main_category_name}_{category_name}'
                                        url = 'https://www2.hm.com' + category['href']
                                        if  '-all' not in fname and '_all' not in fname and 'toys' not in fname:
                                            temp[gender][fname] = url
                            else:
                                fname = f'{sub_gender_name}_{main_category_name}'
                                url = 'https://www2.hm.com' + main_category['href']
                                if  '-all' not in fname and '_all' not in fname and 'toys' not in fname:
                                    temp[gender][fname] = url

        # Ensure directory exists before saving JSON
        os.makedirs(country, exist_ok=True)

        json_file_path = f'{country}/{country}_category_urls.json'
        # Save the collected data to a JSON file
        with open(json_file_path, "w", encoding='utf-8') as outfile:
            json.dump(temp, outfile, ensure_ascii=False, indent=4)

        logging.info(f'{country} category URLs fetched and saved to {json_file_path}')

    # Close the browser
    browser.close()
