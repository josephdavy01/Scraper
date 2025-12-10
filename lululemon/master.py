import os
from datetime import datetime
from validations import (compare_with_previous_data, 
                         check_comparison_results_data, remove_duplicate_urls, remove_duplicate_urls_products)
from step1_get_category_urls import get_category_urls
from step2_get_product_urls import get_product_urls
from step3_daily_count import process_country_data
from step4_get_product_data import get_product_data
from step5_urls_json_comparison import json_url_comparison
from step6_extract_data import upload_to_json
from step7_remove_duplicate_sku import remove_duplicate_sku
from step8_load_to_db import load_to_db
from step8_load_to_db_footwear import footwear_load_to_db
from step9_remove_duplicate_skus_apparels import remove_duplicate_skus_apparel
from step9_remove_duplicate_skus_footwear import remove_duplicate_skus_footwear
from step10_upload_to_melody import load_to_melody
from step10_upload_to_melody_footwear import upload_to_melody_footwear

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = "2025-11-27"
TODAY_DATE_OBJ = datetime.strptime(TODAY_DATE, "%Y-%m-%d")
TODAY = TODAY_DATE_OBJ.strftime("%A")

COUNTRIES = {
    'Canada': 'https://shop.lululemon.com/en-ca/',
    'USA': 'https://shop.lululemon.com/'
}

# Configuration
CONFIG = {
    'USA': {
        'base_url': 'https://shop.lululemon.com',
        'browsers': 2,
        'data_dir': 'USA'
    },
    'Canada': {
        'base_url': 'https://shop.lululemon.com/en-ca',
        'browsers': 2,
        'data_dir': 'Canada'
    }
}

def create_country_directories():
    for country, url in COUNTRIES.items():
        # Make sure the country directory exists
        country_dir = f"{country}/{TODAY_DATE}"
        os.makedirs(country_dir, exist_ok=True)

def main():
    # Create directories for each country
    create_country_directories()
    if TODAY in ['Tuesday', 'Thursday', 'Saturday']:
        print(f"Today is {TODAY}. Proceeding with the script...")

        # Fetch category URLs for all countries
        get_category_urls(COUNTRIES, TODAY_DATE)

        # Fetch product URLs for all countries
        get_product_urls(CONFIG, TODAY_DATE)

        # Remove duplicate product URLs for all countries
        remove_prod_dup = remove_duplicate_urls_products(COUNTRIES, TODAY_DATE)
        if not remove_prod_dup:
            print("Error removing duplicate product URLs. Exiting script.")
            exit()

        # Process country data for daily count
        for country in COUNTRIES.keys():
            process_country_data(country, TODAY_DATE)

        # Get product data for all countries
        get_product_data(CONFIG, TODAY_DATE)

        # Compare product URLs with JSON data for each country
        json_url_comparison(list(COUNTRIES.keys()), TODAY_DATE)

        # Upload processed data to JSON files
        upload_to_json(COUNTRIES, TODAY_DATE, re_run=False)

        # Remove duplicate SKUs from the JSON data
        remove_duplicate_sku(COUNTRIES, TODAY_DATE, re_run=False)

        # Load data to MongoDB Local
        load_to_db(COUNTRIES, TODAY_DATE, allow_reupload=False)
        footwear_load_to_db()
        remove_duplicate_skus_apparel()
        # Remove footwear duplicate SKUs
        remove_duplicate_skus_footwear()

        # # # Load data to Melody
        load_to_melody()
        upload_to_melody_footwear()
        
        print("Script completed successfully.")
    else:
        print(f"Today is {TODAY}. Script only runs on Tuesday,Thursday and Saturday.")
        exit()

if __name__ == "__main__":
    main()
    exit(0)
