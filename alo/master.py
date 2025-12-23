import os
import json
from datetime import datetime
from validations import (compare_with_previous_data, 
                         check_comparison_results_data, remove_duplicate_urls, remove_duplicate_urls_products,
                         compare_product_links, summarize_product_url_changes, check_deviation)
from step1_get_category_urls import get_category_urls
from step2_get_product_urls import get_product_urls
from step3_daily_count import process_country_data
from step4_get_product_data import get_product_data
from step4_get_product_desc import get_product_descriptions
from step5_urls_json_comparison import json_url_comparison
from step5_remap_pid import remap_pids 
from step5_remap_colorid import generate_color_ids_for_all_geographies
from step6_process_json import save_country_data_to_json
from step7_remove_duplicate_data import remove_duplicates_from_json
from step9_upload_to_melody import upload_to_data_melody
from alert import raise_ticket

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = '2025-11-26'


TODAY_DATE_OBJ = datetime.strptime(TODAY_DATE, "%Y-%m-%d")
TODAY = TODAY_DATE_OBJ.strftime("%A")

COUNTRY_MAPPING = {
        'USA': 'United States',
        'UK': 'United Kingdom',
        'Canada': 'Canada'
}

COUNTRIES = {
    'Canada': 'https://www.aloyoga.com/en-ca',
    'USA': 'https://www.aloyoga.com/',
    'UK': 'https://www.aloyoga.com/en-gb'
}

# Configuration
CONFIG = {
    'Canada': {
        'base_url': 'https://www.aloyoga.com/en-ca',
        'lang_code': 'en-ca',
        'browsers': 2,
        'data_dir': 'Canada'
    },
    'USA': {
        'base_url': 'https://www.aloyoga.com/',
        'lang_code': '',
        'browsers': 2,
        'data_dir': 'USA'
    },
    'UK': {
        'base_url': 'https://www.aloyoga.com/en-gb',
        'lang_code': 'en-gb',
        'browsers': 2,
        'data_dir': 'UK'
    }
}

USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]

COUNTRY_CODE_MAP = {
        'USA': 'US',
        'Canada': 'CA',
        'UK': 'GB'
    }

MONGO_CONFIG_APPAREL = {
    'SERVER_URI': 'replace_with_actul_server_string', # IMPORTANT: Fill this in
    'DB_NAME': 'tg_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_alo_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': True, # Set True to delete existing data on the server for the same day and re-upload.
    'DRY_RUN': False        # Set True to simulate the run without writing/deleting any data.
}

EXECUTION_CONFIG = {
    'run_step1_category_urls': True,
    'run_step2_product_urls': True,
    'run_step3_daily_count': True,
    'run_step4_product_data': True,
    'run_step4_product_desc': True,
    'run_step5_comparisons': True,
    'run_step6_process_json': True,
    'run_step6_remap_pid': True,
    'run_step6_remap_colorid': True,
    'run_step7_remove_duplicates': True,
    'run_step9_upload_to_melody': True
}

def create_country_directories():
    for country, url in COUNTRIES.items():
        # Make sure the country directory exists
        country_dir = f"{country}/{TODAY_DATE}"
        os.makedirs(country_dir, exist_ok=True)

def main():
    # Create directories for each country
    create_country_directories()
    if TODAY in ['Monday', 'Wednesday', 'Friday']:
        print(f"Today is {TODAY}. Proceeding with the script...")

        # Fetch category URLs for all countries
        if EXECUTION_CONFIG['run_step1_category_urls']:
            get_category_urls(COUNTRIES, TODAY_DATE, re_run=False, country_mapping=COUNTRY_MAPPING)

            # Remove duplicate URLs for all countries
            remove_cat_dup = remove_duplicate_urls(COUNTRIES, TODAY_DATE)
            if not remove_cat_dup:
                print("Error removing duplicate URLs. Exiting script.")
                raise_ticket("Master", "remove_duplicate_urls", "Failed to remove duplicate category URLs. Script exited.")
                exit()

            # Compare with previous data
            compare_with_previous_data(COUNTRIES, TODAY_DATE)

            '''
                Check if comparison results data exists for all countries 
                check for changes and prompt user if changes are found
            ''' 
            country_wise_status = check_comparison_results_data(COUNTRIES, TODAY_DATE)
            
            if all(country_wise_status.values()):
                print("No changes found in any country.")
            else:
                print("Changes found in the following countries:")
                for country, status in country_wise_status.items():
                    if not status:
                        print(f"{country}: Changes detected.")
                        
                        # Automate handling: Raise ticket and continue
                        comparison_file = os.path.join(country, TODAY_DATE, f"{country}_category_comparison.json")
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

        # Fetch product URLs for all countries
        if EXECUTION_CONFIG['run_step2_product_urls']:
            get_product_urls(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, use_api=True)

            # Remove duplicate product URLs for all countries
            remove_prod_dup = remove_duplicate_urls_products(COUNTRIES, TODAY_DATE)
            if not remove_prod_dup:
                print("Error removing duplicate product URLs. Exiting script.")
                raise_ticket("Master", "remove_duplicate_urls_products", "Failed to remove duplicate product URLs. Script exited.")
                exit()

            # Compare product links with previous data
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
                                elif final_dev < -5:
                                    direction = "Lower (current < previous)"
                                else:
                                    direction = "No change"
                                print(f"Final Summary for {country} on {TODAY_DATE}: {final_summary}")
                                print(f"Deviation: {final_dev}% -> {direction}. Status: {status}")
                            else:
                                print(f"Final Summary for {country} on {TODAY_DATE}: {final_summary}")
                else:
                    print(f"No comparison log found for {country} on {TODAY_DATE}")

        # Process country data for daily count
        if EXECUTION_CONFIG['run_step3_daily_count']:
            for country in COUNTRIES.keys():
                process_country_data(country, TODAY_DATE)

        # Get product data for all countries
        if EXECUTION_CONFIG['run_step4_product_data']:
            get_product_data(CONFIG, TODAY_DATE, USER_AGENTS, COUNTRIES, COUNTRY_CODE_MAP, COUNTRY_MAPPING, re_run=False)

            # Check deviation for each country
            for country in COUNTRIES:
                progress_file_path = os.path.join(country, TODAY_DATE, 'Json_data', f'{country}_global_progress.json')
                deviation = check_deviation(progress_file_path)
                print(f"Deviation for {country} is {deviation:.2f}%")
                if deviation > 5:
                    print(f"Warning: Deviation for {country} is {deviation:.2f}%, which is greater than 5%.")
                    raise_ticket("Step 4", "check_deviation", f"High deviation detected for {country}: {deviation:.2f}%", country)

        # Get Product Desc
        if EXECUTION_CONFIG['run_step4_product_desc']:
            get_product_descriptions(CONFIG, TODAY_DATE, re_run=False)

        # Compare product URLs with JSON data for each country
        if EXECUTION_CONFIG['run_step5_comparisons']:
            json_url_comparison(list(COUNTRIES.keys()), TODAY_DATE)

        # Remap PIDs
        if EXECUTION_CONFIG['run_step6_remap_pid']:
            remap_pids(COUNTRIES, TODAY_DATE)

        # Remap Color IDs
        if EXECUTION_CONFIG['run_step6_remap_colorid']:
            generate_color_ids_for_all_geographies(COUNTRIES, TODAY_DATE)

        # Save to JSON file
        if EXECUTION_CONFIG['run_step6_process_json']:
            save_country_data_to_json(COUNTRIES, TODAY_DATE, re_run=False)

        if EXECUTION_CONFIG['run_step7_remove_duplicates']:
            remove_duplicates_from_json(COUNTRIES, TODAY_DATE)

        if EXECUTION_CONFIG['run_step9_upload_to_melody']:
            upload_to_data_melody(COUNTRIES, TODAY_DATE, MONGO_CONFIG_APPAREL)
        
        print("Script completed successfully.")
    else:
        print(f"Today is {TODAY}. Script only runs on Monday, Wednesday, Friday.")
        exit()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Critical Error: {e}")
        raise_ticket("Main", "main", f"Unhandled exception: {str(e)}")
        exit(1)
    exit(0)
