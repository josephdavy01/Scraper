import os
import json
import asyncio
import logging
import pymongo
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, datetime

load_dotenv()

# ---- Step Imports ---- #
from validations import (
    compare_with_previous_data,
    check_comparison_results_data,
    remove_duplicate_urls,
    compare_product_urls,
)
from step1_get_category_urls import fetch_category_urls
from step2_get_product_urls import fetch_product_urls_from_categories
from step3_get_daily_count import process_country_data as process_daily_count
from step4_get_unique_product_urls import process_country_data as get_unique_urls
from step5_get_product_data import run_xyxxcrew_scraper
from step6_update_cid_pid import run_pid_cid_mapping_tts
from step7_urls_json_comparison import compare_url_json_counts
from step8_process_json import save_country_data_to_json
from step9_remove_duplicate_skus import run_duplicate_removal
from step10_check_data_format import check_data_format
from step11_upload_to_melody import upload_to_data_melody
from alert import raise_ticket

# ---------------------- CONFIGURATION ---------------------- #
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
TODAY_DAY = datetime.now().strftime("%A")

COUNTRIES = {'india':"https://xyxxcrew.com/"}
LOCAL_MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "tg_analytics"

COUNTRY_MAPPING = {
    'india': 'India'
}

COUNTRY_CODE_MAP = {
    'india': 'india'
}

CONFIG = {
    "india": {
        "base_url": "https://xyxxcrew.com/",
        "domain": "xyxxcrew.com",
        "use_proxies": False,
        "browsers": 2,
        "data_dir": "India",
    }
}

MONGO_CONFIG_APPAREL = {
    "SERVER_URI": os.getenv("SERVER_MONGO_URI"),
    "DB_NAME": "tg_analytics",
    "COLLECTION_PREFIX": "crawler_sink_xyxx",
    "THRESHOLD_PERCENT": 10.0,
    "FORCE_UPLOAD": False,
    "DRY_RUN": True,
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
]

# ---------------------- LOGGING ---------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def create_country_directories():
    countries_iter = list(COUNTRIES.keys())
    for country in countries_iter:
        base = os.path.join(country, TODAY_DATE)
        os.makedirs(base, exist_ok=True)

        for sub in ["Category", "Json_data", "Final_json", "Items_urls"]:
            os.makedirs(os.path.join(base, sub), exist_ok=True)


SERVER_MONGO_URI = os.getenv("SERVER_MONGO_URI")

EXECUTION_CONFIG = {
    "run_step1_category_urls": True,
    "run_step2_product_urls": True,
    "run_step3_get_daily_count": True,
    "run_step4_get_unique_product_urls": True,
    "run_step5_product_data": True,
    "run_step6_update_cid_pid": True,
    "run_step7_urls_json_comparison": True,
    "run_step8_process_json": True,
    "run_step9_remove_duplicate_skus": True,
    "run_step10_check_format": True,
    "run_step11_upload_to_melody": True,
}

# ---------------------- MAIN PIPELINE ---------------------- #
async def main():
    # if TODAY_DAY not in ["Tuesday", "Thursday", "Saturday"]:
    #     logging.warning(f"Today is {TODAY_DAY}. Script runs only Tue/Thu/Sat.")
    #     return

    # logging.info(f"Starting scraping {TODAY_DATE}")


    # ---------------------- STEP 1 ---------------------- #
    if EXECUTION_CONFIG.get("run_step1_category_urls"):
        create_country_directories()
        step1_success = False  # Initialize before try block
        
        logging.info("Step 1: Fetching category URLs")
        try:
            await fetch_category_urls()
            step1_success = True
        except Exception as e:
            logging.error(f"Step 1 Critical Error (Scraping): {e}")
            raise_ticket("Master", "run_category_scraper", f"Step 1 Scraping Failed: {e}")
            step1_success = False
        
        # --- 1B. Remove Duplicates (Only if scraping succeeded) ---
        if step1_success:
            logging.info("Removing duplicate category URLs")
            try:
                remove_cat_dup = remove_duplicate_urls(COUNTRIES, TODAY_DATE)
                
                if not remove_cat_dup:
                    logging.error("Error removing duplicate URLs. Halting Step 1 analysis.")
                    raise_ticket("Master", "remove_duplicate_urls", "Failed to remove duplicate category URLs.")
                    step1_success = False 
            except Exception as e:
                logging.error(f"Error in duplicate removal: {e}")
                raise_ticket("Master", "remove_duplicate_urls", f"Exception: {e}")
                step1_success = False

        # --- 1C. Compare Data (Only if deduplication worked) ---
        if step1_success:
            logging.info("Comparing with previous data")
            try:
                compare_with_previous_data(COUNTRIES, TODAY_DATE)
                status = check_comparison_results_data(COUNTRIES, TODAY_DATE)

                for country, ok in status.items():
                    if not ok:
                        # Construct path safely
                        comparison_file = os.path.join(country, TODAY_DATE, f"{country}_category_comparison.json")
                        details = f"Changes detected in category URLs for {country}."

                        if os.path.exists(comparison_file):
                            try:
                                with open(comparison_file, 'r', encoding='utf-8') as f:
                                    comparison_data = json.load(f)
                                    data_str = json.dumps(comparison_data, indent=2)
                                    details = f"Changes detected in {country}: {data_str}"
                            except json.JSONDecodeError:
                                details += " (File found but contains invalid JSON)"
                            except Exception as e:
                                details += f" (Error reading comparison file: {e})"
                        else:
                            details += " (Comparison file not found on disk)"

                        logging.warning(f"Raising ticket for {country} category changes...")
                        raise_ticket("Master", "check_comparison_results_data", details, country)

            except Exception as e:
                logging.error(f"Error during data comparison: {e}")
                raise_ticket("Master", "compare_with_previous_data", f"Error: {e}")
    
    else:
        # Log if skipped so you aren't left guessing
        logging.info("Step 1 skipped (Configuration 'run_step1_category_urls' is False or missing).")
    
    # ---------------------- STEP 2 ---------------------- #
    if EXECUTION_CONFIG.get("run_step2_product_urls"):
        logging.info("\nStep 2: Fetching all product URLs")

        try:
            await fetch_product_urls_from_categories()


        except Exception as e:
            logging.error(f"Step 2 error: {e}")
            raise_ticket("Master", "run_product_url_scraper", f"Step 2 error: {e}")

        # ---------------- COMPARISON ---------------- #
        logging.info("Comparing product URLs")
        try:
            compare_product_urls(COUNTRIES, TODAY_DATE)
        except Exception as e:
            logging.error(f"Error during product URL comparison: {e}")
            raise_ticket("Master", "compare_product_urls", f"Error: {e}")

        # ---------------- FINAL SUMMARY ---------------- #
        for country in COUNTRIES:
            log_file_path = os.path.join(
                country,
                TODAY_DATE,
                'Items_urls',
                f"{country}_product_urls_comparison.json"
            )

            if os.path.exists(log_file_path):
                with open(log_file_path, 'r') as f:
                    log_data = json.load(f)

                final_summary = log_data.get("final_summary", {})

                if final_summary:
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



    # ---------------------- STEP 3 ---------------------- #
    if EXECUTION_CONFIG.get("run_step3_daily_count"):
        logging.info("\nStep 3: Daily count")
        try:
            for country in COUNTRIES:
                process_daily_count(country, TODAY_DATE, EXECUTION_CONFIG)
        except Exception as e:
            logging.error(f"Step 3 error: {e}")
            raise_ticket("Master", "process_country_data", f"Step 3 error: {e}")
    # ---------------------- STEP 4 ---------------------- #
    if EXECUTION_CONFIG.get("run_step4_get_unique_product_urls"):
        logging.info("\nStep 4: Getting unique product URLs")
        try:
            for country in COUNTRIES:
                get_unique_urls(country, TODAY_DATE)
        except Exception as e:
            logging.error(f"Step 4 error: {e}")
            raise_ticket("Master", "get_unique_urls", f"Step 4 error: {e}")

    # ---------------------- STEP 5 ---------------------- #
    if EXECUTION_CONFIG.get("run_step5_product_data"):
        logging.info("\nStep 5: Fetching detailed product data")
        try:
            await run_xyxxcrew_scraper(country='India', headless=False)

            # Check deviation
            for country in COUNTRIES:
                progress_file_path = os.path.join(country, TODAY_DATE, 'Json_data', f'{country}_global_progress.json')
        except Exception as e:
            logging.error(f"Step 5 error: {e}")
            raise_ticket("Master", "get_product_data_main", f"Step 5 error: {e}")

    # ---------------------- STEP 6 ---------------------- #
    if EXECUTION_CONFIG.get("run_step6_update_cid_pid", True):
        logging.info("\nStep 6: updates cid and pid")
        try:
            run_pid_cid_mapping_tts()
        except Exception as e:
            logging.error(f"Step 6 error: {e}")
            raise_ticket("Master", "update_cid_pid", f"Step 6 error: {e}")

    # ---------------------- STEP 7 ---------------------- #
    if EXECUTION_CONFIG.get("run_step7_urls_json_comparison"):
        logging.info("STEP 7: Processing JSON data")
        try:
            save_country_data_to_json(today_str=TODAY_DATE, countries=COUNTRIES, re_run=False)
        except Exception as e:
            raise_ticket("Step 7", "save_country_data_to_json", str(e), "USA")

    # ---------------------- STEP 8 ---------------------- #
    if EXECUTION_CONFIG.get("run_step8_process_json"):
        logging.info("\nStep 8: process_json_data  ")
        try:
            save_country_data_to_json(COUNTRIES, TODAY_DATE, re_run=False)
        except Exception as e:
            logging.error(f"Step 8 error: {e}")
            raise_ticket("Master", "process_json_data", f"Step 8 error: {e}")

    # ---------------------- STEP 9 ---------------------- #
    if EXECUTION_CONFIG.get("run_step9_remove_duplicate_skus"):
        logging.info("\nStep 9: remove_duplicates  ")
        try:
            run_duplicate_removal(COUNTRIES, TODAY_DATE)
        except Exception as e:  
            logging.error(f"Step 9 error: {e}")
            raise_ticket("Master", "remove_duplicates", f"Step 9 error: {e}")

    # ---------------------- STEP 10 ---------------------- #
    if EXECUTION_CONFIG.get("run_step10_check_format"):
        logging.info("\nStep 10: check_data_format  ")
        try:
            check_data_format(COUNTRIES, TODAY_DATE)
        except Exception as e:
            logging.error(f"Step 10 error: {e}")
            raise_ticket("Master", "check_data_format", f"Step 10 error: {e}")

    # ---------------------- STEP 11 ---------------------- #
    if EXECUTION_CONFIG.get("run_step11_upload_to_melody"):
        logging.info("\nStep 11: upload_to_melody  ")
        try:
            upload_to_data_melody(COUNTRIES, TODAY_DATE, MONGO_CONFIG_APPAREL)
        except Exception as e:
            logging.error(f"Step 11 error: {e}")
            raise_ticket("Master", "upload_to_data_melody", f"Step 11 error: {e}")

    logging.info("Scraping completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
