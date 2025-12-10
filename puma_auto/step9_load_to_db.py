import subprocess
from datetime import datetime,date

# Get the day of the week
today_str =date.today().strftime('%Y-%m-%d')
# today_str = '2025-12-01'

    
day= datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Determine the scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step9_load_to_db_apparel_india.py',
        'codes/step9_load_to_db_footwear_india.py',
        'codes/step9_load_to_db_kids_india.py',
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step9_load_to_db_apparel_uae.py',
        'codes/step9_load_to_db_apparel_uk.py',
        'codes/step9_load_to_db_footwear_uae.py',
        'codes/step9_load_to_db_footwear_uk.py',
        'codes/step9_load_to_db_kids_uae.py',
        'codes/step9_load_to_db_kids_uk.py'
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