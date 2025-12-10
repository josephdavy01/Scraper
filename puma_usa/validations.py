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
       

def refresh_token(token):
    """
    Get the total product count for a given category URL path from the Puma GraphQL API.
    
    Args:
        url_path (str): The category path, e.g., '/women/best-sellers'
    """
    session = requests.Session()
    session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS)
        })
    # The API endpoint for the GraphQL service
    api_url = "https://us.puma.com/api/graphql"

    # Define the necessary headers, including Authorization for the Bearer Token
    headers = {
        "Locale": "en-US",
        "Content-Type": "application/json"
    }

    # The complex GraphQL query string provided
    graphql_query = """
    mutation RefreshLogon($input: RefreshLogonInput!) 
    {\n  refreshLogon(input: $input) {\n    ...tokenPayload\n  }\n}\nfragment tokenPayload on TokenPayload 
    {\n  __typename\n  accessToken\n  refreshToken\n  customerId\n  uniqueShopperId\n  customerContext 
    {\n    __typename\n    hashKey\n    customerGroups\n  }\n  user {\n    customerNo\n    email\n  }\n}
    """
    # Construct the JSON payload with the operation name, query, and variables
    payload = {
        "operationName": "RefreshLogon",
        "query": graphql_query,
        "variables": {
            "input": {
                "refreshToken": token
            }
        }
    }

    try:
        # Make the POST request to the GraphQL API
        response = session.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        # Raise an exception for bad status codes (like 401 Unauthorized or 500 Server Error)
        response.raise_for_status()
        
        data = response.json()
    
        access_token = data.get("data", {}).get("refreshLogon", {}).get("accessToken", '')
        print("Token refreshed")
        return access_token

    except Exception as e:
        return None
    

def check_token_expired(data):
        """
        Checks a GraphQL JSON response to see if it contains an 'UNAUTHENTICATED' error.

        Args:
            data (dict): The parsed JSON response from the API.

        Returns:
            bool: True if the specific unauthenticated error is found, False otherwise.
        """
        try:
            # The 'errors' key should be a list. .get() returns None if 'errors' doesn't exist.
            errors = data.get('errors')
            
            # Ensure 'errors' is a list before iterating
            if not isinstance(errors, list):
                return False, None

            # Check each error dictionary in the list
            for error in errors:
                # Safely access the nested 'code' and check its value in one line
                if error.get("extensions", {}).get("code") == "UNAUTHENTICATED":
                    print("Token expired")
                    return True, "Token expired"
                elif error.get("extensions", {}).get("code") == "INTERNAL_SERVER_ERROR":
                    print("Internal server error")
                    return True, "Internal server error"
                    
        except AttributeError:
            # This will catch errors if 'data' is not a dictionary (e.g., None)
            return False, None

        # If the loop completes without finding the specific error
        return False, None