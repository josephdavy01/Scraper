import subprocess
from datetime import date, datetime

# # Get the current day of the week
dt = datetime.now()
day = dt.strftime('%A')
# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')


# Determine the scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step9_load_to_db_canada.py',
        'codes/step9_load_to_db_saudi.py',
        'codes/step9_load_to_db_spain.py',
        'codes/step9_load_to_db_turkey.py'
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step9_load_to_db_uae.py',
        'codes/step9_load_to_db_uk.py',
        'codes/step9_load_to_db_usa.py'
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