import os
import json
from datetime import date

def create_new_entry(pdict, plist):
    eno = len(pdict) + 1
    pid = f"{eno:07}"
    pdict[pid] = plist
    print(f'New entry {pid} : {pdict[pid]}')
    return pid

def update_entry(pdict, plist):
    for i, j in pdict.items():
        intersection = set(plist) & set(j)
        if intersection:
            pdict[i] = list(set(j) | set(plist))
            print(f'Group {i} updated {pdict[i]}')
            return 
    create_new_entry(pdict, plist)

def get_pid(pdict, plist):
    for pid in plist:
        found = False
        for j in pdict.values():
            if pid in j:
                found = True
                break
        if not found:
            update_entry(pdict, plist)

def process_pids(pdict, main_folder):
    genders = os.listdir(main_folder)

    for gender in genders:
        gender_folder = f'{main_folder}/{gender}'
        categories = os.listdir(gender_folder)
        for category in categories:
            category_folder = f'{gender_folder}/{category}'
            files = os.listdir(category_folder)
            for file in files:
                pids = []
                file_path = f'{category_folder}/{file}'
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)

                if data:
                    if 'variants' in data.keys():
                        for pid in data['variants']:
                            pids.append(pid)
                        pid = data['product']['handle']
                        pids.append(pid)
                    elif 'product' in data.keys() and data['product']:
                        pid = data['product']['handle']
                        pids.append(pid)

                    pids = list(set(pids))
                    get_pid(pdict, pids)

if __name__ == "__main__":
    today = date.today()
    fetch_date = today.strftime('%Y-%m-%d')
    # fetch_date = '2025-12-06'

    country = 'India'

    main_folder = f'{country}/Data/{fetch_date}/Json_data'
    pid_path = 'us_polo_pid_remapping.json'

    if os.path.exists(pid_path):
        with open(pid_path, 'r') as json_file:
            pdict = json.load(json_file)
    else:
        pdict = {}

    process_pids(pdict, main_folder)

    with open(pid_path, 'w') as f:
        json.dump(pdict, f, indent=4)

    print(f'PIDs for {country} {fetch_date} are updated.')