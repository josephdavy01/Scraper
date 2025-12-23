import os
import logging
from datetime import datetime, timedelta, timezone
from alert import raise_ticket
import json

# Import step functions
from steps.step1_get_category_url import get_category_urls
from steps.step2_get_product_urls import get_product_urls
from steps.step3_get_product_data import get_product_data
from steps.step4_process_json_footwear import process_footwear
from steps.step5_process_json_apparel import process_apparel
from steps.step6_remove_duplicate_data import remove_duplicates_from_json
from steps.step7_check_data_format import check_data_format 
from steps.step8_upload_to_melody import upload_to_data_melody

from validations import (remove_duplicate_urls, check_deviation,
                         compare_with_previous_data, check_comparison_results_data,
                         compare_product_links, summarize_product_url_changes)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_time():
    return datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')

def update_country_log(country, log_entry):
    # Ensure TODAY_DATE is available
    log_dir = os.path.join(country, TODAY_DATE, 'log')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f'{country}_log.json')
    
    current_logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                current_logs = json.load(f)
                if not isinstance(current_logs, list):
                    current_logs = []
        except:
            current_logs = []
            
    current_logs.append(log_entry)
    
    with open(log_file, 'w') as f:
        json.dump(current_logs, f, indent=4)

def log_step_execution(countries, step_name, status, duration=None):
    timestamp = get_ist_time()
    log_entry = {
        "timestamp": timestamp,
        "step": step_name,
        "status": status
    }
    if duration:
        if isinstance(duration, dict):
             log_entry.update(duration)
        else:
            log_entry["duration"] = str(duration)
        
    for country in countries:
        try:
            update_country_log(country, log_entry)
        except Exception as e:
            print(f"Failed to log for {country}: {e}")

def parse_duration(dur_str):
    try:
        if 'day' in dur_str:
            days_part, time_part = dur_str.split(', ')
            days = int(days_part.split()[0])
            hours, minutes, seconds = map(float, time_part.split(':'))
            return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        else:
            hours, minutes, seconds = map(float, dur_str.split(':'))
            return timedelta(hours=hours, minutes=minutes, seconds=seconds)
    except Exception as e:
        logging.error(f"Error parsing duration {dur_str}: {e}")
        return timedelta(0)

def get_daily_summary(country):
    log_dir = os.path.join(country, TODAY_DATE, 'log')
    log_file = os.path.join(log_dir, f'{country}_log.json')
    
    summary = {}
    total_duration = timedelta(0)
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
                for entry in logs:
                    if entry.get('status') in ['Finished', 'Interrupted'] and 'duration' in entry:
                        step = entry['step']
                        # Skip previous script execution summaries to avoid double counting
                        if step == "Script Execution":
                            continue
                            
                        dur = parse_duration(entry['duration'])
                        if step in summary:
                            summary[step] += dur
                        else:
                            summary[step] = dur
                        total_duration += dur
        except Exception as e:
            logging.error(f"Error reading log for summary: {e}")
    
    # Convert timedeltas to string
    summary_str = {k: str(v) for k, v in summary.items()}
    summary_str['Total Time'] = str(total_duration)
    return summary_str

def cleanup_logs(countries):
    """
    Checks for interrupted steps in the logs and marks them as 'Interrupted'
    with a calculated duration based on file modification times.
    """
    for country in countries:
        log_dir = os.path.join(country, TODAY_DATE, 'log')
        log_file = os.path.join(log_dir, f'{country}_log.json')
        
        if not os.path.exists(log_file):
            continue
            
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
            
            if not logs:
                continue
                
            last_entry = logs[-1]
            
            if last_entry.get('status') == 'Started':
                step = last_entry.get('step')
                start_time_str = last_entry.get('timestamp')
                start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
                start_time = start_time.replace(tzinfo=timezone(timedelta(hours=5, minutes=30))) # Assume IST
                
                end_time = datetime.now(timezone(timedelta(hours=5, minutes=30))) # Default to now
                
                # Smart duration calculation
                try:
                    if step == "Step 3: Scrape Data":
                        json_data_dir = os.path.join(country, TODAY_DATE, 'Json_data')
                        if os.path.exists(json_data_dir):
                            scrap_logs = [os.path.join(json_data_dir, f) for f in os.listdir(json_data_dir) if 'scrape_log.json' in f]
                            if scrap_logs:
                                latest_log = max(scrap_logs, key=os.path.getmtime)
                                mod_time = datetime.fromtimestamp(os.path.getmtime(latest_log)).astimezone(IST)
                                end_time = mod_time

                    elif step == "Step 4: Process Footwear":
                        data_file = os.path.join(country, TODAY_DATE, 'Data', f'{country}_data_footwear.json')
                        if os.path.exists(data_file):
                            mod_time = datetime.fromtimestamp(os.path.getmtime(data_file)).astimezone(IST)
                            end_time = mod_time
                            
                    elif step == "Step 5: Process Apparel":
                        data_file = os.path.join(country, TODAY_DATE, 'Data', f'{country}_data_apparel.json')
                        if os.path.exists(data_file):
                            mod_time = datetime.fromtimestamp(os.path.getmtime(data_file)).astimezone(IST)
                            end_time = mod_time
                            
                except Exception as e:
                    logging.warning(f"Failed to determine smart duration for interrupted step {step} in {country}: {e}")

                duration = end_time - start_time
                if duration.total_seconds() < 0:
                    duration = timedelta(0)

                interrupted_entry = {
                    "timestamp": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "step": step,
                    "status": "Interrupted",
                    "duration": str(duration),
                    "note": "Script restarted. Duration estimated based on file modification or restart time."
                }
                
                logs.append(interrupted_entry)
                
                with open(log_file, 'w') as f:
                    json.dump(logs, f, indent=4)
                    
                logging.info(f"Marked {step} as Interrupted for {country}. Duration: {duration}")

        except Exception as e:
            logging.error(f"Error cleaning up logs for {country}: {e}")



# --- Configuration ---
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
# TODAY_DATE = '2025-12-06' 

COUNTRIES = ['Saudi', 'Spain', 'Turkey', 'UAE']
# COUNTRIES = ['Saudi']

# Moved here so Step 1 is purely logic, not config.

CONFIG = {
    'Saudi': {
        'base_url': 'https://www.lefties.com/sa',
        'store_id': '95009030/90009053',
        'domain': 'www.lefties.com',
        'use_proxies': False,
        'proxies': {
            "server": "p.webshare.io:80",
            "username": "hkzhowmh-rotate",
            "password": "hzzg78l8xrj5"
        },
        'browsers': 2,
        'browsers_product_urls':4
    },
    'Spain': {
        'base_url': 'https://www.lefties.com/es/en',
        'store_id': '94009000/90009053',
        'domain': 'www.lefties.com',
        'use_proxies': False,
        'proxies': {
            "server": "p.webshare.io:80",
            "username": "hkzhowmh-rotate",
            "password": "hzzg78l8xrj5"
        },
        'browsers': 2,
        'browsers_product_urls':4
    },
    'Turkey': {
        'base_url': 'https://www.lefties.com/tr/en',
        'store_id': '94009021/90009064',
        'domain': 'www.lefties.com',
        'use_proxies': False,
        'proxies': {
            "server": "p.webshare.io:80",
            "username": "hkzhowmh-rotate",
            "password": "hzzg78l8xrj5"
        },
        'browsers': 2,
        'browsers_product_urls':4
    },
    'UAE': {
        'base_url': 'https://www.lefties.com/ae',
        'store_id': '95009031/90009053',
        'domain': 'www.lefties.com',
        'use_proxies': False,
        'proxies': {
            "server": "p.webshare.io:80",
            "username": "hkzhowmh-rotate",
            "password": "hzzg78l8xrj5"
        },
        'browsers': 2,
        'browsers_product_urls':4
    }
}

MONGO_CONFIG_APPAREL = {
    'SERVER_URI': 'replace_with_actul_server_string',
    'DB_NAME': 'tg_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_lefties_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': True, # Set True to delete existing data on the server for the same day and re-upload.
    'DRY_RUN': False        # Set True to simulate the run without writing/deleting any data.
}

MONGO_CONFIG_FOOTWEAR = {
    'SERVER_URI': 'replace_with_actul_server_string',
    'DB_NAME': 'footwear_analytics',
    'COLLECTION_PREFIX': 'crawler_sink_lefties_',
    'THRESHOLD_PERCENT': 10.0,
    'FORCE_UPLOAD': True, # Set True to delete existing data on the server for the same day and re-upload.
    'DRY_RUN': False        # Set True to simulate the run without writing/deleting any data.
}


EXECUTION_CONFIG = {
    #Category
    'step1_categories': True,
    'step1_rerun': False,
    #Product URLs 
    'step2_product_urls': True,
    'step2_rerun': False,
    #Scrape Data
    'step3_scrape_data': True,
    'step3_rerun': False,
    #Process Footwear
    'step4_process_footwear': True,
    'step4_process_footwear_rerun': True,
    #Process Apparel
    'step5_process_apparel': True,
    'step5_apparel_rerun': True,
    #Remove Duplicates
    'step6_remove_duplicates': True,
    #Check Data Format
    'step7_check_format': True,
    #Upload
    'step8_upload_apparel': True,
    'step8_upload_footwear': True
}

def main():
    step_durations = {}
    logging.info(f"Starting Lefties Scraper for {TODAY_DATE}")
    
    # Cleanup logs from previous interrupted runs
    cleanup_logs(COUNTRIES)

    # 1. Categories
    if EXECUTION_CONFIG['step1_categories']:
        step_name = "Step 1: Categories"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            get_category_urls(COUNTRIES, TODAY_DATE, CONFIG, re_run=EXECUTION_CONFIG.get('step1_rerun', False))
            remove_duplicate_urls(COUNTRIES, TODAY_DATE, level='category')
            compare_with_previous_data(COUNTRIES, TODAY_DATE)
            country_wise_status = check_comparison_results_data(COUNTRIES, TODAY_DATE)
            
            if all(country_wise_status.values()):
                print("No changes found in any country.")
            else:
                print("Changes found in the following countries:")
                for country, status in country_wise_status.items():
                    if not status:
                        print(f"{country}: Changes detected.")
                        
                        # Automate handling: Raise ticket and continue
                        comparison_file = os.path.join(country, TODAY_DATE, "Category", f"{country}_category_comparison.json")
                        details = f"Changes detected in category URLs for {country}."
                        
                        if os.path.exists(comparison_file):
                            try:
                                with open(comparison_file, 'r', encoding='utf-8') as f:
                                    comparison_data = json.load(f)
                                    # Convert to string for ticket details, maybe truncate if too long
                                    details = f"Changes detected in {country}: {json.dumps(comparison_data, indent=2)}"
                            except Exception as e:
                                details += f" (Error reading comparison file: {e})"
                        
                        print(f"Raising ticket for {country} category changes and continuing...")
                        raise_ticket("Master", "check_comparison_results_data", details, country)
                        print(f"Continuing...")
        except Exception as e:
            logging.error(f"Step 1 Failed: {e}")
            raise_ticket("Step 1", "save_category_urls", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    # 2. Product URLs
    if EXECUTION_CONFIG['step2_product_urls']:
        step_name = "Step 2: Product URLs"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            get_product_urls(CONFIG, TODAY_DATE, re_run=EXECUTION_CONFIG.get('step2_rerun', False))
            if remove_duplicate_urls(COUNTRIES, TODAY_DATE, level='product'):
                print("Duplicate product URLs found and removed.")
            else:
                print("No duplicate product URLs found.")
            compare_product_links(COUNTRIES, TODAY_DATE)
            summarize_product_url_changes(COUNTRIES, TODAY_DATE)

            # Print the final summary for each country
            for country in COUNTRIES:
                log_file_path = os.path.join(country, TODAY_DATE, 'Item_urls', f"{country}_product_link_comparison_log.json")
                if os.path.exists(log_file_path):
                    with open(log_file_path, 'r') as f:
                        log_data = json.load(f)
                        final_summary = log_data.get("final_summary", {})
                        if final_summary:
                            # final_deviation_percent is produced by compare_product_links
                            final_dev = final_summary.get("final_deviation_percent")
                            status = final_summary.get("status", "")
                            if final_dev is not None:
                                if final_dev > 5:
                                    direction = "Greater (current > previous)"
                                    raise_ticket("Step 2", "compare_product_links", f"Significant change in product URLs for {country} on {TODAY_DATE}: Deviation {final_dev}%", country)
                                elif final_dev < -5:
                                    direction = "Lower (current < previous)"
                                    raise_ticket("Step 2", "compare_product_links", f"Significant change in product URLs for {country} on {TODAY_DATE}: Deviation {final_dev}%", country)
                                else:
                                    direction = "No change"
                                print(f"Final Summary for {country} on {TODAY_DATE}: {final_summary}")
                                print(f"Deviation: {final_dev}% -> {direction}. Status: {status}")
                            else:
                                print(f"Final Summary for {country} on {TODAY_DATE}: {final_summary}")
                else:
                    print(f"No comparison log found for {country} on {TODAY_DATE}")
        except Exception as e:
            logging.error(f"Step 2 Failed: {e}")
            raise_ticket("Step 2", "get_product_urls", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    # 3. Scrape Data
    if EXECUTION_CONFIG['step3_scrape_data']:
        step_name = "Step 3: Scrape Data"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            country_statuses = get_product_data(CONFIG, TODAY_DATE, re_run=EXECUTION_CONFIG.get('step3_rerun', False))
            
            for country, status in country_statuses.items():
                print(f"Status for {country}: {status}")
                if status == 'success':
                    print(f"Calculating deviation for {country}...")
                    log_file_path = os.path.join(country, TODAY_DATE, 'Json_data', f'{country}_scrape_log.json')
                    total_urls_file_path = os.path.join(country, TODAY_DATE, 'Item_urls', f'{country}_product_links.json')
                    deviation = check_deviation(log_file_path, total_urls_file_path)
                    if deviation < 0:
                        print(f"Could not calculate deviation for {country} due to missing files.")
                    else:
                        print(f"Deviation (failure rate) for {country} is {deviation:.2f}%")
                        if deviation > 5:
                            print(f"Warning: Deviation for {country} is {deviation:.2f}%, which is greater than 5%.")
                            raise_ticket("Step 3", "check_deviation", f"High deviation detected for {country}: {deviation:.2f}%", country)
                else:
                    error_message = f"Product data scraping failed for {country} due to country setup issues."
                    logging.error(f"Step 3 Failed for {country}: {error_message}")
                    raise_ticket("Step 3", "get_product_data", error_message, country)

        except Exception as e:
            logging.error(f"An unexpected error occurred in Step 3: {e}")
            raise_ticket("Step 3", "get_product_data", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    # 4. Process Footwear Data
    if EXECUTION_CONFIG['step4_process_footwear']:
        step_name = "Step 4: Process Footwear"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            process_footwear(COUNTRIES, TODAY_DATE, re_run=EXECUTION_CONFIG.get('step4_process_footwear_rerun', False))
        except Exception as e:
            logging.error(f"Step 4 Footwear Failed: {e}")
            raise_ticket("Step 4", "process_footwear", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    # 5. Process Apparel Data
    if EXECUTION_CONFIG['step5_process_apparel']:
        step_name = "Step 5: Process Apparel"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            process_apparel(COUNTRIES, TODAY_DATE, re_run=EXECUTION_CONFIG.get('step5_apparel_rerun', False))
        except Exception as e:
            logging.error(f"Step 5 Apparel Failed: {e}")
            raise_ticket("Step 5", "process_apparel", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    # 6. Remove Duplicates
    if EXECUTION_CONFIG['step6_remove_duplicates']:
        step_name = "Step 6: Remove Duplicates"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            remove_duplicates_from_json(COUNTRIES, TODAY_DATE)
        except Exception as e:
            logging.error(f"Step 6 Failed: {e}")
            raise_ticket("Step 6", "remove_duplicates", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    # 8. Check Data Format
    if EXECUTION_CONFIG.get('step7_check_format'):
        step_name = "Step 7: Check Data Format"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            for country in COUNTRIES:
                check_data_format(country, TODAY_DATE)
        except Exception as e:
            logging.error(f"Step 7 Check Data Format Failed: {e}")
            raise_ticket("Step 7", "check_data_format", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    #  7. Upload
    if EXECUTION_CONFIG['step8_upload_apparel']:
        step_name = "Step 8: Upload Apparel"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            upload_to_data_melody(COUNTRIES, TODAY_DATE, MONGO_CONFIG_APPAREL)
        except Exception as e:
            logging.error(f"Step 8 Apparel Failed: {e}")
            raise_ticket("Step 8", "upload apparel", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    if EXECUTION_CONFIG['step8_upload_footwear']:
        step_name = "Step 8: Upload Footwear"
        log_step_execution(COUNTRIES, step_name, "Started")
        step_start = datetime.now(IST)
        try:
            upload_to_data_melody(COUNTRIES, TODAY_DATE, MONGO_CONFIG_FOOTWEAR)
        except Exception as e:
            logging.error(f"Step 8 Footwear Failed: {e}")
            raise_ticket("Step 8", "upload footwear", str(e))
        
        step_end = datetime.now(IST)
        duration = step_end - step_start
        step_durations[step_name] = str(duration)
        log_step_execution(COUNTRIES, step_name, "Finished", duration)

    # Log Daily Summary
    for country in COUNTRIES:
        daily_summary = get_daily_summary(country)
        log_entry = {
            "timestamp": get_ist_time(),
            "step": "Script Execution",
            "status": "Finished",
            "daily_summary": daily_summary
        }
        try:
            update_country_log(country, log_entry)
        except Exception as e:
            logging.error(f"Failed to log daily summary for {country}: {e}")

if __name__ == "__main__":
    # Start time measurement
    start_time = datetime.now()
    main()
    # End time measurement
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"Script started at: {start_time}")
    print(f"Script ended at: {end_time}")
    print(f"Script duration: {duration}")