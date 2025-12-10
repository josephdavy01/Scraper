import json
import os
import asyncio
from datetime import date, time
from playwright.async_api import async_playwright
import time


PRODUCT_DETAIL_API = (
    'https://www.underarmour.in/graphql?hash=434211475'
    '&filter_1=%7B%22id%22%3A%7B%22eq%22%3A%22{product_id}%22%7D%2C'
    '%22customer_group_id%22%3A%7B%22eq%22%3A%220%22%7D%7D&_currency=""'
)


async def save_json(json_dir, gender, category, id, data):
    category_base_path = f'{json_dir}/{gender}/{category}'
    os.makedirs(category_base_path, exist_ok=True)
    write_file_path = f'{category_base_path}/{id}.json'
    with open(write_file_path, "w", encoding="utf-16") as pf:
        json.dump(data, pf, indent=4)

    print(f'Data for product ID {id} saved to {write_file_path}')

async def fetch_product_details(context, json_dir, gender, category, product_id):
    file_path = f'{json_dir}/{gender}/{category}/{product_id}.json'

    # Skip if file already exists
    if os.path.exists(file_path):
        print(f'Skipping product ID {product_id}: File already exists at {file_path}')
        return

    api_url = PRODUCT_DETAIL_API.format(product_id=product_id)
    headers = {
        "accept": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "referer": "https://www.underarmour.in/",
        "accept-language": "en-US,en;q=0.9",
    }

    response = await context.request.get(api_url, headers=headers)
    text = await response.text()

    try:
        product_json = json.loads(text)
        time.sleep(2)
        if product_json:
            await save_json(json_dir, gender, category, product_id, product_json)
    except:
        print(f'Failed to fetch or parse data for product ID {product_id}')

async def main():
    async with async_playwright() as p:
        today_str = date.today().strftime('%Y-%m-%d')
        country = 'India'
        base_dir = f'{country}/Data/{today_str}/Item_urls'
        json_dir = f'{country}/Data/{today_str}/Json_data'
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(json_dir, exist_ok=True)
        read_file_path = f'{base_dir}/unique_product_ids.json'
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        with open(read_file_path, "r", encoding="utf-8") as f:
            products_ids_data = json.load(f)

        for gender, categories in products_ids_data.items():
            for category, product_ids in categories.items():
                print(f"\nProcessing {gender} -> {category} with {len(product_ids)} products")
                
                for product_id in product_ids:
                    print(f"Checking product ID: {product_id}")
                    await fetch_product_details(context, json_dir, gender, category, product_id)

        print("\nFinished saving all product detail JSON files.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
