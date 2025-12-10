import os
import json
import asyncio
from datetime import datetime, date
from playwright.async_api import async_playwright

BASE_URL = "https://www.uniqlo.com/in/en"
API_URL = "https://www.uniqlo.com/in/api/commerce/v3/en/cms?path=%2Fnavigation"

def build_full_url(url):
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return BASE_URL.rstrip("/") + url

def extract_first_level_title(item):
    for c in item.get("content", []):
        if c.get("_type") == "ImagePlusTextER":
            return c.get("title", "").strip()
    return ""

def extract_link_title(link):
    for c in link.get("children", []):
        if c.get("_type") == "ImagePlusTextER":
            return c.get("title", "").strip()
    return link.get("title", "").strip() if link.get("title") else ""

def is_valid_category(name: str) -> bool:
    blocklist = [
        "accessory", "accessories", "accesories",
        "socks",
        "heattech_accessory",
        "toddler (1 year- 5 years)_accesories"
    ]
    name_lower = name.lower()
    if name_lower.startswith("all "): 
        return False
    for word in blocklist:
        if word in name_lower:
            return False
    return True

def extract_categories(data):
    result = {"men": {}, "women": {}, "kids": {}, "baby": {}}
    body = data.get("result", {}).get("body", [])
    if not body:
        return result
    gender_block = body[0]
    for gender_key in ["men", "women", "kids", "baby"]:
        categories = gender_block.get(gender_key, [])
        if not categories:
            continue
        for cat in categories:
            if cat.get("_type") != "ContentsCardER":
                continue
            for content in cat.get("content", []):
                if content.get("_type") != "ClassListER":
                    continue
                for node in content.get("children", []):
                    if node.get("_type") == "ClassItemER":
                        first_level_title = extract_first_level_title(node)
                        if not first_level_title or not is_valid_category(first_level_title):
                            continue
                        gender_name = gender_key
                        subcategories = {}
                        for child in node.get("children", []):
                            if child.get("_type") == "CategoryListER":
                                for link in child.get("children", []):
                                    if link.get("_type") == "LinkER":
                                        title = extract_link_title(link).strip()
                                        if not title or not is_valid_category(title):
                                            continue
                                        url = build_full_url(link.get("url", ""))
                                        key = f"{first_level_title}_{title}"
                                        subcategories[key] = url
                        if subcategories:
                            result[gender_name].update(subcategories)
                    elif node.get("_type") == "LinkER":
                        continue
    return result

def save_category_urls(category_data):
    today = date.today().strftime("%Y-%m-%d")
    output_dir = os.path.join("India", "data", today, "Item_urls")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "category_urls.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(category_data, f, indent=2, ensure_ascii=False)
    print(f"Saved categories to {output_file}")

async def main():
    day = datetime.today().strftime('%A')
    if day not in ['Monday', 'Wednesday', 'Friday']:
        print(f"Today is {day}. Skipping script execution.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(API_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector("pre", timeout=5000)
            pre_text = await page.locator("pre").inner_text()
        except Exception:
            pre_text = await page.content()
        await browser.close()

        pre_text = pre_text.strip()
        start_idx = pre_text.find('{')
        if start_idx != -1:
            pre_text = pre_text[start_idx:]

        try:
            data = json.loads(pre_text)
        except json.JSONDecodeError:
            print("Failed to decode JSON from <pre> content")
            return

        category_data = extract_categories(data)
        save_category_urls(category_data)

if __name__ == "__main__":
    asyncio.run(main())
