import asyncio
import os
import json
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import date
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

countries = {"UK": "https://uk.gymshark.com/"}
pop_key = {"All Products"}


async def get_categories_urls(base_url):
    """
    Asynchronously fetches category URLs from the base URL.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        page = await browser.new_page()

        logging.info(f"Navigating to: {base_url}")
        await page.goto(base_url, timeout=30000)

        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except Exception as e:
            logging.warning(f"Timeout waiting for networkidle: {e}. Proceeding anyway.")

        # Get page content for BeautifulSoup
        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        temp = {"women": {}, "men": {}}

        # Adjust selector based on site’s nav structure
        nav_divs = soup.find_all(
            "ul",
            attrs={
                "class": "subcategory_sub-category-linked-list__LhgFV",
                "id": "navigation-subCategories-clothing-list",
            },
        )
        for category_list in nav_divs:
            for item in category_list.find_all("li"):
                a_tag = item.find("a")
                if a_tag and a_tag.text.strip() not in pop_key:
                    href = a_tag.get("href")
                    title = a_tag.get("title") or a_tag.text
                    if href and title:
                        full_url = urljoin(base_url, href)
                        if "/women" in href:
                            temp["women"][title.strip()] = full_url
                        elif "/men" in href:
                            temp["men"][title.strip()] = full_url

        await browser.close()
        return temp


async def get_category_urls_main():
    """
    Main async function to process all countries and save category URLs.
    """
    today_str = date.today().strftime("%Y-%m-%d")

    for country, url in countries.items():
        logging.info(f"Processing {country} now...")
        category_data = await get_categories_urls(url)

        # Define the path for the JSON file
        json_file_path = os.path.join(
            country, "Data", today_str, "Item_urls", f"{country}_category_links.json"
        )

        # Make sure the full directory structure exists
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

        # Save the data to the JSON file
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(category_data, f, ensure_ascii=False, indent=4)

        logging.info(f"{country} category URLs fetched and saved to {json_file_path}")


if __name__ == "__main__":
    asyncio.run(get_category_urls_main())