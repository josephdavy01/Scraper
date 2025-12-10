import os
import json
import logging
from datetime import datetime
from validations import (compare_with_previous_data, 
                         check_comparison_results_data, remove_duplicate_urls, remove_duplicate_urls_products,
                         compare_product_links, summarize_product_url_changes, check_deviation)
from step1_get_category_urls import get_category_urls
from step2_get_product_pids import get_product_urls
from step3_get_product_data import get_product_data
from step4_process_and_save_apparel import process_jsons as load_apparel
from step4_process_and_save_footwear import process_jsons as load_footwear
from step5_remove_duplicate_skus import remove_duplicates_from_json
from step6_check_data_format import check_data_format
from step7_upload_to_melody import upload_to_data_melody
from alert import raise_ticket

# --- Configuration --- 
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = "2025-12-03"
TODAY_DATE_OBJ = datetime.strptime(TODAY_DATE, "%Y-%m-%d")
TODAY = TODAY_DATE_OBJ.strftime("%A")


COUNTRIES_MON_WED_FRI = {
    "Canada":'https://www.bershka.com/ca/', 
    "India": 'https://www.bershka.com/in/', 
    "Saudi": 'https://www.bershka.com/sa/en/', 
    "Spain": 'https://www.bershka.com/es/en/'
}

COUNTRIES_TUE_THU_SAT = {
    "Turkey": 'https://www.bershka.com/tr/en/',
    "UAE": 'https://www.bershka.com/ae/',
    "UK": 'https://www.bershka.com/gb/',
    "USA": 'https://www.bershka.com/us/'
}

CONFIG_MON_WED_FRI = {
    'Canada': {
        'base_url': 'https://www.bershka.com/ca/',
        'browsers': 4,
        'data_dir': 'Canada',
        'prefix': '/ca/en',
        'max_retries': 5,
        'headless': False,
        'cid': '44009527/40259549' 
    },
    'India': {
        'base_url': 'https://www.bershka.com/in/',
        'browsers': 4,
        'data_dir': 'India',
        'prefix': '/in/en',
        'max_retries': 5,
        'headless': False,
        'cid': '44010164/40259582'
    },
    'Saudi': {
        'base_url': 'https://www.bershka.com/sa/en/',
        'browsers': 4,
        'data_dir': 'Saudi',
        'prefix': '/sa/en',
        'max_retries': 5,
        'headless': False,
        'cid': '45109530/40259548'
    },
    'Spain': {
        'base_url': 'https://www.bershka.com/es/en/',
        'browsers': 4,
        'data_dir': 'Spain',
        'prefix': '/es/en',
        'max_retries': 5,
        'headless': False,
        'cid': '44009500/40259530'
    },
}

CONFIG_TUE_THU_SAT = {
    'Turkey': {
        'base_url': 'https://www.bershka.com/tr/en/',
        'browsers': 4,
        'data_dir': 'Turkey',
        'prefix': '/tr/en',
        'max_retries': 5,
        'headless': False,
        'cid': '44109521/40259537' 
    },
    'UAE': {
        'base_url': 'https://www.bershka.com/ae/',
        'browsers': 4,
        'data_dir': 'UAE',
        'prefix': '/ae/en',
        'max_retries': 5,
        'headless': False,
        'cid': '45109531/40259579'
    },
    'UK': {
        'base_url': 'https://www.bershka.com/gb/',
        'browsers': 4,
        'data_dir': 'UK',
        'prefix': '/gb/en',
        'max_retries': 5,
        'headless': False,
        'cid': '44009506/40259534'
    },
    'USA': {
        'base_url': 'https://www.bershka.com/us/',
        'browsers': 4,
        'data_dir': 'USA',
        'prefix': '/us/en',
        'max_retries': 5,
        'headless': False,
        'cid': '45009578/40259549'
    },
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]


MONGO_CONFIG_APPAREL = {
    'SERVER_URI': 'mongodb://root:iK&dsCaTio976fghI*(bgdskk)~@34.143.153.196:28018/tg_analytics?authSource=admin', 
    'LOCAL_URI': 'mongodb://localhost:27017',
    'DB_NAME': 'tg_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_bershka_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': False, 
    'DRY_RUN': False        
}

MONGO_CONFIG_FOOTWEAR = {
    'SERVER_URI': 'mongodb://root:iK&dsCaTio976fghI*(bgdskk)~@34.143.153.196:28018/tg_analytics?authSource=admin', # IMPORTANT: Update with real URI
    'LOCAL_URI': 'mongodb://localhost:27017',
    'DB_NAME': 'footwear_analytics', # Assuming separate DB or collection logic
    'COLLECTION_PREFIX': 'crawler_sink_bershka_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': False, 
    'DRY_RUN': False
}

EXECUTION_CONFIG = {
    'run_step1_category_urls': True,
    'run_step2_product_urls': True,
    'run_step3_product_data': True,
    'run_step4_process_json': True,
    'run_step5_remove_duplicates': True,
    'run_step6_check_data_format': True,
    'run_step7_upload_to_melody': True
}

def create_country_directories(countries):
    for country in countries:
        country_dir = f"{country}/{TODAY_DATE}"
        os.makedirs(country_dir, exist_ok=True)

def main():
    # 1. Determine which Config to use based on Day
    COUNTRIES = {}
    CONFIG = {}

    # Logic to select countries based on day
    # For testing/forcing, you might want to override this
    if TODAY in ['Monday', 'Wednesday', 'Friday']:
        COUNTRIES = COUNTRIES_MON_WED_FRI
        CONFIG = CONFIG_MON_WED_FRI
    elif TODAY in ['Tuesday', 'Thursday', 'Saturday']:
        COUNTRIES = COUNTRIES_TUE_THU_SAT
        CONFIG = CONFIG_TUE_THU_SAT
    else:
        print(f"Today is {TODAY}, no scheduled scrape.")
    
    # Override for dev/testing if needed
    # COUNTRIES = COUNTRIES_TUE_THU_SAT
    # CONFIG = CONFIG_TUE_THU_SAT

    if not COUNTRIES:
        print("No countries to process. Exiting.")
        return

    print(f"Today is {TODAY}. Proceeding with the script...")
    print(f"Active Countries: {list(COUNTRIES.keys())}")
    create_country_directories(COUNTRIES)

    # --- Step 1: Category URLs ---
    if EXECUTION_CONFIG['run_step1_category_urls']:
        print("\n--- Step 1: Category URLs ---")
        get_category_urls(CONFIG, TODAY_DATE, re_run=True)

        # Remove duplicate URLs
        remove_cat_dup = remove_duplicate_urls(COUNTRIES, TODAY_DATE)
        if not remove_cat_dup:
            print("Error removing duplicate URLs.")
            raise_ticket("Master", "remove_duplicate_urls", "Failed to remove duplicate category URLs.")
            # Decide if you want to exit or continue. Usually continue if possible.

        # Compare with previous data
        compare_with_previous_data(COUNTRIES, TODAY_DATE)
        
        # Check comparison results
        country_wise_status = check_comparison_results_data(COUNTRIES, TODAY_DATE)
        for country, status in country_wise_status.items():
            if not status:
                print(f"{country}: Changes detected in categories.")
                # Ticket raising is handled inside check_comparison_results_data or here?
                # The original code had ticket raising here.
                raise_ticket("Master", "Category Check", f"Category changes detected for {country}", country)

    # --- Step 2: Product URLs ---
    if EXECUTION_CONFIG['run_step2_product_urls']:
        print("\n--- Step 2: Product IDs ---")
        get_product_urls(CONFIG, TODAY_DATE)

        # Remove duplicates
        remove_prod_dup = remove_duplicate_urls_products(COUNTRIES, TODAY_DATE)
        if not remove_prod_dup:
            print("Error removing duplicate product IDs.")
            raise_ticket("Master", "remove_duplicate_urls_products", "Failed to remove duplicate product IDs.")

        # Compare product IDs
        compare_product_links(COUNTRIES, TODAY_DATE)
        summarize_product_url_changes(COUNTRIES, TODAY_DATE)

        # Check deviation
        for country in COUNTRIES:
            log_file_path = os.path.join(country, TODAY_DATE, 'Item_urls', f"{country}_product_link_comparison_log.json")
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r') as f:
                    log_data = json.load(f)
                    final_summary = log_data.get("final_summary", {})
                    final_dev = final_summary.get("final_deviation_percent")
                    if final_dev is not None and (final_dev > 5 or final_dev < -5):
                         raise_ticket("Master", "Product ID Deviation", f"High deviation {final_dev}% for {country}", country)


    # --- Step 3: Product Data ---
    if EXECUTION_CONFIG['run_step3_product_data']:
        print("\n--- Step 3: Product Data ---")
        get_product_data(CONFIG, TODAY_DATE)

        # Check deviation (Global Progress) - if step3 generates this
        for country in COUNTRIES:
            progress_file_path = os.path.join(country, TODAY_DATE, 'Validation', 'global_progress.json')
            if os.path.exists(progress_file_path):
                deviation = check_deviation(progress_file_path)
                if deviation > 5:
                    raise_ticket("Step 3", "check_deviation", f"High deviation in product data extraction: {deviation}%", country)


    # --- Step 4: Process JSONs ---
    if EXECUTION_CONFIG['run_step4_process_json']:
        print("\n--- Step 4: Process JSONs ---")
        
        # Import modules for datetime serialization
        import step4_process_and_save_apparel as apparel_module
        import step4_process_and_save_footwear as footwear_module
        
        # Process each country
        for country in COUNTRIES:
            # Get country code from CONFIG
            c_code = CONFIG[country]['prefix'].lstrip('/')  # e.g., '/in/en' -> 'in/en'
            
            print(f"\n--- Processing {country} ---")
            
            # Process Apparel
            print(f"Processing Apparel for {country}...")
            apparel_products = load_apparel(TODAY_DATE, country, c_code)
            if apparel_products:
                out_dir = os.path.join(country, TODAY_DATE, 'Data')
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f'{country}_data_apparel.json')
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(apparel_products, f, indent=4, ensure_ascii=False, default=apparel_module.datetime_serializer)
                print(f"SUCCESS: Saved {len(apparel_products)} apparel products to {out_path}")
            else:
                print(f"No apparel data found for {country}.")
            
            # Process Footwear
            print(f"Processing Footwear for {country}...")
            footwear_products = load_footwear(TODAY_DATE, country, c_code)
            if footwear_products:
                out_dir = os.path.join(country, TODAY_DATE, 'Data')
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f'{country}_data_footwear.json')
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(footwear_products, f, indent=4, ensure_ascii=False, default=footwear_module.datetime_serializer)
                print(f"SUCCESS: Saved {len(footwear_products)} footwear products to {out_path}")
            else:
                print(f"No footwear data found for {country}.")
    
    # --- Step 5: Remove Duplicates ---
    if EXECUTION_CONFIG['run_step5_remove_duplicates']:
        remove_duplicates_from_json(COUNTRIES, TODAY_DATE)

    # --- Step 6: Check Data Format ---
    if EXECUTION_CONFIG['run_step6_check_data_format']:
        print("\n--- Step 9: Check Data Format ---")
        # Now checking JSON files, not DB
        for country in COUNTRIES:
            check_data_format(TODAY_DATE, country)

    # --- Step 7: Upload to Melody ---
    if EXECUTION_CONFIG['run_step7_upload_to_melody']:
        print("\n--- Step 10: Upload to Melody ---")
        # Upload Apparel
        upload_to_data_melody(COUNTRIES, TODAY_DATE, MONGO_CONFIG_APPAREL)
        # Upload Footwear
        upload_to_data_melody(COUNTRIES, TODAY_DATE, MONGO_CONFIG_FOOTWEAR)
    
    print("\nScript completed successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Critical Error: {e}")
        raise_ticket("Main", "main", f"Unhandled exception: {str(e)}")
        exit(1)
    exit(0)
