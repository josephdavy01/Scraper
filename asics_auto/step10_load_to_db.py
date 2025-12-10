import subprocess
from datetime import datetime

# Get the day of the week
day = datetime.now().strftime('%A')

# Determine the scripts to run based on the day
if day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step10_load_to_db_apparel_uae.py',
        'codes/step10_load_to_db_footwear_india.py',
        'codes/step10_load_to_db_india.py',
        'codes/step10_load_to_db_footwear_uae.py'
    ]
elif day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step10_load_db_apparel_uk.py',
        'codes/step10_load_db_apparel_usa.py',
        'codes/step10_load_db_footwear_uk.py',
        'codes/step10_load_db_footwear_usa.py'
    ]
else:
    scripts = []

if __name__ == "__main__":
    processes = []

    for script in scripts:
        print(f"Launching {script}...")
        process = subprocess.Popen(["python", script])
        processes.append((script, process))

    # Wait for all scripts to complete
    for script, process in processes:
        process.wait()
        if process.returncode != 0:
            print(f"Script {script} failed with return code {process.returncode}")
        else:
            print(f"Finished {script} successfully.")
    print("All scripts executed.")