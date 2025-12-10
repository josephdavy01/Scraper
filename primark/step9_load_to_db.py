import subprocess
from datetime import datetime

# Get the day of the week
# day = datetime.strptime('2025-10-13','%Y-%m-%d').strftime('%A')
day = datetime.now().strftime('%A')

if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        "codes/step9_load_to_db_uk.py",
        "codes/step9_load_to_db_uk_footwear.py",
        "codes/step9_load_to_db_uk_kids.py",
        "codes/step9_load_to_db_uk_kids_footwear.py"
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        "codes/step9_load_to_db_usa.py",
        "codes/step9_load_to_db_usa_footwear.py",
        "codes/step9_load_to_db_usa_kids.py",
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