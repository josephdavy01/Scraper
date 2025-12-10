import os
import json
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
    filename = f"{country}/{today_date}/{country}_category_comparison.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    return filename

def compare_with_previous_data(countries, today_date):
    """Compare today's data with previous data for all countries"""
    for country in countries:
        country_path = os.path.join(country)
        current_file = os.path.join(country_path, today_date, f"{country}_category_links.json")
        
        if not os.path.exists(current_file):
            print(f"No current data found for {country}")
            continue
        
        previous_date = find_previous_date_folder(country_path, today_date)
        if not previous_date:
            print(f"No previous data found for {country}")
            continue
        
        previous_file = os.path.join(country_path, previous_date, f"{country}_category_links.json")
        
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
    for country, url in countries.items():
        # Read the comparison results file
        comparison_file = os.path.join(country, today_date, f"{country}_category_comparison.json")
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
            category_file = os.path.join(country_path, f"{country}_category_links.json")
            
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
                        with open(f"{country_path}/{country}_duplicate_urls.txt", 'a') as dup_file:
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
    

def remove_duplicate_urls_products(countries, today_date):
    """
    Remove duplicate URLs by normalizing them to a base product ID.
    Keeps the first URL encountered for each unique product ID.
    """

    def get_base_product_id(url):
        """Extracts the core product identifier from the URL slug (e.g., 'w51154r')."""
        try:
            # Gets the last part of the URL path (e.g., 'w51154r-airlift-high-waist-7-8-line-up-legging-navy')
            slug = url.rstrip('/').split('/')[-1]
            # Returns the part before the first hyphen
            return slug.split('-')[0]
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

            total_previous_count = 0
            total_current_count = 0
            all_categories = set(previous_data.keys()) | set(current_data.keys())

            for gender in all_categories:
                previous_gender_data = previous_data.get(gender, {})
                current_gender_data = current_data.get(gender, {})
                all_subcategories = set(previous_gender_data.keys()) | set(current_gender_data.keys())

                for subcat in all_subcategories:
                    previous_links = previous_gender_data.get(subcat, [])
                    current_links = current_gender_data.get(subcat, [])
                    
                    previous_count = len(previous_links)
                    current_count = len(current_links)
                    
                    total_previous_count += previous_count
                    total_current_count += current_count
                    
                    deviation = 0.0
                    
                    if previous_count > 0:
                        deviation = ((current_count - previous_count) / previous_count) * 100
                    elif current_count > 0:
                        deviation = 100.0
                    
                    if deviation > 5.0:
                        status = f"Warning: Todays deviation {deviation:.2f}% is 5% higher"
                    elif deviation < -5.0:
                        status = f"Warning: Todays deviation {deviation:.2f}% is 5% lower"
                    else:
                        status = f"OK: Todays deviation is {deviation:.2f}%"
                    
                    log_entry = {
                        "category": f"{gender.lower()}-{subcat.replace(' ', '-')}",
                        "previous_count": previous_count,
                        "current_count": current_count,
                        "deviation_percent": round(deviation, 2),
                        "status": status
                    }
                    log_data["comparison_results"].append(log_entry)

            final_deviation = 0.0
            if total_previous_count > 0:
                final_deviation = ((total_current_count - total_previous_count) / total_previous_count) * 100
            elif total_current_count > 0:
                final_deviation = 100.0

            if final_deviation > 5.0:
                final_status = f"Warning: Final deviation {final_deviation:.2f}% is 5% higher"
            elif final_deviation < -5.0:
                final_status = f"Warning: Final deviation {final_deviation:.2f}% is 5% lower"
            else:
                final_status = f"OK: Final deviation is {final_deviation:.2f}%"

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
    The output file is saved to: <country>/<today_date>/Item_urls/<country>_product_link_changes_summary.json
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


            # Build maps from normalized base product URL -> set(full_urls)
            def get_base_product_url(url):
                """Normalize URL to base product identifier, e.g.
                https://.../products/m5001r-chill... -> https://.../products/m5001r
                Returns original url if '/products/' not found.
                """
                try:
                    parts = url.split('/products/')
                    if len(parts) < 2:
                        return url
                    prefix = parts[0] + '/products/'
                    rest = parts[1]
                    # product id is up to first '-' or '/' in the rest
                    prod_id = rest.split('-')[0].split('/')[0]
                    return prefix + prod_id
                except Exception:
                    return url

            def build_base_map(data):
                base_map = defaultdict(set)
                # data structure: gender -> subcat -> list_of_urls (or nested dicts)
                for gender, subcats in data.items():
                    if isinstance(subcats, dict):
                        for subcat, items in subcats.items():
                            if isinstance(items, list):
                                for u in items:
                                    base = get_base_product_url(u)
                                    base_map[base].add(u)
                            elif isinstance(items, dict):
                                for v in items.values():
                                    if isinstance(v, list):
                                        for u in v:
                                            base = get_base_product_url(u)
                                            base_map[base].add(u)
                    elif isinstance(subcats, list):
                        for u in subcats:
                            base = get_base_product_url(u)
                            base_map[base].add(u)
                return base_map

            prev_map = build_base_map(previous_data)
            curr_map = build_base_map(current_data)

            prev_set = set(prev_map.keys())
            curr_set = set(curr_map.keys())

            # Determine base product ids that are new / removed
            new_bases = sorted(list(curr_set - prev_set))
            removed_bases = sorted(list(prev_set - curr_set))

            # For lists, pick a representative full URL for each base id
            new_urls = [sorted(list(curr_map[b]))[0] for b in new_bases]
            removed_urls = [sorted(list(prev_map[b]))[0] for b in removed_bases]

            summary = {
                "country": country,
                "comparison_period": {
                    "previous_date": previous_date,
                    "current_date": today_date
                },
                "previous_total_count": len(prev_set),
                "current_total_count": len(curr_set),
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


def check_deviation(file_path):
    """
    Checks the deviation of failed items in a global progress JSON file.

    Args:
        file_path (str): The path to the global progress JSON file.

    Returns:
        float: The percentage of failed items, or 0.0 if the file doesn't exist.
    """
    if not os.path.exists(file_path):
        print(f"Progress file not found: {file_path}")
        return 0.0

    with open(file_path, 'r') as f:
        data = json.load(f)

    success_count = len(data.get('successfully_processed', []))
    failed_count = len(data.get('failed_processed', []))
    total_count = success_count + failed_count

    if total_count == 0:
        return 0.0

    deviation = (failed_count / total_count) * 100
    return deviation

