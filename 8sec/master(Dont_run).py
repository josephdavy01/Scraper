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

if day in ["Monday", "Thursday", "Friday"]:

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, mode='a'),
            logging.StreamHandler()
        ]
    )

    programs = [
        'step1_get_product_urls.py',
        'step2_product_data.py',
        'step3_color_id.py',
        # 'step4_Load_to_db.py'
        # 'step5_remove_duplicate_skus.py',
        # 'step6_upload_to_melody.py'
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
            if process.stdout is not None:
                for line in process.stdout:
                    print(line, end='')  # Always show everything on terminal
                    if '- INFO -' in line or '- WARNING -' in line or '- ERROR -' in line:
                        log_file.write(line)  # Only write relevant lines to file
            process.wait()

        logging.info(f"Finished {script} at {datetime.now()} Return code: {process.returncode}\n")

else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, mode='a'),
            logging.StreamHandler()
        ]
    )
    logging.info(f"No scraping scheduled for today ({day}). Exiting.")
    any