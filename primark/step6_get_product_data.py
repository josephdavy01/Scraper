import subprocess
from datetime import datetime

# Get the day of the week
day = datetime.now().strftime('%A')

if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        "codes/step6_get_product_data_uk.py",
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        "codes/step6_get_product_data_usa.py",
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