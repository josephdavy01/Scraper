import os
import json
import asyncio
from datetime import date
from playwright.async_api import async_playwright

API_TEMPLATE = (
    'https://www.underarmour.in/graphql?hash=2818213211&sort_1={{"newest":"DESC"}}'
    '&filter_1={{"price":{{}},"category_id":{{"eq":{category_id}}},"customer_group_id":{{"eq":"0"}}}}'
    '&pageSize_1=78&currentPage_1={page_num}&_currency=""'
)

async def fetch_products_for_category(context, category_id):
    page_num = 1
    products_data = []  # list of dicts: {id, url}

    while True:
        api_url = API_TEMPLATE.format(category_id=category_id, page_num=page_num)
        headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "referer": "https://www.underarmour.in/",
            "accept-language": "en-US,en;q=0.9",
        }
        response = await context.request.get(api_url, headers=headers)
        text = await response.text()

        try:
            json_data = json.loads(text)
        except Exception as e:
            print(f"Failed to parse JSON for category {category_id} page {page_num}: {e}")
            break

        products = json_data.get("data", {}).get("products", {}).get("items", [])
        if not products:
            print(f"No products found in category {category_id} page {page_num}")
            break

        for product in products:
            product_id = product.get("id")
            base_url = product.get("url")
            if not base_url or not product_id:
                continue

            base_url_full = f"https://www.underarmour.in{base_url}"

            # Store main product URL with id
            products_data.append({"id": product_id, "url": base_url_full})

            # Extract color variant URLs with same product id
            color_swatch_list_str = product.get("color_swatch_list")
            if color_swatch_list_str:
                try:
                    color_swatch_list = json.loads(color_swatch_list_str)
                    for variant in color_swatch_list:
                        color_val = variant.get("value")
                        if color_val:
                            variant_url = f"{base_url_full}?color_swatch_square={color_val}"
                            products_data.append({"id": product_id, "url": variant_url})
                except Exception as e:
                    print(f"Error parsing color swatch list for {base_url}: {e}")

        page_info = json_data.get("data", {}).get("products", {}).get("page_info", {})
        total_pages = page_info.get("total_pages", 1)

        if page_num >= total_pages:
            break
        page_num += 1

    return products_data


async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    country = 'India'
    base_dir = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(base_dir, exist_ok=True)

    read_file_path = f'{base_dir}/Category_urls.json'
    url_file_path = f'{base_dir}/product_urls.json'
    id_file_path = f'{base_dir}/product_ids.json'


    with open(read_file_path, "r", encoding="utf-8") as f:
        categories_data = json.load(f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        all_products_urls = {}
        all_products_ids = {}

        for gender, categories in categories_data.items():
            print(f"Processing main category: {gender}")
            all_products_urls[gender] = {}
            all_products_ids[gender] = {}

            for category, cat_dict in categories.items():
                category_id = cat_dict.get("id")
                if not category_id:
                    print(f"Skipping {category} in {gender} - no category_id")
                    continue

                print(f"Fetching products for {gender} -> {category} (category_id={category_id})")
                products_data = await fetch_products_for_category(context, category_id)
                print(f"Found {len(products_data)} products for {category}")

                # Extract just URLs and ids separately
                urls = [p['url'] for p in products_data]
                ids = [p['id'] for p in products_data]

                all_products_urls[gender][category] = urls
                all_products_ids[gender][category] = ids

        # Save product URLs per category/subcategory
        with open(url_file_path, "w", encoding="utf-8") as f:
            json.dump(all_products_urls, f, indent=2, ensure_ascii=False)

        # Save product IDs per category/subcategory separately
        with open(id_file_path, "w", encoding="utf-8") as f:
            json.dump(all_products_ids, f, indent=2, ensure_ascii=False)

        print(f"Saved all product URLs to {url_file_path}")
        print(f"Saved all product IDs to {id_file_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
