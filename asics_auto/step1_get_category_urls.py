import os
import logging
import subprocess
from datetime import datetime, date

# Get today's date as a string
today_str = date.today().strftime('%Y-%m-%d')
# today_str = '2025-11-27'

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Set up logging configuration for main script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
if day in ['Tuesday','Thursday', 'Saturday']:
    programs = [
        'codes/step1_get_category_urls_india.py',
        'codes/step1_get_category_urls_uae.py'
    ]
else: 
    print("no scraper")  

processes = []

for script in programs:
    logging.info(f"Starting {script} at {datetime.now()}...\n")
    process = subprocess.Popen(
        ["python", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append((script, process))

# Collect outputs as processes finish
for script, process in processes:
    for line in process.stdout:
        print(line, end='')
    process.wait()
    logging.info(f"Finished {script} at {datetime.now()} Return code: {process.returncode}\n")
    if process.returncode != 0:
        logging.error(f"{script} failed with return code {process.returncode}")