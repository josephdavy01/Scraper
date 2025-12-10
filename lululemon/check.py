# import json
# import logging
# from playwright.sync_api import sync_playwright

# # Set up logging configuration
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# def inspect_category_data(country_url):
#     with sync_playwright() as playwright:
#         browser = playwright.chromium.launch(headless=False)
#         context = browser.new_context()
#         page = context.new_page()

#         try:
#             logging.info(f"Visiting {country_url}...")
#             page.goto(country_url, wait_until="load", timeout=30000)

#             # Extract JSON data from script tag
#             json_data = page.evaluate("""() => {
#                 const jsonTag = document.querySelector('script#__NEXT_DATA__');
#                 return JSON.parse(jsonTag.textContent);
#             }""")

#             # Access the section where category/nav data used to live
#             data_section = json_data['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']

#             # Save to file for manual inspection
#             with open("debug_category_data.json", "w", encoding="utf-8") as f:
#                 json.dump(data_section, f, indent=2, ensure_ascii=False)

#             # Print to console (for quick look)
#             print(json.dumps(data_section, indent=2, ensure_ascii=False))

#             logging.info("Data dumped to debug_category_data.json. You can inspect it now.")

#         except Exception as e:
#             logging.error(f"Error occurred: {str(e)}")
#         finally:
#             context.close()
#             browser.close()

# if __name__ == "__main__":
#     # Replace with the actual URL you're working with (e.g., Lululemon homepage)
#     url = "https://shop.lululemon.com"
#     inspect_category_data(url)
import json

with open('debug_category_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Root type: {type(data)}")  # likely list

if isinstance(data, list):
    print(f"Length of root list: {len(data)}")
    first = data[0]
    if isinstance(first, dict):
        print("Keys of first element:", first.keys())

        queries = first['props']['pageProps']['dehydratedState']['queries']
        print(f"Number of queries: {len(queries)}")
        # Continue your exploration here...

else:
    print("Root is not a list, unexpected JSON structure.")
