import os
import json
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright

async def main():
    brand_filters = {
        'autograph': '?filter=Brand%253DAutograph',
        'goodmove': '?filter=Brand%253DGoodmove',
        'Per Una': '?filter=Brand%253DPer%2520Una',
        'M&S': '?filter=Brand%253DM%2526S',
        'M&S Sartorial': '?filter=Brand%253DM%2526S%2520SARTORIAL'
    }
    base_path = 'UK'
    today_time = datetime.now().strftime('%Y-%m-%d')
    file_path = f'{base_path}/data/{today_time}/item_urls'
    file_val = 'UK_category_urls.json'
    file_name = os.path.join(file_path, file_val)
    with open(file_name, 'r', encoding='utf-8') as file:
        data = json.load(file)
    temp = {}
    for gender, categories in data.items():
        temp[gender] = {}
        for brand, brand_filter in brand_filters.items():
            temp[gender][brand] = {}
            for category, url in categories.items():
                if '#' in url:
                    url = url.split('#')[0]
                full_url = url + brand_filter
                temp[gender][brand][category] = full_url
    os.makedirs(file_path, exist_ok=True)
    output_file = os.path.join(file_path, 'Brand_name_product_url.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(temp, f, indent=4, ensure_ascii=False)
    print(f"Saved brand-filtered URLs to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
