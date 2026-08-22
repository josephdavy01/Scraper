import os
import logging
import subprocess
from datetime import datetime, date

# Ensure the 'logs' directory exists
os.makedirs("logs", exist_ok=True)

# Get today's date as a string
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
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

programs = []
if day in ['Monday','Tuesday', 'Wednesday', 'Friday']:
    programs = [
    'step1_get_product_urls.py',
    'step2_get_daily_count.py',
    'step3_get_product_data.py',
    'step4_json_comparison.py',
    'step5_update_pids_cids.py',
    'step6_load_to_db.py',
    'step7_remove_duplicate.py',
    'step8_check_data_format.py',
    'step9_upload_to_melody.py'
]
else:
    logging.info(f"Today is {day} — no need to run")

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