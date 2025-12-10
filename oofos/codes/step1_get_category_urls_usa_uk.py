import logging
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin
import os
import datetime
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(message)s")

def close_popups(page):
    try:
        close_buttons = page.query_selector_all(
            "button.klaviyo-close-form, button[aria-label='Close dialog'], .klaviyo-close-form"
        )
        for btn in close_buttons:
            if btn.is_visible():
                btn.click()
                logging.info("Closed a popup via close button.")
                time.sleep(1)
                return
        
        # Remove overlay popup if blocking clicks
        popup = page.query_selector("div[role='dialog'][aria-label*='POPUP']")
        if popup:
            page.evaluate("el => el.remove()", popup)
            logging.info("Removed popup overlay via JS.")
            time.sleep(0.5)
    except Exception as e:
        logging.warning(f"Popup close attempt failed: {e}")

def hover_with_popup_handling(page, selector, retries=3):
    """Attempt to hover over an element, handling popups dynamically."""
    for attempt in range(1, retries + 1):
        try:
            # Always clean up before hover
            close_popups(page)
            time.sleep(3)
            page.hover(selector)
            logging.info(f"Hovered over {selector} successfully.")
            return True
        except Exception as e:
            logging.warning(f"Hover attempt {attempt} failed: {e}")
            close_popups(page)
            time.sleep(3)
    
    # Fallback: use JS hover if all retries fail
    try:
        element = page.query_selector(selector)
        if element:
            page.evaluate(
                """el => el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))""",
                element,
            )
            logging.info(f"Triggered JS hover for {selector} as fallback.")
            return True
    except Exception as e:
        logging.error(f"JS hover fallback failed for {selector}: {e}")
    
    logging.error(f"Failed to hover over {selector} after {retries} attempts.")
    return False

def get_category_urls(base_url):  # FIXED: Changed parameter name from 'url' to 'base_url'
    target_categories = {
        "women": "#menu-item-0",
        "men": "#menu-item-1",
        "sale": "#menu-item-3",
    }
    
    results = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(base_url, wait_until="domcontentloaded")
        
        # Let popup load, then close it once before proceeding
        time.sleep(10)
        close_popups(page)
        
        page.wait_for_selector("ul.navbar-linklist")
        
        for category, selector in target_categories.items():
            if not hover_with_popup_handling(page, selector):
                continue
            
            time.sleep(10)
            close_popups(page)
            
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            all_links = {}
            seen_hrefs = set()
            
            all_subnavs = soup.find_all("div", class_="navbar-subnav")
            
            if not all_subnavs:
                logging.info(f"No submenu found for {category}")
                results[category] = all_links
                continue
            
            navbar_subnav = all_subnavs[-1]
            
            pop_keys = ["holiday-gift-card"]
            
            links = navbar_subnav.find_all("a", href=True)
            for link in links:
                href = link.get("href")
                text = link.get_text(strip=True)
                
                if text and href and not any(key in href for key in pop_keys):
                    if href not in seen_hrefs:
                        seen_hrefs.add(href)
                        key = text.lower().replace(" ", "_")
                        absolute_url = urljoin(base_url, href)
                        all_links[key] = absolute_url
                        logging.info(f"Added: {text} -> {absolute_url}")
                    else:
                        logging.info(f"Duplicate href skipped: {href}")
                else:
                    logging.info(f"Skipped: {text} -> {href}")
            
            results[category] = all_links
            
            page.mouse.move(0, 0)
            time.sleep(10)
        
        context.close()
        browser.close()
    
    return results

def main():
    today_str = date.today().strftime('%Y-%m-%d')
    
    countries = {
        'USA': 'https://www.oofos.com',
        'UK': 'https://www.oofos.co.uk'
    }
    
    for country, url in countries.items():
        logging.info(f'Fetching {country} category URLs now')
        jsondata = get_category_urls(url)
        
        output_path = f'{country}/Data/{today_str}/Item_urls'
        os.makedirs(output_path, exist_ok=True)
        output_file = f'{output_path}/{country}_category_urls.json'
        
        with open(output_file, 'w') as f:
            json.dump(jsondata, f, indent=4)
        
        logging.info(f'{country} category URLs fetched and saved to {output_file}')
        logging.info(f'Found {len(jsondata)} categories for {country}')

if __name__ == "__main__":
    main()
