import os
import json
from datetime import date, datetime

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
        for i, j in pdict.items():
            if pid in j:
                found = True
                break
        if not found:
            update_entry(pdict, plist)

def process_pids(pdict, cdict, main_folder):
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
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    
                    color = data['colour'].lower()
                    if color not in cdict.keys():
                        cno = len(cdict) + 1
                        cid = f"{cno:03}"
                        cdict[color] = cid

                    if data['swatchInfo']:
                        swatches = data['swatchInfo']['swatchItems']
                        for swatch in swatches:
                            pid = swatch['productId']
                            pids.append(pid) 
                    else:
                        pid = data['productId']
                        pids.append(pid)

                    get_pid(pdict, pids)
                except:
                    print(f"error while decoding {file_path}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06'
    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['UK', 'USA']
    else:
        print("Today is not a valid day to run the scripts.")
        countries = []
       
    for country in countries:
        main_folder = f'{country}/Data/{today_str}/Json_data'

        pid_path = 'riverisland_pid_remapping.json'
        cid_path = 'riverisland_cid_remapping.json'

        if os.path.exists(pid_path):
            with open(pid_path, 'r') as json_file:
                pdict = json.load(json_file)
        else:
            pdict = {}

        if os.path.exists(cid_path):
            with open(cid_path, 'r') as json_file:
                cdict = json.load(json_file)
        else:
            cdict = {}

        process_pids(pdict, cdict, main_folder)

        with open(pid_path, 'w') as f:
            json.dump(pdict, f, indent=4)

        with open(cid_path, 'w') as f:
            json.dump(cdict, f, indent=4)

        print(f'CIDs & PIDs for {country} {today_str} are updated.')