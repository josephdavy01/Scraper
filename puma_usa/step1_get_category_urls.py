import datetime
import os
import time
import json
import logging
from playwright.sync_api import sync_playwright
import multiprocessing
from validations import check_category_urls
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import unicodedata
import re
from urllib.parse import urljoin


# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def sanitize_filename(name): 
    if not name:
        return "unnamed"
    
    name = name.lower()
    replacements = {"'": "", '"': "", "–": "-", "—": "-", "&": "and", ",": "", ":": "", ";": "", "!": "", "?": "", "/": "-", "\\": "-", "|": "-", "*": "", "<": "", ">": "", "+": "plus", "=": "equals", "%": "percent", "@": "at", "#": "hash", "$": "dollar", "^": "", "~": "", "`": "", "₹": "rupees", "™": "", "®": "", "©": ""}
    
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = ''.join(char for char in name if unicodedata.category(char)[0] != 'S' or char in ['-', '_'])
    name = unicodedata.normalize('NFD', name)
    name = ''.join(char for char in name if unicodedata.category(char) != 'Mn')
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[-_]+', '_', name)
    name = name.strip('_-')
    if not name:
        name = "unnamed"
    return name

     
def process_country(country, url, today_date):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Flag to track if we've completed country selection

        try:
            logging.info(f"Processing {country}...")
            page.goto(url, wait_until="load", timeout=20000)

            soup = BeautifulSoup(page.content(), 'html.parser')
            main_categories = soup.find_all("li", attrs={"data-test-id": "main-nav-category-item"})
        
            if not main_categories:
                logging.warning("No categories found - possibly blocked by Cloudflare")
                browser.close()
                return {}
                
            result = {}
            base_url = url
            
            for main in main_categories:
                main_link = main.find("a", attrs={"data-link-location": "top-nav-level-1"})
                if not main_link:
                    continue
                
                main_name = sanitize_filename(main_link.get_text(strip=True))
                subcats = {}
                
                level_2_sections = main.find_all("ul", role="menu")
                for section in level_2_sections:
                    section_header = section.find("a", attrs={"data-test-id": "top-nav-level-2-top"})
                    section_name = ""
                    if section_header:
                        section_name = sanitize_filename(section_header.get_text(strip=True)) + "_"
                    
                    sub_links = section.find_all("a", attrs={"data-test-id": "top-nav-level-3"})
                    for sub_link in sub_links:
                        subcat_name = sub_link.get_text(strip=True)
                        subcat_url = urljoin(base_url, sub_link.get("href"))
                        if subcat_url != urljoin(base_url, main_link.get("href")):
                            base_key = sanitize_filename(subcat_name)
                            key = section_name + base_key if section_name else base_key
                            subcats[key] = subcat_url
                
                side_links = main.find_all("a", attrs={"data-test-id": "top-nav-level-2-side"})
                for side_link in side_links:
                    subcat_name = side_link.get_text(strip=True)
                    subcat_url = urljoin(base_url, side_link.get("href"))
                    if subcat_url != urljoin(base_url, main_link.get("href")):
                        key = sanitize_filename(subcat_name)
                        subcats[key] = subcat_url
                
                subcats['shop_all'] = urljoin(base_url, main_link.get("href"))
                result[main_name] = subcats


            json_file_path = f'{country}/{today_date}/{country}_category_links.json'
            with open(json_file_path, "w", encoding='utf-8') as outfile:
                json.dump(result, outfile, ensure_ascii=False, indent=4)

            # logging.info(f'{country} category URLs fetched and saved to {json_file_path}')
        
        except Exception as e:
            logging.error(f"Error processing {country}: {str(e)}")
        finally:
            context.close()
            browser.close()

def get_category_urls(countries, today_date, re_run):
    processes = []
    for country, url in countries.items():
        if not re_run:
            status = check_category_urls(country, today_date)
            if status:
                logging.info(f"Category URLs already exist for {country} on {today_date}. Skipping...")
                continue
        process = multiprocessing.Process(target=process_country, args=(country, url, today_date))
        processes.append(process)
        process.start()
    
    for process in processes:
        process.join()

    logging.info("All countries processed successfully")


    