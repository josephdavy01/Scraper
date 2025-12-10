import os
import json
import asyncio
from datetime import date
from playwright.async_api import async_playwright

API_TEMPLATE = (
    'https://ae.puma.com/graphql?hash=202054943'
    '&sort_1=%7B%22online_from%22%3A%22DESC%22%7D'
    '&filter_1=%7B%22price%22%3A%7B%7D%2C%22category_id%22%3A%7B%22eq%22%3A{category_id}%7D%2C%22customer_group_id%22%3A%7B%22eq%22%3A%220%22%7D%7D'
    '&pageSize_1={PAGE_SIZE}&currentPage_1={PAGE_NUMBER}&id_1={category_id}&_currency=%22%22'
)

PAGE_SIZE = 40
MAX_EMPTY_COUNT = 2

def organize_categories_by_gender(categories_data):
    organized = {}
    
    def extract_categories(data, main_category=""):
        category_items = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    if "id" in value and "url" in value:
                        # This is a category item
                        category_items.append({
                            "category_id": value["id"],
                            "category_name": key,
                            "category_url": value["url"],
                            "main_category": main_category
                        })
                    else:
                        # This is a nested structure, recurse
                        nested_items = extract_categories(value, main_category)
                        category_items.extend(nested_items)
        
        return category_items
    
    for main_section, subcategories in categories_data.items():
        if main_section not in organized:
            organized[main_section] = []
        
        categories = extract_categories(subcategories, main_section)
        organized[main_section].extend(categories)
    
    return organized

async def fetch_products_for_category(context, category_id, category_name):
    page_num = 1
    no_data_pages = 0
    products_data = []
    
    page = await context.new_page()

    while True:
        api_url = API_TEMPLATE.format(
            category_id=category_id,
            PAGE_SIZE=PAGE_SIZE,
            PAGE_NUMBER=page_num
        )

        try:
            await page.goto(api_url)
            content = await page.content()
            
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                raise Exception("No JSON found in response")
            json_text = content[start:end]
            
            json_data = json.loads(json_text)
            
            data_section = json_data.get("data")
            products = None
            if data_section:
                products_section = data_section.get("products")
                if products_section:
                    products = products_section.get("items", [])
                else:
                    products = data_section.get("items", [])
            else:
                products = json_data.get("products", {}).get("items", [])
                if not products:
                    products = json_data.get("items", [])

            if not products:
                no_data_pages += 1
                if no_data_pages >= MAX_EMPTY_COUNT:
                    break
                else:
                    page_num += 1
                    continue

            print(f"Page {page_num}: {len(products)} products")

            for product in products:
                main_id = product.get("id")
                base_url = product.get("url")
                
                if main_id and base_url:
                    full_url = f"https://ae.puma.com{base_url}" if base_url.startswith("/") else base_url
                    products_data.append({
                        "id": main_id,
                        "url": full_url
                    })

            page_num += 1
            no_data_pages = 0

        except Exception as e:
            print(f"Error for category {category_id} page {page_num}: {e}")
            break

    await page.close()
    return products_data

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    country = 'UAE'
    base_dir = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(base_dir, exist_ok=True)
    read_file_path = f'{base_dir}/{country}_category_urls.json'
    output_file_path = f'{base_dir}/{country}_product_urls.json'

    with open(read_file_path, "r", encoding="utf-8") as f:
        categories_data = json.load(f)

    organized_categories = organize_categories_by_gender(categories_data)
    
    print(f"Found {sum(len(cats) for cats in organized_categories.values())} categories in {len(organized_categories)} main sections")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        all_products = {}

        total_categories = 0
        current_category = 0

        for main_section in organized_categories.keys():
            all_products[main_section] = {}

        for main_section, categories in organized_categories.items():
            print(f"\n=== Processing {main_section.upper()} section ===")
            
            for category_info in categories:
                current_category += 1
                total_categories += 1
                
                category_id = category_info.get("category_id")
                category_name = category_info.get("category_name")

                if not category_id:
                    continue

                print(f"[{current_category}/{sum(len(cats) for cats in organized_categories.values())}] {main_section}_{category_name} (ID: {category_id})")

                products_data = await fetch_products_for_category(context, category_id, category_name)

                full_category_name = f"{main_section}_{category_name}"
                all_products[main_section][full_category_name] = products_data

                print(f"Total products: {len(products_data)}")
                await asyncio.sleep(1)

        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, indent=2, ensure_ascii=False)

        total_products = sum(
            sum(len(products) for products in section.values()) 
            for section in all_products.values()
        )
        print(f"\nMain Sections: {len(all_products)}")
        print(f"Total Categories: {total_categories}")
        print(f"Total Products: {total_products}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
