import os
import logging
import asyncio
from datetime import datetime, date
import locale

# Ensure the 'logs' directory exists
os.makedirs("logs", exist_ok=True)

# Get today's date as a string
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Create log filename with today's date
log_filename = f"logs/log_{today_str}.txt"

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, mode='a', encoding="utf-8", errors="replace"),
        logging.StreamHandler()
    ]
)

# Determine scripts to run
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step2_get_product_urls_uk_usa.py',
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step2_get_product_urls_india.py',
    ]
else:
    scripts = []

log_lock = asyncio.Lock()  # Ensure file writes from multiple tasks are safe

async def run_script(script):
    """Run a script and capture live output to console and log file."""
    process = await asyncio.create_subprocess_exec(
        "python", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    logging.info(f"Started {script} at {datetime.now()}")

    system_encoding = locale.getpreferredencoding()

    async for line in process.stdout:
        try:
            decoded = line.decode("utf-8").rstrip()
        except UnicodeDecodeError:
            decoded = line.decode(system_encoding, errors="replace").rstrip()

        print(f"[{script}] {decoded}")
        if '- INFO -' in decoded or '- WARNING -' in decoded or '- ERROR -' in decoded:
            async with log_lock:  # ensure safe write to file
                with open(log_filename, 'a', encoding="utf-8", errors="replace") as f:
                    f.write(f"[{script}] {decoded}\n")

    returncode = await process.wait()
    logging.info(f"Finished {script} at {datetime.now()} Return code: {returncode}")
    if returncode != 0:
        logging.error(f"{script} failed with return code {returncode}")

async def main():
    if not scripts:
        logging.info("No scripts scheduled to run today.")
        return

    tasks = [run_script(script) for script in scripts]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
