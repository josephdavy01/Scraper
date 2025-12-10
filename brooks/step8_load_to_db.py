import subprocess
from datetime import datetime

# Get the current day of the week
day = datetime.now().strftime('%A')

# Determine the scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step8_load_to_db_footwear.py',
        'codes/step8_load_to_db.py'
    ]

def run_script(script):
    print(f"\nLaunching: {script}")
    return subprocess.Popen(['python', script])


if __name__ == "__main__":
    processes = [run_script(script) for script in scripts]

    # Wait for all processes to finish
    for process in processes:
        process.wait()

    print("\nAll scripts executed (concurrently)!")
