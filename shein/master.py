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

if day in ['Monday', 'Tuesday', 'Friday']:
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
        'step2_compare_category.py'
        'step3_get_product_urls.py',
        'step3_get_unique_product_urls.py',
        'step4_remove_duplicate_urls.py',
        'step5_create_color_code.py',
        'step6_get_product_details.py', 
        'step7_extract_data.py',
        'step8_validation.py',
        'step9_check_duplicate.py',
        'step10_load_to_db.py',
        'step11_remove_duplicate_skus.py',
        # 'step12_load_to_db_melody.py'
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