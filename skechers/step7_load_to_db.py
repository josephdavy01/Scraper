import subprocess
from datetime import datetime

# Get the current day of the week
day = datetime.now().strftime('%A')
# day = datetime.strptime('2025-11-28','%Y-%m-%d').strftime('%A')

# Determine the scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step6_load_to_db_footwear_uk_usa.py',
        'codes/step6_load_to_db_uk_usa.py',
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step6_load_to_db_footwear_india.py',
        'codes/step6_load_to_db_india.py',
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