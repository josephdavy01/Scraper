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

# Set up logging configuration for main script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, mode='a'),
        logging.StreamHandler()
    ]
)

logging.info(f"Today is {day}")

# Only run scripts on specific days
if day in ['Monday','Tuesday', 'Wednesday', 'Friday']:
    logging.info("Starting scraping workflow...")

    programs = [
        'step1_get_category_urls.py',
        'step2_get_product_urls.py',
        'step3_get_unique_product_urls.py',
        'step4_daily_count.py',
        'step5_get_product_data.py',
        'step6_urls_json_comparison.py',
        'step7_update_pids_cids.py',
        'step8_load_to_db_footwear.py',
        'step9_remove_duplicate.py',
        'step10_check_data_format.py',
        # 'step11_upload_to_melody.py'
    ]

    for idx, script in enumerate(programs):
        logging.info(f"Starting {script} at {datetime.now()}...\n")

        # Run the script and capture live output
        with subprocess.Popen(
            ["python", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        ) as process, open(log_filename, 'a', encoding='utf-8') as log_file:
            
            for line in process.stdout:
                print(line, end='')
                # Optional: Write only structured log lines
                if any(tag in line for tag in ['- INFO -', '- WARNING -', '- ERROR -']):
                    log_file.write(line)

            process.wait()

        logging.info(f"Finished {script} at {datetime.now()} Return code: {process.returncode}\n")

        # Stop execution if the first critical script fails
        if idx == 0 and process.returncode != 0:
            logging.error(f"Halting further execution due to failure in {script}")
            break

    logging.info("All scripts completed successfully.")

else:
    logging.info(f"Not a scraping day ({day}). Skipping execution.")
