import os
import json
import asyncio
from datetime import date
from playwright.async_api import async_playwright

API_URL = "https://ae.puma.com/graphql?hash=2496928554&identifier_1=%22main-menu%22&_currency=%22%22"
BASE_URL = "https://ae.puma.com"

async def get_category_data(context):
    response = await context.request.get(API_URL, headers={
        "accept": "application/json, text/plain, */*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "referer": "https://ae.puma.com/",
        "accept-language": "en-US,en;q=0.9"
    })

    if response.status != 200:
        raise Exception(f"Request failed with status {response.status}")

    text = await response.text()
    return json.loads(text)

def extract_categories_from_menu(data):
    """Extract hierarchical categories from menu data"""
    categories = {}
    
    if 'data' in data and 'menu' in data['data'] and 'items' in data['data']['menu']:
        items = data['data']['menu']['items']
        
        # Create mapping of items by ID
        item_map = {item['item_id']: item for item in items}
        
        # Find main categories (children of root item 356)
        main_categories = [item for item in items if str(item.get('parent_id')) == '356']
        
        for main_cat in main_categories:
            main_key = create_key(main_cat['title'])
            categories[main_key] = {}
            
            # Process all descendants recursively
            process_children(main_cat['item_id'], categories[main_key], items, item_map)
        
        # Handle standalone items (parent_id = 0 with category_id)
        standalone_items = [item for item in items if item.get('parent_id') == 0 and item.get('category_id') is not None]
        for item in standalone_items:
            key = create_key(item['title'])
            categories[key] = {
                key: {
                    "id": item['category_id'],
                    "url": BASE_URL + item['url'] if item['url'].startswith('/') else item['url']
                }
            }
    
    return categories

def process_children(parent_id, result_dict, items, item_map):
    """Recursively process all children of a parent"""
    children = [item for item in items if str(item.get('parent_id')) == str(parent_id)]
    
    for child in children:
        child_key = create_key(child['title'])
        
        if child.get('category_id') is not None:
            # This child has a category_id, add it to results
            result_dict[child_key] = {
                "id": child['category_id'],
                "url": BASE_URL + child['url'] if child['url'].startswith('/') else child['url']
            }
        
        # Check if this child has its own children (go deeper)
        grandchildren = [item for item in items if str(item.get('parent_id')) == str(child['item_id'])]
        if grandchildren:
            # Process grandchildren recursively
            process_children(child['item_id'], result_dict, items, item_map)

def create_key(title):
    """Create a key from title (lowercase, replace spaces with hyphens)"""
    return title.lower().replace(' ', '-').replace('&', 'and').replace('/', '-').replace('\\', '-').replace('  ', '-')

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    country = 'UAE'
    base_dir = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(base_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        try:
            data = await get_category_data(context)
            categories = extract_categories_from_menu(data)

            file_path = f'{base_dir}/{country}_category_urls.json'
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(categories, f, indent=2, ensure_ascii=False)

            print(f"Saved categories to {file_path}")
            print(f"Extracted {len(categories)} main categories")

        except Exception as e:
            print(f"Error occurred: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
