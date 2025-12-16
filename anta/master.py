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
from step1_category_urls import main as category_urls
from step2_product_data_url import main as product_urls
from step3_urls_json_comparison import compare_urls_json_comparisons
from step4_process_json_apparel_USA import save_country_data_to_json as process_json_apparel_USA
from step4_process_json_footwear_USA import save_country_data_to_json as process_json_footwear_USA
from step4_process_json_footwear_UK import save_country_data_to_json as process_json_footwear_UK
from step5_remove_duplicate_skus import run_duplicate_removal
from step6_check_data_format import check_data_format
from step7_upload_to_melody import upload_to_data_melody
from alert import raise_ticket

# ---------------------- CONFIGURATION ---------------------- #
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
TODAY_DAY = datetime.now().strftime("%A")

COUNTRIES = {'UK':"https://uk.anta.com/",'USA':"https://anta.com/"}
LOCAL_MONGO_URI = "mongodb://localhost:27017"
DB_NAME = ["tg_analytics","footwear_analytics"]

COUNTRY_MAPPING = {
    'UK': 'UK',
    'USA': 'USA'
}

COUNTRY_CODE_MAP = {
    'UK': 'UK',
    'USA': 'USA'
}

CONFIG = {
    "UK": {
        "base_url": "https://uk.anta.com/",
        "domain": "anta.in",
        "use_proxies": False,
        "browsers": 2,
        "data_dir": "UK",
    },
    "USA": {
        "base_url": "https://anta.com/",
        "domain": "anta.com",
        "use_proxies": False,
        "browsers": 2,
        "data_dir": "USA",
    }
}

MONGO_CONFIG = {
    "SERVER_URI": os.getenv("SERVER_MONGO_URI"),
    "THRESHOLD_PERCENT": 10.0,
    "FORCE_UPLOAD": False,
    "DRY_RUN": False,
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

        for sub in ["Category", "Json_data", "Final_json", "Item_urls"]:
            os.makedirs(os.path.join(base, sub), exist_ok=True)


SERVER_MONGO_URI = os.getenv("SERVER_MONGO_URI")

EXECUTION_CONFIG = {
    "run_step1_category_urls": True,
    "run_step2_product_data&urls": True,
    "run_step3_urls_json_comparison": True,
    "run_step4_process_json_apparel_USA": True,
    "run_step4_process_json_footwear_USA": True,
    "run_step4_process_json_footwear_UK": True,
    "run_step5_remove_duplicate_skus": True,
    "run_step6_check_data_format": True,
    "run_step7_upload_to_melody": True,
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
            await category_urls()
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
    if EXECUTION_CONFIG.get("run_step2_product_data&urls"):
        logging.info("\nStep 2: Fetching all product URLs and product data")

        try:
            await product_urls()
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
                'Item_urls',
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


    
    # ---------------------- STEP 3 ---------------------- #
    if EXECUTION_CONFIG.get("run_step3_urls_json_comparison"):
        logging.info("\nStep 3: URLs JSON comparison")
        try:
            compare_urls_json_comparisons()
        except Exception as e:
            logging.error(f"Step 3 error: {e}")
            raise_ticket("Master", "compare_urls_json_comparisons", f"Step 3 error: {e}")

    # ---------------------- STEP 4 ---------------------- #
    if EXECUTION_CONFIG.get("run_step4_process_json"):
        logging.info("\nStep 4: Processing JSON data")
        try:
            logging.info("Processing UK footwear data...")
            process_json_footwear_UK({'UK': 'https://uk.anta.com'}, TODAY_DATE, re_run=False)
            
            logging.info("Processing USA footwear data...")
            process_json_footwear_USA({'USA': 'https://anta.com'}, TODAY_DATE, re_run=False)
            
            logging.info("Processing USA apparel data...")
            process_json_apparel_USA({'USA': 'https://anta.com'}, TODAY_DATE, re_run=False)
        except Exception as e:
            logging.error(f"Step 4 error: {e}")
            raise_ticket("Master", "process_json", f"Step 4 error: {e}")

    # ---------------------- STEP 5 ---------------------- #
    if EXECUTION_CONFIG.get("run_step5_remove_duplicate_skus"):
        logging.info("\nStep 5: Removing duplicate SKUs")
        try:
            run_duplicate_removal(COUNTRIES, TODAY_DATE)
        except Exception as e:
            logging.error(f"Step 5 error: {e}")
            raise_ticket("Master", "run_duplicate_removal", f"Step 5 error: {e}")

    # ---------------------- STEP 6 ---------------------- #
    if EXECUTION_CONFIG.get("run_step6_check_data_format"):
        logging.info("\nStep 6: Checking data format")
        try:
            check_data_format(COUNTRIES, TODAY_DATE)
        except Exception as e:
            logging.error(f"Step 6 error: {e}")
            raise_ticket("Master", "check_data_format", f"Step 6 error: {e}")

    # ---------------------- STEP 7 ---------------------- #
    if EXECUTION_CONFIG.get("run_step7_upload_to_melody"):
        logging.info("\nStep 7: Uploading to MongoDB")
        try:
            from step7_upload_to_melody import main as upload_main
            upload_main()
        except Exception as e:
            logging.error(f"Step 7 error: {e}")
            raise_ticket("Master", "upload_to_melody", f"Step 7 error: {e}")

    logging.info("Scraping completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())