import subprocess
from datetime import date, datetime

    # Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Determine the scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step10_load_to_db_australia.py',
        'codes/step10_load_to_db_australia_kids.py',
        'codes/step10_load_to_db_canada.py',
        'codes/step10_load_to_db_canada_kids.py',
        'codes/step10_load_to_db_india.py',
        'codes/step10_load_to_db_india_kids.py',
        'codes/step10_load_to_db_saudi.py',
        'codes/step10_load_to_db_saudi_kids.py',
        'codes/step10_load_to_db_spain.py',
        'codes/step10_load_to_db_spain_kids.py'
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step10_load_to_db_turkey.py',
        'codes/step10_load_to_db_turkey_kids.py',
        'codes/step10_load_to_db_uae.py',
        'codes/step10_load_to_db_uae_kids.py',
        'codes/step10_load_to_db_uk.py',
        'codes/step10_load_to_db_uk_kids.py',
        'codes/step10_load_to_db_usa.py',
        'codes/step10_load_to_db_usa_kids.py'
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