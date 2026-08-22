import os
import json
from datetime import date

def create_new_entry(pdict, plist):
    pno = len(pdict) + 1
    pid = f"{pno:07}"
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

def update_pid(pdict, plist):
    for pid in plist:
        found = False
        for i, j in pdict.items():
            if pid in j:
                found = True
                break
        if not found:
            update_entry(pdict, plist)

def update_cid(cdict, color):
    if color not in cdict.keys():
        cno = len(cdict) + 1
        cid = f"{cno:03}"
        cdict[color] = cid
        print(f'New color entry {cid} : {color}')

def process_pids_cids(cdict, pdict, main_folder):
    genders = os.listdir(main_folder)
    for gender in genders:
        gender_folder = f'{main_folder}/{gender}'
        categories = os.listdir(gender_folder)
        for category in categories:
            category_folder = f'{gender_folder}/{category}'
            files = os.listdir(category_folder)
            for file in files:
                file_path = f'{category_folder}/{file}'
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    product_list = data.get('product_list', [])
                    if product_list:
                        update_pid(pdict, product_list)

                    if 'color_name' in data:
                        color = data.get('color_name', '').replace('variant sold out or unavailable', '').strip().lower()
                        update_cid(cdict, color)
                        
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-16'

    country = 'India'

    dates = os.listdir(f'{country}/Data')
    for today_str in dates:
        main_folder = f'{country}/Data/{today_str}/Json_data'

        if os.path.exists(main_folder):
            cid_path = 'enamor_cid_remapping.json'
            pid_path = 'enamor_pid_remapping.json'

            if os.path.exists(cid_path):
                with open(cid_path, 'r') as json_file:
                    cdict = json.load(json_file)
            else:
                cdict = {}

            if os.path.exists(pid_path):
                with open(pid_path, 'r') as json_file:
                    pdict = json.load(json_file)
            else:
                pdict = {}

            process_pids_cids(cdict, pdict, main_folder)

            with open(cid_path, 'w') as f:
                json.dump(cdict, f, indent=4)

            with open(pid_path, 'w') as f:
                json.dump(pdict, f, indent=4)

            print(f'CIDs and PIDs for {country} {today_str} are updated.')
        else:
            print(f'There is no data for {today_str}')