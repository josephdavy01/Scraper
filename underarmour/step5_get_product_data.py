import asyncio
from datetime import datetime

# Get the current day of the week
day = datetime.now().strftime('%A')

# Determine which scripts to run based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    scripts = [
        'codes/step6_get_product_data_india.py',
        'codes/step6_get_product_data_uae.py'
    ]
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    scripts = [
        'codes/step6_get_product_data_uk.py',
        'codes/step6_get_product_data_usa.py'
    ]
else:
    scripts = []

async def run_script(script):
    print(f"[{script}] Launching...")
    process = await asyncio.create_subprocess_exec(
        "python", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    # Use communicate() to safely read all output at once
    try:
        stdout, _ = await process.communicate()
        if stdout:
            for line in stdout.decode(errors='ignore').splitlines():
                print(f"[{script}] {line}")
    except asyncio.CancelledError:
        print(f"[{script}] Cancelled! Terminating process.")
        process.kill()
        await process.wait()
        raise

    returncode = await process.wait()
    if returncode != 0:
        print(f"[{script}] Failed with return code {returncode}")
    else:
        print(f"[{script}] Finished successfully.")

async def main():
    if not scripts:
        print("No scripts scheduled to run today.")
        return

    # Run all scripts concurrently
    tasks = [run_script(script) for script in scripts]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
