import os
import logging
import subprocess
from datetime import datetime, date

# Ensure the 'logs' directory exists
os.makedirs("logs", exist_ok=True)

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week1
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Define scraping days
scraping_days = ['Tuesday', 'Thursday', 'Saturday']

# Create log filename with today's date
log_filename = f"logs/log_{today_str}.txt"

# Set up logging configuration
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
    'step2_get_category_sub_urls.py',
    'step3_get_product_urls.py',
    'step4_daily_count.py',
    'step5_get_product_data.py',
    'step6_urls_json_comparison.py',
    'step7_update_pids.py',
    'step8_load_to_db_footwear.py',
    'step8_load_to_db.py',
    'step9_remove_duplicate_skus.py',
    'step10_check_data_format.py',
    'step11_upload_to_melody.py'
]

if day in scraping_days:
    logging.info(f"Today is {day}. Starting scraping process...")

    for script in programs:
        logging.info(f"Starting {script} at {datetime.now()}...\n")
        
        with subprocess.Popen(
            ["python", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        ) as process, open(log_filename, 'a') as log_file:
            for line in process.stdout:
                print(line, end='')  # Always show everything on terminal
                if '- INFO -' in line or '- WARNING -' in line or '- ERROR -' in line:
                    log_file.write(line)
            process.wait()

        logging.info(f"Finished {script} at {datetime.now()} Return code: {process.returncode}\n")

else:
    logging.info(f"Not a scraping day ({day}). Skipping scripts.")
