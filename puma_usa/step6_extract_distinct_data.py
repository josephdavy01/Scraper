import os
import json
import traceback

def get_folders(sub_folders, exclude_folder=None):
    """Lists subdirectories within a given folder, optionally excluding some."""
    try:
        folders = os.listdir(sub_folders)
        # Filter out any files that might be in the directory
        folders = [f for f in folders if os.path.isdir(os.path.join(sub_folders, f))]
        if exclude_folder:
            folders = [folder for folder in folders if folder not in exclude_folder]
        return folders
    except FileNotFoundError:
        print(f"Warning: Directory not found: {sub_folders}")
        return []

def extract_fields_from_product(json_data):
    """
    Extracts the values for the three target fields from a single product's JSON data.

    Args:
        json_data (dict): The loaded JSON content from a file.

    Returns:
        dict: A dictionary containing the values for the target fields. 
              Values can be None if a field is not found.
    """
    # Use .get() for safe navigation to avoid errors if keys are missing
    product_data = json_data.get("data", {}).get("product")
    
    if not product_data:
        return {
            "primaryCategoryId": None,
            "productDivision": None,
            "sizeChartId": None
        }
        
    return {
        "primaryCategoryId": product_data.get("primaryCategoryId"),
        "productDivision": product_data.get("productDivision"),
        "sizeChartId": product_data.get("sizeChartId"),
    }

def process_and_save_distinct_values(country, fetch_date):
    """
    Orchestrates file processing for a single country to find all distinct values.
    It scans through the directory structure, aggregates unique values, and saves them.
    """
    # Sets are used to automatically store only unique values
    distinct_values = {
        "primaryCategoryId": set(),
        "productDivision": set(),
        "sizeChartId": set()
    }
    
    log_data = []
    processed_files = 0
    
    gender_folder = os.path.join(country, fetch_date, 'Json_data')
    genders = get_folders(gender_folder, [])
    
    print(f"Scanning folders in: {gender_folder}")
    
    for gender in genders:
        category_folder = os.path.join(gender_folder, gender)
        categories = get_folders(category_folder, [])
        
        for category in categories:
            file_folder = os.path.join(category_folder, category)
            # Check if file_folder is actually a directory before listing files
            if not os.path.isdir(file_folder):
                continue
            files = os.listdir(file_folder)
            
            for file in files:
                if not file.endswith(".json"):
                    continue
                    
                file_path = os.path.join(file_folder, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    
                    # Extract the specific fields from the JSON data
                    fields = extract_fields_from_product(data)
                    if fields["productDivision"] == 'Accessories':
                        continue
                    # Add the extracted values to our sets (None values are ignored)
                    if fields["primaryCategoryId"]:
                        distinct_values["primaryCategoryId"].add(fields["primaryCategoryId"])
                    if fields["productDivision"]:
                        distinct_values["productDivision"].add(fields["productDivision"])
                    if fields["sizeChartId"]:
                        distinct_values["sizeChartId"].add(fields["sizeChartId"])

                    processed_files += 1
                    if processed_files % 100 == 0:
                        print(f"  ...processed {processed_files} files")

                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")
                    traceback.print_exc()

    # Convert sets to sorted lists for clean, consistent output
    final_output = {key: sorted(list(value)) for key, value in distinct_values.items()}

    # Save the aggregated distinct values to a single JSON file
    output_dir = os.path.join(country, fetch_date, 'Data')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'distinct_values_{country}.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=4)
        
    print(f'\nProcessed {processed_files} files for {country}.')
    print(f'All distinct values saved to {output_file}')

def generate_distinct_values_reports(countries, fetch_date, re_run=False):
    """
    Main entry point function. Iterates through countries and generates a distinct
    values report for each one.
    """   
    for country, _ in countries.items():
        # Define the output file path to check for existence
        data_file = os.path.join(country, fetch_date, 'Data', f'distinct_values_{country}.json')
        
        if not re_run and os.path.exists(data_file):
            print(f"Data file {data_file} already exists. Skipping processing for {country}.")
            continue
            
        print(f"\n--- Processing distinct values for {country} ---")
        process_and_save_distinct_values(country, fetch_date)
    
    print("\nDistinct values processing completed for all countries.")

# ================== MAIN EXECUTION BLOCK ==================
if __name__ == '__main__':
    # Today's date for the fetch_date folder
    FETCH_DATE = "2025-10-09" # Or use: str(date.today())
    
    # Dictionary of countries to process
    # The base_url isn't needed for this script but is kept for consistency
    COUNTRIES_TO_PROCESS = {
        'USA': 'https://www.example-usa.com/',
    }
    
    # Set re_run to True if you want to overwrite existing files
    RE_RUN_PROCESSING = True
    
    generate_distinct_values_reports(
        countries=COUNTRIES_TO_PROCESS,
        fetch_date=FETCH_DATE,
        re_run=RE_RUN_PROCESSING
    )