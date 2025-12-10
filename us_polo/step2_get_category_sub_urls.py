import logging
import os
import json
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_sub_urls(page, url):
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(2000) 
    except TimeoutError as e:
        logging.error(f"Timeout loading {url}: {e}")
        return []
    except Exception as e:
        logging.error(f"Error loading {url}: {e}")
        return []

    html_content = page.content()
    soup = BeautifulSoup(html_content, "html.parser")

    colors = set()
    links = []

    filter_tags = soup.find_all('div', {'class': 'st-widget'})
    for filter_tag in filter_tags:
        h3_tag = filter_tag.find('h3')
        if h3_tag and 'colour' in h3_tag.get_text().lower():
            colour_tags = filter_tag.find_all('div', {'class': 'filter-label'})
            for colour_tag in colour_tags:
                colour_text = colour_tag.get_text().strip().lower()
                if colour_text:
                    color = colour_text.split(' ')[0]
                    colors.add(color)

    for color in colors:
        links.append(f'{url}?f.Colour={color}')

    return links

# Main script execution
if __name__ == "__main__":
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    country = 'India'
    base_dir = os.path.join(country, "Data", today_str, "Item_urls")
    os.makedirs(base_dir, exist_ok=True)

    input_file = os.path.join(base_dir, f"{country}_category_links.json")

    # Check if JSON file exists
    if not os.path.exists(input_file):
        logging.error(f"Input file not found: {input_file}")
        exit(1)

    # Load URLs
    with open(input_file, 'r') as f:
        url_dict = json.load(f)

    updated_url_dict = {}

    folder_path = os.path.join(country)
    file_path = os.path.join(folder_path, f'{country}_updated_category_urls.json')
    os.makedirs(folder_path, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width":1440, "height": 713})

        for gender, categories in url_dict.items():
            if gender not in updated_url_dict:
                updated_url_dict[gender] = {}
            for category, url in categories.items():
                if not url:
                    logging.warning(f"Empty URL for {gender} > {category}, skipping.")
                    continue
                logging.info(f"Processing: {gender} > {category}")
                sub_urls = get_sub_urls(page, url)
                updated_url_dict[gender][category] = sub_urls

                # Save immediately after each category
                with open(file_path, 'w') as f:
                    json.dump(updated_url_dict, f, indent=4)

        browser.close()

    logging.info(f'{country} category URLs fetched and saved to {file_path}')
