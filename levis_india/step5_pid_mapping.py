
import os
import json
from datetime import date, datetime

def get_next_id(pdict):
    """Get the next available 7-digit zero-padded ID."""
    if not pdict:
        return "0000001"
    # Find the highest existing ID and increment it
    max_id = max(int(key) for key in pdict.keys() if key.isdigit())
    return f"{max_id + 1:07d}"

def create_new_entry(pdict, plist):
    """Create a new entry in pdict with a new ID."""
    pid = get_next_id(pdict)
    pdict[pid] = plist
    print(f'New entry {pid} : {pdict[pid]}')
    return pid

def update_entry(pdict, plist):
    """Update an existing entry or create a new one if no match is found."""
    for i, j in pdict.items():
        intersection = set(plist) & set(j)
        if intersection:
            pdict[i] = list(set(j) | set(plist))
            print(f'Group {i} updated {pdict[i]}')
            return
    create_new_entry(pdict, plist)

def get_pid(pdict, plist):
    """Check if any PID in plist exists in pdict; if not, update or create an entry."""
    for pid in plist:
        found = False
        for i, j in pdict.items():
            if pid in j:
                found = True
                break
        if not found:
            update_entry(pdict, plist)

def process_pids(pdict, main_folder):
    """Process JSON files in the main folder to extract or generate PIDs."""
    genders = os.listdir(main_folder)

    for gender in genders:
        try:
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
                    try:
                        # Try to get variant_ids
                        variant_ids = data.get('variant_ids', [])
                        if variant_ids:
                            pids.extend(variant_ids)
                        else:
                            # If no variant_ids, use the handle field
                            handle = data.get('hulkapps_product_json', {}).get('handle') or data.get('handle')
                            if handle and isinstance(handle, str):
                                # Use the handle as a PID
                                pids.append(handle.strip())
                            else:
                                print(f"No valid handle in {file_path}")
                                continue

                        pids = list(set(pids))  # Remove duplicates
                        pids.sort()  # Sort for consistency

                        if pids:  # Only process if there are PIDs
                            get_pid(pdict, pids)
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
        except Exception as e:
            print(f"Error processing {gender_folder}: {e}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-09'

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['Levis_India']  # Matches the country from the previous script

    for country in countries:
        main_folder = f'{country}/data/{today_str}/Json_data'  # Matches folder structure

        pid_path = 'levis_pid_remapping.json'

        if os.path.exists(pid_path):
            with open(pid_path, 'r') as json_file:
                pdict = json.load(json_file)
        else:
            pdict = {}

        process_pids(pdict, main_folder)

        with open(pid_path, 'w') as f:
            json.dump(pdict, f, indent=4)

        print(f'PIDs for {country} {today_str} are updated.')