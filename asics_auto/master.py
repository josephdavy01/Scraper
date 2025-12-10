import os
import logging
import subprocess
from datetime import datetime, date

# Ensure the 'logs' directory exists
os.makedirs("logs", exist_ok=True)

# Get today's date as a string
today_str = date.today().strftime('%Y-%m-%d')
# today_str = '2025-11-13'

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

programs = [
    'step1_get_category_urls.py',
    'step2_get_category_codes.py',
    'step3_get_product_urls.py',
    'step4_get_unique_product_urls.py',
    'step5_daily_count.py',
    'step6_url_validation.py',
    'step7_get_product_data.py',
    'step8_pids_json_comparison.py',
    'step9_data_validation.py',
    'step10_load_to_db_footwear.py',
    'step10_load_to_db.py',
    'step11_remove_duplicate_skus_footwear.py',
    'step11_remove_duplicate_skus.py',
    'step12_check_data_format.py',
    'step13_upload_to_melody_footwear.py',
    'step13_upload_to_melody.py'
 ]

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
                log_file.write(line)  # Only write relevant lines to file
        process.wait()

    logging.info(f"Finished {script} at {datetime.now()} Return code: {process.returncode}\n")