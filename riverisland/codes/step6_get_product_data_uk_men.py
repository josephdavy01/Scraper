import os
import json
import logging
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Specify the path to the manually downloaded ChromeDriver
chrome_driver_path = 'chromedriver.exe'
webdriver_service = ChromeService(executable_path=chrome_driver_path)

# Initialize the Chrome driver
driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)

# Save the JSON data to a file
def save_json(gender, category, filename, json_data, date_subfolder):
    try:
        json_file_path = date_subfolder / 'Json_data' / gender / category
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{filename}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for {filename}: {e}")

def check_file(gender, category, name, date_subfolder):
    file_path = f'{date_subfolder}/Json_data/{gender}/{category}/{name}.json'
    return os.path.exists(file_path)

# Fetch the JSON data from the URL using Selenium and save it
def get_json(date_subfolder, gender, category, urls):
    for url in urls:
        filename = url.split('/')[-1]
        status = check_file(gender, category, filename, date_subfolder)
        if not status:
            try:
                driver.get(url)
                # Save the page source (HTML) to a JSON file
                html_content = driver.page_source

                # Parse the HTML content using BeautifulSoup
                soup = BeautifulSoup(html_content, "html.parser")

                # Find the <script> tag with id="__NEXT_DATA__"
                script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

                # Extract the JSON data from the <script> tag
                if script_tag:
                    json_data = script_tag.string

                    # Parse the JSON data
                    temp = json.loads(json_data)

                    json_data = temp['props']['pageProps']['apolloClientCache']

                    for key in json_data.keys():
                        if 'Product:' in key:
                            data_key = key
                        
                    save_json(gender, category, filename, json_data[data_key], date_subfolder)

            except Exception as e:
                logging.error(f"Error processing the webpage for {url}: {e}")

# Main script execution
if __name__ == "__main__":
    try:
        country = 'UK'
            
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')

        logging.info(f'Now starting {country} men products...')
        date_subfolder = Path(country) / 'Data' / today_str
        date_subfolder.mkdir(parents=True, exist_ok=True)

        file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json')
        with open(file_path) as json_file:
            url_dict = json.load(json_file)

        gender = 'Men'
        # Iterate through the categories and fetch data
        for category, urls in url_dict[gender].items():
            logging.info(f'Now starting {gender} {category} products...')
            get_json(date_subfolder, gender, category, urls)
            logging.info(f'{gender} {category} section completed.')

        logging.info(f'{country} men products completed.')

    except Exception as e:
        logging.critical(f"Unexpected error in main execution: {e}")
    finally:
        driver.quit()