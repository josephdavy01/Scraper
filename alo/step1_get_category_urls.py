import datetime
import os
import time
import json
import logging
from playwright.sync_api import sync_playwright
import multiprocessing
from validations import check_category_urls
from urllib.parse import urlparse
from alert import raise_ticket

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TARGET_KEYWORD = "desktop-navigation-menu?"
TARGET_HOST = "cdn.builder.io"

def handle_popups(page):
    print("Attempting to handle popups...")
    try:
        osano_btn = page.query_selector("button.osano-cm-dialog__close")
        if osano_btn and osano_btn.is_visible():
            osano_btn.click()
            print("Closed Osano cookie popup.")
    except Exception as e:
        print(f"[DEBUG] Osano popup error: {e}")

     # --- NEW: Alo Yoga Join/Sign In modal ---
    try:
        alo_close_btn = page.query_selector("button.alo-modal-close-icon")
        if alo_close_btn and alo_close_btn.is_visible():
            alo_close_btn.click()
            print("Closed Alo Yoga sign-in modal.")
    except Exception as e:
        print(f"[DEBUG] Alo Yoga modal error: {e}")

    try:
        close_btn = page.query_selector("#closeIconContainer")  
        if close_btn and close_btn.is_visible():
            close_btn.click()
            print("Closed promo popup in main frame.")
    except Exception as e:
        print(f"[DEBUG] Promo popup main frame error: {e}")

    try:
        frames = page.frames
        for idx, frame in enumerate(frames):
            try:
                btn = frame.query_selector("#closeIconContainer")
                if btn and btn.is_visible():
                    btn.click()
                    print(f"Closed promo popup in iframe: {frame.name or idx}")
                    return True
            except Exception as e:
                print(f"[DEBUG] Frame {idx} error: {e}")
    except Exception as e:
        print(f"[DEBUG] Error scanning frames: {e}")

    # --- Added block: fallback selectors for Alo Yoga or similar popups ---
    try:
        extra_selectors = [
            "button[data-testid='closeIcon']",
            "button[aria-label='Dismiss this popup']",
            "button.css-1glrhkl"
        ]
        for sel in extra_selectors:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                print(f"Closed popup via extra selector: {sel}")
                return True
    except Exception as e:
        print(f"[DEBUG] Extra popup handler error: {e}")

    return False


def select_country_manually(page, country_full_name, country):
        try:
            print(f"Attempting to select country: {country_full_name}")
            page.wait_for_selector('div[react-render-target="currency-selector"]', timeout=5000)
            page.click('div[react-render-target="currency-selector"] button.sc-modal-trigger')
            time.sleep(1)

            page.wait_for_selector('input.MuiInputBase-input', state="visible")
            input_field = page.query_selector('input.MuiInputBase-input')
            input_field.click()

            input_field.fill(country_full_name)
            time.sleep(0.5)
            page.keyboard.press('ArrowDown')
            time.sleep(0.2)
            page.keyboard.press('Enter')
            time.sleep(0.5)

            save_button = page.wait_for_selector('div.sc-modal-buttons button.button-primary')
            save_button.click()

            print(f"Successfully selected country: {country}")
            return True

        except Exception as e:
            print(f"Country selection failed: {str(e)}")
            raise_ticket("Step 1", "select_country_manually", f"Country selection failed: {str(e)}", country)
            return False
        
def full_country_url(base_url, path):
        parsed = urlparse(base_url)
        prefix = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{prefix}{path}"

def process_category_data(base_url, raw_data):
    processed_data = {}
    nav_data = raw_data.get("desktop-navigation-menu", [{}])[0].get("data", {}).get("items", [])

    for category in nav_data:
        category_title = category.get("title", "")
        if category_title in ["Women", "Men"]:
            processed_data[category_title] = {}

            for section in category.get("items", []):
                if section.get("title", "").lower() == "clothing":
                    for item in section.get("items", []):
                        title = item.get("title", "").lower().replace(" ", "-")
                        url = item.get("url", "")
                        if title and url and "shop-all" not in title:
                            processed_data[category_title][title] = full_country_url(base_url, url)

            for section in category.get("items", []):
                if section.get("title", "").lower() == "featured shops":
                    for item in section.get("items", []):
                        title = item.get("title", "").lower().replace(" ", "-")
                        url = item.get("url", "")
                        if title and url and "sale" in title:
                            processed_data[category_title][title] = full_country_url(base_url, url)

        elif category_title == "Shoes":
            processed_data[category_title] = {}
            for section in category.get("items", []):
                for item in section.get("items", []):
                    title = item.get("title", "")
                    url = item.get("url", "")
                    if title in ["Sneakers", "Slippers & Slides"] and url:
                        processed_title = title.lower().replace(" ", "-").replace("&", "and")
                        processed_data[category_title][processed_title] = full_country_url(base_url, url)

    return processed_data
        
def process_country(country, url, today_date, country_mapping):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Flag to track if we've completed country selection
        country_selected = False
        navigation_json = {}
        
        def handle_response(response):
            nonlocal navigation_json, country_selected
            # Only process responses AFTER country selection is complete
            if (country_selected and 
                TARGET_KEYWORD in response.url and 
                TARGET_HOST in response.url and 
                not navigation_json):
                try:
                    navigation_json = response.json()
                    logging.info(f"Intercepted navigation JSON for {country} AFTER redirect")
                except Exception as e:
                    logging.error("Failed to parse intercepted navigation JSON: %s" % str(e))
        
        # Attach handler BEFORE any navigation
        page.on("response", handle_response)

        try:
            logging.info(f"Processing {country}...")
            page.goto(url, wait_until="load", timeout=20000)
            time.sleep(3)
            handle_popups(page)
            select_country_manually(page, country_mapping.get(country, country), country)
            time.sleep(3)
            handle_popups(page)
            time.sleep(3)
            # page.reload()
            clean_url = page.url.rstrip('?')
            while url != clean_url:
                print(f"Waiting for page to load: {url}")
                time.sleep(1)
                print(f"Page loaded: {clean_url}")
            country_selected = True
            page.reload()

            json_file_path = f'{country}/{today_date}/{country}_category_links_raw.json'
            with open(json_file_path, "w", encoding='utf-8') as outfile:
                json.dump(navigation_json, outfile, ensure_ascii=False, indent=4)
            
            temp = process_category_data(url, navigation_json)

            json_file_path = f'{country}/{today_date}/{country}_category_links.json'
            with open(json_file_path, "w", encoding='utf-8') as outfile:
                json.dump(temp, outfile, ensure_ascii=False, indent=4)

            # logging.info(f'{country} category URLs fetched and saved to {json_file_path}')
        
        except Exception as e:
            logging.error(f"Error processing {country}: {str(e)}")
            raise_ticket("Step 1", "process_country", f"Error processing {country}: {str(e)}", country)
        finally:
            context.close()
            browser.close()

def get_category_urls(countries, today_date, re_run, country_mapping):
    processes = []
    for country, url in countries.items():
        if not re_run:
            status = check_category_urls(country, today_date)
            if status:
                logging.info(f"Category URLs already exist for {country} on {today_date}. Skipping...")
                continue
        process = multiprocessing.Process(target=process_country, args=(country, url, today_date, country_mapping))
        processes.append(process)
        process.start()
    
    for process in processes:
        process.join()

    logging.info("All countries processed successfully")


    
    