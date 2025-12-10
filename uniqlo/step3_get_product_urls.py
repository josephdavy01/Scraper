
# import os
# import logging
# import subprocess
# from datetime import datetime, date

# # Get today's date as a string
# today_str = date.today().strftime('%Y-%m-%d')

# # Get the day of the week
# day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# # Set up logging configuration for main script
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler()
#     ]
# )
# programs = [
#     'codes/step3_get_product_url_india.py',
#     'codes/step3_get_product_url.py'
# ] 

# processes = []

# for script in programs:
#     logging.info(f"Starting {script} at {datetime.now()}...\n")
#     process = subprocess.Popen(
#         ["python", script],
#         stdout=subprocess.PIPE,
#         stderr=subprocess.STDOUT,
#         text=True,
#         bufsize=1
#     )
#     processes.append((script, process))

# # Collect outputs as processes finish
# for script, process in processes:
#     for line in process.stdout:
#         print(line, end='')
#     process.wait()
#     logging.info(f"Finished {script} at {datetime.now()} Return code: {process.returncode}\n")
#     if process.returncode != 0:
#         logging.error(f"{script} failed with return code {process.returncode}")
#!/usr/bin/env python3
import os
import sys
import logging
import subprocess
from datetime import datetime, date

# =====================================
# Ensure UTF-8 output (fixes UnicodeEncodeError)
# =====================================
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# =====================================
# Setup logging
# =====================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# =====================================
# Get date info
# =====================================
today_str = date.today().strftime('%Y-%m-%d')
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# =====================================
# Define scripts to run
# =====================================
programs = [
    "codes/step3_get_product_url_india.py",
    "codes/step3_get_product_url.py"
]

# =====================================
# Run scripts concurrently
# =====================================
processes = []

for script in programs:
    logging.info(f"Starting {script} at {datetime.now().isoformat()} ...")
    process = subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8',      # ensures UTF-8 from subprocess
        errors='replace'       # replace invalid chars safely
    )
    processes.append((script, process))

# =====================================
# Stream output live and capture results
# =====================================
for script, process in processes:
    logging.info(f"--- Output from {script} ---")
    for line in process.stdout:
        # Each line is already UTF-8 safe
        print(line, end='', flush=True)
    process.wait()
    logging.info(f"Finished {script} at {datetime.now().isoformat()} Return code: {process.returncode}")
    if process.returncode != 0:
        logging.error(f"{script} failed with return code {process.returncode}")
    else:
        logging.info(f"{script} completed successfully.")
