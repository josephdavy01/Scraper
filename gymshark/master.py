import asyncio
import logging
import os
import pymongo
from datetime import date, datetime
from dotenv import load_dotenv

# ---- Step Imports ---- #
from validations import (
    compare_with_previous_data,
    check_comparison_results_data,
    remove_duplicate_urls,
    remove_duplicate_urls_products
)
from step1_get_category_urls import get_category_urls_main
from step2_get_product_urls import run_product_urls_scraper
from step3_get_unique_product_urls import get_unique_product_urls_main
from step4_daily_count import daily_count_main
from step5_get_product_data import get_product_data_main
from step6_urls_json_comparison import compare_urls_json_comparisons
from step7_load_to_db import process_jsons 
from step8_remove_duplicate_skus import remove_duplicate_skus
from step9_check_data_format import check_data_format
from step10_upload_to_melody import upload_to_melody

# ---------------------- CONFIGURATION ---------------------- #
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
TODAY = datetime.now().strftime("%A")

COUNTRIES = {'UK': 'https://uk.gymshark.com/'}
LOCAL_MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "tg_analytics"

# ---------------------- LOGGING ---------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# load environment for server mongo (optional)
load_dotenv()
SERVER_MONGO_URI = os.getenv("SERVER_MONGO_URI")  # if not set, upload step will be skipped safely

# ---------------------- MAIN PIPELINE ---------------------- #
async def main():
    TODAY = datetime.now().strftime("%A")

    # Run only specific days
    if TODAY not in ["Monday", "Wednesday", "Friday"]:
        logging.warning(f"Today is {TODAY}. Script allowed only Mon/Wed/Fri.")
        return

    logging.info(f"Starting scraping  {TODAY_DATE}")

    # ---------------------- STEP 1 ---------------------- #
    logging.info("\nStep 1: Fetching category URLs")
    try:
        await get_category_urls_main()
    except Exception as e:
        logging.error(f"Step 1 error: {e}")

    # ---------------------- STEP 2 ---------------------- #
    logging.info(" Removing duplicate category URLs")
    try:
        remove_duplicate_urls(COUNTRIES, TODAY_DATE)
    except Exception as e:
        logging.error(f"error: {e}")

    # ---------------------- STEP 3 ---------------------- #
    logging.info(" Comparing with previous data")
    try:
        compare_with_previous_data(COUNTRIES, TODAY_DATE)
        status = check_comparison_results_data(COUNTRIES, TODAY_DATE)

        for country, ok in status.items():
            if not ok:
                inp = input(f"Changes detected in {country}. Continue? (y/n): ").lower()
                if inp != "y":
                    logging.warning("User stopped pipeline.")
                    return
    except Exception as e:
        logging.error(f" error: {e}")

    # ---------------------- STEP 4 ---------------------- #
    logging.info("\nStep 2: Fetching all product URLs")
    try:
        await run_product_urls_scraper()
    except Exception as e:
        logging.error(f"Step 2 error: {e}")

    # ---------------------- STEP 5 ---------------------- #
    logging.info(" Removing duplicate product URLs")
    try:
        remove_duplicate_urls_products(COUNTRIES, TODAY_DATE)
    except Exception as e:
        logging.error(f" error: {e}")

    # ---------------------- STEP 6 ---------------------- #
    logging.info("\nStep 3: Getting unique product URLs")
    try:
        get_unique_product_urls_main()
    except Exception as e:
        logging.error(f"Step 3 error: {e}")

    # ---------------------- STEP 7 ---------------------- #
    logging.info("\nStep 4: Daily count")
    try:
        daily_count_main()
    except Exception as e:
        logging.error(f"Step 4 error: {e}")

    # ---------------------- STEP 8 ---------------------- #
    logging.info("\nStep 5: Fetching detailed product data")
    try:
        await get_product_data_main()
    except Exception as e:
        logging.error(f"Step 5 error: {e}")

    # ---------------------- STEP 9 ---------------------- #
    logging.info("\nStep 6: Validate JSON comparisons")
    try:
        compare_urls_json_comparisons()
    except Exception as e:
        logging.error(f"Step 6 error: {e}")

    # ---------------------- STEP 7 ---------------------- #
    logging.info("\nStep 7: Loading to DB")
    try:
        today_str = TODAY_DATE
        local_client = pymongo.MongoClient(LOCAL_MONGO_URI)
        local_db = local_client[DB_NAME]

        for country in COUNTRIES:
            geography = country.lower()
            collection = local_db[f"crawler_sink_gymshark_{geography}"]
            process_jsons(today_str, country, collection)

        local_client.close()

    except Exception as e:
        logging.error(f"Step 7 error: {e}")

    # ---------------------- STEP 12 ---------------------- #
    logging.info("\nStep 8: Removing duplicate SKUs")
    try:
        connection_string = LOCAL_MONGO_URI
        database_name = DB_NAME
        date = TODAY_DATE

        for country in COUNTRIES:
            geography = country.lower()
            collection_name = f"crawler_sink_gymshark_{geography}"
            remove_duplicate_skus(connection_string,database_name,collection_name,geography,date)

    except Exception as e:
        logging.error(f"Step 8 error: {e}")

    # ---------------------- STEP 13 ---------------------- #
    logging.info("\nStep 9: Checking data format")
    try:
        for country in COUNTRIES:
            geography = country.lower()
            collections = [
                f"crawler_sink_gymshark_{geography}",
            ]
            for collection_name in collections:
                check_data_format(LOCAL_MONGO_URI, DB_NAME, collection_name, geography, TODAY_DATE)
    except Exception as e:
        logging.error(f"Step 9 error: {e}")

    # ---------------------- STEP 14 ---------------------- #
    logging.info("\nStep 10: Uploading to Melody")
    try:
        if not SERVER_MONGO_URI:
            logging.warning("SERVER_MONGO_URI not set. Skipping upload to Melody.")
        else:
            # create clients / db objects
            server_client = pymongo.MongoClient(SERVER_MONGO_URI)
            server_db = server_client[DB_NAME]

            local_client = pymongo.MongoClient(LOCAL_MONGO_URI)
            local_db = local_client[DB_NAME]

            for country in COUNTRIES:
                geography = country.lower()

                source_collection = local_db[f"crawler_sink_gymshark_{geography}"]
                target_collection = server_db[f"crawler_sink_gymshark_{geography}"]

                # upload_to_melody expects collection objects
                upload_to_melody(source_collection, target_collection, TODAY_DATE)

            # close clients
            server_client.close()
            local_client.close()

    except Exception as e:
        logging.error(f"Step 10 error: {e}")

    logging.info("Scraping completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
