import subprocess
from datetime import datetime,date

today_str = date.today().strftime('%Y-%m-%d')


# Get the current day of the week
day =datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Determine the scripts to run based on the day
if day in ['Tuesday']:
    scripts = [
        'codes/step6_get_india_product_data.py',
        'codes/step6_get_india_product_availability.py'
    ]
elif day in ['Thursday']:
    scripts = [
        'codes/step6_get_uk_product_availability.py',
        'codes/step6_get_uk_product_data.py'
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