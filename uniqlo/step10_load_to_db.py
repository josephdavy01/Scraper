import subprocess
from datetime import datetime

# Get the day of the week
day = datetime.now().strftime('%A')

# Determine the scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step10_load_to_db_india.py',
        'codes/step10_load_to_db_kids_india.py',
        'codes/step10_load_to_db_kids_uk.py',
        'codes/sstep10_load_to_db_kids_usa.py',
        'codes/step10_load_to_db_uk.py',
        'codes/step10_load_to_db_usa.py'
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step10_load_to_db_australia.py',
        'codes/step10_load_to_db_canada.py',
        'codes/step10_load_to_db_kids_australia.py',
        'codes/step10_load_to_db_kids_canada.py',
        'codes/step10_load_to_db_kids_spain.py',
        'codes/step10_load_to_db_spain.py'
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