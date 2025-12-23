import os
from datetime import datetime
from validations import (compare_with_previous_data, 
                         check_comparison_results_data, remove_duplicate_urls, remove_duplicate_urls_products)
from step1_get_category_urls import get_category_urls
from step2_get_product_url import get_product_urls
from step3_daily_count import process_country_data
from step4_get_product_data import get_product_data
from step5_urls_json_comparison import json_url_comparison
from step6_extract_data_footwear import upload_to_json_footwear
from step6_extract_data_apparel import upload_to_json_apparel
from step7_remove_duplicate_sku_footwear import remove_duplicate_sku_footwear
from step7_remove_duplicate_sku_apparel import remove_duplicate_sku_apparel
from step8_load_to_db_footwear import load_to_db_footwear
from step8_load_to_db_apparel import load_to_db_apparel
from step9_upload_to_melody_footwear import upload_data_to_melody_footwear
from step9_upload_to_melody_apparel import upload_data_to_melody_apparel


TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = '2025-12-01'

TODAY_DATE_OBJ = datetime.strptime(TODAY_DATE, "%Y-%m-%d")
TODAY = TODAY_DATE_OBJ.strftime("%A")

COUNTRIES = {
    'USA': 'https://us.puma.com/us/en',
}

# Configuration
CONFIG = {
    'USA': {
        'base_url': 'https://us.puma.com/us/en',
        'lang_code': '',
        'browsers': 2,
        'data_dir': 'USA',
        'api': True,
        'prefix': '/us/en',
        'token':'eyJ2ZXIiOiIxLjAiLCJqa3UiOiJzbGFzL3Byb2QvYmNqcF9wcmQiLCJraWQiOiI1NzYxYzFlZS0yMDI2LTQxNDQtOTAxNS0zMTA1NTc3ODI2NmIiLCJ0eXAiOiJqd3QiLCJjbHYiOiJKMi4zLjQiLCJhbGciOiJFUzI1NiJ9.eyJhdXQiOiJHVUlEIiwic2NwIjoic2ZjYy5zaG9wcGVyLW15YWNjb3VudC5iYXNrZXRzIHNmY2Muc2hvcHBlci1teWFjY291bnQuYWRkcmVzc2VzIHNmY2Muc2hvcHBlci1wcm9kdWN0cyBzZmNjLnNob3BwZXItbXlhY2NvdW50LnJ3IHNmY2Muc2hvcHBlci1teWFjY291bnQucGF5bWVudGluc3RydW1lbnRzIHNmY2Muc2hvcHBlci1jdXN0b21lcnMubG9naW4gc2ZjYy5zaG9wcGVyLWNvbnRleHQgc2ZjYy5zaG9wcGVyLWNvbnRleHQucncgc2ZjYy5zaG9wcGVyLW15YWNjb3VudC5vcmRlcnMgc2ZjYy5zaG9wcGVyLWN1c3RvbWVycy5yZWdpc3RlciBzZmNjLnNob3BwZXItYmFza2V0cy1vcmRlcnMgc2ZjYy5zaG9wcGVyLW15YWNjb3VudC5hZGRyZXNzZXMucncgc2ZjYy5zaG9wcGVyLW15YWNjb3VudC5wcm9kdWN0bGlzdHMucncgc2ZjYy5zaG9wcGVyLXByb2R1Y3RsaXN0cyBzZmNjLnNob3BwZXItcHJvbW90aW9ucyBzZmNjLnNob3BwZXItYmFza2V0cy1vcmRlcnMucncgY19wcmljaW5nQW5kUHJvbW90aW9uc19yIHNmY2Muc2hvcHBlci1teWFjY291bnQucGF5bWVudGluc3RydW1lbnRzLnJ3IHNmY2Muc2hvcHBlci1naWZ0LWNlcnRpZmljYXRlcyBzZmNjLnNob3BwZXItcHJvZHVjdC1zZWFyY2ggc2ZjYy5zaG9wcGVyLW15YWNjb3VudC5wcm9kdWN0bGlzdHMgc2ZjYy5zaG9wcGVyLWNhdGVnb3JpZXMgc2ZjYy5zaG9wcGVyLW15YWNjb3VudCIsInN1YiI6ImNjLXNsYXM6OmJjanBfcHJkOjpzY2lkOjFjOGM4YTNlLTY1NmUtNDFiMS04YjZmLWZiMDZjNDUxZjAxOTo6dXNpZDo4ODQwM2Y5My0yYzNmLTRkMjYtOWJkZC01ZmYzYTdiN2FmODgiLCJjdHgiOiJzbGFzIiwiaXNzIjoic2xhcy9wcm9kL2JjanBfcHJkIiwiaXN0IjoxLCJkbnQiOiIwIiwiYXVkIjoiY29tbWVyY2VjbG91ZC9wcm9kL2JjanBfcHJkIiwibmJmIjoxNzU5ODQ2NjM4LCJzdHkiOiJVc2VyIiwiaXNiIjoidWlkbzpzbGFzOjp1cG46R3Vlc3Q6OnVpZG46R3Vlc3QgVXNlcjo6Z2NpZDphYm1iRVlrYmxLbXJrUmtLa1h4R1lZeGJnMDo6Y2hpZDpOQSIsImV4cCI6MTc1OTg0ODQ2OCwiaWF0IjoxNzU5ODQ2NjY4LCJqdGkiOiJDMkMtMTg0NDYwNDc3MDA3NDA2MzQzNzIxNTYwNjUyNjk0NjAyNjIifQ._1p2uvkFmEQY3EX8LP8fI3Ufq92_59RBw-zoHMvQISdnLB2vTEt3mZmgiIf-nDuuANNigFCyTiaFwuFfAqa2Iw',
        'refresh_token':'G2fuo2MHIiEYnNs84IwLObrA_QSaCAoobt07oq0VpIU',
        'max_retries': 5,
        'api_concurrency': 50
    },
}

USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]

MONGO_CONFIG_APPAREL = {
    'SERVER_URI': 'replace_with_actul_server_string', # IMPORTANT: Fill this in
    'LOCAL_URI': 'mongodb://localhost:27017',
    'DB_NAME': 'tg_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_puma_',
    'THRESHOLD_PERCENT': 60.0,
    'FORCE_UPLOAD': True, # Set True to delete existing data on the server for the same day and re-upload.
    'DRY_RUN': False        # Set True to simulate the run without writing/deleting any data.
}

MONGO_CONFIG_FOOTWEAR = {
    'SERVER_URI': 'replace_with_actul_server_string', # IMPORTANT: Fill this in
    'LOCAL_URI': 'mongodb://localhost:27017',
    'DB_NAME': 'footwear_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_puma_',
    'THRESHOLD_PERCENT': 60.0,
    'FORCE_UPLOAD': True, # Set True to delete existing data on the server for the same day and re-upload.
    'DRY_RUN': False        # Set True to simulate the run without writing/deleting any data.
}

LOCAL_DB_CONFIG = {
    'LOCAL_URI': 'mongodb://localhost:27017',
    'FORCE_UPLOAD': True  # Set True to delete and re-upload data to the local DB.
                           # Set False to skip if data for the day already exists.
}

def create_country_directories():
    for country, url in COUNTRIES.items():
        # Make sure the country directory exists
        country_dir = f"{country}/{TODAY_DATE}"
        os.makedirs(country_dir, exist_ok=True)

def main():
    # Create directories for each country
    create_country_directories()
    if TODAY in ['Monday', 'Tuesday', 'Thursday' ,'Wednesday', 'Friday','Saturday']:
        print(f"Today is {TODAY}. Proceeding with the script...")

        # Fetch category URLs for all countries
        get_category_urls(COUNTRIES, TODAY_DATE, re_run=False)

        # Remove duplicate URLs for all countries
        remove_cat_dup = remove_duplicate_urls(COUNTRIES, TODAY_DATE)
        if not remove_cat_dup:
            print("Error removing duplicate URLs. Exiting script.")
            exit()

        # Compare with previous data
        compare_with_previous_data(COUNTRIES, TODAY_DATE)

        '''
        #     Check if comparison results data exists for all countries 
        #     check for changes and prompt user if changes are found
        # ''' 
        country_wise_status = check_comparison_results_data(COUNTRIES, TODAY_DATE)
        
        if all(country_wise_status.values()):
            print("No changes found in any country.")
        else:
            print("Changes found in the following countries:")
            for country, status in country_wise_status.items():
                if not status:
                    print(f"{country}: Changes detected.")
                    # Press Yes/y to continue
                    if input(f"Do you want to continue with {country}? (y/n): ").strip().lower() != 'y':
                        print(f"Exiting Scraping for all countries.")
                        exit()
                    else:
                        print(f"Continuing...")

        # Fetch product URLs for all countries
        get_product_urls(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES)

        # Remove duplicate product URLs for all countries
        remove_prod_dup = remove_duplicate_urls_products(COUNTRIES, TODAY_DATE)
        if not remove_prod_dup:
            print("Error removing duplicate product URLs. Exiting script.")
            exit()

        # Process country data for daily count
        for country in COUNTRIES.keys():
            process_country_data(country, TODAY_DATE)

        # Get product data for all countries
        get_product_data(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, re_run=False)

        # Compare product URLs with JSON data for each country
        json_url_comparison(list(COUNTRIES.keys()), TODAY_DATE)

        # Upload processed data to JSON files
        upload_to_json_footwear(CONFIG, TODAY_DATE, re_run=True)
        upload_to_json_apparel(CONFIG, TODAY_DATE, re_run=True)


        # Remove duplicate SKUs from the JSON data
        remove_duplicate_sku_footwear(COUNTRIES, TODAY_DATE, re_run=True)
        remove_duplicate_sku_apparel(COUNTRIES, TODAY_DATE, re_run=True)

        # Load data to MongoDB Local
        load_to_db_footwear(TODAY_DATE, COUNTRIES, LOCAL_DB_CONFIG)
        load_to_db_apparel(TODAY_DATE, COUNTRIES, LOCAL_DB_CONFIG)


        # Upload data to Melody
        print("\n--- Starting Melody Upload Step ---")
        if MONGO_CONFIG_APPAREL.get('DRY_RUN', False):
            print("INFO: Running in DRY RUN mode. No data will be written or deleted on the server.")
        if MONGO_CONFIG_APPAREL.get('FORCE_UPLOAD', False):
            print("INFO: FORCE UPLOAD is enabled. Existing data for today may be replaced.")
        upload_data_to_melody_apparel(CONFIG, MONGO_CONFIG_APPAREL, TODAY_DATE)

        print("\n--- Starting Melody Upload Step ---")
        if MONGO_CONFIG_FOOTWEAR.get('DRY_RUN', False):
            print("INFO: Running in DRY RUN mode. No data will be written or deleted on the server.")
        if MONGO_CONFIG_FOOTWEAR.get('FORCE_UPLOAD', False):
            print("INFO: FORCE UPLOAD is enabled. Existing data for today may be replaced.")
        upload_data_to_melody_footwear(CONFIG, MONGO_CONFIG_FOOTWEAR, TODAY_DATE)
        
        print("Script completed successfully.")
    else:
        print(f"Today is {TODAY}. Script only runs on Monday, Wednesday, Friday.")
        exit()

if __name__ == "__main__":
    main()
    exit(0)
