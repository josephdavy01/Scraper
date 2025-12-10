import os
import json
from datetime import date, datetime
import re


def run_pid_cid_mapping_tts():

    # ------------------ DATE CHECK ------------------ #
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = "2025-12-08"
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['india']

    def create_new_entry(pdict, pname):
        eno = len(pdict) + 1
        pid = f"{eno:07}"
        pdict[pid] = pname  
        print(f'New entry {pid} : {pdict[pid]}')
        return pid

    def update_entry(pdict, pname):
        for i, j in pdict.items():
            if pname == j:
                return
        create_new_entry(pdict, pname)

    def get_pid(pdict, pname):
        if pname not in pdict.values():
            update_entry(pdict, pname)

    def process_pids(pdict, cdict, main_folder):
        if not os.path.exists(main_folder):
            print(f"Folder not found: {main_folder}")
            return

        print(f"Walking through {main_folder}...")

        for root, dirs, files in os.walk(main_folder):
            for file in files:
                if not file.endswith(".json"):
                    continue
                
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    # Handle both nested 'product' key and root-level keys
                    if data.get("product"):
                         product_data = data.get("product")
                    else:
                         product_data = data
                    
                    title = product_data.get("title")

                    if title:
                        # ---------- CID mapping ----------
                        color_parts = title.rsplit("-")
                        if color_parts:
                            color_url = color_parts[-1]
                            color_url = re.sub(r"\s*\(.*?\)", "", color_url).strip().lower()
                            if color_url and color_url not in cdict:
                                cid = f"{len(cdict) + 1:03}"
                                cdict[color_url] = cid

                        # ---------- PID FIX ----------
                        pid_parts = title.rsplit(" - ", 1)

                        if len(pid_parts) == 2:
                            pids = pid_parts[0].strip()
                        else:
                            pids = title.strip()

                        if pids:
                            get_pid(pdict, pids)


                except Exception as e:
                    print(f"Error reading JSON {file_path}: {e}")

    # ------------------ MAIN EXECUTION ------------------ #

    pid_path = 'jockey_pid_remapping.json'
    cid_path = 'jockey_cid_remapping.json'

    # Load PID mapping
    pdict = {}
    if os.path.exists(pid_path):
        try:
            with open(pid_path, 'r') as f:
                pdict = json.load(f)
        except json.JSONDecodeError:
            pdict = {}

    for k, v in list(pdict.items()):
        if isinstance(v, list) and v:
            pdict[k] = v[0]

    cdict = {}
    if os.path.exists(cid_path):
        try:
            with open(cid_path, 'r') as f:
                cdict = json.load(f)
        except json.JSONDecodeError:
            cdict = {}

    for country in countries:
        print(f" Processing PIDs & CIDs for {country}...")

        main_folder = f"{country}/{today_str}/Json_data"
        process_pids(pdict, cdict, main_folder)

        print(f"PIDs & CIDs for {country} {today_str} updated.")

    with open(pid_path, 'w') as f:
        json.dump(pdict, f, indent=4)

    with open(cid_path, 'w') as f:
        json.dump(cdict, f, indent=4)

    print("PID & CID remapping completed for all valid countries.")


if __name__ == "__main__":
    run_pid_cid_mapping_tts()
