import os
import json
import re
from datetime import datetime
from collections import defaultdict

def find_previous_date_folder(country_path, current_date):
    """Find the most recent previous date folder in the country directory"""
    date_folders = []
    # Convert the current_date string to a datetime object for comparison
    current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")
    
    for folder in os.listdir(country_path):
        if os.path.isdir(os.path.join(country_path, folder)):
            try:
                date_obj = datetime.strptime(folder, "%Y-%m-%d")
                # Only append dates that are earlier than the current date
                if date_obj < current_date_obj:
                    date_folders.append((date_obj, folder))
            except ValueError:
                continue
    
    if not date_folders:
        return None
    
    # Sort the valid past dates in descending order to find the most recent one
    date_folders.sort(reverse=True)
    return date_folders[0][1]

def find_duplicate_urls(data):
    """Find duplicate URLs within the same data (flat key:url format)"""
    url_map = defaultdict(list)
    for name, url in data.items():
        url_map[url].append(name)
    
    return {url: names for url, names in url_map.items() if len(names) > 1}

def compare_json_data(current_data, previous_data):
    """Compare two JSON data structures with lists of URLs under keys."""
    differences = {
        'changes': {}
    }
    all_categories = set(current_data.keys()) | set(previous_data.keys())
    category_changes = {}

    for category in all_categories:
        current_urls = set(current_data.get(category, []))
        previous_urls = set(previous_data.get(category, []))

        added_urls = sorted(list(current_urls - previous_urls))
        removed_urls = sorted(list(previous_urls - current_urls))

        if added_urls or removed_urls:
            category_changes[category] = {}
            if added_urls:
                category_changes[category]['added'] = added_urls
            if removed_urls:
                category_changes[category]['removed'] = removed_urls
    
    if category_changes:
        differences['changes'] = category_changes
        
    return differences

def save_comparison_results(country, results, today_date):
    """Save comparison results to a JSON file"""
    output_dir = os.path.join(country, today_date, "Category")
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{country}_category_comparison.json")
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    return filename

def compare_with_previous_data(countries, today_date):
    """Compare today's data with previous data for all countries"""
    for country in countries:
        country_path = os.path.join(country)
        current_file = os.path.join(country_path, today_date, "Category", f"{country}_category.json")
        
        if not os.path.exists(current_file):
            print(f"No current data found for {country}")
            continue
        
        previous_date = find_previous_date_folder(country_path, today_date)
        if not previous_date:
            print(f"No previous data found for {country}")
            continue
        
        previous_file = os.path.join(country_path, previous_date, "Category", f"{country}_category.json")
        
        print(f"\nComparing {country} ({today_date} vs {previous_date})")
        
        try:
            with open(current_file, 'r') as f:
                current_data = json.load(f)
            with open(previous_file, 'r') as f:
                previous_data = json.load(f)
            
            results = compare_json_data(current_data, previous_data)
            output_file = save_comparison_results(country, results, today_date)
            print(f"Results saved to {output_file}")
        
        except Exception as e:
            print(f"Error processing {country}: {str(e)}")

def check_category_urls(country, today_date):
    """Check if category URLs exist for all countries"""
    country_path = os.path.join(country, today_date)
    category_file = os.path.join(country_path, f"{country}_category_links.json")
    if not os.path.exists(category_file):
        return False
    else:
        return True
    
def check_comparison_results_data(countries, today_date):
    """Check if comparison results exist for all countries"""
    country_wise_status = {}
    for country in countries:
        # Read the comparison results file
        comparison_file = os.path.join(country, today_date, "Category", f"{country}_category_comparison.json")
        if not os.path.exists(comparison_file):
            print(f"No comparison results found for {country} on {today_date}")
            country_wise_status[country] = False
        else:
            with open(comparison_file, 'r') as f:
                data = json.load(f)
                if not data.get('changes'):
                    print(f"No changes found in comparison results for {country} on {today_date}")
                    country_wise_status[country] = True
                else:
                    print(f"Changes found in comparison results for {country} on {today_date}")
                    country_wise_status[country] = False
    return country_wise_status

def remove_duplicate_urls(countries, today_date, level='category'):
    """
    Remove duplicate URLs from JSON data, handling both 'category' and 'product' levels.
    Returns True if duplicates were found and removed, False otherwise.
    """
    duplicates_found = False
    if level == 'category':
        for country in countries:
            try:
                country_path = os.path.join(country, today_date, "Category")
                file_path = os.path.join(country_path, f"{country}_category.json")
                if not os.path.exists(file_path):
                    continue
                with open(file_path, 'r') as f:
                    data = json.load(f)

                seen_urls = set()
                cleaned_data = {}
                duplicates_log = []

                # Helper to clean URL for comparison (remove ID suffix)
                def clean_url_for_comparison(url):
                    base_url = url.split('?')[0]
                    match = re.search(r'(_[a-zA-Z0-9]+)$', base_url)
                    if match:
                        return base_url[:match.start()]
                    return base_url

                for category, urls in data.items():
                    # 1. Filter out /h/ URLs
                    filtered_urls = [url for url in urls if '/h/' not in url]
                    
                    # 2. Parent/Child filtering (Inverted: Remove Parent if Child exists)
                    # We need to check if a URL is a parent of ANY other URL in the list.
                    # If yes, remove it.
                    # If no, keep it.
                    
                    urls_to_remove = set()
                    
                    # Pre-calculate clean URLs for comparison
                    # We use a list of tuples (original, clean) to avoid re-cleaning
                    url_pairs = [(url, clean_url_for_comparison(url)) for url in filtered_urls]
                    
                    for i, (parent_url, parent_clean) in enumerate(url_pairs):
                        for j, (child_url, child_clean) in enumerate(url_pairs):
                            if i == j:
                                continue
                            
                            # Check if parent
                            # Parent clean path + '/' must be prefix of child clean path
                            if child_clean.startswith(parent_clean + '/'):
                                urls_to_remove.add(parent_url)
                                duplicates_log.append({"path": category, "url": parent_url, "reason": f"Parent of {child_url} (Removed to prefer child)"})
                                break
                    
                    accepted_urls = []
                    for url in filtered_urls:
                        if url not in urls_to_remove:
                            if url not in seen_urls:
                                seen_urls.add(url)
                                accepted_urls.append(url)
                            else:
                                duplicates_log.append({"path": category, "url": url, "reason": "Duplicate"})
                    
                    cleaned_data[category] = accepted_urls

                with open(file_path, 'w') as f:
                    json.dump(cleaned_data, f, indent=4)

                if duplicates_log:
                    duplicates_found = True
                    log_path = os.path.join(country_path, f"{country}_duplicate_urls.json")
                    with open(log_path, 'w') as f:
                        json.dump(duplicates_log, f, indent=2)
            except Exception as e:
                print(f"Error removing category duplicates for {country}: {e}")

    elif level == 'product':
        for country in countries:
            try:
                country_path = os.path.join(country, today_date, "Item_urls")
                file_path = os.path.join(country_path, f"{country}_product_links.json")
                if not os.path.exists(file_path):
                    continue
                with open(file_path, 'r') as f:
                    data = json.load(f)

                seen_urls = set()
                duplicates_log = []
                
                def process_level(d, path=[]):
                    if isinstance(d, dict):
                        return {key: process_level(value, path + [key]) for key, value in d.items()}
                    elif isinstance(d, list):
                        unique_urls = []
                        for url in d:
                            if url not in seen_urls:
                                seen_urls.add(url)
                                unique_urls.append(url)
                            else:
                                duplicates_log.append({"removed_from": " > ".join(path), "url": url})
                        return unique_urls
                    return d
                cleaned_data = process_level(data)

                with open(file_path, 'w') as f:
                    json.dump(cleaned_data, f, indent=4)
                
                if duplicates_log:
                    duplicates_found = True
                    log_path = os.path.join(country_path, f"{country}_duplicate_product_urls.json")
                    with open(log_path, 'w') as f:
                        json.dump(duplicates_log, f, indent=2)
            
            except Exception as e:
                print(f"Error removing product duplicates for {country}: {e}")
    else:
        print(f"Unknown level for remove_duplicate_urls: {level}")
        
    return duplicates_found


def compare_product_links(countries, today_date):
    """Compare today's product links with previous day's product links and log the counts and deviation."""
    for country in countries:
        try:
            country_path = os.path.join(country)
            current_file_path = os.path.join(country_path, today_date, 'Item_urls', f"{country}_product_links.json")

            if not os.path.exists(current_file_path):
                print(f"No current product links file found for {country} on {today_date}")
                continue

            previous_date = find_previous_date_folder(country_path, today_date)
            if not previous_date:
                print(f"No previous product links folder found for {country}")
                continue

            previous_file_path = os.path.join(country_path, previous_date, 'Item_urls', f"{country}_product_links.json")

            if not os.path.exists(previous_file_path):
                print(f"No previous product links file found for {country} in folder {previous_date}")
                continue

            with open(current_file_path, 'r') as f:
                current_data = json.load(f)
            with open(previous_file_path, 'r') as f:
                previous_data = json.load(f)

            log_file_path = os.path.join(country_path, today_date, 'Item_urls', f"{country}_product_link_comparison_log.json")
            
            log_data = {
                "country": country,
                "comparison_period": {
                    "previous_date": previous_date,
                    "current_date": today_date
                },
                "comparison_results": []
            }

            # --- Recursive comparison function ---
            def compare_levels(prev, curr, path=[]):
                all_keys = set(prev.keys()) | set(curr.keys())
                for key in all_keys:
                    current_path = path + [key]
                    prev_value = prev.get(key)
                    curr_value = curr.get(key)

                    if isinstance(prev_value, dict) or isinstance(curr_value, dict):
                        compare_levels(prev_value or {}, curr_value or {}, current_path)
                    elif isinstance(prev_value, list) or isinstance(curr_value, list):
                        prev_list = prev_value or []
                        curr_list = curr_value or []
                        
                        prev_count = len(prev_list)
                        curr_count = len(curr_list)

                        deviation = 0.0
                        if prev_count > 0:
                            deviation = ((curr_count - prev_count) / prev_count) * 100
                        elif curr_count > 0:
                            deviation = 100.0
                        
                        status = "OK"
                        if deviation > 5.0: status = f"Warning: Deviation is {deviation:.2f}% higher"
                        elif deviation < -5.0: status = f"Warning: Deviation is {deviation:.2f}% lower"
                        
                        log_data["comparison_results"].append({
                            "category_path": " > ".join(current_path),
                            "previous_count": prev_count,
                            "current_count": curr_count,
                            "deviation_percent": round(deviation, 2),
                            "status": status
                        })

            compare_levels(previous_data, current_data)

            # --- Final Summary Calculation ---
            total_previous_count = sum(item['previous_count'] for item in log_data['comparison_results'])
            total_current_count = sum(item['current_count'] for item in log_data['comparison_results'])

            final_deviation = 0.0
            if total_previous_count > 0:
                final_deviation = ((total_current_count - total_previous_count) / total_previous_count) * 100
            elif total_current_count > 0:
                final_deviation = 100.0

            final_status = f"OK: Final deviation is {final_deviation:.2f}%"
            if final_deviation > 5.0:
                final_status = f"Warning: Final deviation {final_deviation:.2f}% is 5% higher"
            elif final_deviation < -5.0:
                final_status = f"Warning: Final deviation {final_deviation:.2f}% is 5% lower"

            log_data["final_summary"] = {
                "total_previous_count": total_previous_count,
                "total_current_count": total_current_count,
                "final_deviation_percent": round(final_deviation, 2),
                "status": final_status
            }

            with open(log_file_path, 'w') as log_file:
                json.dump(log_data, log_file, indent=4)
            
            print(f"Product link comparison log created for {country} at: {log_file_path}")

        except Exception as e:
            print(f"Error comparing product links for {country}: {e}")


def summarize_product_url_changes(countries, today_date):
    """
    For each country, compare today's product links with the most recent previous day's product links
    and write a JSON summary that includes counts and lists of new and removed URLs.
    """
    for country in countries:
        try:
            country_path = os.path.join(country)
            current_file_path = os.path.join(country_path, today_date, 'Item_urls', f"{country}_product_links.json")

            if not os.path.exists(current_file_path):
                print(f"No current product links file found for {country} on {today_date}")
                continue

            previous_date = find_previous_date_folder(country_path, today_date)
            if not previous_date:
                print(f"No previous product links folder found for {country}. Skipping summary.")
                continue

            previous_file_path = os.path.join(country_path, previous_date, 'Item_urls', f"{country}_product_links.json")
            if not os.path.exists(previous_file_path):
                print(f"No previous product links file found for {country} in folder {previous_date}")
                continue

            with open(current_file_path, 'r') as f:
                current_data = json.load(f)
            with open(previous_file_path, 'r') as f:
                previous_data = json.load(f)

            # --- Helper function to extract all URLs from the nested structure ---
            def extract_urls(data):
                urls = set()
                if isinstance(data, dict):
                    for value in data.values():
                        urls.update(extract_urls(value))
                elif isinstance(data, list):
                    urls.update(data)
                return urls

            previous_urls = extract_urls(previous_data)
            current_urls = extract_urls(current_data)

            new_urls = sorted(list(current_urls - previous_urls))
            removed_urls = sorted(list(previous_urls - current_urls))

            summary = {
                "country": country,
                "comparison_period": {
                    "previous_date": previous_date,
                    "current_date": today_date
                },
                "previous_total_count": len(previous_urls),
                "current_total_count": len(current_urls),
                "new_count": len(new_urls),
                "removed_count": len(removed_urls),
                "new_urls": new_urls,
                "removed_urls": removed_urls
            }

            out_dir = os.path.join(country_path, today_date, 'Item_urls')
            os.makedirs(out_dir, exist_ok=True)
            out_file = os.path.join(out_dir, f"{country}_product_link_changes_summary.json")

            with open(out_file, 'w') as outf:
                json.dump(summary, outf, indent=2)

            print(f"Product URL changes summary created for {country} at: {out_file}")

        except Exception as e:
            print(f"Error summarizing product URL changes for {country}: {e}")


def count_urls_in_json(data):
    """Recursively counts the number of URLs in a nested dictionary/list structure."""
    count = 0
    if isinstance(data, dict):
        for value in data.values():
            count += count_urls_in_json(value)
    elif isinstance(data, list):
        # Basic check to see if items in the list look like URLs
        count += len([item for item in data if isinstance(item, str) and item.startswith('http')])
    return count

def extract_pid_from_url(url):
    """Extracts the Product ID from a Mango URL."""
    if not isinstance(url, str):
        return None
        
    # Handle ...p12345.html format
    match = re.search(r'p(\d+)\.html', url)
    if match:
        return match.group(1)
        
    # Handle ..._ID format (common in Mango URLs)
    base_url = url.split('?')[0]
    match = re.search(r'_(\d+)$', base_url)
    if match:
        return match.group(1)
        
    # Handle .../ID format
    match = re.search(r'/(\d+)$', base_url.rstrip('/'))
    if match:
        return match.group(1)
        
    return None

def check_deviation(log_file_path, total_urls_file_path):
    """
    Calculates the deviation between total URLs and successfully scraped URLs.
    Deviation is defined as the percentage of URLs that were not successfully scraped.
    Also saves a summary report with a list of failed URLs.
    """
    # Load the log file
    if not os.path.exists(log_file_path):
        print(f"Log file not found at {log_file_path}")
        return 100.0  # If no log, 100% are pending/failed

    log_data = {}
    with open(log_file_path, 'r', encoding='utf-8') as f:
        try:
            log_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Could not decode JSON from log file: {log_file_path}")
            pass

    # Load the total URLs file
    if not os.path.exists(total_urls_file_path):
        print(f"Total URLs file not found at {total_urls_file_path}")
        return -1.0 

    with open(total_urls_file_path, 'r', encoding='utf-8') as f:
        try:
            total_urls_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Could not decode JSON from total URLs file: {total_urls_file_path}")
            return -1.0

    # Extract all URLs from the total URLs file
    all_expected_urls = set()
    
    def collect_urls(data):
        if isinstance(data, dict):
            for value in data.values():
                collect_urls(value)
        elif isinstance(data, list):
            for url in data:
                if isinstance(url, str):
                    all_expected_urls.add(url)

    collect_urls(total_urls_data)
    
    total_urls = len(all_expected_urls)

    # Identify successful URLs from the log
    successful_urls = set()
    for url, status in log_data.items():
        if status == 'success':
            successful_urls.add(url)
            
    successful_scrapes = len(successful_urls)

    # Identify failed URLs (present in expected but not successful in log)
    failed_urls = sorted(list(all_expected_urls - successful_urls))
    failed_count = len(failed_urls)

    # Calculate deviation
    if total_urls == 0:
        deviation = 0.0
    else:
        deviation = ((total_urls - successful_scrapes) / total_urls) * 100

    # Create and save summary
    try:
        # Derive country from the log file path, assuming path is like: COUNTRY/DATE/...
        country = log_file_path.split(os.sep)[0]
        summary = {
            "Total_Url_Count": total_urls,
            "Total_Scraped_Count": successful_scrapes,
            "Total_Failed_Count": failed_count,
            "Deviation_Percent": round(deviation, 2),
            "Failed_Urls": failed_urls
        }
        summary_dir = os.path.dirname(log_file_path)
        summary_file_path = os.path.join(summary_dir, f'{country}_scrap_summary.json')

        with open(summary_file_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=4)
        print(f"Scraping summary saved to {summary_file_path}")

    except Exception as e:
        print(f"Error saving scraping summary: {e}")

    return deviation

