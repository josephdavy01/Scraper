import os
import json
import asyncio
from datetime import date
from playwright.async_api import async_playwright

API_URL = "https://www.underarmour.in/graphql?hash=4126164937&identifier_1=%22new-main-menu%22&_currency=%22%22"
BASE_URL = "https://www.underarmour.in"

async def get_category_data(context):
    response = await context.request.get(API_URL, headers={
        "accept": "application/json, text/plain, */*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "referer": "https://www.underarmour.in/",
        "accept-language": "en-US,en;q=0.9"
    })

    if response.status != 200:
        raise Exception(f"Request failed with status {response.status}")

    text = await response.text()
    return json.loads(text)

def extract_titles_urls(data):
    results = []

    items = data['data']['menu']['items']

    for item in items:
        title = item.get("title", "")
        url = item.get("url", "")
        id = item.get("category_id", "")
        if title and url and '/shoes.html' != url and '/accessories.html' != url and id and title not in ['Men', 'Women','Outlet','Featured','Shop by Category','Shop by Sport','Shop by Collection','Shop by Gender']:
            results.append({"title": title, "url": BASE_URL + url, "id": id})
    return results

def format_data(all_urls):
    temp = {}
    for i in all_urls:
        id = i['id']
        url = i['url']
        splits = url.split('/')
        gender = splits[3].split('.')[0]
        category = splits[-1].split('.')[0]

        if gender not in temp:
            temp[gender] = {}

        # If category exists with different ID, append the ID to make it unique
        if category in temp[gender]:
            existing_id = temp[gender][category]['id']
            if existing_id != id:
                category = f"{category}_{id}"

        temp[gender][category] = {'id': id, 'url': url}

    return temp

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    country = 'India'
    base_dir = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(base_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        data = await get_category_data(context)
        all_titles_urls = extract_titles_urls(data)

        category_data = format_data(all_titles_urls)

        file_path = f'{base_dir}/Category_urls.json'
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(category_data, f, indent=2, ensure_ascii=False)

        print(f"Saved cleaned and grouped categories to {file_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
