import os
import json
import logging
from datetime import datetime
from collections import defaultdict
import requests
import random

# --- Global Utilities (Moved from utils.py) ---

def save_json(path, data, **kwargs):
    """Saves data to a JSON file, creating directories if needed."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False, **kwargs)
    except Exception as e:
        logging.error(f"Error saving JSON to {path}: {e}")

def load_json(path):
    """Loads data from a JSON file."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading JSON from {path}: {e}")
        return {}

def append_log(path, message):
    """Appends a message to a log file."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(message + '\n')
    except Exception as e:
        logging.error(f"Error appending to log {path}: {e}")

def log_success(path, item):
    """Logs a success message."""
    append_log(path, f"SUCCESS|{item}")

def log_failure(path, item, reason):
    """Logs a failure message."""
    append_log(path, f"FAILURE|{item}|{reason}")

def load_logged_set(path):
    """Loads a set of logged items for resumability."""
    processed = set()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('|')
                    if len(parts) >= 2:
                        processed.add(parts[1]) 
        except Exception as e:
            logging.error(f"Error loading log {path}: {e}")
    return processed

# --- End Global Utilities ---

USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]


def find_previous_date_folder(country_path, current_date):
    """Find the most recent previous date folder in the country directory"""
    date_folders = []
    if not os.path.exists(country_path):
        return None
        
    for folder in os.listdir(country_path):
        if os.path.isdir(os.path.join(country_path, folder)) and folder != current_date:
            try:
                date_obj = datetime.strptime(folder, "%Y-%m-%d")
                date_folders.append((date_obj, folder))
            except ValueError:
                continue
    
    if not date_folders:
        return None
    
    date_folders.sort(reverse=True)
    return date_folders[0][1]

def find_duplicate_ids(data):
    """Find duplicate IDs within the same data"""
    id_map = defaultdict(list)
    for category, items in data.items():
        for name, item in items.items():
            # Handle both string URLs (old format - shouldn't happen but safe to keep) and dict items (new format)
            if isinstance(item, dict):
                item_id = item.get('id')
                if item_id:
                    id_map[item_id].append(f"{category} > {name}")
            # If it's just a URL string, we can't really check ID duplicates, so ignore or handle differently.
            # Assuming new format is dominant now.
    
    return {item_id: names for item_id, names in id_map.items() if len(names) > 1}

def compare_json_data(current_data, previous_data):
    """Compare two JSON data structures with enhanced detection using IDs"""
    differences = {
        'metadata': {
            'duplicates': {
                'current': find_duplicate_ids(current_data),
                'previous': find_duplicate_ids(previous_data)
            },
            'renamed_items': []
        },
        'changes': defaultdict(dict)
    }
    
    # Create ID to key mapping
    previous_id_map = defaultdict(list)
    current_id_map = defaultdict(list)
    
    for cat, items in previous_data.items():
        for name, item in items.items():
            if isinstance(item, dict):
                item_id = item.get('id')
                if item_id:
                    previous_id_map[item_id].append(f"{cat} > {name}")
    
    for cat, items in current_data.items():
        for name, item in items.items():
            if isinstance(item, dict):
                item_id = item.get('id')
                if item_id:
                    current_id_map[item_id].append(f"{cat} > {name}")
    
    # Detect renamed items (same ID, different name/path)
    common_ids = set(previous_id_map.keys()) & set(current_id_map.keys())
    for item_id in common_ids:
        prev_names = previous_id_map[item_id]
        curr_names = current_id_map[item_id]
        if set(prev_names) != set(curr_names):
            differences['metadata']['renamed_items'].append({
                'id': item_id,
                'from': prev_names,
                'to': curr_names
            })
    
    # Standard comparison by category
    all_categories = set(current_data.keys()) | set(previous_data.keys())
    
    for category in all_categories:
        current_cat = current_data.get(category, {})
        previous_cat = previous_data.get(category, {})
        
        diff = {
            'removed': {},
            'added': {},
            'modified': {}
        }
        
        # Find removed items (in previous but not in current)
        for name, item in previous_cat.items():
            if isinstance(item, dict):
                item_id = item.get('id')
                # If name is gone, and this ID is not found anywhere else in current data
                if name not in current_cat and not any(item_id in items for items in current_id_map.values()):
                    diff['removed'][name] = item
            else:
                # Fallback for old string format if any
                pass
        
        # Find added and modified items
        for name, item in current_cat.items():
            if isinstance(item, dict):
                item_id = item.get('id')
                item_url = item.get('url')
                
                # Added: Name not in previous, and ID not found anywhere in previous
                if name not in previous_cat and not any(item_id in items for items in previous_id_map.values()):
                    diff['added'][name] = item
                
                # Modified: Name exists, check if URL changed for the same ID
                elif name in previous_cat:
                    prev_item = previous_cat[name]
                    if isinstance(prev_item, dict):
                        prev_url = prev_item.get('url')
                        if item_url != prev_url:
                            diff['modified'][name] = {
                                'old_url': prev_url,
                                'new_url': item_url
                            }
        
        # Remove empty sections
        category_diff = {k: v for k, v in diff.items() if v}
        if category_diff:
            differences['changes'][category] = category_diff
    
    return differences

def save_comparison_results(country, results, today_date):
    """Save comparison results to a JSON file"""
    filename = f"{country}/{today_date}/Category/{country}_category_comparison.json"
    save_json(filename, results) # Use the global save_json
    return filename

def compare_with_previous_data(countries, today_date):
    """Compare today's data with previous data for all countries"""
    for country in countries:
        country_path = os.path.join(country)
        # Corrected filename to match step1 output
        current_file = os.path.join(country_path, today_date, 'Category', f"{country}_category_urls.json")
        
        if not os.path.exists(current_file):
            print(f"No current data found for {country}")
            continue
        
        previous_date = find_previous_date_folder(country_path, today_date)
        if not previous_date:
            print(f"No previous data found for {country}")
            continue
        
        # Corrected filename to match step1 output
        previous_file = os.path.join(country_path, previous_date, 'Category', f"{country}_category_urls.json")
        
        print(f"\nComparing {country} ({today_date} vs {previous_date})")
        
        try:
            current_data = load_json(current_file) # Use global load_json
            previous_data = load_json(previous_file) # Use global load_json
            
            results = compare_json_data(current_data, previous_data)
            output_file = save_comparison_results(country, results, today_date)
            print(f"Results saved to {output_file}")
        
        except Exception as e:
            print(f"Error processing {country}: {str(e)}")

def check_category_urls(country, today_date):
    """Check if category URLs exist for all countries"""
    country_path = os.path.join(country, today_date)
    # Corrected filename to match step1 output
    category_file = os.path.join(country_path, 'Category', f"{country}_category_urls.json")
    if not os.path.exists(category_file):
        return False
    else:
        return True
    
def check_comparison_results_data(countries, today_date):
    """Check if comparison results exist for all countries"""
    country_wise_status = {}
    for country, url in countries.items():
        # Read the comparison results file
        comparison_file = os.path.join(country, today_date, 'Category', f"{country}_category_comparison.json")
        if not os.path.exists(comparison_file):
            print(f"No comparison results found for {country} on {today_date}")
            country_wise_status[country] = False
        else:
            data = load_json(comparison_file) # Use global load_json
            if not data.get('changes'):
                print(f"No changes found in comparison results for {country} on {today_date}")
                country_wise_status[country] = True
            else:
                print(f"Changes found in comparison results for {country} on {today_date}")
                country_wise_status[country] = False
    return country_wise_status

def remove_duplicate_urls(countries, today_date):
    """Remove duplicate URLs from the JSON data while preserving structure"""
    try:
        for country in countries:
            country_path = os.path.join(country, today_date)
            # Corrected filename to match step1 output
            category_file = os.path.join(country_path, 'Category', f"{country}_category_urls.json")
            
            if not os.path.exists(category_file):
                print(f"No category links file found for {country} on {today_date}")
                continue
            
            data = load_json(category_file) # Use global load_json
            
            print(f"Removed duplicates from {country} category links.")
            seen_ids = set()
            cleaned_data = {}
            
            for category, items in data.items():
                cleaned_items = {}
                for name, item in items.items():
                    # Handle both string URLs and dict items
                    if isinstance(item, dict):
                        item_id = item.get('id')
                        item_url = item.get('url') # For logging
                        
                        if item_id:
                            if item_id not in seen_ids:
                                seen_ids.add(item_id)
                                cleaned_items[name] = item # Keep the original item structure
                            else:
                                print(f"Removing duplicate ID: {category} > {name} (ID: {item_id})")
                                # Save the duplicate information
                                append_log(os.path.join(country_path, f"{country}_duplicate_urls.txt"), f"{category} > {name}: ID {item_id}, URL {item_url}")
                        else:
                             # If no ID, we can't really dedupe by ID. Keep it? Or fallback to URL?
                             # Assuming ID is mandatory now. If missing, maybe log warning.
                             # For now, let's keep it to be safe, or maybe it's a bad item.
                             cleaned_items[name] = item
                    else:
                        # Fallback for old string format
                        cleaned_items[name] = item

                cleaned_data[category] = cleaned_items

            # Save cleaned data back to the file
            save_json(category_file, cleaned_data) # Use global save_json
            print(f"Cleaned data saved for {country} on {today_date}")
        return True
    except Exception as e:
        print(f"Error removing duplicates for {country} on {today_date}: {str(e)}")
        return False
    
    """
    Remove duplicate URLs by normalizing them to a base product ID.
    Keeps the first URL encountered for each unique product ID.
    """

    def get_base_product_id(url):
        """Extracts the core product identifier from the URL slug."""
        try:
            # Remove query parameters first
            base_url = url.split('?')[0]
            # Get the last part of the path
            slug = base_url.rstrip('/').split('/')[-1]
            return slug
        except IndexError:
            # Fallback in case there's an issue with the URL format
            return url 

    try:
        # Correctly loop through the list of countries
        for country in countries:
            country_path = os.path.join(country, today_date, 'Item_urls')
            product_file = os.path.join(country_path, f"{country}_product_links.json")
            
            if not os.path.exists(product_file):
                print(f"No product links file found for {country} on {today_date}")
                continue
            
            data = load_json(product_file) # Use global load_json
            
            print(f"Removing duplicates from {country} product links.")
            # This set will now store the base product IDs that have been seen
            seen_product_ids = set()
            cleaned_data = {}
            
            for category, items in data.items():
                cleaned_items = {}
                for product_type, urls in items.items():
                    unique_urls = []
                    for url in urls:
                        # Get the normalized base ID for the current URL
                        base_id = get_base_product_id(url)
                        
                        # Check if this base ID has been seen before
                        if base_id not in seen_product_ids:
                            # If not, add the ID to the set and keep the URL
                            seen_product_ids.add(base_id)
                            unique_urls.append(url)
                        else:
                            # If the ID has been seen, it's a duplicate
                            print(f"Removing duplicate for product ID '{base_id}': {url}")
                            # Use os.path.join for creating the log file path
                            duplicate_log_path = os.path.join(country_path, f"{country}_duplicate_product_urls.txt")
                            append_log(duplicate_log_path, f"{category} > {product_type}: {url}")
                    cleaned_items[product_type] = unique_urls
                cleaned_data[category] = cleaned_items

            # Save cleaned data back to the file
            save_json(product_file, cleaned_data) # Use global save_json
            print(f"Cleaned product data saved for {country} on {today_date}")
        return True
    except Exception as e:
        # The exception message should reference the specific country being processed
        print(f"Error removing duplicates on {today_date}: {str(e)}")
        return False

def remove_duplicate_urls_products(countries, today_date):
    """
    Remove duplicate product IDs based on the EXACT ID.
    Works with product ID arrays instead of URL arrays.
    """
    try:
        for country in countries:
            country_path = os.path.join(country, today_date, 'Item_urls')
            product_file = os.path.join(country_path, f"{country}_product_ids.json")
            
            if not os.path.exists(product_file):
                print(f"No product IDs file found for {country} on {today_date}")
                continue
            
            data = load_json(product_file) # Use global load_json
            
            print(f"[{country}] Removing exact duplicate product IDs...")
            
            # This set stores product IDs
            seen_ids = set()
            cleaned_data = {}
            
            for gender, categories in data.items():
                cleaned_categories = {}
                for category, product_ids in categories.items():
                    unique_ids = []
                    for pid in product_ids:
                        # Check exact product ID
                        if pid not in seen_ids:
                            seen_ids.add(pid)
                            unique_ids.append(pid)
                        else:
                            # This is an EXACT duplicate
                            pass
                            
                    cleaned_categories[category] = unique_ids
                cleaned_data[gender] = cleaned_categories

            # Save cleaned data back to the file
            save_json(product_file, cleaned_data) # Use global save_json
                
            print(f"[{country}] Cleaned. Total unique IDs: {len(seen_ids)}")
            
        return True
    except Exception as e:
        print(f"Error removing duplicates on {today_date}: {str(e)}")
        return False
               
def compare_product_links(countries, today_date):
    """
    Compares product links between today and the previous run.
    Generates a log file with details of added/removed/modified links.
    """
    for country in countries:
        country_path = os.path.join(country)
        current_file = os.path.join(country_path, today_date, 'Item_urls', f"{country}_product_ids.json")
        
        if not os.path.exists(current_file):
            print(f"No current product IDs found for {country}")
            continue
            
        previous_date = find_previous_date_folder(os.path.join(country_path), today_date)
        if not previous_date:
            print(f"No previous data found for {country}")
            continue
            
        previous_file = os.path.join(country_path, previous_date, 'Item_urls', f"{country}_product_ids.json")
        
        print(f"\nComparing Product IDs for {country} ({today_date} vs {previous_date})")
        
        try:
            current_data = load_json(current_file) # Use global load_json
            previous_data = load_json(previous_file) # Use global load_json
                
            # Flatten data for comparison: {gender > category: set(product_ids)}
            def flatten(data):
                flat = {}
                for gender, cats in data.items():
                    for cat, product_ids in cats.items():
                        key = f"{gender} > {cat}"
                        flat[key] = set(product_ids)
                return flat

            curr_flat = flatten(current_data)
            prev_flat = flatten(previous_data)
            
            all_keys = set(curr_flat.keys()) | set(prev_flat.keys())
            
            comparison_log = {
                "metadata": {
                    "country": country,
                    "current_date": today_date,
                    "previous_date": previous_date
                },
                "changes": {}
            }
            
            total_curr_count = 0
            total_prev_count = 0
            
            for key in all_keys:
                curr_ids = curr_flat.get(key, set())
                prev_ids = prev_flat.get(key, set())
                
                total_curr_count += len(curr_ids)
                total_prev_count += len(prev_ids)
                
                added = list(curr_ids - prev_ids)
                removed = list(prev_ids - curr_ids)
                
                if added or removed:
                    comparison_log["changes"][key] = {
                        "added_count": len(added),
                        "removed_count": len(removed),
                        "added_ids": added,
                        "removed_ids": removed
                    }
            
            # Calculate deviation
            if total_prev_count > 0:
                deviation = ((total_curr_count - total_prev_count) / total_prev_count) * 100
            else:
                deviation = 100.0 if total_curr_count > 0 else 0.0
                
            comparison_log["final_summary"] = {
                "total_current_products": total_curr_count,
                "total_previous_products": total_prev_count,
                "final_deviation_percent": round(deviation, 2),
                "status": "Stable" if abs(deviation) < 10 else "High Deviation"
            }
            
            # Save log
            log_file = os.path.join(country_path, today_date, 'Item_urls', f"{country}_product_link_comparison_log.json")
            save_json(log_file, comparison_log) # Use global save_json
            print(f"Product comparison log saved to {log_file}")
            
        except Exception as e:
            print(f"Error comparing product links for {country}: {e}")

def summarize_product_url_changes(countries, today_date):
    """
    Reads the comparison log and prints a summary to the console.
    """
    for country in countries:
        log_file = os.path.join(country, today_date, 'Item_urls', f"{country}_product_link_comparison_log.json")
        if os.path.exists(log_file):
            try:
                data = load_json(log_file) # Use global load_json
                summary = data.get("final_summary", {})
                print(f"[{country}] Product Summary: {summary}")
            except Exception as e:
                print(f"Error reading summary for {country}: {e}")

def check_deviation(file_path):
    """
    Checks the deviation from a progress file (if it exists) or returns 0.
    Placeholder for logic that might read a specific progress JSON.
    """
    try:
        if os.path.exists(file_path):
            data = load_json(file_path) # Use global load_json
            # Assuming the file has a 'deviation' key or similar logic
            return data.get('deviation', 0.0)
    except:
        pass
    return 0.0