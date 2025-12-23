import os
import json
import logging
from datetime import datetime
from validations import (compare_with_previous_data, 
                         check_comparison_results_data, remove_duplicate_urls, remove_duplicate_urls_products,
                         compare_product_links, summarize_product_url_changes, check_deviation)
from step1_get_category_urls import get_category_urls
from step2_get_product_urls import get_product_urls
from step3_daily_count import process_country_data
from step4_get_product_data import get_product_data
from step5_url_json_comparison import compare_pid_json
from step6_update_pids_cids import update_pids_cids
from step7_process_and_save_apparel import process_jsons as load_apparel
from step7_process_and_save_footwear import process_jsons_footwear as load_footwear
import step7_process_and_save_apparel as apparel_module
import step7_process_and_save_footwear as footwear_module
from step8_remove_duplicate_skus import remove_duplicates_from_json
from step9_check_data_format import check_data_format
from step10_upload_to_melody import upload_to_data_melody

from alert import raise_ticket

# --- Configuration --- 
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = "2025-12-06"
TODAY_DATE_OBJ = datetime.strptime(TODAY_DATE, "%Y-%m-%d")
TODAY = TODAY_DATE_OBJ.strftime("%A")


# Define Countries and Configs
COUNTRIES_TUE_THU_SAT = {
    'India': 'https://www.snitch.com/shop',
}

COUNTRIES_MON_WED_FRI = {
    # Add other countries if needed
}

CONFIG_TUE_THU_SAT = {
    'India': {
        'base_url': 'https://www.snitch.com/shop',
        'browsers': 2,
        'data_dir': 'India',
        'prefix': '/us/en',
        'max_retries': 5,
        'api': True,
        'headless': False 
    }
}

CONFIG_MON_WED_FRI = {}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

COUNTRY_CODE_MAP = {
    'India': 'in',
}

MONGO_CONFIG_APPAREL = {
    'SERVER_URI': 'replace_with_actul_server_string', 
    'LOCAL_URI': 'mongodb://localhost:27017',
    'DB_NAME': 'tg_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_snitch_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': False, 
    'DRY_RUN': False        
}

MONGO_CONFIG_FOOTWEAR = {
    'SERVER_URI': 'replace_with_actul_server_string', # IMPORTANT: Update with real URI
    'LOCAL_URI': 'mongodb://localhost:27017',
    'DB_NAME': 'footwear_analytics', # Assuming separate DB or collection logic
    'COLLECTION_PREFIX': 'crawler_sink_snitch_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': False, 
    'DRY_RUN': False
}

EXECUTION_CONFIG = {
    'run_step1_category_urls': True,
    'run_step2_product_urls': True,
    'run_step3_daily_count': True,
    'run_step4_product_data': True,
    'run_step5_comparisons': True,
    'run_step6_remap_pid_cid': True,
    'run_step7_process_json': True,
    'run_step8_remove_duplicates': True,
    'run_step9_check_data_format': True,
    'run_step10_upload_to_melody': True
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
    elif TODAY in ['Tuesday', 'Thursday', 'Saturday']: # Added Sunday for testing if needed
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
        get_category_urls(CONFIG, TODAY_DATE, re_run=False)

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
        print("\n--- Step 2: Product URLs ---")
        get_product_urls(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, use_api=True)

        # Remove duplicates
        remove_prod_dup = remove_duplicate_urls_products(COUNTRIES, TODAY_DATE)
        if not remove_prod_dup:
            print("Error removing duplicate product URLs.")
            raise_ticket("Master", "remove_duplicate_urls_products", "Failed to remove duplicate product URLs.")

        # Compare product links
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
                         raise_ticket("Master", "Product URL Deviation", f"High deviation {final_dev}% for {country}", country)

    # --- Step 3: Daily Count ---
    if EXECUTION_CONFIG['run_step3_daily_count']:
        print("\n--- Step 3: Daily Count ---")
        for country in COUNTRIES:
            process_country_data(country, TODAY_DATE)

    # --- Step 4: Product Data ---
    if EXECUTION_CONFIG['run_step4_product_data']:
        print("\n--- Step 4: Product Data ---")
        get_product_data(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, re_run=False)

        # Check deviation (Global Progress) - assuming step4 generates this
        for country in COUNTRIES:
            progress_file_path = os.path.join(country, TODAY_DATE, 'Json_data', f'{country}_global_progress.json')
            deviation = check_deviation(progress_file_path)
            if deviation > 5:
                raise_ticket("Step 4", "check_deviation", f"High deviation in product data extraction: {deviation}%", country)

    # --- Step 5: Comparisons ---
    if EXECUTION_CONFIG['run_step5_comparisons']:
        print("\n--- Step 5: Comparisons ---")
        compare_pid_json(list(COUNTRIES.keys()), TODAY_DATE)

    # --- Step 6: Remap PIDs/CIDs ---
    if EXECUTION_CONFIG['run_step6_remap_pid_cid']:
        print("\n--- Step 6: Remap PIDs/CIDs ---")
        update_pids_cids(TODAY_DATE)

    # --- Step 7: Process JSONs ---
    if EXECUTION_CONFIG['run_step7_process_json']:
        print("\n--- Step 7: Process JSONs ---")
        
        # Load remapping dictionaries and set them in imported modules
      
        
        pid_path = 'snitch_pid_remapping.json'
        cid_path = 'snitch_cid_remapping.json'
        
        if os.path.exists(pid_path):
            with open(pid_path, 'r', encoding='utf-8') as f:
                pdict = json.load(f)
        else:
            pdict = {}
        
        if os.path.exists(cid_path):
            with open(cid_path, 'r', encoding='utf-8') as f:
                cdict = json.load(f)
        else:
            cdict = {}
        
        # Set globals in both modules
        apparel_module.pdict = pdict
        apparel_module.cdict = cdict
        footwear_module.pdict = pdict
        footwear_module.cdict = cdict
        
        print("Processing Apparel...")
        apparel_products, apparel_logs = load_apparel(TODAY_DATE, 'India')
        if apparel_products:
            out_dir = os.path.join('India', TODAY_DATE, 'Data')
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, 'India_data_apparel.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(apparel_products, f, indent=4, ensure_ascii=False, default=apparel_module.datetime_serializer)
            print(f"SUCCESS: Saved {len(apparel_products)} apparel products to {out_path}")
            
            # Save log CSV
            if apparel_logs:
                log_dir = os.path.join('India', TODAY_DATE, 'Logs')
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, 'India_sku_details.csv')
                apparel_module.log_sku_details_to_csv(apparel_logs, log_path)
                print(f"Logged {len(apparel_logs)} apparel SKUs to {log_path}")
        else:
            print("No apparel data found.")
        
        print("Processing Footwear...")
        footwear_products, footwear_logs = load_footwear(TODAY_DATE, 'India')
        if footwear_products:
            out_dir = os.path.join('India', TODAY_DATE, 'Data')
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, 'India_data_footwear.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(footwear_products, f, indent=4, ensure_ascii=False, default=footwear_module.datetime_serializer)
            print(f"SUCCESS: Saved {len(footwear_products)} footwear products to {out_path}")
            
            # Save log CSV
            if footwear_logs:
                log_dir = os.path.join('India', TODAY_DATE, 'Logs')
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, 'India_footwear_sku_details.csv')
                footwear_module.log_sku_details_to_csv(footwear_logs, log_path)
                print(f"Logged {len(footwear_logs)} footwear SKUs to {log_path}")
        else:
            print("No footwear data found.")
    
    # --- Step 8: Remove Duplicates ---
    if EXECUTION_CONFIG['run_step8_remove_duplicates']:
        remove_duplicates_from_json(COUNTRIES, TODAY_DATE)

    # --- Step 9: Check Data Format ---
    if EXECUTION_CONFIG['run_step9_check_data_format']:
        print("\n--- Step 9: Check Data Format ---")
        # Now checking JSON files, not DB
        for country in COUNTRIES:
            check_data_format(TODAY_DATE, country)

    # --- Step 10: Upload to Melody ---
    if EXECUTION_CONFIG['run_step10_upload_to_melody']:
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
