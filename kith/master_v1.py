import os
import logging
from datetime import datetime
from alert import raise_ticket
import json

# Import step functions
from steps.step1_get_category_urls import get_category_urls
from steps.step2_get_product_urls import get_product_urls
from steps.step3_get_product_data import get_product_data
from steps.step4_remap_ids import remap_ids
from steps.step5_process_and_save_footwear import process_footwear
from steps.step6_remove_duplicate_data import remove_duplicates_from_json
from steps.step5_process_and_save_apparel import process_apparel
from steps.step8_upload_to_melody import upload_to_data_melody
from validations import (remove_duplicate_urls, check_deviation,
                         compare_with_previous_data, check_comparison_results_data,
                         compare_product_links, summarize_product_url_changes)

# --- Configuration ---
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = '2025-12-08' 

COUNTRIES = ['USA', 'UK']

# Kith Specific Navigation Structure
# Moved here so Step 1 is purely logic, not config.
NAV_CONFIG = {
    "category_tabs": {
        "MENS": "desktop-drawer-parent-tab-mens-2024-main-mens",
        "WOMENS": "desktop-drawer-parent-tab-womens-2024-main-womens",
        "KIDS": "desktop-drawer-parent-tab-kids-2024-main-kids"
    },
    "sub_categories": {
        "MENS": {
            "Footwear": "desktop-drawer-child-tab-mens-2024-main-mens-kith-footwear",
            "Tailoring": "desktop-drawer-child-tab-mens-2024-main-mens-kith-tailoring",
            "Outerwear": "desktop-drawer-child-tab-mens-2024-main-mens-kith-outerwear",
            "Knitwear": "desktop-drawer-child-tab-mens-2024-main-mens-kith-knitwear",
            "Tops": "desktop-drawer-child-tab-mens-2024-main-mens-kith-tops",
            "Bottoms": "desktop-drawer-child-tab-mens-2024-main-mens-kith-bottoms"
        },
        "WOMENS": {
            "Footwear": "desktop-drawer-child-tab-womens-2024-main-womens-kith-women-footwear",
            "Outerwear": "desktop-drawer-child-tab-womens-2024-main-womens-kith-women-outerwear",
            "Tops": "desktop-drawer-child-tab-womens-2024-main-womens-kith-women-tops",
            "Bottoms": "desktop-drawer-child-tab-womens-2024-main-womens-kith-women-bottoms",
            "Knitwear": "desktop-drawer-child-tab-womens-2024-main-womens-kith-women-knitwear"
        },
        "KIDS": {
            "Tops": "desktop-drawer-child-tab-kids-2024-main-kids-kith-kids-tops",
            "Bottoms": "desktop-drawer-child-tab-kids-2024-main-kids-kith-kids-bottoms",
            "Footwear": "desktop-drawer-child-tab-kids-2024-main-kids-kith-kids-footwear"
        }
    }
}

CONFIG = {
    'USA': {
        'base_url': 'https://kith.com/',
        'domain': 'kith.com',
        'currency': 'USD',
        'welcome_mat_selector': "div[js-button-container] > button:has-text('Shop kith.com')",
        'popup_selectors': [],
        'nav_config': NAV_CONFIG, # Pass the nav structure
        'use_proxies': False,
        'use_proxies_product':False,
        'proxies': {
            "server": "p.webshare.io:80",
            "username": "ioeohvre-rotate",
            "password": "vc0yuzmm8sze"
        },
        'browsers': 3
    },
    'UK': {
        'base_url': 'https://eu.kith.com/',
        'domain': 'eu.kith.com',
        'currency': 'GBP',
        'welcome_mat_selector': "div[js-unsupported-buttons] > button:has-text('Stay on EU.KITH.COM')",
        'popup_selectors': ["button[aria-label='Close dialog']"],
        'nav_config': NAV_CONFIG,
        'use_proxies': False,
        'use_proxies_product':False,
        'proxies': {
            "server": "p.webshare.io:80",
            "username": "ioeohvre-rotate",
            "password": "vc0yuzmm8sze"
        },
        'browsers': 3
    }
}

MONGO_CONFIG_APPAREL = {
    'SERVER_URI': 'replace_with_actul_server_string',
    'DB_NAME': 'tg_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_kith_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': True, # Set True to delete existing data on the server for the same day and re-upload.
    'DRY_RUN': False        # Set True to simulate the run without writing/deleting any data.
}

MONGO_CONFIG_FOOTWEAR = {
    'SERVER_URI': 'replace_with_actul_server_string',
    'DB_NAME': 'footwear_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_kith_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': True, # Set True to delete existing data on the server for the same day and re-upload.
    'DRY_RUN': False        # Set True to simulate the run without writing/deleting any data.
}

EXECUTION_CONFIG = {
    #Category
    'step1_categories': True,
    'step1_rerun': False,
    #Product URLs 
    'step2_product_urls': True,
    'step2_rerun': False,
    #Scrape Data
    'step3_scrape_data': True,
    #Remap IDs
    'step4_remap_ids': True,
    #Process Footwear
    'step5_process_footwear': True,
    'step5_footwear_rerun': False,
    #Process Apparel
    'step5_process_apparel': True,
    'step5_apparel_rerun': False,
    #Remove Duplicates
    'step6_remove_duplicates': True,
    #Upload
    'step7_upload_apparel': True,
    'step7_upload_footwear': True
}

def main():

    logging.info(f"Starting Kith for {TODAY_DATE}")

    # 1. Categories
    if EXECUTION_CONFIG['step1_categories']:
        try:
            get_category_urls(CONFIG, TODAY_DATE, re_run=EXECUTION_CONFIG.get('step1_rerun', False))
            remove_duplicate_urls(COUNTRIES, TODAY_DATE, level='category')
            compare_with_previous_data(COUNTRIES, TODAY_DATE)
            country_wise_status = check_comparison_results_data(COUNTRIES, TODAY_DATE)
            
            if all(country_wise_status.values()):
                print("No changes found in any country.")
            else:
                print("Changes found in the following countries:")
                for country, status in country_wise_status.items():
                    if not status:
                        print(f"{country}: Changes detected.")
                        
                        # Automate handling: Raise ticket and continue
                        comparison_file = os.path.join(country, TODAY_DATE, "Category", f"{country}_category_comparison.json")
                        details = f"Changes detected in category URLs for {country}."
                        
                        if os.path.exists(comparison_file):
                            try:
                                with open(comparison_file, 'r', encoding='utf-8') as f:
                                    comparison_data = json.load(f)
                                    # Convert to string for ticket details, maybe truncate if too long
                                    details = f"Changes detected in {country}: {json.dumps(comparison_data, indent=2)}"
                            except Exception as e:
                                details += f" (Error reading comparison file: {e})"
                        
                        print(f"Raising ticket for {country} category changes and continuing...")
                        raise_ticket("Master", "check_comparison_results_data", details, country)
                        print(f"Continuing...")
        except Exception as e:
            logging.error(f"Step 1 Failed: {e}")
            raise_ticket("Step 1", "get_category_urls", str(e))

    # 2. Product URLs
    if EXECUTION_CONFIG['step2_product_urls']:
        try:
            get_product_urls(CONFIG, TODAY_DATE, re_run=EXECUTION_CONFIG.get('step2_rerun', False))
            if remove_duplicate_urls(COUNTRIES, TODAY_DATE, level='product'):
                print("Duplicate product URLs found and removed.")
            else:
                print("No duplicate product URLs found.")
            compare_product_links(COUNTRIES, TODAY_DATE)
            summarize_product_url_changes(COUNTRIES, TODAY_DATE)

            # Print the final summary for each country
            for country in COUNTRIES:
                log_file_path = os.path.join(country, TODAY_DATE, 'Item_urls', f"{country}_product_link_comparison_log.json")
                if os.path.exists(log_file_path):
                    with open(log_file_path, 'r') as f:
                        log_data = json.load(f)
                        final_summary = log_data.get("final_summary", {})
                        if final_summary:
                            # final_deviation_percent is produced by compare_product_links
                            final_dev = final_summary.get("final_deviation_percent")
                            status = final_summary.get("status", "")
                            if final_dev is not None:
                                if final_dev > 5:
                                    direction = "Greater (current > previous)"
                                    raise_ticket("Step 2", "compare_product_links", f"Significant change in product URLs for {country} on {TODAY_DATE}: Deviation {final_dev}%", country)
                                elif final_dev < -5:
                                    direction = "Lower (current < previous)"
                                    raise_ticket("Step 2", "compare_product_links", f"Significant change in product URLs for {country} on {TODAY_DATE}: Deviation {final_dev}%", country)
                                else:
                                    direction = "No change"
                                print(f"Final Summary for {country} on {TODAY_DATE}: {final_summary}")
                                print(f"Deviation: {final_dev}% -> {direction}. Status: {status}")
                            else:
                                print(f"Final Summary for {country} on {TODAY_DATE}: {final_summary}")
                else:
                    print(f"No comparison log found for {country} on {TODAY_DATE}")
        except Exception as e:
            logging.error(f"Step 2 Failed: {e}")
            raise_ticket("Step 2", "get_product_urls", str(e))

    # 3. Scrape Data
    if EXECUTION_CONFIG['step3_scrape_data']:
        try:
            country_statuses = get_product_data(CONFIG, TODAY_DATE)
            #Set Country Statuses Manually for Testing
            country_statuses = {country: 'success' for country in COUNTRIES}
            
            for country, status in country_statuses.items():
                if status == 'success':
                    log_file_path = os.path.join(country, TODAY_DATE, 'Json_data', f'{country}_scrape_log.json')
                    total_urls_file_path = os.path.join(country, TODAY_DATE, 'Item_urls', f'{country}_product_links.json')
                    deviation = check_deviation(log_file_path, total_urls_file_path)
                    
                    if deviation < 0:
                        print(f"Could not calculate deviation for {country} due to missing files.")
                    else:
                        print(f"Deviation (failure rate) for {country} is {deviation:.2f}%")
                        if deviation > 5:
                            print(f"Warning: Deviation for {country} is {deviation:.2f}%, which is greater than 5%.")
                            raise_ticket("Step 3", "check_deviation", f"High deviation detected for {country}: {deviation:.2f}%", country)
                else:
                    error_message = f"Product data scraping failed for {country} due to country setup issues."
                    logging.error(f"Step 3 Failed for {country}: {error_message}")
                    raise_ticket("Step 3", "get_product_data", error_message, country)

        except Exception as e:
            logging.error(f"An unexpected error occurred in Step 3: {e}")
            raise_ticket("Step 3", "get_product_data", str(e))

    # 4. Remap PIDs & CIDs
    if EXECUTION_CONFIG['step4_remap_ids']:
        try:
            remap_ids(COUNTRIES, TODAY_DATE)
        except Exception as e:
            logging.error(f"Step 4 Failed: {e}")
            raise_ticket("Step 4", "remap_ids", str(e))

    # 5. Process Footwear Data
    if EXECUTION_CONFIG['step5_process_footwear']:
        try:
            process_footwear(COUNTRIES, TODAY_DATE, re_run=EXECUTION_CONFIG.get('step5_footwear_rerun', False))
        except Exception as e:
            logging.error(f"Step 5 Footwear Failed: {e}")
            raise_ticket("Step 5", "process_footwear", str(e))

    # 5. Process Apparel Data
    if EXECUTION_CONFIG['step5_process_apparel']:
        try:
            process_apparel(COUNTRIES, TODAY_DATE, re_run=EXECUTION_CONFIG.get('step5_apparel_rerun', False))
        except Exception as e:
            logging.error(f"Step 5 Apparel Failed: {e}")
            raise_ticket("Step 5", "process_apparel", str(e))

    # 6. Remove Duplicates
    if EXECUTION_CONFIG['step6_remove_duplicates']:
        try:
            remove_duplicates_from_json(COUNTRIES, TODAY_DATE)
        except Exception as e:
            logging.error(f"Step 6 Failed: {e}")
            raise_ticket("Step 6", "remove_duplicates", str(e))

    #  7. Upload
    if EXECUTION_CONFIG['step7_upload_apparel']:
        try:
            upload_to_data_melody(COUNTRIES, TODAY_DATE, MONGO_CONFIG_APPAREL)
        except Exception as e:
            logging.error(f"Step 7 Apparel Failed: {e}")
            raise_ticket("Step 7", "upload apparel", str(e))

    if EXECUTION_CONFIG['step7_upload_footwear']:
        try:
            upload_to_data_melody(COUNTRIES, TODAY_DATE, MONGO_CONFIG_FOOTWEAR)
        except Exception as e:
            logging.error(f"Step 7 Footwear Failed: {e}")
            raise_ticket("Step 7", "upload footwear", str(e))

if __name__ == "__main__":
    main()