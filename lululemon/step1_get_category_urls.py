import asyncio
import json
import os
import datetime
import logging
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import multiprocessing

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_category_urls(country, today_date):
    """Check if JSON already exists."""
    json_file_path = f'{country}/{today_date}/{country}_category_urls.json'
    return os.path.exists(json_file_path)

async def process_country(country, url, today_date):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            logging.info(f"Processing {country}...")
            await page.goto(url, wait_until="load", timeout=30000)

            # Try closing the welcome offer popup
            try:
                popup_container = 'div.welcome-offer-modal_modalContentWrapper__xuPMF'
                close_button_selector = 'button.modal_closeButton__4a9SL[aria-label="Close"]'
                
                # Wait for the popup container to appear (increased timeout)
                logging.info("Checking for welcome offer popup...")
                await page.wait_for_selector(popup_container, timeout=10000)
                
                # Ensure the close button is visible and clickable
                close_button = page.locator(close_button_selector)
                await close_button.wait_for(state="visible", timeout=5000)
                
                # Scroll to the button and click with force
                await close_button.scroll_into_view_if_needed()
                await close_button.click(force=True)
                logging.info("Welcome offer popup closed successfully.")
                
                # Wait briefly to ensure popup is gone
                await page.wait_for_timeout(1000)
            except Exception as e:
                logging.info(f"Failed to close welcome offer popup: {str(e)}. Continuing with scraping.")

            categories = ["Women", "Men"]
            all_subcats = {}

            for cat in categories:
                locator = page.locator(f'a[data-label="{cat}"]')
                # Retry hover to handle potential popup interference
                for attempt in range(3):
                    try:
                        await locator.hover()
                        break
                    except Exception as e:
                        logging.warning(f"Hover attempt {attempt + 1} for {cat} failed: {str(e)}")
                        await page.wait_for_timeout(1000)
                else:
                    logging.error(f"Failed to hover on {cat} after retries. Skipping category.")
                    continue

                await page.wait_for_timeout(2000)  # Allow menu to open

                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')

                # Match both US (/c/...) and Canada (/en-ca/c/...) URLs
                subcat_links = soup.find_all(
                    'a',
                    href=lambda h: h and (
                        h.startswith(f'/c/{cat.lower()}-') or
                        h.startswith(f'/en-ca/c/{cat.lower()}-')
                    )
                )

                subcat_dict = {}
                for link in subcat_links:
                    href = link.get('href')
                    if not href:
                        continue
                    full_url = "https://shop.lululemon.com" + href
                    subcat_name = link.get_text(strip=True)

                    if not subcat_name:
                        last_segment = href.split('/')[-1]
                        if 'whats-new' in last_segment.lower():
                            subcat_name = "What's New"
                        else:
                            subcat_name = last_segment.replace(f'{cat.lower()}-', '').replace('-', ' ')
                            subcat_name = re.sub(r'\b[a-z0-9]{8,}\b', '', subcat_name).strip().title()

                    if subcat_name:
                        subcat_dict[subcat_name] = full_url
                        logging.info(f"Found subcategory: {subcat_name} -> {full_url}")

                all_subcats[cat] = subcat_dict

            # Save results
            os.makedirs(f'{country}/{today_date}', exist_ok=True)
            json_file_path = f'{country}/{today_date}/{country}_category_urls.json'
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(all_subcats, f, ensure_ascii=False, indent=4)

            logging.info(f"{country} category URLs saved to {json_file_path}")

        except Exception as e:
            logging.error(f"Error processing {country}: {str(e)}")
        finally:
            await browser.close()

def run_async_process(country, url, today_date):
    asyncio.run(process_country(country, url, today_date))

def get_category_urls(countries, today_date, re_run=False):
    processes = []
    for country, url in countries.items():
        if not re_run and check_category_urls(country, today_date):
            logging.info(f"{country} already processed. Skipping...")
            continue
        process = multiprocessing.Process(target=run_async_process, args=(country, url, today_date))
        processes.append(process)
        process.start()

    for process in processes:
        process.join()

    logging.info("All countries processed successfully.")

if __name__ == "__main__":
    countries = {
        "USA": "https://shop.lululemon.com",
        "Canada": "https://shop.lululemon.com/en-ca"
    }
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    get_category_urls(countries, today_date, re_run=False)