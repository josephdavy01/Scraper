import json
import asyncio
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date, datetime
from playwright.async_api import async_playwright

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

pop_keys = [
    "socks-and-tights", "socks", "sports-socks", "shoes-and-accessories", "accessories",
    "bags-and-purses", "hair-accessories", "sunglasses", "reading-glasses", "jewellery",
    "belts", "hats-gloves-and-scarves", "bags-and-wallets", "baby-boys_socks-and-tights",
    "jewellery", "bags-and-purses", "hats-gloves-and-scarves", "sunglasses", "jewelry",
    "belts", "baby-boys_socks-and-tights","gym-bags"
]

# Fetch the JSON data from the URL using Playwright and save it
async def get_json(url, page):
    temp = {}
    await page.goto(url)
    await page.wait_for_timeout(5000)  # Wait 5 seconds

    html_content = await page.content()
    soup = BeautifulSoup(html_content, 'html.parser')

    nav_div = soup.find('div', {'class': 'MuiBox-root mui-1hyfx7x'})
    
    if nav_div:
        div_tags = nav_div.find_all('div', {'class': 'MuiBox-root mui-0'})
        for div_tag in div_tags:
            a_tags = div_tag.find_all('a')
            for a_tag in a_tags:
                link = a_tag.get('href')
                if not link:
                    continue

                linksplit = link.split('/')
                if len(linksplit) < 4:
                    continue

                gender = linksplit[3]
                category = linksplit[-1]

                if category in pop_keys:
                    continue

                if gender in ['women', 'men'] and len(linksplit) <= 8 and 'filters' not in link:
                    if gender not in temp:
                        temp[gender] = {}
                    temp[gender][category] = 'https://www.primark.com' + link
                elif gender in ['baby', 'kids'] and len(linksplit) <= 8 and 'clothing' in link and 'filters' not in link:
                    if linksplit[-3] not in ['browse-by-product', 'shop-by-product', 'explore-by-product']:
                        if gender not in temp:
                            temp[gender] = {}
                        temp[gender][linksplit[-3] + '_' + category] = 'https://www.primark.com' + link
        return temp
    else:
        logging.warning("div not found.")
        return None


# Main script execution
async def main():

    today_str = date.today().strftime('%Y-%m-%d')

    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')
    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = {
            'UK': 'https://www.primark.com/en-gb'
        }
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = {
            'USA': 'https://www.primark.com/en-us'
        }
    else:
        countries = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        context = await browser.new_context()
        page = await context.new_page()

        for country, url in countries.items():
            country_dir = Path(country) / 'Data' / today_str / 'Item_urls'
            country_dir.mkdir(parents=True, exist_ok=True)
            cat_json = await get_json(url, page)
            if cat_json:
                output_path = country_dir / f'{country}_category_urls.json'
                with open(output_path, 'w', encoding='utf-8') as outfile:
                    json.dump(cat_json, outfile, ensure_ascii=False, indent=4)
                    logging.info(f"Saved data for {country} to {outfile.name}")
            else:
                logging.warning(f"No data found for {country}.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
