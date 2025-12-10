import os
import json
from datetime import date, datetime


def run_pid_cid_mapping_tts():

    # ------------------ DATE CHECK ------------------ #
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = "2025-12-04"
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['india']

    # ------------------ Helper Functions ------------------ #

    def create_new_entry(pdict, plist):
        eno = len(pdict) + 1
        pid = f"{eno:07}"
        pdict[pid] = plist
        print(f'New entry {pid} : {pdict[pid]}')
        return pid

    def update_entry(pdict, plist):
        for i, j in pdict.items():
            if set(plist) & set(j):
                pdict[i] = list(set(j) | set(plist))
                print(f'Group {i} updated {pdict[i]}')
                return
        create_new_entry(pdict, plist)

    def get_pid(pdict, plist):
        for pid in plist:
            found = any(pid in group for group in pdict.values())
            if not found:
                update_entry(pdict, plist)

    def process_pids(pdict, cdict, main_folder):
        if not os.path.exists(main_folder):
            print(f"Folder not found: {main_folder}")
            return

        genders = os.listdir(main_folder)

        for gender in genders:
            gender_folder = f"{main_folder}/{gender}"
            if not os.path.isdir(gender_folder):
                continue

            categories = os.listdir(gender_folder)
            for category in categories:
                category_folder = f"{gender_folder}/{category}"
                if not os.path.isdir(category_folder):
                    continue

                for file in os.listdir(category_folder):
                    file_path = f"{category_folder}/{file}"
                    if not file_path.endswith(".json"):
                        continue

                    try:
                        with open(file_path, 'r', encoding='utf-8') as json_file:
                            data = json.load(json_file)

                        # ---------- CID mapping ----------
                        color_url = data.get("color").lower() 
                        if color_url and color_url not in cdict:
                            cid = f"{len(cdict) + 1:03}"
                            cdict[color_url] = cid

                        # ---------- PID grouping ----------
                        pids = []
                        handles = data.get("group_handles")
                        if handles:
                            for handle in handles:
                                pids.append(handle)

                        get_pid(pdict, pids)

                    except Exception:
                        print(f"Error reading JSON → {file_path}")

    # ------------------ MAIN EXECUTION ------------------ #

    pid_path = 'xyxx_pid_remapping.json'
    cid_path = 'xyxx_cid_remapping.json'

    # Load PID mapping
    pdict = {}
    if os.path.exists(pid_path):
        try:
            with open(pid_path, 'r') as f:
                pdict = json.load(f)
        except json.JSONDecodeError:
            pdict = {}

    # Load CID mapping
    cdict = {}
    if os.path.exists(cid_path):
        try:
            with open(cid_path, 'r') as f:
                cdict = json.load(f)
        except json.JSONDecodeError:
            cdict = {}

    # Process each country
    for country in countries:
        print(f" Processing PIDs & CIDs for {country}...")

        main_folder = f"{country}/{today_str}/Json_data"
        process_pids(pdict, cdict, main_folder)

        print(f"PIDs & CIDs for {country} {today_str} updated.")

    # Save updated mappings
    with open(pid_path, 'w') as f:
        json.dump(pdict, f, indent=4)

    with open(cid_path, 'w') as f:
        json.dump(cdict, f, indent=4)

    print("PID & CID remapping completed for all valid countries.")


# Optional direct run
if __name__ == "__main__":
    run_pid_cid_mapping_tts()
