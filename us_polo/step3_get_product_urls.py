import json
import logging
import asyncio
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


country = 'India'
today_str = date.today().strftime('%Y-%m-%d')
INPUT_FILE = f'{country}/{country}_updated_category_urls.json'
OUTPUT_FILE = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'

# Concurrency control
sem = asyncio.Semaphore(4)
output_data = {}
output_lock = asyncio.Lock()

async def auto_scroll(page):
    await page.evaluate("""
        async () => {
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            let lastHeight = document.body.scrollHeight;
            let noChangeCount = 0;
            const maxAttempts = 25;

            while (noChangeCount < maxAttempts) {
                window.scrollBy(0, 100);
                await delay(700);
                let newHeight = document.body.scrollHeight;
                if (newHeight === lastHeight) {
                    noChangeCount++;
                } else {
                    noChangeCount = 0;
                    lastHeight = newHeight;
                }
            }
        }
    """)

async def get_product_urls(page, url):
    try:
        await page.goto(url, timeout=20000)
        await page.evaluate("""
            () => {
                const footer = document.getElementById('footer-wrapper');
                if (footer) footer.style.display = 'none';
            }
        """)
        await asyncio.sleep(1)

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        count_tag = soup.find('div', {'class': 'st-show-result st-w-full st-text-[12px]'})
        count = 0
        if count_tag:
            try:
                num_tag = count_tag.find('span').find('span')
                count = int(num_tag.text.strip())
            except Exception:
                pass

        if count > 24:
            await auto_scroll(page)
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')

        product_tags = soup.find_all('div', {'class': 'st-product-wrap'})
        links = []
        for tag in product_tags:
            a_tag = tag.find('a')
            if a_tag:
                href = a_tag.get('href')
                if href and '/collections/' not in href:
                    links.append(href)
        return list(set(links))

    except PlaywrightTimeoutError:
        logging.error(f"Timeout while loading {url}")
    except Exception as e:
        logging.error(f"Unexpected error processing {url}: {e}")
    return []

def save_output(data):
    output_dir = Path(OUTPUT_FILE).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def process_category(playwright, gender, category, urls):
    async with sem:
        try:
            browser = await playwright.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1440, "height": 713})

            product_urls = []
            for url in urls:
                links = await get_product_urls(page, url)
                product_urls.extend(links)

            async with output_lock:
                output_data.setdefault(gender, {})[category] = list(set(product_urls))
                save_output(output_data)

            logging.info(f"{gender} > {category} completed: {len(product_urls)} links")

        except Exception as e:
            logging.error(f"Error in processing category {gender}/{category}: {e}")
        finally:
            await browser.close()

async def main():
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            url_dict = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load input file: {e}")
        return

    # Process with Playwright
    async with async_playwright() as p:
        tasks = []
        for gender, categories in url_dict.items():
            for category, urls in categories.items():
                tasks.append(process_category(p, gender, category, urls))
        await asyncio.gather(*tasks)

    logging.info(f"All product URLs saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
