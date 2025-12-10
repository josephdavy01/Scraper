import subprocess
from datetime import datetime

# Get today's day
day = datetime.now().strftime('%A')
# day = datetime.strptime('2025-12-06', '%Y-%m-%d').strftime('%A')

if day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step10_load_to_db_uk.py',
        'codes/step10_load_to_db_uk_kids.py',
        'codes/step10_load_to_db_usa.py',
        'codes/step10_load_to_db_usa_kids.py'
    ]
else:
    print("Today is not a valid day to run the scripts.")
    scripts = []

if __name__ == "__main__":
    for script in scripts:
        print(f"\nRunning {script}...")
        result = subprocess.run(["python", script])
        if result.returncode != 0:
            print(f"Script {script} failed with return code {result.returncode}")
        else:
            print(f"Finished {script} successfully.")