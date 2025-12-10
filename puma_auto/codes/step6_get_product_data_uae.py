import json
import os
import asyncio
from datetime import date
from urllib.parse import quote
from playwright.async_api import async_playwright


os.environ["PYTHONIOENCODING"] = "utf-8"

async def save_json(json_dir, gender, category, id, data):
    category_base_path = f'{json_dir}/{gender}/{category}'
    os.makedirs(category_base_path, exist_ok=True)
    write_file_path = f'{category_base_path}/{id}.json'
    with open(write_file_path, "w", encoding="utf-8") as pf:
        json.dump(data, pf, indent=4, ensure_ascii=False)
    
    print(f'Data for id {id} saved to {write_file_path}')


async def fetch_product_details(context, json_dir, gender, category, product):
    
    id = product.get('id') if isinstance(product, dict) else product
    
    if not id:
        print(f'Invalid product data: {product}')
        return
    
    file_path = f'{json_dir}/{gender}/{category}/{id}.json'
    
    # Skip if file already exists
    if os.path.exists(file_path):
        print(f'Skipping id {id}: File already exists')
        return
    
    api_url = 'https://ae.puma.com/graphql?hash=1005521&filter_1={%22id%22:{%22eq%22:product_id},%22customer_group_id%22:{%22eq%22:%220%22}}&_currency=%22%22'
    api_url = api_url.replace('product_id', str(id))
    
    headers = {
        "accept": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "referer": "https://ae.puma.com/", 
        "accept-language": "en-US,en;q=0.9",
    }
    
    try:
        response = await context.request.get(api_url, headers=headers)
        
        if response.status != 200:
            print(f'HTTP {response.status} for id {id}')
            print(f'URL: {api_url}') 
            return
        
        text = await response.text()
        product_json = json.loads(text)
        
        if product_json:
            await save_json(json_dir, gender, category, id, product_json)
        else:
            print(f'Empty response for id {id}')
            
    except json.JSONDecodeError as e:
        print(f'JSON decode error for id {id}: {e}')
    except Exception as e:
        print(f'Failed to fetch or parse data for id {id}: {e}')
        print(f'URL: {api_url}')


async def main():
    async with async_playwright() as p:
        today_str = date.today().strftime('%Y-%m-%d')
        # today_str = '2025-11-27'
        country = 'UAE'
        base_dir = f'{country}/Data/{today_str}/Item_urls'
        json_dir = f'{country}/Data/{today_str}/Json_data'
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(json_dir, exist_ok=True)
        read_file_path = f'{base_dir}/{country}_unique_product_urls.json'
        
        # Check if input file exists
        if not os.path.exists(read_file_path):
            print(f'Input file not found: {read_file_path}')
            return
        
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        try:
            with open(read_file_path, "r", encoding="utf-8") as f:
                products_data = json.load(f)
            
            total_products = 0
            for gender, categories in products_data.items():
                for category, products in categories.items():
                    total_products += len(products)
                    print(f"Found {len(products)} products in {gender} -> {category}".encode('ascii', errors='ignore').decode())
            
            print(f"\nTotal products to process: {total_products}")
            processed = 0
            
            for gender, categories in products_data.items():
                for category, products in categories.items():
                    print(f"\nProcessing {gender} -> {category} with {len(products)} products")
                    
                    for product in products:
                        processed += 1
                        id = product.get('id') if isinstance(product, dict) else product
                        print(f"Processing {processed}/{total_products}: id {id}")

                        file_path = f'{json_dir}/{gender}/{category}/{id}.json'

                        if os.path.exists(file_path):
                            print(f'Skipping id {id}: File already exists')
                            continue

                        await fetch_product_details(context, json_dir, gender, category, product)
                        await asyncio.sleep(1)

            
            print("\nFinished saving all product detail JSON files.")
            
        except json.JSONDecodeError as e:
            print(f'Error reading input JSON file: {e}')
        except Exception as e:
            print(f'Unexpected error: {e}')
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
