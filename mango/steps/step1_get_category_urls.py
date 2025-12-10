import os
import json
import logging
from curl_cffi import requests

def extract_urls(menu, base_url):
    """Recursively extracts URLs from the menu structure."""
    urls = []

    if 'url' in menu:
        urls.append(base_url + menu['url'])

    for sub in menu.get('menus', []):
        urls.extend(extract_urls(sub, base_url))

    return urls

def get_category_data(country, url, session):
    """Fetches category data from the given URL using curl_cffi."""
    try:
        response = session.get(url, impersonate="chrome110")
        response.raise_for_status()  # Raise an exception for bad status codes
        json_data = response.json()
        logging.info(f"Successfully fetched categories for {country}.")
        return json_data
    except requests.errors.RequestsError as e:
        logging.error(f"Error making request for {country}: {e}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON for {country}.")
        return None

def get_category_urls(countries, today_date, config, re_run=False):
    """
    Fetches and saves category URLs for the given countries.
    Implements re-run logic based on file existence and content.
    """
    logging.info("Starting Step 1: Get category URLs")
    
    with requests.Session() as session:
        for country in countries:
            country_config = config.get(country)
            if not country_config:
                logging.warning(f"No configuration found for {country}, skipping.")
                continue

            file_path = os.path.join(country, today_date, "Category", f"{country}_category.json")
            
            if not re_run and os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    if data: # Checks if the loaded json is not empty (e.g., not {} or [])
                        logging.info(f"Category URLs for {country} already exist and are not empty. Skipping.")
                        continue
                    else:
                        logging.info(f"Category URLs file for {country} is empty. Re-running.")
                except (json.JSONDecodeError, FileNotFoundError):
                     logging.info(f"Category URLs file for {country} is invalid or not found. Re-running.")
                except Exception as e:
                    logging.warning(f"Error checking existing file for {country}: {e}. Re-running.")


            logging.info(f'Fetching {country} category URLs now')
            url = country_config['base_url']
            base_url = country_config['base']
            json_data = get_category_data(country, url, session)

            if json_data is None:
                continue

            temp_json = {}
            for i in json_data.get('menus', []):
                if i.get("id") == 'she':
                    temp_json['women'] = extract_urls(i, base_url)
                elif i.get("id") == 'he':
                    temp_json['men'] = extract_urls(i, base_url)
                elif i.get("id") == 'teen':
                    temp_json['teen'] = extract_urls(i, base_url)
                elif i.get("id") == 'kids':
                    temp_json['kids'] = extract_urls(i, base_url)

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as outfile:
                json.dump(temp_json, outfile, ensure_ascii=False, indent=4)

            logging.info(f'{country} category URLs fetched and saved to {file_path}')

    logging.info("Finished Step 1: Get category URLs")
