import os
import json
from datetime import datetime
from collections import defaultdict

# Import COUNTRY_MAPPING to handle case sensitivity
try:
    from master import COUNTRY_MAPPING
except ImportError:
    # Fallback if master.py is not available
    COUNTRY_MAPPING = {'india': 'India'}


def check_comparison_status(countries, verbose=True):
    """
    Diagnostic function to check what date folders exist and which ones have comparison files.
    Useful for debugging why comparisons aren't happening.
    
    Args:
        countries: Dictionary of countries to check
        verbose: If True, prints detailed status; if False, returns data only
    
    Returns:
        Dictionary with status information for each country
    """
    status = {}
    
    for country in countries:
        country_path = os.path.join(country)
        
        if not os.path.exists(country_path):
            if verbose:
                print(f"❌ Country folder '{country}' does not exist!")
            status[country] = {"exists": False, "dates": []}
            continue
        
        # Find all date folders
        date_folders = []
        for folder in os.listdir(country_path):
            folder_path = os.path.join(country_path, folder)
            if os.path.isdir(folder_path):
                try:
                    datetime.strptime(folder, "%Y-%m-%d")
                    date_folders.append(folder)
                except ValueError:
                    pass
        
        date_folders.sort()
        
        # Check comparison files for each date
        dates_info = []
        for i, date_folder in enumerate(date_folders):
            has_previous = i > 0
            previous_date = date_folders[i-1] if has_previous else None
            
            category_comp = os.path.join(country, date_folder, "Category", f"{country}_category_comparison.json")
            product_comp = os.path.join(country, date_folder, "Items_urls", f"{country}_product_comparison.json")
            
            date_info = {
                "date": date_folder,
                "has_previous": has_previous,
                "previous_date": previous_date,
                "category_comparison_exists": os.path.exists(category_comp),
                "product_comparison_exists": os.path.exists(product_comp),
                "category_comparison_path": category_comp,
                "product_comparison_path": product_comp
            }
            dates_info.append(date_info)
            
            if verbose:
                print(f"\n📅 {country.upper()} - {date_folder}:")
                if has_previous:
                    print(f"   ✅ Can compare against: {previous_date}")
                else:
                    print(f"   ❌ No previous date (comparison not possible)")
                
                print(f"   Category comparison: {'✅ EXISTS' if date_info['category_comparison_exists'] else '❌ MISSING'}")
                print(f"   Product comparison:  {'✅ EXISTS' if date_info['product_comparison_exists'] else '❌ MISSING'}")
        
        status[country] = {
            "exists": True,
            "total_dates": len(date_folders),
            "dates": dates_info
        }
    
    return status


def find_previous_date_folder(country_path, current_date):
    """Find the most recent previous date folder in the country directory"""
    date_folders = []
    current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")

    for folder in os.listdir(country_path):
        folder_path = os.path.join(country_path, folder)
        if os.path.isdir(folder_path):
            try:
                date_obj = datetime.strptime(folder, "%Y-%m-%d")
                if date_obj < current_date_obj:
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

    previous_url_map = defaultdict(list)
    current_url_map = defaultdict(list)

    for cat, items in previous_data.items():
        for name, url in items.items():
            previous_url_map[url].append(f"{cat} > {name}")

    for cat, items in current_data.items():
        for name, url in items.items():
            current_url_map[url].append(f"{cat} > {name}")

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

    all_categories = set(current_data.keys()) | set(previous_data.keys())

    for category in all_categories:
        current_cat = current_data.get(category, {})
        previous_cat = previous_data.get(category, {})

        diff = {
            'removed': {},
            'added': {},
            'modified': {}
        }

        for name, url in previous_cat.items():
            if name not in current_cat and url not in current_url_map:
                diff['removed'][name] = url

        for name, url in current_cat.items():
            if name not in previous_cat and url not in previous_url_map:
                diff['added'][name] = url
            elif name in previous_cat and url != previous_cat[name]:
                diff['modified'][name] = {
                    'old': previous_cat[name],
                    'new': url
                }

        category_diff = {k: v for k, v in diff.items() if v}
        if category_diff:
            differences['changes'][category] = category_diff

    return differences


# ✅ FIXED SAVE PATH
def save_comparison_results(country, results, today_date):
    """Save comparison results to a JSON file"""
    dir_path = os.path.join(country, today_date, "Category")
    os.makedirs(dir_path, exist_ok=True)

    filename = os.path.join(dir_path, f"{country}_category_comparison.json")

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    return filename


def compare_with_previous_data(countries, today_date):
    """Compare today's data with previous data for all countries"""
    for country in countries:
        # Get properly capitalized country name for folder structure
        country_folder = COUNTRY_MAPPING.get(country, country.capitalize())
        
        # Get absolute path for the script's directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        country_path = os.path.join(script_dir, country_folder)

        current_file = os.path.join(
            country_path,
            today_date,
            "Category",
            f"{country_folder}_category_urls.json"
        )

        if not os.path.exists(current_file):
            print(f"No current data found for {country}")
            continue

        previous_date = find_previous_date_folder(country_path, today_date)
        if not previous_date:
            print(f"No previous data found for {country}")
            continue

        previous_file = os.path.join(
            country_path,
            previous_date,
            "Category",
            f"{country_folder}_category_urls.json"
        )
        
        print(f"Checking for previous file at: {os.path.abspath(previous_file)}")
        print(f"{os.path.exists(previous_file)}")

        if not os.path.exists(previous_file):
            print(f"No previous data file found for {country} at {previous_file}")
            continue

        print(f"\nComparing {country} ({today_date} vs {previous_date})")

        try:
            with open(current_file, 'r', encoding='utf-8') as f:
                current_data = json.load(f)

            with open(previous_file, 'r', encoding='utf-8') as f:
                previous_data = json.load(f)

            results = compare_json_data(current_data, previous_data)
            output_file = save_comparison_results(country_folder, results, today_date)

            print(f"Category comparison results saved to {output_file}")

        except Exception as e:
            print(f"Error processing {country}: {str(e)}")


def check_comparison_results_data(countries, today_date, level="category"):
    country_wise_status = {}

    for country in countries:
        # Get properly capitalized country name
        country_folder = COUNTRY_MAPPING.get(country, country.capitalize())
        
        if level == "category":
            comparison_file = os.path.join(
                country_folder,
                today_date,
                "Category",
                f"{country_folder}_category_comparison.json"
            )
        elif level == "product":
            comparison_file = os.path.join(
                country_folder,
                today_date,
                "Items_urls",
                f"{country_folder}_product_comparison.json"
            )
        else:
            print(f"Unknown level: {level}")
            country_wise_status[country] = False
            continue

        if not os.path.exists(comparison_file):
            print(f"No comparison results found for {country} on {today_date} for level {level}")
            country_wise_status[country] = False
        else:
            with open(comparison_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data.get('changes'):
                print(f"No changes found in comparison results for {country} on {today_date} for level {level}")
                country_wise_status[country] = True
            else:
                print(f"Changes found in comparison results for {country} on {today_date} for level {level}")
                country_wise_status[country] = False

    return country_wise_status


def remove_duplicate_urls(countries, today_date, level="category"):
    try:
        for country in countries:
            # Get properly capitalized country name
            country_folder = COUNTRY_MAPPING.get(country, country.capitalize())
            
            if level == "category":
                file_path = os.path.join(country_folder, today_date, "Category")
                json_file = os.path.join(file_path, f"{country_folder}_category_urls.json")
            elif level == "product":
                file_path = os.path.join(country_folder, today_date, "Items_urls")
                json_file = os.path.join(file_path, f"{country_folder}_product_urls.json")
            else:
                print(f"Unknown level for duplicate removal: {level}")
                continue

            if not os.path.exists(json_file):
                print(f"No file found for {country} on {today_date} at level {level}")
                continue

            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            seen_urls = set()
            cleaned_data = {}

            if level == "category":
                for category, items in data.items():
                    cleaned_items = {}
                    for name, url in items.items():
                        if url not in seen_urls:
                            seen_urls.add(url)
                            cleaned_items[name] = url
                        else:
                            print(f"Removing duplicate: {category} > {name} ({url})")
                            dup_path = os.path.join(file_path, f"{country}_duplicate_urls.txt")
                            with open(dup_path, 'a', encoding='utf-8') as dup_file:
                                dup_file.write(f"{level} - {category} > {name}: {url}\n")
                    cleaned_data[category] = cleaned_items
            
            elif level == "product":
                for gender, categories in data.items():
                    cleaned_gender_data = {}
                    for category, urls in categories.items():
                        cleaned_urls = []
                        for url in urls:
                            if url not in seen_urls:
                                seen_urls.add(url)
                                cleaned_urls.append(url)
                            else:
                                print(f"Removing duplicate product url: {gender} > {category} ({url})")
                                dup_path = os.path.join(file_path, f"{country}_duplicate_urls.txt")
                                with open(dup_path, 'a', encoding='utf-8') as dup_file:
                                    dup_file.write(f"{level} - {gender} > {category}: {url}\n")
                        cleaned_gender_data[category] = cleaned_urls
                    cleaned_data[gender] = cleaned_gender_data

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=2)

            print(f"Cleaned {level} data saved for {country} on {today_date}")

        return True

    except Exception as e:
        print(f"Error removing duplicates: {str(e)}")
        return False


def save_product_urls_comparison_results(country, results, today_date):
    """Save product URL comparison results to a JSON file"""
    dir_path = os.path.join(country, today_date, "Items_urls")
    os.makedirs(dir_path, exist_ok=True)
    filename = os.path.join(dir_path, f"{country}_product_comparison.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    return filename


def compare_product_urls(countries, today_date):
    """Compare today's product URLs with previous data for all countries"""
    for country in countries:
        country_path = os.path.join(country)
        current_file = os.path.join(
            country_path,
            today_date,
            "Items_urls",
            f"{country}_product_urls.json"
        )

        if not os.path.exists(current_file):
            print(f"No current product URL data found for {country}")
            continue

        previous_date = find_previous_date_folder(country_path, today_date)
        if not previous_date:
            print(f"No previous product URL data found for {country}")
            continue

        previous_file = os.path.join(
            country_path,
            previous_date,
            "Items_urls",
            f"{country}_product_urls.json"
        )

        if not os.path.exists(previous_file):
            print(f"No previous product URL data file found for {country} at {previous_file}")
            continue

        print(f"\nComparing product URLs for {country} ({today_date} vs {previous_date})")

        try:
            with open(current_file, 'r', encoding='utf-8') as f:
                current_data = json.load(f)

            with open(previous_file, 'r', encoding='utf-8') as f:
                previous_data = json.load(f)

            results = compare_product_url_data(current_data, previous_data)
            output_file = save_product_urls_comparison_results(country, results, today_date)
            print(f"Product URL comparison results saved to {output_file}")

        except Exception as e:
            print(f"Error processing product URLs for {country}: {str(e)}")


def find_duplicate_product_urls(data):
    """Find duplicate URLs within the product URL data structure"""
    url_map = defaultdict(list)
    for gender, categories in data.items():
        for category, urls in categories.items():
            for url in urls:
                url_map[url].append(f"{gender} > {category}")
    
    return {url: names for url, names in url_map.items() if len(names) > 1}


def compare_product_url_data(current_data, previous_data):
    """Compare two product URL data structures"""
    
    # Flatten all URLs into sets
    current_urls = set()
    for gender, categories in current_data.items():
        for category, urls in categories.items():
            current_urls.update(urls)

    previous_urls = set()
    for gender, categories in previous_data.items():
        for category, urls in categories.items():
            previous_urls.update(urls)

    differences = {
        'metadata': {
            'duplicates': {
                'current': find_duplicate_product_urls(current_data),
                'previous': find_duplicate_product_urls(previous_data)
            }
        },
        'changes': {
            'added': list(current_urls - previous_urls),
            'removed': list(previous_urls - current_urls)
        }
    }
    
    return differences
