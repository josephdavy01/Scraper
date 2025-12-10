import os
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# ---------------------- IMPORT NECESSARY STEPS ---------------------- #
from validations import (
    compare_with_previous_data,
    check_comparison_results_data,
    remove_duplicate_urls,
    compare_product_urls,
    summarize_product_url_changes,
    check_deviation,
)

from step1_get_category_urls import fetch_categories as save_category_urls
from step2_get_product import run_scraper as get_product_urls
from step3_daily_count import process_country_data
from step4_update_pids_cids import run_cid_mapping
from step5_process_json import run_gant_processing
from step6_remove_duplicate_data import remove_duplicates_from_json
from step7_check_data_format import check_data_format
from step8_upload_to_melody import upload_to_data_melody
from alert import raise_ticket


# ---------------------- CONFIG ---------------------- #
load_dotenv()

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = "2025-11-24"
TODAY = datetime.strptime(TODAY_DATE, "%Y-%m-%d").strftime("%A")


COUNTRY_MAPPING = {
    "UAE": "United Arab Emirates",
}

COUNTRIES = {"UAE": "https://gant.ae/"}

CONFIG = {
    "UAE": {
        "base_url": "https://gant.ae/",
        "domain": "gant.ae",
        "use_proxies": False,
        "browsers": 2,
        "data_dir": "UAE",
    }
}

MONGO_CONFIG_APPAREL = {
    "SERVER_URI": os.getenv("SERVER_MONGO_URI"),
    "DB_NAME": "tg_analytics",
    "COLLECTION_PREFIX": "crawler_sink_gant_",
    "THRESHOLD_PERCENT": 10.0,
    "FORCE_UPLOAD": False,
    "DRY_RUN": False,
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

EXECUTION_CONFIG = {
    "run_step1_category_urls": True,
    "run_step2_product_urls": True,
    "run_step3_daily_count": True,
    "run_step4_remap_pid_cid": True,
    "run_step5_process_json": True,
    "run_step6_remove_duplicate_skus": True,
    "run_step7_check_format": True,
    "run_step8_upload_to_melody": True,
}

# ---------------------- LOGGING ---------------------- #
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def create_country_directories():
    countries_iter = list(COUNTRIES.keys())
    for country in countries_iter:
        base = os.path.join(country, TODAY_DATE)
        os.makedirs(base, exist_ok=True)

        for sub in ["Category", "Json_data", "Final_json", "Item_urls"]:
            os.makedirs(os.path.join(base, sub), exist_ok=True)


# ---------------------- MAIN PIPELINE STEPS 1–7 ---------------------- #
async def main():
    if TODAY not in ["Monday","Wednesday", "Friday"]:
        logging.warning(f"Today is {TODAY}. Script allowed only Mon/Wed/Fri. Exiting.")
        exit(0)
        

    logging.info(f"Starting GANT pipeline for {TODAY_DATE}")

    create_country_directories()

    # ---------------------- STEP 1 ---------------------- #
    if EXECUTION_CONFIG["run_step1_category_urls"]:
        logging.info("STEP 1: Fetching category URLs")
        try:
            await save_category_urls()
            remove_duplicate_urls(COUNTRIES, TODAY_DATE, level="category")

            compare_with_previous_data(COUNTRIES, TODAY_DATE)
            check_comparison_results_data(COUNTRIES, TODAY_DATE)

        except Exception as e:
            raise_ticket("Step 1", "fetch_categories", str(e), "UAE")

    # ---------------------- STEP 2 ---------------------- #
    if EXECUTION_CONFIG["run_step2_product_urls"]:
        logging.info("STEP 2: Fetching product URLs")
        try:
            await get_product_urls()
            remove_duplicate_urls(COUNTRIES, TODAY_DATE, level="product")

            compare_product_urls(COUNTRIES, TODAY_DATE)
            summarize_product_url_changes(COUNTRIES, TODAY_DATE)

        except Exception as e:
            raise_ticket("Step 2", "run_scraper", str(e), "UAE")

    # ---------------------- STEP 3 ---------------------- #
    if EXECUTION_CONFIG["run_step3_daily_count"]:
        logging.info("STEP 3: Processing daily count")
        try:
            process_country_data("UAE", TODAY_DATE)
        except Exception as e:
            raise_ticket("Step 3", "process_country_data", str(e), "UAE")

    # ---------------------- STEP 5 ---------------------- #
    if EXECUTION_CONFIG["run_step4_remap_pid_cid"]:
        logging.info("STEP 5: PID/CID remapping")
        try:
            run_cid_mapping("UAE", TODAY_DATE)
        except Exception as e:
            raise_ticket("Step 4", "run_cid_mapping", str(e), "UAE")

    # ---------------------- STEP 6 ---------------------- #
    if EXECUTION_CONFIG["run_step5_process_json"]:
        logging.info("STEP 5: Processing JSON data")
        try:
            run_gant_processing(today_str=TODAY_DATE, countries=COUNTRIES, re_run=False)
        except Exception as e:
            raise_ticket("Step 5", "run_gant_processing", str(e), "UAE")

    # ---------------------- STEP 7 ---------------------- #
    if EXECUTION_CONFIG["run_step6_remove_duplicate_skus"]:
        logging.info("STEP 6: Removing duplicate SKUs")
        try:
            remove_duplicates_from_json(COUNTRIES, TODAY_DATE)
        except Exception as e:
            raise_ticket("Step 6", "remove_duplicate_skus", str(e), "UAE")

    logging.info("Main pipeline steps 1–7 completed.")


# ---------------------- POST STEPS (Option B) ---------------------- #
async def run_post_steps():
    # ---------------------- STEP 8 ---------------------- #
    if EXECUTION_CONFIG.get("run_step7_check_format"):
        logging.info("STEP 7: Checking data format")
        try:
            for country in COUNTRIES:
                check_data_format(country, TODAY_DATE)
        except Exception as e:
            raise_ticket("Step 7", "check_data_format", str(e), "UAE")

    # ---------------------- STEP 9 ---------------------- #
    if EXECUTION_CONFIG.get("run_step8_upload_to_melody"):
        logging.info("STEP 8: Uploading to Melody")
        try:
            upload_to_data_melody(COUNTRIES.keys(), TODAY_DATE, MONGO_CONFIG_APPAREL)
        except Exception as e:
            logging.error(f"Failed to upload to Melody: {str(e)}")
            raise_ticket("Step 8", "upload_to_melody", str(e), "UAE")

    logging.info("Post pipeline steps completed.")


# ---------------------- RUN SCRIPT ---------------------- #
if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(run_post_steps())
