import os
import logging
import subprocess
from datetime import datetime, date

# Ensure the 'logs' directory exists
os.makedirs("logs", exist_ok=True)

# Get today's date as a string
today_str = date.today().strftime('%Y-%m-%d')
# today_str = '2025-11-14'
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

# Determine the scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step1_get_category_urls_saudi.py',
        'codes/step1_get_category_urls_uae.py'
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step1_get_category_urls_india.py',
        'codes/step1_get_category_urls_uk.py'
    ]
else:
    scripts = []

for idx, script in enumerate(scripts):
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