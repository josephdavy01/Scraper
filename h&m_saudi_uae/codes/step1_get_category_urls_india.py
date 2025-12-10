import os
import json
import logging
from datetime import date
from bs4 import BeautifulSoup
from proxy_code import get_page_source

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_category_urls(url):
    # Parse the page source
    page_source = get_page_source(url)
    soup = BeautifulSoup(page_source, 'html.parser')

    json_tag = soup.find('script', {'id': '__NEXT_DATA__'})
    json_content = json_tag.get_text(strip=True)
    json_data = json.loads(json_content)
    return json_data['props']['pageProps']['headerData']['menuItems']


def get_category_dict(url):
    json_data = get_category_urls(url)

    temp = {}

    for gender_dict in json_data:
        gender = gender_dict['nodeId']
        if gender in ['ladies' ,'women', 'men']:
            temp[gender] = {}
            for main_category in gender_dict['children']:
                main_category_name = main_category['nodeName'].lower().replace(' ', '-').strip()
                if main_category_name in ['clothing', 'sport']:
                    for category in main_category['children']:
                        category_name = category['nodeName'].lower().replace(' ', '-').strip()
                        if '-all' in category_name:
                            url = 'https://www2.hm.com' + category['href']
                            temp[gender][f'{main_category_name}_{category_name}'] = url

        elif gender in ['kids']:
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
                                        if  '-all' in fname and '_all' in fname and 'toys' not in fname and 'accessories' not in fname:
                                            temp[gender][fname] = url
                                else:
                                    fname = f'{sub_gender_name}_{main_category_name}_{category_name}'
                                    url = 'https://www2.hm.com' + category['href']
                                    if  '-all' in fname and '_all' in fname and 'toys' not in fname and 'accessories' not in fname:
                                        temp[gender][fname] = url
                        else:
                            fname = f'{sub_gender_name}_{main_category_name}'
                            url = 'https://www2.hm.com' + main_category['href']
                            if  '-all' in fname and '_all' in fname and 'toys' not in fname and 'accessories' not in fname:
                                temp[gender][fname] = url
    return temp

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')

    countries = {
        'India': 'https://www2.hm.com/en_in/index.html',
        'UK': 'https://www2.hm.com/en_gb/index.html'
    }
    
    for country, url in countries.items():
        category_dict = get_category_dict(url)

        # Ensure directory exists before saving JSON
        output_dir = f"{country}/Data/{today_str}/Item_urls"
        os.makedirs(output_dir, exist_ok=True)

        json_file_path = f'{output_dir}/{country}_category_urls.json'
        # Save the collected data to a JSON file
        with open(json_file_path, "w", encoding='utf-8') as outfile:
            json.dump(category_dict, outfile, ensure_ascii=False, indent=4)

        logging.info(f'{country} category URLs fetched and saved to {json_file_path}')