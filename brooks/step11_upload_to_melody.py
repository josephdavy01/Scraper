import subprocess
from datetime import datetime

# Get the current day of the week
day = datetime.now().strftime('%A')

# Determine the scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step11_upload_to_melody_footwear.py',
        'codes/step11_upload_to_melody_apparel.py'
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
