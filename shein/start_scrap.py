from step1_get_category_urls import *
from step2_compare_category import *
from step3_get_product_urls import *
from step4_remove_duplicate_urls import *
from step5_create_color_code import *
from step6_get_product_details import *
from step7_extract_data import *
from step8_validation import *
from step9_check_duplicate import *
from step10_load_to_db import *
from step11_remove_duplicate_skus import *
from step12_load_to_db_melody import *

time_stamp = datetime.now().strftime("%Y%m%d")

def checkStep1Completed():
    if os.path.exists(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}/sheinindia_category_urls.json"):
        with open(f"{WEBSITE_NAME}/CATEGORY/{time_stamp}/sheinindia_category_urls.json", "r", encoding="utf-8") as file:
            category_data = json.load(file)
    else:
        category_data = {}

    if category_data.get('status') == "success" and category_data.get('date') == time_stamp:
        return True
    else:
        return False


if __name__ == "__main__":
    # Ensure directory exists before saving JSON
    print("Starting the scraping process...")
    start_time = time.time()
    if not checkStep1Completed():
        logging.info("Step 1 not completed. Starting Step 1...")
        step1 = False
        retries = 0
        max_retries = 5
        delay = 5  # delay in seconds

        while not step1 and retries < max_retries:
            step1 = start_step1()
            retries += 1
            if not step1:
                logging.warning(f"Step 1 failed. Retrying ({retries}/{max_retries}) in {delay} seconds...")
                time.sleep(delay)

            else:
                #Need to write something to log or send mail to tech team regarding the failure of step 1
                logging.error("Step 1 failed after maximum retries.")
    else:
        logging.info("Step 1 already completed. Proceeding to Step 2...")
        step1 = True

    if step1:
        logging.info("Step 1 completed. Starting Step 2...")
        step2 = start_step2()
        logging.info("Step 2 completed. Starting Step 3...")
    if step2:
        step3 = start_step3()
        logging.info("Step 3 completed. Starting Step 4...")
    if step3:
        step4 = start_step4()
        logging.info("Step 4 completed. Starting Step 5...")
    if step4:
        step5 = start_step5()
        logging.info("Step 5 completed. Starting Step 6...")
    if step5:
        step6 = run_in_threads()
        logging.info("Step 6 completed. Starting Step 7...")
    if step6:
        step7 = start_step7()
        logging.info("Step 7 completed.")
    # if step7:
    #     step8 = start_step8()
    #     logging.info("Step 8 completed.")
    if step7:
        step9 = start_step9()
        logging.info("Step 9 completed.")
    if step9:
        step10 = start_step10()
        logging.info("Step 10 completed.")
    if step10:
        step11 = start_step11()
        logging.info("Step 11 completed.")
    # if step11:
    #     step12 = start_step12()
    #     logging.info("Step 12 completed.")

    time_taken = time.time() - start_time
    logging.info(f"Multi-threaded processing completed in {time_taken:.2f} seconds.")
