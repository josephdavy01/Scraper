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

# Configure logging (master logger)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, mode='a'),
        logging.StreamHandler()
    ]
)

if day in ["Tuesday", "Thursday", "Saturday"]:
    programs = [
        'step1_get_category_urls.py',
        'step2_category_ids.py',
        'step3_get_product_urls.py',
        'step5_unique_urls.py',
        'step4_daily_count.py',
        'step5_get_product_data.py',
        'step7_update_cids.py',
        'step8_load_to_db.py',
        'step9_remove_duplicate_skus.py',
        'step10_check_data_format.py',
        'step9_upload_to_melody.py'
    ]

    logging.info(f"Master pipeline started for {today_str} ({day})")

    for script in programs:
        logging.info(f"Starting {script} at {datetime.now()}...\n")

        with subprocess.Popen(
            ["python", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        ) as process, open(log_filename, 'a', encoding='utf-8') as log_file:
            if process.stdout is not None:
                for line in process.stdout:
                    print(line, end='')        # Always show on terminal
                    log_file.write(line)       # Write all output to log file
            process.wait()

        logging.info(f"Finished {script} at {datetime.now()} | Return code: {process.returncode}\n")

    logging.info(f"Master pipeline finished for {today_str} ({day})\n")

else:
    logging.info(f"No scraping scheduled for today ({day}). Exiting.\n")


# [
#   {
#     "$group": {
#       "_id": "$date_of_scraping",
#       "count": { "$sum": 1 } // Counts the number of entries for each date
#     }
#   },
#   {
#     "$sort": {
#       "_id": -1 // Sorts the dates in ascending order
#     }
#   }
# ]