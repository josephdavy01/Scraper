import os
import json
from datetime import datetime
from collections import defaultdict
import requests
import random

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

def find_duplicate_urls(data):
    """Find duplicate URLs within the same data"""
    url_map = defaultdict(list)
    for category, items in data.items():
        for name, url in items.items():
            url_map[url].append(f"{category} > {name}")
    
    return {url: names for url, names in url_map.items() if len(names) > 1}

def compare_json_data(current_data, previous_data):
    """Compare two JSON data structures with enhanced detection"""
    differences = {
        'metadata': {
            'duplicates': {
                'current': find_duplicate_urls(current_data),
                'previous': find_duplicate_urls(previous_data)
            },
            'renamed_items': []
        },
        'changes': defaultdict(dict)
    }
    
    # Create URL to key mapping
    previous_url_map = defaultdict(list)
    current_url_map = defaultdict(list)
    
    for cat, items in previous_data.items():
        for name, url in items.items():
            previous_url_map[url].append(f"{cat} > {name}")
    
    for cat, items in current_data.items():
        for name, url in items.items():
            current_url_map[url].append(f"{cat} > {name}")
    
    # Detect renamed items
    common_urls = set(previous_url_map.keys()) & set(current_url_map.keys())
    for url in common_urls:
        prev_names = previous_url_map[url]
        curr_names = current_url_map[url]
        if set(prev_names) != set(curr_names):
            differences['metadata']['renamed_items'].append({
                'url': url,
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
        for name, url in previous_cat.items():
            if name not in current_cat and not any(url in items for items in current_url_map.values()):
                diff['removed'][name] = url
        
        # Find added and modified items
        for name, url in current_cat.items():
            if name not in previous_cat and not any(url in items for items in previous_url_map.values()):
                diff['added'][name] = url
            elif name in previous_cat and url != previous_cat[name]:
                diff['modified'][name] = {
                    'old': previous_cat[name],
                    'new': url
                }
        
        # Remove empty sections
        category_diff = {k: v for k, v in diff.items() if v}
        if category_diff:
            differences['changes'][category] = category_diff
    
    return differences

def save_comparison_results(country, results, today_date):
    """Save comparison results to a JSON file"""
    filename = f"{country}/{today_date}/Category/{country}_category_comparison.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
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
            with open(comparison_file, 'r') as f:
                data = json.load(f)
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
            
            with open(category_file, 'r') as f:
                data = json.load(f)
            
            print(f"Removed duplicates from {country} category links.")
            seen_urls = set()
            cleaned_data = {}
            
            for category, items in data.items():
                cleaned_items = {}
                for name, url in items.items():
                    if url not in seen_urls:
                        seen_urls.add(url)
                        cleaned_items[name] = url
                    else:
                        print(f"Removing duplicate: {category} > {name} ({url})")
                        # Save the duplicate information
                        with open(f"{country_path}\{country}_duplicate_urls.txt", 'a') as dup_file:
                            dup_file.write(f"{category} > {name}: {url}\n")
                cleaned_data[category] = cleaned_items

            # Save cleaned data back to the file
            with open(category_file, 'w') as f:
                json.dump(cleaned_data, f, indent=2)
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
            
            with open(product_file, 'r') as f:
                data = json.load(f)
            
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
                            with open(duplicate_log_path, 'a') as dup_file:
                                dup_file.write(f"{category} > {product_type}: {url}\n")
                    cleaned_items[product_type] = unique_urls
                cleaned_data[category] = cleaned_items

            # Save cleaned data back to the file
            with open(product_file, 'w') as f:
                json.dump(cleaned_data, f, indent=2)
                print(f"Cleaned product data saved for {country} on {today_date}")
        return True
    except Exception as e:
        # The exception message should reference the specific country being processed
        print(f"Error removing duplicates on {today_date}: {str(e)}")
        return False

def remove_duplicate_urls_products(countries, today_date):
    """
    Remove duplicate URLs based on the EXACT URL string.
    If the same product exists in 'Trending' and 'Shirts' with different URLs,
    BOTH will be kept.
    """
    try:
        for country in countries:
            country_path = os.path.join(country, today_date, 'Item_urls')
            product_file = os.path.join(country_path, f"{country}_product_links.json")
            
            if not os.path.exists(product_file):
                print(f"No product links file found for {country} on {today_date}")
                continue
            
            with open(product_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"[{country}] Removing exact duplicate URLs...")
            
            # This set stores the full URL strings
            seen_urls = set()
            cleaned_data = {}
            
            for category, items in data.items():
                cleaned_items = {}
                for product_type, urls in items.items():
                    unique_urls = []
                    for url in urls:
                        # Clean whitespace just in case
                        clean_url = url.strip()
                        
                        # Check exact URL string
                        if clean_url not in seen_urls:
                            seen_urls.add(clean_url)
                            unique_urls.append(clean_url)
                        else:
                            # This is an EXACT duplicate (same category, same link)
                            pass
                            
                    cleaned_items[product_type] = unique_urls
                cleaned_data[category] = cleaned_items

            # Save cleaned data back to the file
            with open(product_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
                
            print(f"[{country}] Cleaned. Total unique URLs: {len(seen_urls)}")
            
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
        current_file = os.path.join(country_path, today_date, 'Item_urls', f"{country}_product_links.json")
        
        if not os.path.exists(current_file):
            print(f"No current product links found for {country}")
            continue
            
        previous_date = find_previous_date_folder(country_path, today_date)
        if not previous_date:
            print(f"No previous data found for {country}")
            continue
            
        previous_file = os.path.join(country_path, previous_date, 'Item_urls', f"{country}_product_links.json")
        
        print(f"\nComparing Product Links for {country} ({today_date} vs {previous_date})")
        
        try:
            with open(current_file, 'r') as f:
                current_data = json.load(f)
            with open(previous_file, 'r') as f:
                previous_data = json.load(f)
                
            # Flatten data for comparison: {category > product_type: [urls]}
            def flatten(data):
                flat = {}
                for gender, cats in data.items():
                    for cat, urls in cats.items():
                        key = f"{gender} > {cat}"
                        flat[key] = set(urls)
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
                curr_urls = curr_flat.get(key, set())
                prev_urls = prev_flat.get(key, set())
                
                total_curr_count += len(curr_urls)
                total_prev_count += len(prev_urls)
                
                added = list(curr_urls - prev_urls)
                removed = list(prev_urls - curr_urls)
                
                if added or removed:
                    comparison_log["changes"][key] = {
                        "added_count": len(added),
                        "removed_count": len(removed),
                        "added_urls": added,
                        "removed_urls": removed
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
            with open(log_file, 'w') as f:
                json.dump(comparison_log, f, indent=4)
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
                with open(log_file, 'r') as f:
                    data = json.load(f)
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
            with open(file_path, 'r') as f:
                data = json.load(f)
            # Assuming the file has a 'deviation' key or similar logic
            return data.get('deviation', 0.0)
    except:
        pass
    return 0.0