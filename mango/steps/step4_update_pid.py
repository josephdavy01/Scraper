import os
import json
import logging

def create_new_entry(pdict, plist):
    pid = plist[0]
    pdict[pid] = plist
    logging.info(f'New entry {pid} : {pdict[pid]}')
    return pid

def update_entry(pdict, plist):
    for i, j in pdict.items():
        intersection = set(plist) & set(j)
        if intersection:
            pdict[i] = list(set(j) | set(plist))
            logging.info(f'Group {i} updated {pdict[i]}')
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

def process_pids(pdict, main_folder):
    if not os.path.exists(main_folder):
        logging.warning(f"Data folder not found: {main_folder}")
        return

    genders = os.listdir(main_folder)

    for gender in genders:
        gender_folder = os.path.join(main_folder, gender)
        if not os.path.isdir(gender_folder):
            continue
            
        categories = os.listdir(gender_folder)
        for category in categories:
            category_folder = os.path.join(gender_folder, category)
            if not os.path.isdir(category_folder):
                continue
                
            files = os.listdir(category_folder)
            for file in files:
                # Exclude log and summary files
                if file.endswith('scrap_log.json') or file.endswith('summary.json') or file.endswith('duplicate_urls.json'):
                    continue
                
                if not file.endswith('.json'):
                    continue

                pids = []
                file_path = os.path.join(category_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    
                    product = data.get('product')
                    if product:
                        colors = product.get('colors', [])
                        for color in colors:
                            rid = color.get('relatedProductId')
                            if rid:
                                pids.append(rid) 
                        pid = product.get('id')
                        if pid:
                            pids.append(pid)
                
                    if pids:
                        pids = list(set(pids))
                        pids.sort()
                        get_pid(pdict, pids)
                except Exception as e:
                    logging.error(f"Error processing file {file_path}: {e}")

def update_pids(countries, today_date):
    """
    Updates the mango_pid_remapping.json file based on the scraped data.
    """
    pid_path = 'mango_pid_remapping.json'
    
    if os.path.exists(pid_path):
        try:
            with open(pid_path, 'r') as json_file:
                pdict = json.load(json_file)
        except Exception as e:
            logging.error(f"Error loading existing PID remapping file: {e}")
            pdict = {}
    else:
        pdict = {}

    for country in countries:
        # Path: Country/Date/Json_data
        main_folder = os.path.join(country, today_date, 'Json_data')
        logging.info(f"Processing PIDs for {country} from {main_folder}")
        process_pids(pdict, main_folder)
        logging.info(f'PIDs for {country} {today_date} processed.')

    try:
        with open(pid_path, 'w') as f:
            json.dump(pdict, f, indent=4)
        logging.info(f"Successfully updated {pid_path}")
    except Exception as e:
        logging.error(f"Error saving PID remapping file: {e}")
