import os
import logging
import subprocess
from datetime import datetime, date

# Ensure the 'logs' directory exists
os.makedirs("logs", exist_ok=True)

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

if day in ['Monday', 'Wednesday', 'Friday']:
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
        'step2_get_product_urls.py',
        'step3_get_unique_product_urls.py',
        'step4_daily_count.py',
        'step5_url_validation.py',
        'step6_get_product_data.py',
        'step7_urls_json_comparison.py',
        'step8_data_validation.py',
        'step9_load_to_db_footwear.py',
        'step9_load_to_db.py',
        'step10_remove_duplicate_skus.py',
        'step11_check_data_format.py',
        'step12_upload_to_melody.py'
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