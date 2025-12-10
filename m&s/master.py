import os
import logging
import subprocess
from datetime import datetime, date

# Ensure the 'logs' directory exists
os.makedirs("logs", exist_ok=True)

# Get today's date as a string
today_str = date.today().strftime('%Y-%m-%d')
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')
# Create log filename with today's date
log_filename = f"logs/log_{today_str}.txt"

if day in ["Monday","Wednesday","Friday"]:

    # Set up logging configuration for main script
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, mode='a'),
            logging.StreamHandler()
        ]
    )

    programs = [
        'step1_get_category_urls.py',
        'step2_find_brand_name.py',
        'step3_get_product_urls.py',
        'step4_get_unique_product_urls.py',
        'step5_daily_count.py',
        'step6_url_validation.py',
        'step7_get_product_data.py',
        'step8_pids_json_comparison.py',
        'step9_data_validation.py',
        # 'step10_load_to_db_footwear_india.py',
        # 'step10_load_to_db_footwear_uk.py',
        # 'step10_load_to_db_footwear_usa.py',
        # 'step10_load_to_db_india.py',
        # 'step10_load_to_db_uk.py',
        # 'step10_load_to_db_usa.py',
        # 'step11_check_data_format.py',
        # 'step11_remove_duplicate_skus.py'
    ]

    for idx, script in enumerate(programs):
        logging.info(f"Starting {script} at {datetime.now()}...\n")

        with subprocess.Popen(
            ["python", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        ) as process, open(log_filename, 'a') as log_file:
            for line in process.stdout:
                print(line, end='')  # print to terminal
                if '- INFO -' in line or '- WARNING -' in line or '- ERROR -' in line:
                    log_file.write(line)  # write selected logs to file
            process.wait()

        logging.info(f"Finished {script} at {datetime.now()} Return code: {process.returncode}\n")

        # Stop execution if script failed
        if idx == 0 and process.returncode != 0:
            logging.error(f"Halting further execution due to failure in {script}")
            break
else:
    print(f"Today is not scraping day {day} enjoy!!!")