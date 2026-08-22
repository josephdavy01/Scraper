import os
import json
import asyncio
import logging
from datetime import date
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm_asyncio
from playwright.async_api import async_playwright

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Concurrency limiter (adjust based on your system resources)
semaphore = asyncio.Semaphore(5)

# Save the JSON data to a file
def save_json(gender, category, name, json_data, date_subfolder):
    try:
        json_file_path = f'{date_subfolder}/Json_data/{gender}/{category}'
        os.makedirs(json_file_path, exist_ok=True)
        with open(f'{json_file_path}/{name}.json', 'w', encoding='utf-8') as outfile:
            json.dump(json_data, outfile, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")

# Check if file already exists
def check_file(gender, category, name, date_subfolder):
    file_path = f'{date_subfolder}/Json_data/{gender}/{category}/{name}.json'
    return os.path.exists(file_path)

# Main scraping function (runs in separate browser instance)
async def scrape_url(url, gender, category, date_subfolder):
    name = url.split('?')[0].split('/')[-1]
    if check_file(gender, category, name, date_subfolder):
        return url  # Already exists

    async with semaphore:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(f'{url}&country=US')

                html_content = await page.content()
                soup = BeautifulSoup(html_content, "html.parser")

                script_tags = soup.find_all("script")
                for script_tag in script_tags:
                    script_string = script_tag.string
                    if script_string and 'self.__next_f.push([1,"5:' in script_string:
                        first_bracket_index = script_string.find('[')
                        start = script_string.find('[', first_bracket_index + 1)
                        last_bracket_index = script_string.rfind(']')
                        end = script_string.rfind(']', 0, last_bracket_index)

                        product_data = script_string[start: end + 1]
                        product_data = product_data.encode().decode("unicode_escape")
                        product = json.loads(product_data)
                        product = product[0][-1]['product']
                        save_json(gender, category, name, product, date_subfolder)

                return url

        except Exception as e:
            logging.error(f"Error processing URL {url}: {e}")
            return None

# Manage all scraping tasks per category
async def process_urls(gender, category, urls, date_subfolder):
    tasks = [
        scrape_url(url, gender, category, date_subfolder)
        for url in urls
    ]
    results = await tqdm_asyncio.gather(*tasks, desc=f"Processing {gender}/{category}", total=len(tasks))

# Main script execution
async def main():
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    country = 'USA'

    # Define the folder path and file path
    date_subfolder = f'{country}/Data/{today_str}'
    os.makedirs(date_subfolder, exist_ok=True)
    read_file_path = f'{date_subfolder}/Item_urls/{country}_unique_product_urls.json'

    with open(read_file_path) as json_file:
        urls_dict = json.load(json_file)

    for gender, categories in urls_dict.items():
        logging.info(f'Starting {country} {gender} section...')
        for category, urls in categories.items():
            logging.info(f'Starting {country} {gender} {category} section...')
            await process_urls(gender, category, urls, date_subfolder)
            logging.info(f'{country} {gender} {category} section complete.')
        logging.info(f'{country} {gender} section complete.')

    logging.info(f'{country} products completed.')

# Entry point
if __name__ == "__main__":
    asyncio.run(main())
