import os
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

pop_keys = ['all', 'premium', 'room', 'arrivals', 'edition', 'care', 'adorables', 'fancy']

def extract_category_urls(menu_ul, gender, temp):
    category_tags = menu_ul.find_all('a')
    for category_tag in category_tags:
        name = category_tag.get_text(strip=True)
        if name:
            li_tag = category_tag.find_parent('li')
            main_category_name = li_tag.get('data-gtm-name') if li_tag and li_tag.get('data-gtm-name') else name
            name = (main_category_name + '_' + name).strip().lower().replace(' ', '-')
            if not any(keyword in name for keyword in pop_keys):
                link = 'https://sa.hm.com' + category_tag.get('href')
                temp[gender][name] = link

                subcategories_ul = li_tag.find_all('ul', {'class': 'submenu-ul'})
                for subcategory_ul in subcategories_ul:
                    subcategory_urls = subcategory_ul.find_all('a')
                    for subcategory_link in subcategory_urls:
                        subcategory_name = subcategory_link.get_text(strip=True)
                        if subcategory_name:
                            subcategory_name = (main_category_name + '_' + subcategory_name).strip().lower().replace(' ', '-')
                            subcategory_link_url = 'https://sa.hm.com' + subcategory_link.get('href')
                            if not any(keyword in subcategory_name for keyword in pop_keys):
                                temp[gender][subcategory_name] = subcategory_link_url

def get_category_urls(page, url):
    page.goto(url, wait_until='domcontentloaded')
    page.wait_for_timeout(5000)
    temp ={}

    html_content = page.content()
    soup = BeautifulSoup(html_content, "html.parser")

    menu_tag = soup.find("div", {"class": "sub-menu-wrapper"})
    if menu_tag:
        gender_tags = menu_tag.find_all("ul", {"class": "submenu-ul submenu-ul-2"})
        for gender_tag in gender_tags:
            gender = gender_tag.get('data-gtm-name')
            if gender in ['Women', 'Men']:
                temp[gender] = {}
                main_category_tag = gender_tag.find('li', {'data-gtm-name': 'Shop By Product'})
                a_tags = main_category_tag.find_all('a')
                for a_tag in a_tags:
                    name = a_tag.string
                    if name:
                        name = name.strip().lower().replace(' ', '-')
                        if not any(keyword in name for keyword in pop_keys):
                            link = 'https://sa.hm.com' + a_tag.get('href')
                            temp[gender][name] = link

            elif gender.lower() == 'baby':
                temp[gender] = {}
                baby_menu_ul = soup.find("ul", {"id": "submenu-ul-9762", "class": "submenu-ul submenu-ul-2"})
                if baby_menu_ul:
                    extract_category_urls(baby_menu_ul, gender, temp)

            elif gender.lower() == 'kids':
                temp[gender] = {}
                kids_menu_ul = soup.find("ul", {"id": "submenu-ul-1281", "class": "submenu-ul submenu-ul-2"})
                if kids_menu_ul:
                    extract_category_urls(kids_menu_ul, gender, temp)

            elif gender.lower() == 'sale':
                main_categories_tags = gender_tag.find_all('li', {'class': 'submenu-li level-3-li no-images'})
                for main_category_tag in main_categories_tags:
                    main_category_name = main_category_tag.get('data-gtm-name')
                    if main_category_name in ['Women', 'Men', 'Kids', 'Baby']:
                        a_tags = main_category_tag.find_all('a')
                        for a_tag in a_tags:
                            name = a_tag.string
                            if name:
                                name = (main_category_name + '_' + name).strip().lower().replace(' ', '-')
                                if not any(keyword in name for keyword in pop_keys):
                                    link = 'https://sa.hm.com' + a_tag.get('href')
                                    if main_category_name not in temp:
                                        temp[main_category_name] = {}
                                    temp[main_category_name]['sale_' + name] = link
    return temp

# Main script execution
if __name__ == "__main__":
    countries = {
        'Saudi': 'https://sa.hm.com/en/'
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        for country, url in countries.items():
            print(f'Fetching {country} category URLs now')
            jsondata = get_category_urls(page, url)

            folder_path = os.path.join(country)
            file_path = os.path.join(country, f'{country}_category_urls.json')

            os.makedirs(folder_path, exist_ok=True)

            with open(file_path, 'w') as f:
                json.dump(jsondata, f, indent=4)

            print(f'{country} category URLs fetched and saved to {file_path}')
        
        browser.close()
